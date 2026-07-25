"""Formal task Action chain ROS 2 smoke scenario."""

import json
import threading
import time

from action_msgs.msg import GoalStatus
from execution_manager.execution_manager_node import ExecutionManagerNode
from motion_msgs.msg import ExecutionState, MotionCommand, TaskExecutionState
from motion_msgs.msg import TeleopControl
from parallel_3dof_controller.controller_node import Parallel3DOFControllerNode
import rclpy
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from servo_hardware.safety_latch import DriverSafetyLatch, ros_time_to_ns
from servo_hardware.safety_qos import driver_safety_qos_profile
from servo_msgs.msg import DriverSafetyState, ServoCommand
from servo_msgs.srv import ExecuteBusCommand, ReadServoPosition, SetDriverSafety
from std_msgs.msg import Bool
from task_api_msgs.action import ExecuteTask
from task_service_bridge.bridge_node import TaskServiceBridgeNode


SCENARIO_TIMEOUT_SEC = 25.0
WAIT_TIMEOUT_SEC = 4.0
POSITION_STEP = 60
HELD_TARGET_GAP = 80


def _wait_for(predicate, timeout_sec: float, description: str):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.01)
    raise RuntimeError(f'timeout waiting for {description}')


def _wait_future(future, timeout_sec: float, description: str):
    _wait_for(lambda: future.done(), timeout_sec, description)
    exception = future.exception()
    if exception is not None:
        raise exception
    return future.result()


