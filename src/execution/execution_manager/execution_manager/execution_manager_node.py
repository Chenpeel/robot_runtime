"""execution_manager ROS 2 节点。"""

from threading import RLock

from builtin_interfaces.msg import Time
from motion_msgs.msg import ActuatorState
from motion_msgs.msg import ExecutionState
from motion_msgs.msg import MotionCommand
from motion_msgs.msg import TaskExecutionControl
from motion_msgs.msg import TaskExecutionState
from motion_msgs.msg import TeleopControl
from motion_msgs.srv import ReadActuatorPosition
from motion_msgs.srv import StopActuators
import rclpy
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.task import Future
from servo_msgs.msg import DriverSafetyState, ServoCommand, ServoState
from servo_msgs.srv import ExecuteBusCommand, ReadServoPosition, SetDriverSafety
from std_msgs.msg import Bool

from .arbitrator import CommandArbitrator
from .actuator_service_adapter import read_response_fields
from .actuator_service_adapter import stop_command_for_protocol
from .actuator_service_adapter import stop_summary
from .command_adapter import motion_command_to_setpoint
from .command_adapter import setpoint_to_servo_fields
from .feedback_adapter import feedback_to_actuator_state_fields
from .feedback_adapter import servo_state_to_feedback


class ExecutionManagerNode(Node):
    """最小执行仲裁节点。"""

    def __init__(self) -> None:
        super().__init__('execution_manager')

        self.declare_parameter('teleop_command_topic', '/execution/teleop/command')
        self.declare_parameter('teleop_control_topic', '/execution/teleop/control')
        self.declare_parameter('task_command_topic', '/execution/task/command')
        self.declare_parameter('task_control_topic', '/execution/task/control')
        self.declare_parameter('motion_command_topic', '/execution/motion/command')
        self.declare_parameter('output_command_topic', '/servo/command')
        self.declare_parameter('driver_state_topic', '/servo/state')
        self.declare_parameter(
            'actuator_state_topic',
            '/execution/actuator_state',
        )
        self.declare_parameter('state_topic', '/execution/state')
        self.declare_parameter('task_state_topic', '/execution/task/state')
        self.declare_parameter(
            'read_actuator_position_service',
            '/execution/read_actuator_position',
        )
        self.declare_parameter(
            'stop_actuators_service',
            '/execution/stop_actuators',
        )
        self.declare_parameter(
            'driver_read_position_service',
            '/servo/read_position',
        )
        self.declare_parameter(
            'driver_execute_command_service',
            '/servo/execute_command',
        )
        self.declare_parameter('driver_safety_topic', '/servo/driver_safety')
        self.declare_parameter(
            'driver_safety_service',
            '/servo/set_driver_safety',
        )
        self.declare_parameter('estop_topic', '/execution/estop')
        self.declare_parameter('teleop_timeout_sec', 0.8)
        self.declare_parameter('motion_timeout_sec', 0.5)
        self.declare_parameter('task_timeout_sec', 5.0)
        self.declare_parameter('driver_service_timeout_sec', 2.0)
        self.declare_parameter('publish_state_period_sec', 0.2)
        self.declare_parameter('debug', False)

        teleop_command_topic = self.get_parameter('teleop_command_topic').value
        teleop_control_topic = self.get_parameter('teleop_control_topic').value
        task_command_topic = self.get_parameter('task_command_topic').value
        task_control_topic = self.get_parameter('task_control_topic').value
        motion_command_topic = self.get_parameter('motion_command_topic').value
        output_command_topic = self.get_parameter('output_command_topic').value
        driver_state_topic = self.get_parameter('driver_state_topic').value
        actuator_state_topic = self.get_parameter('actuator_state_topic').value
        self.state_topic = self.get_parameter('state_topic').value
        task_state_topic = self.get_parameter('task_state_topic').value
        read_actuator_position_service = self.get_parameter(
            'read_actuator_position_service'
        ).value
        stop_actuators_service = self.get_parameter(
            'stop_actuators_service'
        ).value
        driver_read_position_service = self.get_parameter(
            'driver_read_position_service'
        ).value
        driver_execute_command_service = self.get_parameter(
            'driver_execute_command_service'
        ).value
        driver_safety_topic = str(
            self.get_parameter('driver_safety_topic').value
        ).strip()
        driver_safety_service = str(
            self.get_parameter('driver_safety_service').value
        ).strip()
        estop_topic = self.get_parameter('estop_topic').value
        teleop_timeout_sec = float(self.get_parameter('teleop_timeout_sec').value)
        motion_timeout_sec = float(self.get_parameter('motion_timeout_sec').value)
        task_timeout_sec = float(self.get_parameter('task_timeout_sec').value)
        self.driver_service_timeout_sec = max(
            0.1,
            float(self.get_parameter('driver_service_timeout_sec').value),
        )
        publish_state_period_sec = float(
            self.get_parameter('publish_state_period_sec').value
        )
        self.debug = bool(self.get_parameter('debug').value)

        self.arbitrator = CommandArbitrator(
            teleop_timeout_sec=teleop_timeout_sec,
            motion_timeout_sec=motion_timeout_sec,
            task_timeout_sec=task_timeout_sec,
        )
        self.arbitrator_lock = RLock()
        self.service_callback_group = ReentrantCallbackGroup()
        self._known_bus_actuator_ids = set()
        self._next_stop_operation_id = 1
        self._active_stop_operation_ids = set()
        self._latched_stop_fault_reason = ''
        self._last_driver_safety_stamp_ns = 0
        self.driver_safety_topic = driver_safety_topic
        self.driver_safety_qos = QoSProfile(
            depth=1,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
        )

        self.output_command_pub = self.create_publisher(
            ServoCommand,
            output_command_topic,
            50,
        )
        self.state_pub = self.create_publisher(
            ExecutionState,
            self.state_topic,
            10,
        )
        self.task_state_pub = self.create_publisher(
            TaskExecutionState,
            task_state_topic,
            10,
        )
        self.actuator_state_pub = self.create_publisher(
            ActuatorState,
            actuator_state_topic,
            50,
        )
        self.driver_safety_pub = self.create_publisher(
            DriverSafetyState,
            self.driver_safety_topic,
            self.driver_safety_qos,
        )
        self.driver_read_position_client = self.create_client(
            ReadServoPosition,
            driver_read_position_service,
            callback_group=self.service_callback_group,
        )
        self.driver_execute_command_client = self.create_client(
            ExecuteBusCommand,
            driver_execute_command_service,
            callback_group=self.service_callback_group,
        )
        self.driver_safety_client = self.create_client(
            SetDriverSafety,
            driver_safety_service,
            callback_group=self.service_callback_group,
        )
        self.read_actuator_position_srv = self.create_service(
            ReadActuatorPosition,
            read_actuator_position_service,
            self._handle_read_actuator_position,
            callback_group=self.service_callback_group,
        )
        self.stop_actuators_srv = self.create_service(
            StopActuators,
            stop_actuators_service,
            self._handle_stop_actuators,
            callback_group=self.service_callback_group,
        )

        self.teleop_sub = self.create_subscription(
            MotionCommand,
            teleop_command_topic,
            lambda msg: self._handle_command('teleop', msg),
            50,
        )
        self.teleop_control_sub = self.create_subscription(
            TeleopControl,
            teleop_control_topic,
            self._handle_teleop_control,
            20,
        )
        self.task_sub = self.create_subscription(
            MotionCommand,
            task_command_topic,
            lambda msg: self._handle_command('task', msg),
            50,
        )
        self.task_control_sub = self.create_subscription(
            TaskExecutionControl,
            task_control_topic,
            self._handle_task_control,
            20,
        )
        self.motion_sub = self.create_subscription(
            MotionCommand,
            motion_command_topic,
            lambda msg: self._handle_command('motion', msg),
            50,
        )
        self.estop_sub = self.create_subscription(
            Bool,
            estop_topic,
            self._handle_estop,
            10,
        )
        self.driver_state_sub = self.create_subscription(
            ServoState,
            driver_state_topic,
            self._handle_driver_state,
            50,
        )

        period = publish_state_period_sec if publish_state_period_sec > 0 else 0.2
        self.state_timer = self.create_timer(period, self._publish_state)

        self.get_logger().info(
            'execution_manager 已启动: '
            f'teleop={teleop_command_topic}, '
            f'teleop_control={teleop_control_topic}, '
            f'task={task_command_topic}, '
            f'task_control={task_control_topic}, '
            f'task_state={task_state_topic}, '
            f'read_actuator={read_actuator_position_service}, '
            f'stop_actuators={stop_actuators_service}, '
            f'motion={motion_command_topic}, '
            f'output={output_command_topic}, '
            f'driver_state={driver_state_topic}, '
            f'actuator_state={actuator_state_topic}, '
            f'estop={estop_topic}'
        )
        self._publish_driver_safety(False, '')

    def _handle_command(self, source: str, msg: MotionCommand) -> None:
        now_sec = self._now_sec()
        setpoint = motion_command_to_setpoint(msg)
        requester_id = str(getattr(msg, 'requester_id', '') or '').strip()
        lease_id = str(getattr(msg, 'lease_id', '') or '').strip()
        with self.arbitrator_lock:
            if self._active_stop_operation_ids:
                result = self.arbitrator.reject_command(
                    source,
                    now_sec,
                    requester_id,
                    'stop_operation_pending',
                )
            else:
                result = self.arbitrator.receive_command(
                    source,
                    now_sec,
                    requester_id=requester_id,
                    lease_id=lease_id,
                )
            if result.accepted:
                if setpoint.actuator_type == 'bus':
                    self._known_bus_actuator_ids.add(int(setpoint.actuator_id))
                output_msg = self._to_servo_command(setpoint, msg)
                # 驱动 fence 依据 execution_manager 的本地时间戳判断旧命令。
                output_msg.stamp = self.get_clock().now().to_msg()
                self.output_command_pub.publish(output_msg)
        if result.accepted:
            if self.debug:
                self.get_logger().info(
                    f'接受 {source} 命令: type={setpoint.actuator_type} '
                    f'id={setpoint.actuator_id} encoding={setpoint.value_encoding} '
                    f'target_raw={setpoint.target_raw} '
                    f'duration_ms={setpoint.duration_ms} '
                    f'requester_id={requester_id} lease_id={lease_id}'
                )
        else:
            self.get_logger().warn(
                f'拒绝 {source} 命令: reason={result.reason} '
                f'id={setpoint.actuator_id} target_raw={setpoint.target_raw} '
                f'requester_id={requester_id} lease_id={lease_id}'
            )

        self._publish_state(now_sec)

    def _handle_teleop_control(self, msg: TeleopControl) -> None:
        now_sec = self._now_sec()
        action = str(msg.action).strip().lower()
        requester_id = str(msg.requester_id).strip()
        lease_id = str(msg.lease_id).strip()
        with self.arbitrator_lock:
            result = self.arbitrator.receive_teleop_control(
                action,
                now_sec,
                requester_id=requester_id,
                lease_id=lease_id,
            )

        if self.debug:
            self.get_logger().info(
                f'teleop 控制动作: action={action} requester_id={requester_id} '
                f'lease_id={lease_id} '
                f'accepted={result.accepted} mode={result.mode}'
            )

        if not result.accepted:
            self.get_logger().warn(
                f'拒绝 teleop 控制动作: action={action} reason={result.reason}'
            )

        self._publish_state(now_sec)

    def _handle_task_control(self, msg: TaskExecutionControl) -> None:
        now_sec = self._now_sec()
        action = str(msg.action).strip().lower()
        task_id = str(msg.task_id).strip()
        trace_id = str(msg.trace_id).strip()
        session_id = str(msg.session_id).strip()
        lease_id = str(msg.lease_id).strip()
        with self.arbitrator_lock:
            if action == 'start' and self._active_stop_operation_ids:
                result = self.arbitrator.reject_task_control(
                    action,
                    now_sec,
                    task_id,
                    trace_id,
                    session_id,
                    'task_stop_pending',
                )
            else:
                result = self.arbitrator.receive_task_control(
                    action,
                    now_sec,
                    task_id=task_id,
                    trace_id=trace_id,
                    session_id=session_id,
                    lease_id=lease_id,
                )

        if self.debug:
            self.get_logger().info(
                f'task 控制动作: action={action} task_id={task_id} '
                f'trace_id={trace_id} session_id={session_id} '
                f'lease_id={lease_id} accepted={result.accepted} '
                f'mode={result.mode}'
            )

        if not result.accepted:
            self.get_logger().warn(
                f'拒绝 task 控制动作: action={action} task_id={task_id} '
                f'reason={result.reason}'
            )

        self._publish_state(now_sec)

    async def _handle_estop(self, msg: Bool) -> None:
        requested_active = bool(msg.data)
        if not requested_active:
            await self._handle_estop_release()
            return

        actuator_ids = []
        operation_id = None
        with self.arbitrator_lock:
            state = self.arbitrator.set_estop(True, self._now_sec())
            actuator_ids = sorted(self._known_bus_actuator_ids)
            if actuator_ids:
                operation_id = self._register_stop_operation()
        self._publish_driver_safety(
            True,
            str(state.get('estop_reason') or 'estop'),
        )
        if actuator_ids:
            summary = stop_summary(
                actuator_ids,
                [None] * len(actuator_ids),
            )
            try:
                responses, timed_out = await self._stop_driver_actuators(
                    actuator_ids,
                    operation_id,
                )
                summary = stop_summary(actuator_ids, responses)
                if not summary['stop_command_sent']:
                    fault_reason = (
                        'driver_stop_timeout'
                        if timed_out
                        else 'driver_stop_failed'
                    )
                    self._latch_stop_fault(
                        operation_id,
                        fault_reason,
                    )
                    operation_id = None
                    summary['status'] = 'stop_fault'
                    summary['reason'] = fault_reason
                    summary['recoverable'] = False
            finally:
                if operation_id is not None:
                    await self._finish_stop_operation(operation_id)
            if not summary['stop_command_sent']:
                self.get_logger().error(
                    '急停驱动 stop 未完整写出: '
                    f'reason={summary["reason"]}'
                )
        self.get_logger().warn(
            f'执行层急停状态已切换: estop_active={state["estop_active"]}'
        )
        self._publish_state()

    async def _handle_estop_release(self) -> None:
        operation_id = None
        with self.arbitrator_lock:
            snapshot = self.arbitrator.snapshot(self._now_sec())
            if (
                not snapshot['estop_active']
                or self._latched_stop_fault_reason
                or self._active_stop_operation_ids
            ):
                state = snapshot
            else:
                operation_id = self._register_stop_operation()
                state = None

        if operation_id is not None:
            released, fault_reason, stamp = (
                await self._request_driver_safety_release()
            )
            if released:
                with self.arbitrator_lock:
                    state = self.arbitrator.set_estop(False, self._now_sec())
                    self._active_stop_operation_ids.discard(operation_id)
                    self._publish_driver_safety(False, '', stamp=stamp)
            else:
                self._latch_stop_fault(operation_id, fault_reason)
                with self.arbitrator_lock:
                    state = self.arbitrator.snapshot(self._now_sec())

        self.get_logger().warn(
            f'执行层急停状态已切换: estop_active={state["estop_active"]}'
        )
        self._publish_state()

    def _handle_driver_state(self, msg: ServoState) -> None:
        feedback = servo_state_to_feedback(msg)
        if feedback.actuator_type == 'bus':
            with self.arbitrator_lock:
                self._known_bus_actuator_ids.add(int(feedback.actuator_id))
        fields = feedback_to_actuator_state_fields(feedback)
        state_msg = ActuatorState()
        state_msg.actuator_type = fields['actuator_type']
        state_msg.actuator_id = fields['actuator_id']
        state_msg.position_raw = fields['position_raw']
        state_msg.value_encoding = fields['value_encoding']
        state_msg.load = fields['load']
        state_msg.temperature = fields['temperature']
        state_msg.status = fields['status']
        state_msg.reason = fields['reason']
        state_msg.recoverable = fields['recoverable']
        state_msg.driver_error_code = fields['driver_error_code']
        state_msg.stamp = msg.stamp
        self.actuator_state_pub.publish(state_msg)

    async def _handle_read_actuator_position(
        self,
        request: ReadActuatorPosition.Request,
        response: ReadActuatorPosition.Response,
    ):
        validation = self._validate_task_operation(request)
        if not validation.accepted:
            fields = read_response_fields(None)
            fields['reason'] = validation.reason
            return self._fill_read_actuator_response(response, fields)
        if str(request.actuator_type).strip().lower() != 'bus':
            fields = read_response_fields(None)
            fields['reason'] = 'unsupported_actuator_type'
            fields['recoverable'] = False
            return self._fill_read_actuator_response(response, fields)
        if not self.driver_read_position_client.service_is_ready():
            return self._fill_read_actuator_response(
                response,
                read_response_fields(None),
            )

        driver_request = ReadServoPosition.Request()
        driver_request.servo_id = int(request.actuator_id)
        driver_request.protocol = ''
        try:
            driver_response, timed_out = await self._await_driver_response(
                self.driver_read_position_client.call_async(driver_request)
            )
        except Exception as exc:
            fields = read_response_fields(None)
            fields['reason'] = f'driver_read_exception:{exc}'
            return self._fill_read_actuator_response(response, fields)
        if timed_out:
            fields = read_response_fields(None)
            fields['reason'] = 'driver_read_timeout'
            return self._fill_read_actuator_response(response, fields)
        return self._fill_read_actuator_response(
            response,
            read_response_fields(driver_response),
        )

    async def _handle_stop_actuators(
        self,
        request: StopActuators.Request,
        response: StopActuators.Response,
    ):
        actuator_ids = [int(value) for value in request.actuator_ids]
        if str(request.actuator_type).strip().lower() != 'bus':
            fields = stop_summary(actuator_ids, [None] * len(actuator_ids))
            fields['accepted'] = False
            fields['reason'] = 'unsupported_actuator_type'
            fields['recoverable'] = False
            return self._fill_stop_actuators_response(response, fields)
        if not actuator_ids:
            fields = stop_summary([], [])
            fields['reason'] = 'actuator_ids_required'
            fields['recoverable'] = False
            return self._fill_stop_actuators_response(response, fields)

        operation_id, validation = self._begin_stop_operation(request)
        if operation_id is None:
            fields = stop_summary(actuator_ids, [None] * len(actuator_ids))
            fields['accepted'] = False
            fields['reason'] = validation.reason
            return self._fill_stop_actuators_response(response, fields)
        self._publish_driver_safety(True, 'stop_operation')
        release_operation = False
        try:
            driver_responses, timed_out = await self._stop_driver_actuators(
                actuator_ids,
                operation_id,
            )
            fields = stop_summary(actuator_ids, driver_responses)
            if not fields['stop_command_sent']:
                fault_reason = (
                    'driver_stop_timeout'
                    if timed_out
                    else 'driver_stop_failed'
                )
                self._latch_stop_fault(operation_id, fault_reason)
                release_operation = False
                fields['status'] = 'stop_fault'
                fields['reason'] = fault_reason
                fields['recoverable'] = False
            else:
                release_operation = True
        finally:
            if release_operation:
                await self._finish_stop_operation(operation_id)
        return self._fill_stop_actuators_response(
            response,
            fields,
        )

    async def _stop_driver_actuators(self, actuator_ids, operation_id=None):
        driver_responses = []
        any_timed_out = False
        for actuator_id in actuator_ids:
            if (
                not self.driver_read_position_client.service_is_ready()
                or not self.driver_execute_command_client.service_is_ready()
            ):
                driver_responses.append(None)
                continue
            protocol_request = ReadServoPosition.Request()
            protocol_request.servo_id = actuator_id
            protocol_request.protocol = ''
            try:
                protocol_response = (
                    await self._await_driver_response(
                        self.driver_read_position_client.call_async(
                            protocol_request
                        )
                    )
                )
            except Exception:
                driver_responses.append(None)
                continue
            protocol_response, timed_out = protocol_response
            if timed_out:
                any_timed_out = True
                driver_responses.append(None)
                continue
            protocol = str(protocol_response.protocol).strip().lower()
            if not bool(protocol_response.success) or protocol not in ('lx', 'zl'):
                driver_responses.append(None)
                continue
            driver_request = ExecuteBusCommand.Request()
            driver_request.servo_id = actuator_id
            driver_request.protocol = protocol
            driver_request.command = stop_command_for_protocol(protocol)
            driver_request.params = []
            try:
                with self.arbitrator_lock:
                    if (
                        operation_id is not None
                        and operation_id not in self._active_stop_operation_ids
                    ):
                        driver_responses.append(None)
                        continue
                    pending_response = (
                        self.driver_execute_command_client.call_async(
                            driver_request
                        )
                    )
                driver_response, timed_out = await self._await_driver_response(
                    pending_response
                )
                if timed_out:
                    any_timed_out = True
                    driver_responses.append(None)
                    continue
                driver_responses.append(driver_response)
            except Exception:
                driver_responses.append(None)
        return driver_responses, any_timed_out

    def _begin_stop_operation(self, request):
        with self.arbitrator_lock:
            validation = self.arbitrator.validate_task_operation(
                self._now_sec(),
                task_id=request.task_id,
                trace_id=request.trace_id,
                session_id=request.session_id,
                lease_id=request.lease_id,
            )
            if not validation.accepted:
                return None, validation
            operation_id = self._register_stop_operation()
            return operation_id, validation

    def _register_stop_operation(self):
        operation_id = self._next_stop_operation_id
        self._next_stop_operation_id += 1
        self._active_stop_operation_ids.add(operation_id)
        return operation_id

    async def _finish_stop_operation(self, operation_id) -> None:
        with self.arbitrator_lock:
            other_operations = self._active_stop_operation_ids - {operation_id}
            snapshot = self.arbitrator.snapshot(self._now_sec())
            if (
                other_operations
                or self._latched_stop_fault_reason
                or snapshot['estop_active']
            ):
                self._active_stop_operation_ids.discard(operation_id)
                return

        released, fault_reason, stamp = (
            await self._request_driver_safety_release()
        )
        if not released:
            self._latch_stop_fault(operation_id, fault_reason)
            return

        with self.arbitrator_lock:
            self._active_stop_operation_ids.discard(operation_id)
            snapshot = self.arbitrator.snapshot(self._now_sec())
            if (
                self._active_stop_operation_ids
                or self._latched_stop_fault_reason
                or snapshot['estop_active']
            ):
                return
            self._publish_driver_safety(False, '', stamp=stamp)

    def _latch_stop_fault(self, operation_id, reason) -> None:
        with self.arbitrator_lock:
            if operation_id not in self._active_stop_operation_ids:
                return
            self._latched_stop_fault_reason = str(reason)
            self.arbitrator.set_estop(
                True,
                self._now_sec(),
                reason=self._latched_stop_fault_reason,
            )
        self._publish_driver_safety(True, self._latched_stop_fault_reason)

    async def _request_driver_safety_release(self):
        stamp = self._next_driver_safety_stamp()
        if not self.driver_safety_client.service_is_ready():
            return False, 'driver_safety_release_unavailable', stamp

        request = SetDriverSafety.Request()
        request.estop_active = False
        request.reason = ''
        request.stamp = stamp
        try:
            response, timed_out = await self._await_driver_response(
                self.driver_safety_client.call_async(request)
            )
        except Exception:
            return False, 'driver_safety_release_failed', stamp
        if timed_out:
            return False, 'driver_safety_release_timeout', stamp
        if response is None or not bool(response.success):
            return False, 'driver_safety_release_failed', stamp
        return True, '', stamp

    def _publish_driver_safety(
        self,
        active: bool,
        reason: str,
        stamp=None,
    ) -> None:
        message = DriverSafetyState()
        message.estop_active = bool(active)
        message.reason = str(reason or '')
        message.stamp = stamp or self._next_driver_safety_stamp()
        self.driver_safety_pub.publish(message)

    def _next_driver_safety_stamp(self):
        with self.arbitrator_lock:
            now_ns = int(self.get_clock().now().nanoseconds)
            stamp_ns = max(now_ns, self._last_driver_safety_stamp_ns + 1)
            self._last_driver_safety_stamp_ns = stamp_ns
        stamp = Time()
        stamp.sec = int(stamp_ns // 1_000_000_000)
        stamp.nanosec = int(stamp_ns % 1_000_000_000)
        return stamp

    async def _await_driver_response(self, pending_future):
        completed = Future()
        timer_holder = {}

        def finish(response_future=None):
            timer = timer_holder.pop('timer', None)
            if timer is not None:
                self.destroy_timer(timer)
            if not completed.done():
                completed.set_result(response_future)

        timer_holder['timer'] = self.create_timer(
            self.driver_service_timeout_sec,
            finish,
            callback_group=self.service_callback_group,
        )
        pending_future.add_done_callback(finish)
        finished_future = await completed
        if finished_future is None:
            return None, True
        return finished_future.result(), False

    def _validate_task_operation(self, request):
        with self.arbitrator_lock:
            return self.arbitrator.validate_task_operation(
                self._now_sec(),
                task_id=request.task_id,
                trace_id=request.trace_id,
                session_id=request.session_id,
                lease_id=request.lease_id,
            )

    def _fill_read_actuator_response(self, response, fields):
        response.success = bool(fields['success'])
        response.position_raw = int(fields['position_raw'])
        response.value_encoding = str(fields['value_encoding'])
        response.status = str(fields['status'])
        response.reason = str(fields['reason'])
        response.recoverable = bool(fields['recoverable'])
        response.stamp = fields['stamp'] or self.get_clock().now().to_msg()
        return response

    def _fill_stop_actuators_response(self, response, fields):
        response.accepted = bool(fields['accepted'])
        response.stop_command_sent = bool(fields['stop_command_sent'])
        response.stop_confirmed = bool(fields['stop_confirmed'])
        response.status = str(fields['status'])
        response.reason = str(fields['reason'])
        response.recoverable = bool(fields['recoverable'])
        response.stopped_actuator_ids = [
            int(value) for value in fields['stopped_actuator_ids']
        ]
        response.unsupported_actuator_ids = [
            int(value) for value in fields['unsupported_actuator_ids']
        ]
        response.stamp = self.get_clock().now().to_msg()
        return response

    def _publish_state(self, now_sec: float | None = None) -> None:
        if now_sec is None:
            now_sec = self._now_sec()

        with self.arbitrator_lock:
            snapshot = self.arbitrator.snapshot(now_sec)
        state_msg = ExecutionState()
        state_msg.mode = str(snapshot['mode'])
        state_msg.active_source = str(snapshot['active_source'] or '')
        state_msg.teleop_holder_id = str(snapshot['teleop_holder_id'] or '')
        state_msg.teleop_lease_id = str(snapshot['teleop_lease_id'] or '')
        state_msg.estop_active = bool(snapshot['estop_active'])
        state_msg.teleop_active = bool(snapshot['teleop_active'])
        state_msg.motion_active = bool(snapshot['motion_active'])
        state_msg.teleop_timeout_sec = float(snapshot['teleop_timeout_sec'])
        state_msg.motion_timeout_sec = float(snapshot['motion_timeout_sec'])
        state_msg.teleop_control_remaining_sec = float(
            snapshot['teleop_control_remaining_sec']
        )
        state_msg.last_teleop_control_action = str(
            snapshot['last_teleop_control_action']
        )
        state_msg.last_teleop_control_accepted = bool(
            snapshot['last_teleop_control_accepted']
        )
        state_msg.last_teleop_control_reason = str(
            snapshot['last_teleop_control_reason']
        )
        state_msg.teleop_control_accepted_count = int(
            snapshot['teleop_control_accepted_count']
        )
        state_msg.teleop_control_rejected_count = int(
            snapshot['teleop_control_rejected_count']
        )
        state_msg.teleop_accepted_count = int(snapshot['accepted_counts']['teleop'])
        state_msg.motion_accepted_count = int(snapshot['accepted_counts']['motion'])
        state_msg.teleop_rejected_count = int(snapshot['rejected_counts']['teleop'])
        state_msg.motion_rejected_count = int(snapshot['rejected_counts']['motion'])
        state_msg.last_rejection_reason = str(snapshot['last_rejection_reason'])
        state_msg.stamp = self.get_clock().now().to_msg()
        self.state_pub.publish(state_msg)

        task_state_msg = TaskExecutionState()
        task_state_msg.active = bool(snapshot['task_active'])
        task_state_msg.task_id = str(snapshot['task_id'])
        task_state_msg.trace_id = str(snapshot['task_trace_id'])
        task_state_msg.session_id = str(snapshot['task_session_id'])
        task_state_msg.lease_id = str(snapshot['task_lease_id'])
        task_state_msg.lease_timeout_sec = float(snapshot['task_timeout_sec'])
        task_state_msg.lease_remaining_sec = float(
            snapshot['task_control_remaining_sec']
        )
        task_state_msg.last_action = str(snapshot['last_task_control_action'])
        task_state_msg.last_task_id = str(
            snapshot['last_task_control_task_id']
        )
        task_state_msg.last_trace_id = str(
            snapshot['last_task_control_trace_id']
        )
        task_state_msg.last_session_id = str(
            snapshot['last_task_control_session_id']
        )
        task_state_msg.last_action_accepted = bool(
            snapshot['last_task_control_accepted']
        )
        task_state_msg.status = str(snapshot['task_status'])
        task_state_msg.reason = str(snapshot['task_state_reason'])
        task_state_msg.recoverable = bool(snapshot['task_recoverable'])
        task_state_msg.control_accepted_count = int(
            snapshot['task_control_accepted_count']
        )
        task_state_msg.control_rejected_count = int(
            snapshot['task_control_rejected_count']
        )
        task_state_msg.last_command_requester_id = str(
            snapshot['last_task_command_requester_id']
        )
        task_state_msg.last_command_accepted = bool(
            snapshot['last_task_command_accepted']
        )
        task_state_msg.last_command_reason = str(
            snapshot['last_task_command_reason']
        )
        task_state_msg.command_accepted_count = int(
            snapshot['accepted_counts']['task']
        )
        task_state_msg.command_rejected_count = int(
            snapshot['rejected_counts']['task']
        )
        task_state_msg.stamp = state_msg.stamp
        self.task_state_pub.publish(task_state_msg)

    def _now_sec(self) -> float:
        return self.get_clock().now().nanoseconds / 1_000_000_000.0

    @staticmethod
    def _to_servo_command(setpoint, msg: MotionCommand) -> ServoCommand:
        servo_fields = setpoint_to_servo_fields(setpoint)
        output_msg = ServoCommand()
        output_msg.servo_type = servo_fields['servo_type']
        output_msg.servo_id = servo_fields['servo_id']
        output_msg.position = servo_fields['position']
        output_msg.speed = servo_fields['speed']
        output_msg.stamp = msg.stamp
        return output_msg


def main(args=None) -> None:
    """入口函数。"""
    rclpy.init(args=args)
    node = ExecutionManagerNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)

    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
