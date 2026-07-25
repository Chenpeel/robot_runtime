"""ROS 2 task admission pub/sub smoke scenario."""

import json
import threading
import time

from motion_msgs.msg import ExecutionState
from motion_msgs.msg import MotionCommand
from motion_msgs.msg import TaskExecutionControl
from motion_msgs.msg import TaskExecutionState
from motion_msgs.msg import TeleopControl
import rclpy
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from servo_msgs.msg import ServoCommand
from servo_msgs.srv import ExecuteBusCommand, ReadServoPosition, SetDriverSafety
from std_msgs.msg import Bool

from execution_manager.execution_manager_node import ExecutionManagerNode


class _Probe(Node):
    def __init__(self) -> None:
        super().__init__('task_admission_smoke_probe')
        self.task_states = []
        self.execution_states = []
        self.servo_commands = []

        self.task_control_pub = self.create_publisher(
            TaskExecutionControl,
            '/execution/task/control',
            10,
        )
        self.task_command_pub = self.create_publisher(
            MotionCommand,
            '/execution/task/command',
            10,
        )
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
        self.estop_pub = self.create_publisher(
            Bool,
            '/execution/estop',
            10,
        )
        self.create_subscription(
            TaskExecutionState,
            '/execution/task/state',
            self.task_states.append,
            10,
        )
        self.create_subscription(
            ExecutionState,
            '/execution/state',
            self.execution_states.append,
            10,
        )
        self.create_subscription(
            ServoCommand,
            '/servo/command',
            self.servo_commands.append,
            10,
        )
        self.create_service(
            ReadServoPosition,
            '/servo/read_position',
            self._read_servo_position,
        )
        self.create_service(
            ExecuteBusCommand,
            '/servo/execute_command',
            self._execute_bus_command,
        )
        self.create_service(
            SetDriverSafety,
            '/servo/set_driver_safety',
            self._set_driver_safety,
        )

    def _read_servo_position(self, request, response):
        response.success = True
        response.position = 1600
        response.protocol = 'lx' if int(request.servo_id) % 2 else 'zl'
        response.error_code = 0
        response.message = ''
        response.stamp = self.get_clock().now().to_msg()
        return response

    def _execute_bus_command(self, request, response):
        response.success = True
        response.protocol = str(request.protocol)
        response.error_code = 0
        response.message = ''
        response.value = 0
        response.values = []
        response.raw_hex = ''
        response.result_json = ''
        response.stamp = self.get_clock().now().to_msg()
        return response

    def _set_driver_safety(self, request, response):
        response.success = True
        response.reason = ''
        response.stamp = self.get_clock().now().to_msg()
        return response


def _wait_for(predicate, timeout_sec: float, description: str):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.01)
    raise RuntimeError(f'timeout waiting for {description}')


def _task_control(
    action: str,
    lease_id: str = '',
    identity: str = '1',
) -> TaskExecutionControl:
    msg = TaskExecutionControl()
    msg.action = action
    msg.task_id = f'task-ros-{identity}'
    msg.trace_id = f'trace-ros-{identity}'
    msg.session_id = f'session-ros-{identity}'
    msg.lease_id = lease_id
    return msg


def _motion_command(requester_id: str = '', lease_id: str = '') -> MotionCommand:
    msg = MotionCommand()
    msg.servo_type = 'bus'
    msg.servo_id = 7
    msg.position = 1600
    msg.value_encoding = 'bus_pulse_us'
    msg.duration_ms = 45
    msg.requester_id = requester_id
    msg.lease_id = lease_id
    return msg