class FakeDriverNode(Node):
    """Driver double whose sampled positions physically approach each target."""

    def __init__(self) -> None:
        super().__init__('task_chain_fake_driver')
        self._lock = threading.Lock()
        self._callback_group = ReentrantCallbackGroup()
        self._positions = {}
        self._targets = {}
        self._stopped = set()
        self._completion_released = False
        self.command_count = 0
        self.move_attempt_count = 0
        self.move_rejected_count = 0
        self.late_move_rejected_ids = []
        self.active_move_rejected_ids = []
        self.non_target_read_count = 0
        self.target_read_counts = {}
        self.stop_read_counts = {}
        self.stop_attempts = []
        self.stop_commands = []
        self.driver_safety_requests = []
        self._block_next_stop = False
        self._blocked_stop_id = None
        self._blocked_stop_entered = threading.Event()
        self._blocked_stop_release = threading.Event()
        self._defer_move_count = 0
        self._deferred_move_expected_count = 0
        self._deferred_move_entered_count = 0
        self._deferred_move_exited_count = 0
        self._deferred_move_entered = threading.Event()
        self._deferred_move_release = threading.Event()
        self._deferred_move_exited = threading.Event()
        self.safety_latch = DriverSafetyLatch()

        self.create_subscription(
            ServoCommand,
            '/servo/command',
            self._on_servo_command,
            20,
            callback_group=self._callback_group,
        )
        self.create_subscription(
            DriverSafetyState,
            '/servo/driver_safety',
            self._on_driver_safety,
            driver_safety_qos_profile(),
            callback_group=self._callback_group,
        )
        self.create_service(
            ReadServoPosition,
            '/servo/read_position',
            self._read_position,
            callback_group=self._callback_group,
        )
        self.create_service(
            ExecuteBusCommand,
            '/servo/execute_command',
            self._execute_command,
            callback_group=self._callback_group,
        )
        self.create_service(
            SetDriverSafety,
            '/servo/set_driver_safety',
            self._set_driver_safety,
            callback_group=self._callback_group,
        )

    def hold_before_target(self) -> None:
        with self._lock:
            self._positions.clear()
            self._targets.clear()
            self._stopped.clear()
            self._completion_released = False

    def release_targets(self) -> None:
        with self._lock:
            self._completion_released = True

    def block_next_stop(self) -> None:
        with self._lock:
            self._block_next_stop = True
            self._blocked_stop_id = None
            self._blocked_stop_entered.clear()
            self._blocked_stop_release.clear()

    def wait_for_blocked_stop(self) -> bool:
        return self._blocked_stop_entered.wait(WAIT_TIMEOUT_SEC)

    def release_blocked_stop(self) -> None:
        self._blocked_stop_release.set()

    def defer_next_moves(self, count: int) -> None:
        with self._lock:
            self._defer_move_count = max(0, int(count))
            self._deferred_move_expected_count = self._defer_move_count
            self._deferred_move_entered_count = 0
            self._deferred_move_exited_count = 0
            self._deferred_move_entered.clear()
            self._deferred_move_release.clear()
            self._deferred_move_exited.clear()

    def wait_for_deferred_moves(self) -> bool:
        return self._deferred_move_entered.wait(WAIT_TIMEOUT_SEC)

    def release_deferred_moves(self) -> None:
        self._deferred_move_release.set()

    def wait_for_deferred_move_exit(self) -> bool:
        return self._deferred_move_exited.wait(WAIT_TIMEOUT_SEC)

    def target_ids(self):
        with self._lock:
            return set(self._targets)

    def minimum_target_reads(self) -> int:
        with self._lock:
            if not self._targets:
                return 0
            return min(
                self.target_read_counts.get(actuator_id, 0)
                for actuator_id in self._targets
            )

    def minimum_stop_reads(self) -> int:
        with self._lock:
            if not self._stopped:
                return 0
            return min(
                self.stop_read_counts.get(actuator_id, 0)
                for actuator_id in self._stopped
            )

    def snapshot(self) -> dict:
        with self._lock:
            return {
                'command_count': self.command_count,
                'move_attempt_count': self.move_attempt_count,
                'move_rejected_count': self.move_rejected_count,
                'late_move_rejected_ids': list(self.late_move_rejected_ids),
                'active_move_rejected_ids': list(self.active_move_rejected_ids),
                'non_target_read_count': self.non_target_read_count,
                'target_read_counts': dict(self.target_read_counts),
                'stop_read_counts': dict(self.stop_read_counts),
                'stop_commands': list(self.stop_commands),
                'stop_attempts': list(self.stop_attempts),
                'driver_safety_requests': list(self.driver_safety_requests),
                'blocked_stop_id': self._blocked_stop_id,
                'target_ids': sorted(self._targets),
                'targets': dict(self._targets),
                'positions': dict(self._positions),
                'stopped_ids': sorted(self._stopped),
                'safety_latched': self.safety_latch.latched,
                'safety_fence_ns': self.safety_latch.fence_ns,
                'deferred_move_exited_count': self._deferred_move_exited_count,
            }

    def _on_servo_command(self, message: ServoCommand) -> None:
        actuator_id = int(message.servo_id)
        target = int(message.position)
        should_defer = False
        with self._lock:
            self.move_attempt_count += 1
            if self._defer_move_count > 0:
                self._defer_move_count -= 1
                self._deferred_move_entered_count += 1
                should_defer = True
                if self._defer_move_count == 0:
                    self._deferred_move_entered.set()
        if should_defer:
            self._deferred_move_release.wait(SCENARIO_TIMEOUT_SEC)

        stamp_ns = ros_time_to_ns(message.stamp)
        if not self.safety_latch.admit(stamp_ns):
            with self._lock:
                self.move_rejected_count += 1
                if stamp_ns <= self.safety_latch.fence_ns:
                    self.late_move_rejected_ids.append(actuator_id)
                else:
                    self.active_move_rejected_ids.append(actuator_id)
                if should_defer:
                    self._deferred_move_exited_count += 1
                    if (
                        self._deferred_move_exited_count
                        >= self._deferred_move_expected_count
                    ):
                        self._deferred_move_exited.set()
            return

        with self._lock:
            self.command_count += 1
            if actuator_id not in self._positions:
                if target <= 1900:
                    self._positions[actuator_id] = min(2500, target + 500)
                else:
                    self._positions[actuator_id] = max(500, target - 500)
            self._targets[actuator_id] = target
            self._stopped.discard(actuator_id)
            self.target_read_counts[actuator_id] = 0
            self.stop_read_counts[actuator_id] = 0
            if should_defer:
                self._deferred_move_exited_count += 1
                if (
                    self._deferred_move_exited_count
                    >= self._deferred_move_expected_count
                ):
                    self._deferred_move_exited.set()

    def _on_driver_safety(self, message: DriverSafetyState) -> None:
        self.safety_latch.observe_authority(
            active=bool(message.estop_active),
            stamp_ns=ros_time_to_ns(message.stamp),
            now_ns=int(self.get_clock().now().nanoseconds),
        )

    def _set_driver_safety(self, request, response):
        with self._lock:
            self.driver_safety_requests.append(bool(request.estop_active))
        self.safety_latch.observe_authority(
            active=bool(request.estop_active),
            stamp_ns=ros_time_to_ns(request.stamp),
            now_ns=int(self.get_clock().now().nanoseconds),
        )
        response.success = (
            self.safety_latch.latched == bool(request.estop_active)
        )
        response.reason = '' if response.success else 'stale_safety_state'
        response.stamp = self.get_clock().now().to_msg()
        return response

    def _read_position(self, request, response):
        actuator_id = int(request.servo_id)
        with self._lock:
            current = self._positions.get(actuator_id, 1500)
            target = self._targets.get(actuator_id)
            if actuator_id in self._stopped:
                self.stop_read_counts[actuator_id] = (
                    self.stop_read_counts.get(actuator_id, 0) + 1
                )
            elif target is not None:
                allowed_gap = 0 if self._completion_released else HELD_TARGET_GAP
                difference = target - current
                if abs(difference) > allowed_gap:
                    movement = min(POSITION_STEP, abs(difference) - allowed_gap)
                    current += movement if difference > 0 else -movement
                    self._positions[actuator_id] = current

            if target is not None and current == target:
                self.target_read_counts[actuator_id] = (
                    self.target_read_counts.get(actuator_id, 0) + 1
                )
            elif target is not None:
                self.non_target_read_count += 1

            response.position = int(current)
            response.protocol = self._protocol_for(actuator_id)

        response.success = True
        response.error_code = 0
        response.message = ''
        response.stamp = self.get_clock().now().to_msg()
        return response

    def _execute_command(self, request, response):
        actuator_id = int(request.servo_id)
        protocol = str(request.protocol).strip().lower()
        command = str(request.command).strip().lower()
        expected = 'move_stop' if protocol == 'lx' else 'stop_motion'
        self.safety_latch.admit_protocol_command(
            command,
            now_ns=int(self.get_clock().now().nanoseconds),
        )
        should_block = False
        with self._lock:
            self.stop_attempts.append((actuator_id, protocol, command))
            if self._block_next_stop:
                self._block_next_stop = False
                self._blocked_stop_id = actuator_id
                should_block = True
        if should_block:
            self._blocked_stop_entered.set()
            self._blocked_stop_release.wait(SCENARIO_TIMEOUT_SEC)
        accepted = (
            protocol == self._protocol_for(actuator_id)
            and command == expected
        )
        with self._lock:
            self.stop_commands.append((actuator_id, protocol, command, accepted))
            if accepted:
                self._stopped.add(actuator_id)
                self.stop_read_counts[actuator_id] = 0

        response.success = accepted
        response.protocol = protocol
        response.error_code = 0 if accepted else 1
        response.message = '' if accepted else 'unexpected_stop_command'
        response.value = 0
        response.values = []
        response.raw_hex = ''
        response.result_json = ''
        response.stamp = self.get_clock().now().to_msg()
        return response

    @staticmethod
    def _protocol_for(actuator_id: int) -> str:
        return 'lx' if actuator_id % 2 else 'zl'


