"""
3-DOF并联控制器ROS 2节点

订阅脚踝姿态命令,转换为 MotionCommand 并发布
"""

import math
import threading
import time

from motion_msgs.action import ExecuteMotion
from motion_msgs.msg import TaskExecutionControl
from motion_msgs.msg import TaskExecutionState
from motion_msgs.srv import ReadActuatorPosition
from motion_msgs.srv import StopActuators
import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.task import Future
from geometry_msgs.msg import Vector3
from motion_msgs.msg import MotionCommand
from std_msgs.msg import Float32MultiArray
import numpy as np

from .kinematics_solver import Parallel3DOFKinematicsSolver
from .motion_execution import active_task_lease
from .motion_execution import ActuatorObservation
from .motion_execution import is_terminal_task_state
from .motion_execution import MotionGoalValidationError
from .motion_execution import SingleGoalAdmission
from .motion_execution import StablePositionTracker
from .motion_execution import evaluate_target_feedback
from .motion_execution import normalize_motion_goal
from .motion_execution import progress_fraction
from .motion_execution import task_start_was_accepted
from .motion_execution import task_start_was_rejected
from .motion_execution import terminal_task_status

DEFAULT_COMMAND_TOPIC = '/execution/motion/command'


class Parallel3DOFControllerNode(Node):
    """
    3-DOF并联控制器节点

    功能:
    - 订阅脚踝RPY姿态命令
    - 将RPY转换为舵机目标
    - 发布 MotionCommand 执行命令

    话题:
    - 订阅: ~/ankle_rpy (Vector3) - 脚踝RPY命令 (度)
    - 发布: command_topic (MotionCommand) - 执行命令
    - 发布: ~/ankle_theta (Float32MultiArray) - Theta角反馈 (度)

    参数:
    - l0: 平台半径 (米, 默认0.02)
    - l1: 动平台距离 (米, 默认0.02)
    - l2: 静平台距离 (米, 默认0.02)
    - ankle_side: 控制哪侧脚踝 ('right'/'left', 默认'right')
    - servo_ids: 自定义舵机ID列表 (3个元素)
    - servo_offsets: 自定义舵机offset列表 (3个元素, 可选)
    - servo_directions: 自定义舵机direction列表 (3个元素, 可选)
    - default_speed: 默认运动时长 (毫秒, 保留旧参数名, 默认100)
    - command_topic: 控制命令输出话题 (默认/execution/motion/command)
    - debug: 是否打印调试信息 (默认False)
    """

    def __init__(self):
        super().__init__('ankle_controller_node')

        # 声明参数
        self.declare_parameter('l0', 0.02)
        self.declare_parameter('l1', 0.02)
        self.declare_parameter('l2', 0.02)
        self.declare_parameter('ankle_side', 'right')
        self.declare_parameter('default_speed', 100)
        self.declare_parameter('debug', False)
        self.declare_parameter('command_topic', DEFAULT_COMMAND_TOPIC)
        self.declare_parameter('task_command_topic', '/execution/task/command')
        self.declare_parameter('task_control_topic', '/execution/task/control')
        self.declare_parameter('task_state_topic', '/execution/task/state')
        self.declare_parameter('motion_action_name', '/motion/execute')
        self.declare_parameter('enable_motion_action_server', True)
        self.declare_parameter(
            'read_actuator_position_service',
            '/execution/read_actuator_position',
        )
        self.declare_parameter(
            'stop_actuators_service',
            '/execution/stop_actuators',
        )
        self.declare_parameter('task_lease_wait_timeout_sec', 2.0)
        self.declare_parameter('task_terminal_wait_timeout_sec', 2.0)
        self.declare_parameter('task_keepalive_period_sec', 1.0)
        self.declare_parameter('feedback_poll_period_sec', 0.05)
        self.declare_parameter('service_call_timeout_sec', 1.0)
        self.declare_parameter('stable_sample_count', 3)
        self.declare_parameter('stop_position_tolerance', 1)
        self.declare_parameter('servo_ids', [])
        self.declare_parameter('servo_offsets', [])
        self.declare_parameter('servo_directions', [])

        # 获取参数
        l0 = self.get_parameter('l0').value
        l1 = self.get_parameter('l1').value
        l2 = self.get_parameter('l2').value
        self.ankle_side = self.get_parameter('ankle_side').value
        self.default_speed = self.get_parameter('default_speed').value
        self.debug = self.get_parameter('debug').value
        self.command_topic = self.get_parameter('command_topic').value
        self.task_command_topic = self.get_parameter('task_command_topic').value
        self.task_control_topic = self.get_parameter('task_control_topic').value
        task_state_topic = self.get_parameter('task_state_topic').value
        motion_action_name = self.get_parameter('motion_action_name').value
        enable_motion_action_server = bool(
            self.get_parameter('enable_motion_action_server').value
        )
        read_actuator_position_service = self.get_parameter(
            'read_actuator_position_service'
        ).value
        stop_actuators_service = self.get_parameter(
            'stop_actuators_service'
        ).value
        self.task_lease_wait_timeout_sec = max(
            0.1,
            float(self.get_parameter('task_lease_wait_timeout_sec').value),
        )
        self.task_terminal_wait_timeout_sec = max(
            0.1,
            float(
                self.get_parameter('task_terminal_wait_timeout_sec').value
            ),
        )
        self.task_keepalive_period_sec = max(
            0.05,
            float(self.get_parameter('task_keepalive_period_sec').value),
        )
        self.feedback_poll_period_sec = max(
            0.001,
            float(self.get_parameter('feedback_poll_period_sec').value),
        )
        self.service_call_timeout_sec = max(
            0.1,
            float(self.get_parameter('service_call_timeout_sec').value),
        )
        self.stable_sample_count = max(
            1,
            int(self.get_parameter('stable_sample_count').value),
        )
        self.stop_position_tolerance = max(
            0,
            int(self.get_parameter('stop_position_tolerance').value),
        )
        servo_ids = self.get_parameter('servo_ids').value
        servo_offsets = self.get_parameter('servo_offsets').value
        servo_directions = self.get_parameter('servo_directions').value

        servo_config = None
        if servo_ids:
            servo_ids = list(servo_ids)
            if len(servo_ids) != 3:
                raise ValueError("servo_ids must contain exactly 3 elements")

            servo_offsets = list(servo_offsets) if servo_offsets else [0.0, 0.0, 0.0]
            servo_directions = list(servo_directions) if servo_directions else [1, 1, 1]
            if len(servo_offsets) != 3:
                raise ValueError("servo_offsets must contain exactly 3 elements")
            if len(servo_directions) != 3:
                raise ValueError("servo_directions must contain exactly 3 elements")

            base_mapping = Parallel3DOFKinematicsSolver._default_servo_config()['position_mapping']
            servo_config = {
                'custom': {
                    'servo_1': {
                        'id': int(servo_ids[0]),
                        'offset': float(servo_offsets[0]),
                        'direction': int(servo_directions[0])
                    },
                    'servo_2': {
                        'id': int(servo_ids[1]),
                        'offset': float(servo_offsets[1]),
                        'direction': int(servo_directions[1])
                    },
                    'servo_3': {
                        'id': int(servo_ids[2]),
                        'offset': float(servo_offsets[2]),
                        'direction': int(servo_directions[2])
                    }
                },
                'position_mapping': dict(base_mapping)
            }

            # 使用自定义舵机组
            self.ankle_side = 'custom'

        # 初始化运动学求解器
        try:
            self.solver = Parallel3DOFKinematicsSolver(
                l0=l0,
                l1=l1,
                l2=l2,
                servo_config=servo_config
            )
            self.get_logger().info(f"运动学求解器初始化成功")
        except Exception as e:
            self.get_logger().error(f"运动学求解器初始化失败: {e}")
            raise

        # 订阅脚踝RPY命令
        self.rpy_sub = self.create_subscription(
            Vector3,
            '~/ankle_rpy',
            self.ankle_rpy_callback,
            10
        )

        # 发布执行命令
        self.motion_command_pub = self.create_publisher(
            MotionCommand,
            self.command_topic,
            10
        )
        self.task_motion_command_pub = self.create_publisher(
            MotionCommand,
            self.task_command_topic,
            10,
        )
        self.task_control_pub = self.create_publisher(
            TaskExecutionControl,
            self.task_control_topic,
            10,
        )
        self._task_state_lock = threading.Lock()
        self._latest_task_state = None
        self._task_state_sequence = 0
        self._goal_admission = SingleGoalAdmission()
        self._pending_start_cleanups = {}
        self.task_state_sub = self.create_subscription(
            TaskExecutionState,
            task_state_topic,
            self._on_task_state,
            20,
        )
        self._action_callback_group = ReentrantCallbackGroup()
        self.read_actuator_position_client = self.create_client(
            ReadActuatorPosition,
            read_actuator_position_service,
            callback_group=self._action_callback_group,
        )
        self.stop_actuators_client = self.create_client(
            StopActuators,
            stop_actuators_service,
            callback_group=self._action_callback_group,
        )
        self.motion_action_server = None
        if enable_motion_action_server:
            self.motion_action_server = ActionServer(
                self,
                ExecuteMotion,
                motion_action_name,
                execute_callback=self._execute_motion,
                goal_callback=self._motion_goal_callback,
                cancel_callback=self._motion_cancel_callback,
                callback_group=self._action_callback_group,
            )

        # 发布theta角反馈 (可选,用于调试)
        self.theta_pub = self.create_publisher(
            Float32MultiArray,
            '~/ankle_theta',
            10
        )

        self.get_logger().info(
            f"3-DOF并联控制器节点已启动 (侧: {self.ankle_side}, "
            f"l0={l0}m, l1={l1}m, l2={l2}m, "
            f"command_topic={self.command_topic})"
        )

        # 打印工作空间限制
        limits = self.solver.get_workspace_limits()
        self.get_logger().info("工作空间限制:")
        for axis, lim in limits.items():
            self.get_logger().info(
                f"  {axis}: {lim['deg'][0]:.1f}° ~ {lim['deg'][1]:.1f}°"
            )

    def ankle_rpy_callback(self, msg: Vector3):
        """
        处理脚踝RPY命令

        参数:
            msg: Vector3消息,包含 x=roll, y=pitch, z=yaw (度)
        """
        try:
            # 将度转换为弧度
            roll_rad = np.radians(msg.x)
            pitch_rad = np.radians(msg.y)
            yaw_rad = np.radians(msg.z)

            if self.debug:
                self.get_logger().info(
                    f"收到RPY命令 (度): R={msg.x:.2f}, P={msg.y:.2f}, Y={msg.z:.2f}"
                )

            # 转换为舵机命令
            commands = self.solver.rpy_to_servo_commands(
                roll_rad,
                pitch_rad,
                yaw_rad,
                ankle_side=self.ankle_side,
                speed=self.default_speed
            )

            # 将求解器输出适配为 MotionCommand 并发布
            for cmd in commands:
                motion_msg = self._build_motion_command(cmd)
                self.motion_command_pub.publish(motion_msg)

                if self.debug:
                    self.get_logger().info(
                        f"  actuator_id={motion_msg.servo_id}: "
                        f"target_pulse_us={motion_msg.position}, "
                        f"duration_ms={motion_msg.duration_ms}, "
                        f"theta={cmd['theta_deg']:.2f}°"
                    )

            # 发布theta角反馈
            theta_msg = Float32MultiArray()
            theta_msg.data = [
                float(commands[0]['theta_deg']),
                float(commands[1]['theta_deg']),
                float(commands[2]['theta_deg'])
            ]
            self.theta_pub.publish(theta_msg)

        except Exception as e:
            self.get_logger().error(f"处理RPY命令失败: {e}")

    def _build_motion_command(self, cmd: dict) -> MotionCommand:
        return self._build_execution_command(cmd, '', '')

    def _build_execution_command(
        self,
        cmd: dict,
        requester_id: str,
        lease_id: str,
    ) -> MotionCommand:
        target_pulse_us = int(cmd['position'])
        duration_ms = int(cmd['duration_ms'])

        motion_msg = MotionCommand()
        motion_msg.servo_type = "bus"
        motion_msg.servo_id = int(cmd['id'])
        motion_msg.position = target_pulse_us
        motion_msg.value_encoding = 'bus_pulse_us'
        motion_msg.duration_ms = duration_ms
        motion_msg.requester_id = str(requester_id)
        motion_msg.lease_id = str(lease_id)
        motion_msg.stamp = self.get_clock().now().to_msg()
        return motion_msg

    def _on_task_state(self, msg: TaskExecutionState) -> None:
        cleanup_requests = []
        with self._task_state_lock:
            self._latest_task_state = msg
            self._task_state_sequence += 1
            completed_identities = []
            for identity, (spec, cancel_sent) in (
                self._pending_start_cleanups.items()
            ):
                lease_id = active_task_lease(msg, spec)
                if lease_id and not cancel_sent:
                    self._pending_start_cleanups[identity] = (spec, True)
                    cleanup_requests.append((spec, lease_id))
                elif (
                    is_terminal_task_state(msg, spec)
                    or task_start_was_rejected(msg, spec)
                ):
                    completed_identities.append(identity)
            for identity in completed_identities:
                del self._pending_start_cleanups[identity]
        for spec, lease_id in cleanup_requests:
            self._publish_task_control(
                'cancel',
                spec,
                lease_id,
            )

    def _motion_goal_callback(self, goal_request) -> GoalResponse:
        try:
            normalize_motion_goal(goal_request)
        except MotionGoalValidationError as exc:
            self.get_logger().warning(f'reject motion goal: {exc.reason}')
            return GoalResponse.REJECT
        if not self._task_admission_ready():
            self.get_logger().warning(
                'reject motion goal: task_admission_unavailable'
            )
            return GoalResponse.REJECT
        with self._task_state_lock:
            cleanup_pending = bool(self._pending_start_cleanups)
        if cleanup_pending:
            self.get_logger().warning(
                'reject motion goal: task_admission_cleanup_pending'
            )
            return GoalResponse.REJECT
        if not self._goal_admission.try_acquire():
            self.get_logger().warning('reject motion goal: motion_goal_active')
            return GoalResponse.REJECT
        return GoalResponse.ACCEPT

    def _task_admission_ready(self) -> bool:
        with self._task_state_lock:
            state_received = self._task_state_sequence > 0
        return (
            state_received
            and self.task_control_pub.get_subscription_count() > 0
        )

    @staticmethod
    def _motion_cancel_callback(unused_goal_handle) -> CancelResponse:
        return CancelResponse.ACCEPT

    async def _execute_motion(self, goal_handle):
        request = goal_handle.request
        result = ExecuteMotion.Result()
        self._set_result_identity(result, request)
        self._initialize_result_fields(result)
        spec = None
        lease_id = ''
        targets = {}
        admission_requested = False
        try:
            try:
                spec = normalize_motion_goal(request)
                commands = self.solver.rpy_to_servo_commands(
                    math.radians(spec.roll_deg),
                    math.radians(spec.pitch_deg),
                    math.radians(spec.yaw_deg),
                    ankle_side=spec.target_group[:-len('_ankle')],
                    speed=spec.duration_ms,
                )
            except (MotionGoalValidationError, ValueError) as exc:
                goal_handle.abort()
                return self._finish_result(
                    result,
                    'rejected',
                    getattr(exc, 'reason', str(exc)),
                    recoverable=False,
                )

            start_sequence = self._task_state_snapshot()[0]
            self._publish_task_control('start', spec)
            admission_requested = True
            lease_id, lease_reason, cleanup_required = (
                await self._wait_for_task_lease(
                    spec,
                    start_sequence,
                    goal_handle,
                )
            )
            if not lease_id:
                if cleanup_required:
                    self._register_pending_start_cleanup(spec)
                if goal_handle.is_cancel_requested:
                    goal_handle.canceled()
                    status = 'cancelled'
                else:
                    goal_handle.abort()
                    status = 'rejected'
                return self._finish_result(
                    result,
                    status,
                    lease_reason,
                    recoverable=True,
                )

            if goal_handle.is_cancel_requested:
                return await self._cancel_before_command(
                    goal_handle,
                    result,
                    spec,
                    lease_id,
                )

            issued_monotonic = time.monotonic()
            targets = {
                int(command['id']): int(command['position'])
                for command in commands
            }
            for command in commands:
                self.task_motion_command_pub.publish(
                    self._build_execution_command(
                        command,
                        spec.task_id,
                        lease_id,
                    )
                )

            tracker = StablePositionTracker(self.stable_sample_count)
            deadline = issued_monotonic + spec.execution_timeout_sec
            last_keepalive = issued_monotonic
            while time.monotonic() <= deadline:
                if goal_handle.is_cancel_requested:
                    return await self._cancel_motion(
                        goal_handle,
                        result,
                        spec,
                        lease_id,
                        targets,
                    )

                if (
                    time.monotonic() - last_keepalive
                    >= self.task_keepalive_period_sec
                ):
                    self._publish_task_control('keepalive', spec, lease_id)
                    last_keepalive = time.monotonic()

                observations, read_error = await self._read_positions(
                    spec,
                    lease_id,
                    targets,
                )
                if read_error:
                    return await self._abort_motion(
                        goal_handle,
                        result,
                        spec,
                        lease_id,
                        targets,
                        'failed',
                        read_error,
                        recoverable=True,
                    )

                reached_count, driver_error = evaluate_target_feedback(
                    targets,
                    observations,
                    issued_monotonic,
                    spec.position_tolerance,
                )
                if driver_error is not None:
                    return await self._abort_motion(
                        goal_handle,
                        result,
                        spec,
                        lease_id,
                        targets,
                        'failed',
                        driver_error.reason or 'actuator_error',
                        recoverable=driver_error.recoverable,
                    )

                self._publish_motion_feedback(
                    goal_handle,
                    spec,
                    'executing',
                    '',
                    reached_count,
                    len(targets),
                )
                if tracker.update(reached_count, len(targets)):
                    if goal_handle.is_cancel_requested:
                        return await self._cancel_motion(
                            goal_handle,
                            result,
                            spec,
                            lease_id,
                            targets,
                        )
                    terminal_status = await self._release_task_admission(
                        'finish',
                        spec,
                        lease_id,
                    )
                    result.target_reached = True
                    result.admission_released = bool(terminal_status)
                    if terminal_status != 'finished':
                        self._register_pending_start_cleanup(spec)
                        goal_handle.abort()
                        if terminal_status:
                            reason = f'task_admission_{terminal_status}'
                        else:
                            reason = 'task_admission_release_unconfirmed'
                        return self._finish_result(
                            result,
                            'failed',
                            reason,
                            recoverable=True,
                        )
                    goal_handle.succeed()
                    result.success = True
                    return self._finish_result(
                        result,
                        'succeeded',
                        '',
                        recoverable=False,
                    )
                await self._sleep(self.feedback_poll_period_sec)

            return await self._abort_motion(
                goal_handle,
                result,
                spec,
                lease_id,
                targets,
                'timed_out',
                'execution_timeout',
                recoverable=True,
            )
        except Exception as exc:
            return await self._handle_unexpected_motion_error(
                goal_handle,
                result,
                spec,
                lease_id,
                targets,
                admission_requested,
                'failed',
                f'motion_execution_error:{exc}',
                recoverable=True,
            )
        finally:
            self._goal_admission.release()

    async def _abort_motion(
        self,
        goal_handle,
        result,
        spec,
        lease_id,
        targets,
        status,
        reason,
        recoverable,
    ):
        stop_fields = await self._request_stop(spec, lease_id, targets)
        terminal_status = await self._release_task_admission(
            'cancel',
            spec,
            lease_id,
        )
        goal_handle.abort()
        result.admission_released = bool(terminal_status)
        result.stop_requested = True
        result.stop_command_sent = stop_fields['stop_command_sent']
        result.stop_confirmed = False
        if not terminal_status:
            self._register_pending_start_cleanup(spec)
            reason = 'task_admission_release_unconfirmed'
            recoverable = True
        return self._finish_result(
            result,
            status,
            reason,
            recoverable=recoverable,
        )

    async def _cancel_motion(self, goal_handle, result, spec, lease_id, targets):
        self._publish_motion_feedback(
            goal_handle,
            spec,
            'cancelled',
            '',
            0,
            len(targets),
            cancel_requested=True,
        )
        stop_fields = await self._request_stop(spec, lease_id, targets)
        stop_confirmed = False
        if stop_fields['stop_command_sent']:
            stop_confirmed = await self._confirm_stopped(
                spec,
                lease_id,
                targets,
            )
        terminal_status = await self._release_task_admission(
            'cancel',
            spec,
            lease_id,
        )
        goal_handle.canceled()
        result.admission_released = bool(terminal_status)
        result.stop_requested = True
        result.stop_command_sent = stop_fields['stop_command_sent']
        result.stop_confirmed = stop_confirmed
        if not terminal_status:
            self._register_pending_start_cleanup(spec)
            reason = 'task_admission_release_unconfirmed'
        elif not stop_confirmed:
            reason = 'stop_not_confirmed'
        else:
            reason = ''
        return self._finish_result(
            result,
            'cancelled',
            reason,
            recoverable=not stop_confirmed or not terminal_status,
        )

    async def _cancel_before_command(
        self,
        goal_handle,
        result,
        spec,
        lease_id,
    ):
        terminal_status = await self._release_task_admission(
            'cancel',
            spec,
            lease_id,
        )
        goal_handle.canceled()
        result.admission_released = bool(terminal_status)
        if not terminal_status:
            self._register_pending_start_cleanup(spec)
        return self._finish_result(
            result,
            'cancelled',
            '' if terminal_status else 'task_admission_release_unconfirmed',
            recoverable=not terminal_status,
        )

    async def _handle_unexpected_motion_error(
        self,
        goal_handle,
        result,
        spec,
        lease_id,
        targets,
        admission_requested,
        status,
        reason,
        recoverable,
    ):
        result.stop_requested = bool(lease_id and targets)
        if lease_id and targets:
            try:
                stop_fields = await self._request_stop(
                    spec,
                    lease_id,
                    targets,
                )
                result.stop_command_sent = stop_fields['stop_command_sent']
            except Exception as stop_exc:
                self.get_logger().warning(
                    f'unexpected motion stop failed: {stop_exc}'
                )
        if spec is not None and lease_id:
            try:
                terminal_status = await self._release_task_admission(
                    'cancel',
                    spec,
                    lease_id,
                )
                result.admission_released = bool(terminal_status)
            except Exception as release_exc:
                self.get_logger().warning(
                    f'unexpected admission cleanup failed: {release_exc}'
                )
        if (
            admission_requested
            and spec is not None
            and not result.admission_released
        ):
            self._register_pending_start_cleanup(spec)
        goal_handle.abort()
        if (
            admission_requested
            and spec is not None
            and not result.admission_released
        ):
            reason = 'task_admission_release_unconfirmed'
            recoverable = True
        return self._finish_result(
            result,
            status,
            reason,
            recoverable=recoverable,
        )

    async def _confirm_stopped(self, spec, lease_id, targets) -> bool:
        previous_positions = None
        stable_tracker = StablePositionTracker(self.stable_sample_count)
        stop_deadline = time.monotonic() + min(spec.execution_timeout_sec, 2.0)
        while time.monotonic() <= stop_deadline:
            self._publish_task_control('keepalive', spec, lease_id)
            observations, read_error = await self._read_positions(
                spec,
                lease_id,
                targets,
            )
            if read_error:
                return False
            current_positions = {
                actuator_id: observation.position_raw
                for actuator_id, observation in observations.items()
            }
            if previous_positions is None:
                unchanged = 0
            else:
                unchanged = sum(
                    1 for actuator_id, position in current_positions.items()
                    if abs(position - previous_positions.get(actuator_id, position))
                    <= self.stop_position_tolerance
                )
            if stable_tracker.update(unchanged, len(targets)):
                return True
            previous_positions = current_positions
            await self._sleep(self.feedback_poll_period_sec)
        return False

    async def _read_positions(self, spec, lease_id, targets):
        observations = {}
        for actuator_id in targets:
            if not self.read_actuator_position_client.service_is_ready():
                return {}, 'read_actuator_service_unavailable'
            request = ReadActuatorPosition.Request()
            self._fill_task_operation_request(request, spec, lease_id)
            request.actuator_type = 'bus'
            request.actuator_id = int(actuator_id)
            response = await self._await_service_response(
                self.read_actuator_position_client.call_async(request)
            )
            if response is None:
                return {}, 'actuator_position_read_timeout'
            if not response.success:
                return {}, response.reason or 'actuator_position_read_failed'
            observations[actuator_id] = ActuatorObservation(
                position_raw=int(response.position_raw),
                status=str(response.status),
                reason=str(response.reason),
                recoverable=bool(response.recoverable),
                observed_monotonic=time.monotonic(),
            )
        return observations, ''

    async def _request_stop(self, spec, lease_id, targets):
        if not self.stop_actuators_client.service_is_ready():
            return {'stop_command_sent': False, 'stop_confirmed': False}
        request = StopActuators.Request()
        self._fill_task_operation_request(request, spec, lease_id)
        request.actuator_type = 'bus'
        request.actuator_ids = [int(value) for value in targets]
        response = await self._await_service_response(
            self.stop_actuators_client.call_async(request)
        )
        if response is None:
            return {'stop_command_sent': False, 'stop_confirmed': False}
        return {
            'stop_command_sent': bool(response.stop_command_sent),
            'stop_confirmed': bool(response.stop_confirmed),
        }

    async def _wait_for_task_lease(
        self,
        spec,
        minimum_sequence,
        goal_handle,
    ):
        deadline = time.monotonic() + self.task_lease_wait_timeout_sec
        while time.monotonic() <= deadline:
            if goal_handle.is_cancel_requested:
                return '', 'motion_cancel_requested', True
            sequence, state = self._task_state_snapshot()
            if sequence > minimum_sequence:
                if task_start_was_rejected(state, spec):
                    return (
                        '',
                        str(state.reason) or 'task_lease_not_granted',
                        False,
                    )
                if task_start_was_accepted(state, spec):
                    return active_task_lease(state, spec), '', False
            await self._sleep(0.01)
        return '', 'task_admission_state_unconfirmed', True

    async def _release_task_admission(
        self,
        action,
        spec,
        lease_id,
    ) -> str:
        sequence, state = self._task_state_snapshot()
        status = terminal_task_status(state, spec)
        if status:
            return status
        self._publish_task_control(action, spec, lease_id)
        return await self._wait_for_task_terminal(spec, sequence)

    async def _wait_for_task_terminal(self, spec, minimum_sequence) -> str:
        deadline = time.monotonic() + self.task_terminal_wait_timeout_sec
        while time.monotonic() <= deadline:
            sequence, state = self._task_state_snapshot()
            if sequence > minimum_sequence:
                status = terminal_task_status(state, spec)
                if status:
                    return status
            await self._sleep(0.01)
        return ''

    def _task_state_snapshot(self):
        with self._task_state_lock:
            return self._task_state_sequence, self._latest_task_state

    def _register_pending_start_cleanup(self, spec) -> None:
        cleanup_request = None
        identity = (spec.task_id, spec.trace_id, spec.session_id)
        with self._task_state_lock:
            state = self._latest_task_state
            if is_terminal_task_state(state, spec):
                self._pending_start_cleanups.pop(identity, None)
                return
            lease_id = active_task_lease(state, spec)
            self._pending_start_cleanups[identity] = (spec, bool(lease_id))
            if lease_id:
                cleanup_request = (spec, lease_id)
        if cleanup_request is not None:
            self._publish_task_control(
                'cancel',
                cleanup_request[0],
                cleanup_request[1],
            )

    async def _sleep(self, delay_sec) -> None:
        completed = Future()
        timer_holder = {}

        def wake() -> None:
            timer = timer_holder.get('timer')
            if timer is not None:
                self.destroy_timer(timer)
            if not completed.done():
                completed.set_result(None)

        timer_holder['timer'] = self.create_timer(
            max(0.001, float(delay_sec)),
            wake,
            callback_group=self._action_callback_group,
        )
        await completed

    async def _await_service_response(self, pending_future):
        completed = Future()
        timer_holder = {}

        def finish(response_future=None) -> None:
            timer = timer_holder.pop('timer', None)
            if timer is not None:
                self.destroy_timer(timer)
            if not completed.done():
                completed.set_result(response_future)

        timer_holder['timer'] = self.create_timer(
            self.service_call_timeout_sec,
            finish,
            callback_group=self._action_callback_group,
        )
        pending_future.add_done_callback(finish)
        finished_future = await completed
        if finished_future is None:
            return None
        try:
            return finished_future.result()
        except Exception as exc:
            self.get_logger().warning(f'service call failed: {exc}')
            return None

    def _publish_task_control(self, action, spec, lease_id='') -> None:
        msg = TaskExecutionControl()
        msg.action = str(action)
        msg.task_id = spec.task_id
        msg.trace_id = spec.trace_id
        msg.session_id = spec.session_id
        msg.lease_id = str(lease_id)
        msg.stamp = self.get_clock().now().to_msg()
        self.task_control_pub.publish(msg)

    @staticmethod
    def _fill_task_operation_request(request, spec, lease_id):
        request.task_id = spec.task_id
        request.trace_id = spec.trace_id
        request.session_id = spec.session_id
        request.lease_id = lease_id

    @staticmethod
    def _set_result_identity(result, request):
        result.task_id = str(request.task_id)
        result.trace_id = str(request.trace_id)
        result.session_id = str(request.session_id)

    @staticmethod
    def _initialize_result_fields(result):
        result.success = False
        result.target_reached = False
        result.admission_released = False
        result.stop_requested = False
        result.stop_command_sent = False
        result.stop_confirmed = False

    @staticmethod
    def _finish_result(result, status, reason, recoverable):
        result.status = str(status)
        result.reason = str(reason)
        result.recoverable = bool(recoverable)
        return result

    def _publish_motion_feedback(
        self,
        goal_handle,
        spec,
        status,
        reason,
        reached_count,
        target_count,
        cancel_requested=False,
        stop_command_sent=False,
        stop_confirmed=False,
    ):
        feedback = ExecuteMotion.Feedback()
        feedback.task_id = spec.task_id
        feedback.trace_id = spec.trace_id
        feedback.session_id = spec.session_id
        feedback.status = str(status)
        feedback.reason = str(reason)
        feedback.progress = progress_fraction(reached_count, target_count)
        feedback.reached_actuator_count = int(reached_count)
        feedback.target_actuator_count = int(target_count)
        feedback.cancel_requested = bool(cancel_requested)
        feedback.stop_command_sent = bool(stop_command_sent)
        feedback.stop_confirmed = bool(stop_confirmed)
        goal_handle.publish_feedback(feedback)


def main(args=None):
    """主函数"""
    rclpy.init(args=args)

    node = None
    executor = None
    try:
        node = Parallel3DOFControllerNode()
        executor = MultiThreadedExecutor(num_threads=4)
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"节点异常: {e}")
    finally:
        if executor is not None:
            executor.shutdown()
        if node is not None:
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