def run_scenario() -> dict:
    """运行可由 pytest/colcon 自动调用的真实 ROS pub/sub 场景。"""
    rclpy.init()
    manager = ExecutionManagerNode()
    probe = _Probe()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(manager)
    executor.add_node(probe)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    try:
        publishers = (
            probe.task_control_pub,
            probe.task_command_pub,
            probe.motion_command_pub,
            probe.teleop_control_pub,
            probe.estop_pub,
        )
        _wait_for(
            lambda: all(pub.get_subscription_count() > 0 for pub in publishers),
            3.0,
            'execution_manager subscriptions',
        )

        probe.task_control_pub.publish(_task_control('start'))
        active_state = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if state.active and state.task_id == 'task-ros-1'
                ),
                None,
            ),
            3.0,
            'active task lease',
        )
        lease_id = active_state.lease_id
        if not lease_id:
            raise RuntimeError('execution_manager returned an empty task lease')

        rejected_command_count = active_state.command_rejected_count
        probe.task_command_pub.publish(
            _motion_command('task-ros-1', 'wrong-task-lease')
        )
        lease_rejection = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if state.command_rejected_count > rejected_command_count
                    and not state.last_command_accepted
                    and state.last_command_reason == 'task_lease_mismatch'
                ),
                None,
            ),
            3.0,
            'task command lease rejection state',
        )

        motion_rejected_before = max(
            (
                state.motion_rejected_count
                for state in probe.execution_states
            ),
            default=0,
        )
        execution_count_before_motion = len(probe.execution_states)
        servo_count = len(probe.servo_commands)
        probe.motion_command_pub.publish(_motion_command())
        _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(
                        probe.execution_states[execution_count_before_motion:]
                    )
                    if state.motion_rejected_count > motion_rejected_before
                    and state.last_rejection_reason == 'task_active'
                ),
                None,
            ),
            3.0,
            'ordinary motion task_active rejection',
        )
        if len(probe.servo_commands) != servo_count:
            raise RuntimeError('ordinary motion escaped the active task boundary')

        teleop_control_rejected_before = max(
            (
                state.teleop_control_rejected_count
                for state in probe.execution_states
            ),
            default=0,
        )
        execution_count_before_teleop = len(probe.execution_states)
        teleop = TeleopControl()
        teleop.action = 'claim'
        teleop.requester_id = 'operator-ros-1'
        probe.teleop_control_pub.publish(teleop)
        teleop_rejection = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(
                        probe.execution_states[execution_count_before_teleop:]
                    )
                    if state.teleop_control_rejected_count
                    > teleop_control_rejected_before
                    and state.last_teleop_control_action == 'claim'
                    and not state.last_teleop_control_accepted
                    and state.last_teleop_control_reason == 'task_active'
                ),
                None,
            ),
            3.0,
            'teleop task_active rejection',
        )

        probe.task_command_pub.publish(
            _motion_command('task-ros-1', lease_id)
        )
        task_servo = _wait_for(
            lambda: (
                probe.servo_commands[-1]
                if len(probe.servo_commands) > servo_count
                else None
            ),
            3.0,
            'task command driver output',
        )

        probe.task_control_pub.publish(_task_control('finish', lease_id))
        finished_state = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if not state.active
                    and state.last_action == 'finish'
                    and state.status == 'finished'
                ),
                None,
            ),
            3.0,
            'finished task state',
        )
        if (
            finished_state.task_id != 'task-ros-1'
            or finished_state.trace_id != 'trace-ros-1'
            or finished_state.session_id != 'session-ros-1'
            or finished_state.lease_id
        ):
            raise RuntimeError('finished task state lost terminal identity')

        post_finish_count = len(probe.servo_commands)
        probe.motion_command_pub.publish(_motion_command())
        _wait_for(
            lambda: len(probe.servo_commands) > post_finish_count,
            3.0,
            'ordinary motion after task finish',
        )

        probe.task_control_pub.publish(_task_control('start', identity='2'))
        cancel_active = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if state.active and state.task_id == 'task-ros-2'
                ),
                None,
            ),
            3.0,
            'second active task lease',
        )
        probe.task_control_pub.publish(
            _task_control('cancel', cancel_active.lease_id, identity='2')
        )
        cancelled_state = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if not state.active
                    and state.task_id == 'task-ros-2'
                    and state.status == 'cancelled'
                ),
                None,
            ),
            3.0,
            'cancelled task terminal state',
        )

        probe.task_control_pub.publish(_task_control('start', identity='3'))
        _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if state.active and state.task_id == 'task-ros-3'
                ),
                None,
            ),
            3.0,
            'third active task lease',
        )
        expired_state = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if not state.active
                    and state.task_id == 'task-ros-3'
                    and state.status == 'expired'
                    and state.reason == 'task_lease_expired'
                ),
                None,
            ),
            7.0,
            'expired task terminal state',
        )

        probe.task_control_pub.publish(_task_control('start', identity='4'))
        _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if state.active and state.task_id == 'task-ros-4'
                ),
                None,
            ),
            3.0,
            'fourth active task lease',
        )
        estop = Bool()
        estop.data = True
        probe.estop_pub.publish(estop)
        blocked_state = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if not state.active
                    and state.task_id == 'task-ros-4'
                    and state.status == 'blocked'
                    and state.reason == 'estop'
                ),
                None,
            ),
            3.0,
            'estop task terminal state',
        )
        execution_count_before_release = len(probe.execution_states)
        task_count_before_release = len(probe.task_states)
        estop.data = False
        probe.estop_pub.publish(estop)
        _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(
                        probe.execution_states[execution_count_before_release:]
                    )
                    if not state.estop_active and state.mode == 'idle'
                ),
                None,
            ),
            3.0,
            'released estop execution state',
        )
        released_blocked_state = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(
                        probe.task_states[task_count_before_release:]
                    )
                    if not state.active
                    and state.task_id == 'task-ros-4'
                    and state.status == 'blocked'
                    and state.reason == 'estop'
                ),
                None,
            ),
            3.0,
            'persistent estop task terminal state',
        )

        probe.task_control_pub.publish(_task_control('start', identity='4'))
        replay_state = _wait_for(
            lambda: next(
                (
                    state
                    for state in reversed(probe.task_states)
                    if not state.last_action_accepted
                    and state.last_action == 'start'
                    and state.reason == 'task_control_replay'
                ),
                None,
            ),
            3.0,
            'replayed task start rejection',
        )

        result = {
            'task_mode': 'task_active',
            'task_lease_nonempty': bool(lease_id),
            'ordinary_motion_blocked': True,
            'teleop_rejection': teleop_rejection.last_teleop_control_reason,
            'task_command_rejection': lease_rejection.last_command_reason,
            'task_servo_id': int(task_servo.servo_id),
            'task_servo_position': int(task_servo.position),
            'task_servo_speed': int(task_servo.speed),
            'finish_status': finished_state.status,
            'cancel_status': cancelled_state.status,
            'timeout_status': expired_state.status,
            'estop_status': blocked_state.status,
            'estop_status_after_release': released_blocked_state.status,
            'replay_rejection': replay_state.reason,
            'ordinary_motion_restored': True,
        }
        print(json.dumps(result, sort_keys=True))
        return result
    finally:
        executor.shutdown()
        manager.destroy_node()
        probe.destroy_node()
        rclpy.shutdown()
        spin_thread.join(timeout=1.0)


def main() -> None:
    """命令行入口。"""
    run_scenario()


if __name__ == '__main__':
    main()