class ProbeNode(Node):
    """External task client plus execution-boundary observations."""

    def __init__(self) -> None:
        super().__init__('task_chain_smoke_probe')
        self._lock = threading.Lock()
        self.task_states = []
        self.execution_states = []
        self.feedback = {}
        self.servo_commands = []

        self.task_client = ActionClient(self, ExecuteTask, '/task/execute')
        self.motion_command_pub = self.create_publisher(
            MotionCommand,
            '/execution/motion/command',
            10,
        )
        self.teleop_control_pub = self.create_publisher(
            TeleopControl,
            '/execution/teleop/control',
            10,
        )
        self.estop_pub = self.create_publisher(Bool, '/execution/estop', 10)
        self.raw_servo_command_pub = self.create_publisher(
            ServoCommand,
            '/servo/command',
            20,
        )
        self.create_subscription(
            TaskExecutionState,
            '/execution/task/state',
            self._on_task_state,
            20,
        )
        self.create_subscription(
            ExecutionState,
            '/execution/state',
            self._on_execution_state,
            20,
        )
        self.create_subscription(
            ServoCommand,
            '/servo/command',
            self._on_servo_command,
            20,
        )

    def send_task(self, identity: str):
        goal = ExecuteTask.Goal()
        goal.task_id = f'task-chain-{identity}'
        goal.trace_id = f'trace-chain-{identity}'
        goal.session_id = f'session-chain-{identity}'
        goal.task_type = 'ankle_pose'
        goal.target_group = 'right_ankle'
        if identity == 'cancel':
            goal.roll_deg = -9.0
            goal.pitch_deg = 5.0
            goal.yaw_deg = -3.0
        else:
            goal.roll_deg = 8.0
            goal.pitch_deg = -4.0
            goal.yaw_deg = 2.0
        goal.duration_ms = 250
        goal.position_tolerance = 10
        goal.execution_timeout_sec = 6.0
        return self.task_client.send_goal_async(
            goal,
            feedback_callback=lambda message: self._on_feedback(
                identity,
                message.feedback,
            ),
        )

    def feedback_for(self, identity: str):
        with self._lock:
            return list(self.feedback.get(identity, ()))

    def task_state_for(self, task_id: str, active=None):
        with self._lock:
            for state in reversed(self.task_states):
                if state.task_id != task_id:
                    continue
                if active is None or bool(state.active) == bool(active):
                    return state
        return None

    def latest_execution_state(self):
        with self._lock:
            return self.execution_states[-1] if self.execution_states else None

    def servo_command_count(self) -> int:
        with self._lock:
            return len(self.servo_commands)

    def servo_commands_since(self, index: int):
        with self._lock:
            return list(self.servo_commands[int(index):])

    def publish_raw_servo_move(self, actuator_id: int, position: int) -> None:
        message = ServoCommand()
        message.servo_type = 'bus'
        message.servo_id = int(actuator_id)
        message.position = int(position)
        message.speed = 100
        message.stamp = self.get_clock().now().to_msg()
        self.raw_servo_command_pub.publish(message)

    def set_estop(self, active: bool) -> None:
        message = Bool()
        message.data = bool(active)
        self.estop_pub.publish(message)

    def _on_feedback(self, identity: str, feedback) -> None:
        with self._lock:
            self.feedback.setdefault(identity, []).append(feedback)

    def _on_task_state(self, state: TaskExecutionState) -> None:
        with self._lock:
            self.task_states.append(state)

    def _on_execution_state(self, state: ExecutionState) -> None:
        with self._lock:
            self.execution_states.append(state)

    def _on_servo_command(self, command: ServoCommand) -> None:
        with self._lock:
            self.servo_commands.append(command)


def _ordinary_motion() -> MotionCommand:
    message = MotionCommand()
    message.servo_type = 'bus'
    message.servo_id = 99
    message.position = 1700
    message.value_encoding = 'bus_pulse_us'
    message.duration_ms = 100
    return message


def _teleop_claim() -> TeleopControl:
    message = TeleopControl()
    message.action = 'claim'
    message.requester_id = 'task-chain-operator'
    return message


def _assert_feedback_identity(feedback, identity: str) -> None:
    expected = (
        f'task-chain-{identity}',
        f'trace-chain-{identity}',
        f'session-chain-{identity}',
    )
    actual = (feedback.task_id, feedback.trace_id, feedback.session_id)
    if actual != expected:
        raise RuntimeError(f'feedback identity mismatch: {actual!r}')


def _assert_result_identity(result, identity: str) -> None:
    expected = (
        f'task-chain-{identity}',
        f'trace-chain-{identity}',
        f'session-chain-{identity}',
    )
    actual = (result.task_id, result.trace_id, result.session_id)
    if actual != expected:
        raise RuntimeError(f'result identity mismatch: {actual!r}')


def _wait_for_active_task(probe: ProbeNode, identity: str):
    task_id = f'task-chain-{identity}'
    return _wait_for(
        lambda: probe.task_state_for(task_id, active=True),
        WAIT_TIMEOUT_SEC,
        f'active task lease for {task_id}',
    )


def _wait_for_terminal_task(probe: ProbeNode, identity: str, status: str):
    task_id = f'task-chain-{identity}'
    return _wait_for(
        lambda: next(
            (
                state
                for state in reversed(probe.task_states)
                if state.task_id == task_id
                and not state.active
                and not state.lease_id
                and state.status == status
            ),
            None,
        ),
        WAIT_TIMEOUT_SEC,
        f'{status} terminal task state for {task_id}',
    )


def _exercise_active_task_boundaries(probe: ProbeNode) -> dict:
    state = probe.latest_execution_state()
    motion_rejected_before = state.motion_rejected_count if state else 0
    teleop_rejected_before = state.teleop_control_rejected_count if state else 0
    servo_count = probe.servo_command_count()

    probe.motion_command_pub.publish(_ordinary_motion())
    motion_rejection = _wait_for(
        lambda: (
            probe.latest_execution_state()
            if probe.latest_execution_state() is not None
            and probe.latest_execution_state().motion_rejected_count
            > motion_rejected_before
            and probe.latest_execution_state().last_rejection_reason
            == 'task_active'
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'ordinary motion task_active rejection',
    )
    if probe.servo_command_count() != servo_count:
        raise RuntimeError('ordinary motion escaped the active task boundary')

    probe.teleop_control_pub.publish(_teleop_claim())
    teleop_rejection = _wait_for(
        lambda: (
            probe.latest_execution_state()
            if probe.latest_execution_state() is not None
            and probe.latest_execution_state().teleop_control_rejected_count
            > teleop_rejected_before
            and probe.latest_execution_state().last_teleop_control_reason
            == 'task_active'
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'teleop task_active rejection',
    )
    return {
        'motion_rejection': motion_rejection.last_rejection_reason,
        'teleop_rejection': teleop_rejection.last_teleop_control_reason,
    }


def _run_success_scenario(probe: ProbeNode, driver: FakeDriverNode) -> dict:
    identity = 'success'
    driver.hold_before_target()
    command_count_before = driver.snapshot()['command_count']
    probe_command_count_before = probe.servo_command_count()
    goal_handle = _wait_future(
        probe.send_task(identity),
        WAIT_TIMEOUT_SEC,
        'successful task goal response',
    )
    if not goal_handle.accepted:
        raise RuntimeError('successful task goal was rejected')
    result_future = goal_handle.get_result_async()
    active_state = _wait_for_active_task(probe, identity)
    if not active_state.lease_id:
        raise RuntimeError('active task lease was empty')
    _wait_for(
        lambda: (
            driver.snapshot()['command_count'] >= command_count_before + 3
            and len(driver.target_ids()) == 3
            and probe.servo_command_count() >= probe_command_count_before + 3
        ),
        WAIT_TIMEOUT_SEC,
        'three task actuator commands at fake driver',
    )

    second_goal = _wait_future(
        probe.send_task('concurrent'),
        WAIT_TIMEOUT_SEC,
        'concurrent task goal response',
    )
    if second_goal.accepted:
        raise RuntimeError('concurrent task goal was unexpectedly accepted')

    boundaries = _exercise_active_task_boundaries(probe)
    feedback = _wait_for(
        lambda: (
            probe.feedback_for(identity)
            if len(probe.feedback_for(identity)) > 1
            and driver.snapshot()['non_target_read_count'] > 0
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'multiple pre-target feedback samples',
    )
    if result_future.done():
        raise RuntimeError('task succeeded before the sampled target was reached')
    for sample in feedback:
        _assert_feedback_identity(sample, identity)

    driver.release_targets()
    result_response = _wait_future(
        result_future,
        WAIT_TIMEOUT_SEC,
        'successful task result',
    )
    result = result_response.result
    _assert_result_identity(result, identity)
    for sample in probe.feedback_for(identity):
        _assert_feedback_identity(sample, identity)
    if result_response.status != GoalStatus.STATUS_SUCCEEDED:
        raise RuntimeError('successful task Action did not reach succeeded state')
    if not result.success or not result.target_reached:
        raise RuntimeError('successful task result did not confirm target reached')
    if not result.admission_released:
        raise RuntimeError('successful task did not confirm admission release')
    if driver.minimum_target_reads() < 3:
        raise RuntimeError('task succeeded without three stable target samples')

    terminal = _wait_for_terminal_task(probe, identity, 'finished')
    return {
        'goal_accepted': True,
        'feedback_count': len(probe.feedback_for(identity)),
        'identity_preserved': True,
        'not_completed_before_target': True,
        'stable_target_samples': driver.minimum_target_reads(),
        'lease_cleared': not terminal.lease_id,
        'concurrent_task_rejected': not second_goal.accepted,
        **boundaries,
    }


def _run_cancel_scenario(probe: ProbeNode, driver: FakeDriverNode) -> dict:
    identity = 'cancel'
    driver.hold_before_target()
    driver_snapshot = driver.snapshot()
    command_count_before = driver_snapshot['command_count']
    stop_count_before = len(driver_snapshot['stop_commands'])
    goal_handle = _wait_future(
        probe.send_task(identity),
        WAIT_TIMEOUT_SEC,
        'cancel task goal response',
    )
    if not goal_handle.accepted:
        raise RuntimeError('cancel task goal was rejected')
    _wait_for_active_task(probe, identity)
    _wait_for(
        lambda: (
            driver.snapshot()['command_count'] >= command_count_before + 3
            and len(driver.target_ids()) == 3
        ),
        WAIT_TIMEOUT_SEC,
        'three cancel-scenario actuator commands at fake driver',
    )
    _wait_for(
        lambda: (
            probe.feedback_for(identity)
            if len(probe.feedback_for(identity)) > 1
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'cancel task executing feedback',
    )

    cancel_response = _wait_future(
        goal_handle.cancel_goal_async(),
        WAIT_TIMEOUT_SEC,
        'external task cancel response',
    )
    if not cancel_response.goals_canceling:
        raise RuntimeError('external task cancellation was rejected')

    result_response = _wait_future(
        goal_handle.get_result_async(),
        WAIT_TIMEOUT_SEC,
        'cancelled task result',
    )
    result = result_response.result
    _assert_result_identity(result, identity)
    if result_response.status != GoalStatus.STATUS_CANCELED:
        raise RuntimeError('cancelled task Action did not reach canceled state')
    if result.status != 'cancelled' or result.success or result.target_reached:
        raise RuntimeError('cancelled task returned inconsistent result fields')
    if not (
        result.stop_requested
        and result.stop_command_sent
        and result.stop_confirmed
        and result.admission_released
    ):
        raise RuntimeError('cancelled task did not confirm stop and lease release')

    feedback = _wait_for(
        lambda: (
            probe.feedback_for(identity)
            if any(
                sample.cancel_requested
                for sample in probe.feedback_for(identity)
            )
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'cancel propagation feedback',
    )
    for sample in feedback:
        _assert_feedback_identity(sample, identity)

    stop_commands = driver.snapshot()['stop_commands'][stop_count_before:]
    target_ids = driver.target_ids()
    accepted_stop_ids = {
        actuator_id
        for actuator_id, unused_protocol, unused_command, accepted
        in stop_commands
        if accepted
    }
    if accepted_stop_ids != target_ids:
        raise RuntimeError('not every commanded actuator received a driver stop')
    if driver.minimum_stop_reads() < 4:
        raise RuntimeError('stop was confirmed without consecutive frozen samples')

    terminal = _wait_for_terminal_task(probe, identity, 'cancelled')
    return {
        'goal_accepted': True,
        'cancel_propagated': True,
        'stop_command_count': len(accepted_stop_ids),
        'stop_confirmed': result.stop_confirmed,
        'stable_stop_samples': driver.minimum_stop_reads(),
        'lease_cleared': not terminal.lease_id,
        'identity_preserved': True,
    }


def _run_delayed_stop_scenario(
    probe: ProbeNode,
    driver: FakeDriverNode,
    manager: ExecutionManagerNode,
) -> dict:
    identity = 'delayed-stop'
    driver.hold_before_target()
    driver.block_next_stop()
    safety_request_count_before = len(
        driver.snapshot()['driver_safety_requests']
    )
    command_count_before = driver.snapshot()['command_count']
    goal_handle = _wait_future(
        probe.send_task(identity),
        WAIT_TIMEOUT_SEC,
        'delayed-stop task goal response',
    )
    if not goal_handle.accepted:
        raise RuntimeError('delayed-stop task goal was rejected')
    _wait_for_active_task(probe, identity)
    _wait_for(
        lambda: driver.snapshot()['command_count'] >= command_count_before + 3,
        WAIT_TIMEOUT_SEC,
        'delayed-stop task actuator commands',
    )
    cancel_response = _wait_future(
        goal_handle.cancel_goal_async(),
        WAIT_TIMEOUT_SEC,
        'delayed-stop cancel response',
    )
    if not cancel_response.goals_canceling:
        raise RuntimeError('delayed-stop cancellation was rejected')
    if not driver.wait_for_blocked_stop():
        raise RuntimeError('driver stop did not enter the configured delay')
    first_result = _wait_future(
        goal_handle.get_result_async(),
        WAIT_TIMEOUT_SEC,
        'delayed-stop timed-out client result',
    )
    if first_result.status != GoalStatus.STATUS_CANCELED:
        raise RuntimeError('delayed-stop source task was not canceled')

    blocked_command_count = driver.snapshot()['command_count']
    blocked_goal = _wait_future(
        probe.send_task('stop-pending'),
        WAIT_TIMEOUT_SEC,
        'stop-pending task goal response',
    )
    if not blocked_goal.accepted:
        raise RuntimeError('stop-pending task was rejected before motion mapping')
    blocked_result = _wait_future(
        blocked_goal.get_result_async(),
        WAIT_TIMEOUT_SEC,
        'stop-pending task result',
    )
    if blocked_result.result.reason != 'task_stop_pending':
        raise RuntimeError(
            'delayed stop did not reject the next task with task_stop_pending'
        )
    if driver.snapshot()['command_count'] != blocked_command_count:
        raise RuntimeError('a task command escaped while old stop was pending')

    driver.release_blocked_stop()
    _wait_for(
        lambda: not manager._active_stop_operation_ids,
        WAIT_TIMEOUT_SEC,
        'delayed stop operation completion',
    )
    safety_requests = driver.snapshot()['driver_safety_requests'][
        safety_request_count_before:
    ]
    if not safety_requests or safety_requests[-1] is not False:
        raise RuntimeError('stop token cleared before driver release ACK')
    driver.hold_before_target()
    recovery_count_before = driver.snapshot()['command_count']
    recovery_goal = _wait_future(
        probe.send_task('stop-recovery'),
        WAIT_TIMEOUT_SEC,
        'stop recovery task goal response',
    )
    if not recovery_goal.accepted:
        raise RuntimeError('task admission did not recover after delayed stop')
    _wait_for(
        lambda: driver.snapshot()['command_count'] >= recovery_count_before + 3,
        WAIT_TIMEOUT_SEC,
        'stop recovery actuator commands',
    )
    driver.release_targets()
    recovery_result = _wait_future(
        recovery_goal.get_result_async(),
        WAIT_TIMEOUT_SEC,
        'stop recovery task result',
    )
    if recovery_result.status != GoalStatus.STATUS_SUCCEEDED:
        raise RuntimeError('task did not succeed after delayed stop completed')
    return {
        'source_cancelled': True,
        'new_task_blocked': True,
        'blocked_reason': blocked_result.result.reason,
        'no_command_during_pending_stop': True,
        'recovered_after_stop': True,
        'release_acknowledged': True,
    }


def _run_estop_scenario(probe: ProbeNode, driver: FakeDriverNode) -> dict:
    identity = 'estop'
    driver.hold_before_target()
    driver.defer_next_moves(3)
    snapshot = driver.snapshot()
    command_count_before = snapshot['command_count']
    rejected_count_before = snapshot['move_rejected_count']
    stop_count_before = len(snapshot['stop_commands'])
    probe_command_count_before = probe.servo_command_count()
    goal_handle = _wait_future(
        probe.send_task(identity),
        WAIT_TIMEOUT_SEC,
        'estop task goal response',
    )
    if not goal_handle.accepted:
        raise RuntimeError('estop task goal was rejected')
    _wait_for_active_task(probe, identity)
    task_commands = _wait_for(
        lambda: (
            probe.servo_commands_since(probe_command_count_before)
            if len(probe.servo_commands_since(probe_command_count_before)) >= 3
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'estop task commands published by execution manager',
    )
    target_ids = {int(command.servo_id) for command in task_commands[:3]}
    probe.set_estop(True)
    _wait_for(
        lambda: driver.snapshot()['safety_latched'],
        WAIT_TIMEOUT_SEC,
        'driver safety latch activation',
    )
    if not driver.wait_for_deferred_moves():
        raise RuntimeError('task move callbacks did not enter after estop publish')
    stop_commands = _wait_for(
        lambda: (
            driver.snapshot()['stop_commands'][stop_count_before:]
            if {
                actuator_id
                for actuator_id, unused_protocol, unused_command, accepted
                in driver.snapshot()['stop_commands'][stop_count_before:]
                if accepted
            } == target_ids
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'estop driver stop commands',
    )
    terminal = _wait_for_terminal_task(probe, identity, 'blocked')
    result_response = _wait_future(
        goal_handle.get_result_async(),
        WAIT_TIMEOUT_SEC,
        'estop task result',
    )
    if result_response.status != GoalStatus.STATUS_ABORTED:
        raise RuntimeError('estop task Action did not abort')

    stop_snapshot = driver.snapshot()
    driver.release_deferred_moves()
    if not driver.wait_for_deferred_move_exit():
        raise RuntimeError('deferred task move callbacks did not exit')
    late_snapshot = driver.snapshot()
    late_ids = set(
        late_snapshot['late_move_rejected_ids'][
            len(snapshot['late_move_rejected_ids']):
        ]
    )
    if late_ids != target_ids:
        raise RuntimeError('not every pre-estop move was rejected by the fence')
    if late_snapshot['command_count'] != command_count_before:
        raise RuntimeError('a deferred pre-estop move was applied after stop')
    if (
        late_snapshot['targets'] != stop_snapshot['targets']
        or late_snapshot['positions'] != stop_snapshot['positions']
        or late_snapshot['stopped_ids'] != stop_snapshot['stopped_ids']
    ):
        raise RuntimeError('a deferred move changed driver state after stop')

    active_rejected_before = len(late_snapshot['active_move_rejected_ids'])
    active_test_id = min(target_ids)
    probe.publish_raw_servo_move(active_test_id, 2100)
    active_snapshot = _wait_for(
        lambda: (
            driver.snapshot()
            if len(driver.snapshot()['active_move_rejected_ids'])
            > active_rejected_before
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'active-estop raw move rejection',
    )
    if active_snapshot['command_count'] != command_count_before:
        raise RuntimeError('a new move was applied while driver safety was active')

    probe.set_estop(False)
    _wait_for(
        lambda: (
            probe.latest_execution_state()
            if probe.latest_execution_state() is not None
            and not probe.latest_execution_state().estop_active
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'estop release state',
    )
    if driver.snapshot()['driver_safety_requests'][-1] is not False:
        raise RuntimeError('estop state cleared without driver release ACK')
    recovery_count_before = driver.snapshot()['command_count']
    probe.publish_raw_servo_move(active_test_id, 2050)
    recovery_snapshot = _wait_for(
        lambda: (
            driver.snapshot()
            if driver.snapshot()['command_count'] > recovery_count_before
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'post-release driver move recovery',
    )
    if recovery_snapshot['targets'].get(active_test_id) != 2050:
        raise RuntimeError('post-release move did not reach the fake driver')
    accepted_ids = {
        actuator_id
        for actuator_id, unused_protocol, unused_command, accepted
        in stop_commands
        if accepted
    }
    return {
        'goal_accepted': True,
        'stop_command_count': len(accepted_ids),
        'all_actuators_stopped': accepted_ids == target_ids,
        'lease_cleared': not terminal.lease_id,
        'action_aborted': True,
        'late_move_rejected': late_ids == target_ids,
        'late_move_rejected_count': len(late_ids),
        'active_move_rejected': (
            active_test_id in active_snapshot['active_move_rejected_ids']
        ),
        'target_unchanged_after_stop': True,
        'recovered_after_release': True,
        'release_acknowledged': True,
        'total_move_rejections': (
            recovery_snapshot['move_rejected_count'] - rejected_count_before
        ),
    }


def _run_driver_timeout_fault_scenario(
    probe: ProbeNode,
    driver: FakeDriverNode,
    manager: ExecutionManagerNode,
) -> dict:
    identity = 'driver-timeout'
    driver.hold_before_target()
    driver.block_next_stop()
    initial_snapshot = driver.snapshot()
    command_count_before = initial_snapshot['command_count']
    stop_attempt_count_before = len(initial_snapshot['stop_attempts'])
    stop_command_count_before = len(initial_snapshot['stop_commands'])
    goal_handle = _wait_future(
        probe.send_task(identity),
        WAIT_TIMEOUT_SEC,
        'driver-timeout task goal response',
    )
    if not goal_handle.accepted:
        raise RuntimeError('driver-timeout task goal was rejected')
    _wait_for_active_task(probe, identity)
    _wait_for(
        lambda: driver.snapshot()['command_count'] >= command_count_before + 3,
        WAIT_TIMEOUT_SEC,
        'driver-timeout task actuator commands',
    )
    target_ids = driver.target_ids()
    cancel_response = _wait_future(
        goal_handle.cancel_goal_async(),
        WAIT_TIMEOUT_SEC,
        'driver-timeout cancel response',
    )
    if not cancel_response.goals_canceling:
        raise RuntimeError('driver-timeout cancellation was rejected')
    if not driver.wait_for_blocked_stop():
        raise RuntimeError('driver timeout stop did not block')
    _wait_future(
        goal_handle.get_result_async(),
        WAIT_TIMEOUT_SEC,
        'driver-timeout source task result',
    )
    fault_state = _wait_for(
        lambda: next(
            (
                state
                for state in reversed(probe.task_states)
                if state.task_id == f'task-chain-{identity}'
                and state.status == 'blocked'
                and state.reason == 'driver_stop_timeout'
            ),
            None,
        ),
        WAIT_TIMEOUT_SEC,
        'latched driver stop timeout state',
    )
    if manager._latched_stop_fault_reason != 'driver_stop_timeout':
        raise RuntimeError('driver stop timeout fault was not latched')
    if not manager._active_stop_operation_ids:
        raise RuntimeError('driver stop timeout released the safety token')

    stop_snapshot = driver.snapshot()
    attempted_ids = {
        actuator_id
        for actuator_id, unused_protocol, unused_command
        in stop_snapshot['stop_attempts'][stop_attempt_count_before:]
    }
    blocked_actuator_id = stop_snapshot['blocked_stop_id']
    accepted_stop_ids = {
        actuator_id
        for actuator_id, unused_protocol, unused_command, accepted
        in stop_snapshot['stop_commands'][stop_command_count_before:]
        if accepted
    }
    remaining_ids = target_ids - {blocked_actuator_id}
    if attempted_ids != target_ids:
        raise RuntimeError('stop timeout skipped one or more actuator attempts')
    if not remaining_ids.issubset(accepted_stop_ids):
        raise RuntimeError('remaining actuators were not stopped after one timeout')
    if not stop_snapshot['safety_latched']:
        raise RuntimeError('driver safety latch was released after stop timeout')

    driver.release_blocked_stop()
    blocked_command_count = driver.snapshot()['command_count']
    blocked_goal = _wait_future(
        probe.send_task('fault-latched'),
        WAIT_TIMEOUT_SEC,
        'fault-latched task goal response',
    )
    if not blocked_goal.accepted:
        raise RuntimeError('fault-latched task was rejected before motion mapping')
    blocked_result = _wait_future(
        blocked_goal.get_result_async(),
        WAIT_TIMEOUT_SEC,
        'fault-latched task result',
    )
    if blocked_result.result.reason != 'driver_stop_timeout':
        raise RuntimeError('latched driver timeout reason was not propagated')
    if driver.snapshot()['command_count'] != blocked_command_count:
        raise RuntimeError('command escaped after driver timeout fault')
    probe.set_estop(False)
    time.sleep(0.1)
    state = probe.latest_execution_state()
    if state is None or not state.estop_active:
        raise RuntimeError('latched driver timeout estop was unexpectedly cleared')
    if not driver.snapshot()['safety_latched']:
        raise RuntimeError('raw estop release bypassed the driver safety latch')
    return {
        'fault_reason': fault_state.reason,
        'estop_latched': True,
        'stop_token_retained': True,
        'new_task_blocked': True,
        'no_command_after_fault': True,
        'blocked_actuator_id': blocked_actuator_id,
        'all_stop_ids_attempted': attempted_ids == target_ids,
        'remaining_actuators_stopped': remaining_ids.issubset(
            accepted_stop_ids
        ),
        'remaining_stop_command_count': len(
            remaining_ids.intersection(accepted_stop_ids)
        ),
        'driver_safety_latched': True,
    }


def run_scenario() -> dict:
    """Run the complete task chain in one real ROS graph."""
    started = time.monotonic()
    rclpy.init()
    manager = ExecutionManagerNode()
    controller = Parallel3DOFControllerNode()
    bridge = TaskServiceBridgeNode()
    driver = FakeDriverNode()
    probe = ProbeNode()
    nodes = (manager, controller, bridge, driver, probe)
    executor = MultiThreadedExecutor(num_threads=12)
    for node in nodes:
        executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    try:
        if not probe.task_client.wait_for_server(timeout_sec=WAIT_TIMEOUT_SEC):
            raise RuntimeError('/task/execute Action server unavailable')
        services = (
            manager.driver_read_position_client,
            manager.driver_execute_command_client,
            controller.read_actuator_position_client,
            controller.stop_actuators_client,
        )
        for client in services:
            if not client.wait_for_service(timeout_sec=WAIT_TIMEOUT_SEC):
                raise RuntimeError(
                    f'{client.srv_name} service unavailable for task chain'
                )
        _wait_for(
            lambda: (
                probe.motion_command_pub.get_subscription_count() > 0
                and probe.teleop_control_pub.get_subscription_count() > 0
            ),
            WAIT_TIMEOUT_SEC,
            'execution boundary subscriptions',
        )
        _wait_for(
            controller._task_admission_ready,
            WAIT_TIMEOUT_SEC,
            'motion owner task admission readiness',
        )
        success = _run_success_scenario(probe, driver)
        cancel = _run_cancel_scenario(probe, driver)
        delayed_stop = _run_delayed_stop_scenario(probe, driver, manager)
        estop = _run_estop_scenario(probe, driver)
        driver_timeout = _run_driver_timeout_fault_scenario(
            probe,
            driver,
            manager,
        )
        elapsed = time.monotonic() - started
        if elapsed >= SCENARIO_TIMEOUT_SEC:
            raise RuntimeError(f'task chain smoke exceeded {SCENARIO_TIMEOUT_SEC}s')
        return {
            'success': success,
            'cancel': cancel,
            'delayed_stop': delayed_stop,
            'estop': estop,
            'driver_timeout': driver_timeout,
            'driver': driver.snapshot(),
            'elapsed_sec': elapsed,
        }
    finally:
        executor.shutdown(timeout_sec=2.0)
        spin_thread.join(timeout=2.0)
        for node in reversed(nodes):
            node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    print(json.dumps(run_scenario(), indent=2, sort_keys=True))
