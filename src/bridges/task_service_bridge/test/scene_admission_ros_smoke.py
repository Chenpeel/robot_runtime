"""Scene context admission through the real task and motion ROS 2 chain."""

import json
import threading
import time

from action_msgs.msg import GoalStatus
from execution_manager.execution_manager_node import ExecutionManagerNode
from motion_msgs.msg import MotionCommand, TaskExecutionControl
from parallel_3dof_controller.controller_node import Parallel3DOFControllerNode
from perception_msgs.msg import DetectedObject, SceneState
import rclpy
from rclpy.action import ActionClient
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from rclpy.parameter import Parameter
from servo_msgs.msg import ServoCommand
from task_api_msgs.action import ExecuteTask
from task_chain_ros_smoke import FakeDriverNode
from task_service_bridge.bridge_node import TaskServiceBridgeNode


SCENE_MAX_AGE_SEC = 0.25
WAIT_TIMEOUT_SEC = 6.0
SCENARIO_TIMEOUT_SEC = 55.0
QUIET_PERIOD_SEC = 0.15
LEASE_START_DELAY_SEC = 0.35


def _wait_for(predicate, timeout_sec: float, description: str):
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(0.01)
    raise RuntimeError('timeout waiting for ' + description)


def _wait_future(future, timeout_sec: float, description: str):
    _wait_for(lambda: future.done(), timeout_sec, description)
    exception = future.exception()
    if exception is not None:
        raise exception
    return future.result()


class SceneAdmissionProbe(Node):
    """Publish scenes and observe every execution boundary after task admission."""

    def __init__(self) -> None:
        super().__init__('scene_admission_smoke_probe')
        self._lock = threading.Lock()
        self.task_controls = []
        self.task_motion_commands = []
        self.servo_commands = []

        self.task_client = ActionClient(self, ExecuteTask, '/task/execute')
        self.scene_publisher = self.create_publisher(
            SceneState,
            '/perception/scene_state',
            20,
        )
        self.create_subscription(
            TaskExecutionControl,
            '/execution/task/control',
            self._on_task_control,
            20,
        )
        self.create_subscription(
            MotionCommand,
            '/execution/task/command',
            self._on_task_motion_command,
            50,
        )
        self.create_subscription(
            ServoCommand,
            '/servo/command',
            self._on_servo_command,
            50,
        )

    @staticmethod
    def session_id(identity: str) -> str:
        return 'session-scene-' + identity

    def send_task(self, identity: str):
        goal = ExecuteTask.Goal()
        goal.task_id = 'task-scene-' + identity
        goal.trace_id = 'trace-scene-' + identity
        goal.session_id = self.session_id(identity)
        goal.task_type = 'ankle_pose'
        goal.target_group = 'right_ankle'
        goal.roll_deg = 4.0
        goal.pitch_deg = -2.0
        goal.yaw_deg = 1.0
        goal.duration_ms = 150
        goal.position_tolerance = 10
        goal.execution_timeout_sec = 5.0
        return self.task_client.send_goal_async(goal)

    def publish_scene(
            self,
            identity: str,
            *,
            session_id: str,
            status: str = 'ok',
            reason: str = '',
            observation_id=None,
            frame_id: str = 'camera_link',
            object_label: str = 'right_ankle',
            object_confidence: float = 0.95,
            object_x: float = 0.2,
            object_size_x: float = 0.2,
    ) -> str:
        if observation_id is None:
            observation_id = 'observation-scene-' + identity
        message = SceneState()
        message.stamp = self.get_clock().now().to_msg()
        message.observation_id = observation_id
        message.session_id = session_id
        message.frame_id = frame_id
        target = DetectedObject()
        target.object_id = 'target-scene-' + identity
        target.label = object_label
        target.confidence = object_confidence
        target.x = object_x
        target.y = -0.1
        target.z = 0.8
        target.size_x = object_size_x
        target.size_y = 0.2
        target.size_z = 0.3
        message.objects = [target]
        message.status = status
        message.reason = reason
        message.recoverable = status != 'ok'
        self.scene_publisher.publish(message)
        return observation_id

    def counts(self) -> dict:
        with self._lock:
            return {
                'task_controls': len(self.task_controls),
                'task_motion_commands': len(self.task_motion_commands),
                'servo_commands': len(self.servo_commands),
            }

    def task_controls_since(self, start_index: int):
        with self._lock:
            return list(self.task_controls[start_index:])

    def _on_task_control(self, message: TaskExecutionControl) -> None:
        with self._lock:
            self.task_controls.append(message)

    def _on_task_motion_command(self, message: MotionCommand) -> None:
        with self._lock:
            self.task_motion_commands.append(message)

    def _on_servo_command(self, message: ServoCommand) -> None:
        with self._lock:
            self.servo_commands.append(message)


class DelayedStartExecutionManagerNode(ExecutionManagerNode):
    """仅为 smoke 在 start 到 lease 之间提供可控场景失效窗口。"""

    def __init__(self) -> None:
        super().__init__()
        self._delay_lock = threading.Lock()
        self._delay_next_start = False
        self.start_delay_entered = threading.Event()

    def delay_next_start(self) -> None:
        with self._delay_lock:
            self._delay_next_start = True
            self.start_delay_entered.clear()

    def _handle_task_control(self, message: TaskExecutionControl) -> None:
        should_delay = False
        with self._delay_lock:
            if (
                    self._delay_next_start
                    and str(message.action).strip().lower() == 'start'):
                self._delay_next_start = False
                should_delay = True
        if should_delay:
            self.start_delay_entered.set()
            time.sleep(LEASE_START_DELAY_SEC)
        super()._handle_task_control(message)


def _assert_result_identity(result, identity: str) -> None:
    expected = (
        'task-scene-' + identity,
        'trace-scene-' + identity,
        'session-scene-' + identity,
    )
    actual = (result.task_id, result.trace_id, result.session_id)
    if actual != expected:
        raise RuntimeError(
            'scene admission result identity mismatch: %r != %r'
            % (actual, expected)
        )


def _run_rejection(
        probe: SceneAdmissionProbe,
        identity: str,
        expected_reason: str,
) -> dict:
    before = probe.counts()
    goal_handle = _wait_future(
        probe.send_task(identity),
        WAIT_TIMEOUT_SEC,
        identity + ' task goal response',
    )
    if not goal_handle.accepted:
        raise RuntimeError(identity + ' task was rejected before motion result')

    response = _wait_future(
        goal_handle.get_result_async(),
        WAIT_TIMEOUT_SEC,
        identity + ' task result',
    )
    result = response.result
    _assert_result_identity(result, identity)
    if response.status != GoalStatus.STATUS_ABORTED:
        raise RuntimeError(identity + ' task Action did not abort')
    if (
            result.success
            or result.status != 'rejected'
            or result.reason != expected_reason
            or not result.recoverable):
        raise RuntimeError(
            '%s returned inconsistent rejection: status=%r reason=%r '
            'success=%r recoverable=%r'
            % (
                identity,
                result.status,
                result.reason,
                result.success,
                result.recoverable,
            )
        )

    # The result must not race ahead of a late control or actuator command.
    time.sleep(QUIET_PERIOD_SEC)
    after = probe.counts()
    if after != before:
        raise RuntimeError(
            '%s escaped scene admission: before=%r after=%r'
            % (identity, before, after)
        )
    return {
        'reason': result.reason,
        'identity_preserved': True,
        'no_task_control': True,
        'no_task_motion_command': True,
        'no_servo_command': True,
    }


def _publish_and_wait_for_scene(
        probe: SceneAdmissionProbe,
        controller: Parallel3DOFControllerNode,
        identity: str,
        *,
        session_id: str,
        status: str = 'ok',
        reason: str = '',
        observation_id=None,
        frame_id: str = 'camera_link',
        object_label: str = 'right_ankle',
        object_confidence: float = 0.95,
        object_x: float = 0.2,
        object_size_x: float = 0.2,
) -> None:
    observation_id = probe.publish_scene(
        identity,
        session_id=session_id,
        status=status,
        reason=reason,
        observation_id=observation_id,
        frame_id=frame_id,
        object_label=object_label,
        object_confidence=object_confidence,
        object_x=object_x,
        object_size_x=object_size_x,
    )
    _wait_for(
        lambda: (
            controller.scene_admission.snapshot()
            if controller.scene_admission.snapshot() is not None
            and controller.scene_admission.snapshot().observation_id
            == observation_id
            else None
        ),
        WAIT_TIMEOUT_SEC,
        identity + ' scene at motion owner',
    )


def _run_success(
        probe: SceneAdmissionProbe,
        controller: Parallel3DOFControllerNode,
        driver: FakeDriverNode,
) -> dict:
    identity = 'fresh'
    driver.hold_before_target()
    _publish_and_wait_for_scene(
        probe,
        controller,
        identity,
        session_id=probe.session_id(identity),
    )
    before = probe.counts()
    driver_before = driver.snapshot()['command_count']

    goal_handle = _wait_future(
        probe.send_task(identity),
        WAIT_TIMEOUT_SEC,
        'fresh scene task goal response',
    )
    if not goal_handle.accepted:
        raise RuntimeError('fresh scene task goal was rejected')
    result_future = goal_handle.get_result_async()
    _wait_for(
        lambda: (
            probe.counts()
            if probe.counts()['task_controls'] >= before['task_controls'] + 1
            and probe.counts()['task_motion_commands']
            >= before['task_motion_commands'] + 3
            and probe.counts()['servo_commands'] >= before['servo_commands'] + 3
            and driver.snapshot()['command_count'] >= driver_before + 3
            else None
        ),
        WAIT_TIMEOUT_SEC,
        'fresh scene commands through execution manager',
    )
    if result_future.done():
        raise RuntimeError('fresh scene task completed before target release')

    driver.release_targets()
    response = _wait_future(
        result_future,
        WAIT_TIMEOUT_SEC,
        'fresh scene successful result',
    )
    result = response.result
    _assert_result_identity(result, identity)
    if response.status != GoalStatus.STATUS_SUCCEEDED:
        raise RuntimeError('fresh scene task Action did not succeed')
    if not (
            result.success
            and result.status == 'succeeded'
            and result.target_reached
            and result.admission_released):
        raise RuntimeError('fresh scene task returned incomplete success fields')
    return {
        'status': result.status,
        'identity_preserved': True,
        'target_reached': result.target_reached,
        'admission_released': result.admission_released,
        'task_control_observed': True,
        'task_motion_command_count': (
            probe.counts()['task_motion_commands']
            - before['task_motion_commands']
        ),
        'servo_command_count': (
            probe.counts()['servo_commands'] - before['servo_commands']
        ),
    }


def _run_lease_wait_recheck(
        probe: SceneAdmissionProbe,
        controller: Parallel3DOFControllerNode,
        manager: DelayedStartExecutionManagerNode,
) -> dict:
    """场景在 lease 等待中失效时，取消已获准入且不发送命令。"""
    identity = 'lease-race'
    _publish_and_wait_for_scene(
        probe,
        controller,
        'lease-race-ready',
        session_id=probe.session_id(identity),
    )
    before = probe.counts()
    manager.delay_next_start()
    goal_handle = _wait_future(
        probe.send_task(identity),
        WAIT_TIMEOUT_SEC,
        'lease race task goal response',
    )
    if not goal_handle.accepted:
        raise RuntimeError('lease race task goal was unexpectedly rejected')
    _wait_for(
        manager.start_delay_entered.is_set,
        WAIT_TIMEOUT_SEC,
        'delayed task start at execution manager',
    )
    _publish_and_wait_for_scene(
        probe,
        controller,
        'lease-race-rejected',
        session_id=probe.session_id(identity),
        status='rejected',
        reason='detector_unavailable',
    )
    response = _wait_future(
        goal_handle.get_result_async(),
        WAIT_TIMEOUT_SEC,
        'lease race task result',
    )
    result = response.result
    _assert_result_identity(result, identity)
    if response.status != GoalStatus.STATUS_ABORTED:
        raise RuntimeError('lease race task Action did not abort')
    if not (
            not result.success
            and result.status == 'rejected'
            and result.reason == 'scene_context_rejected'
            and result.recoverable
            and result.admission_released):
        raise RuntimeError('lease race result did not release rejected admission')
    time.sleep(QUIET_PERIOD_SEC)
    after = probe.counts()
    if (
            after['task_motion_commands'] != before['task_motion_commands']
            or after['servo_commands'] != before['servo_commands']):
        raise RuntimeError('lease race emitted motion or servo commands')
    controls = probe.task_controls_since(before['task_controls'])
    if [control.action for control in controls] != ['start', 'cancel']:
        raise RuntimeError('lease race did not emit ordered start/cancel controls')
    expected_identity = (
        'task-scene-' + identity,
        'trace-scene-' + identity,
        'session-scene-' + identity,
    )
    if any(
            (control.task_id, control.trace_id, control.session_id)
            != expected_identity
            for control in controls):
        raise RuntimeError('lease race control identity was not preserved')
    if controls[0].lease_id or not controls[1].lease_id:
        raise RuntimeError('lease race cancel did not preserve the granted lease')
    return {
        'reason': result.reason,
        'identity_preserved': True,
        'admission_released': result.admission_released,
        'lease_cancelled': True,
        'ordered_start_cancel': True,
        'cancel_lease_id_present': True,
        'no_task_motion_command': True,
        'no_servo_command': True,
    }


def run_scenario() -> dict:
    """Exercise rejected and accepted scene decisions in one real ROS graph."""
    started = time.monotonic()
    rclpy.init()
    manager = DelayedStartExecutionManagerNode()
    controller = Parallel3DOFControllerNode(parameter_overrides=[
        Parameter('require_scene_context', value=True),
        Parameter('scene_max_age_sec', value=SCENE_MAX_AGE_SEC),
    ])
    bridge = TaskServiceBridgeNode()
    driver = FakeDriverNode()
    probe = SceneAdmissionProbe()
    nodes = (manager, controller, bridge, driver, probe)
    executor = MultiThreadedExecutor(num_threads=12)
    for node in nodes:
        executor.add_node(node)
    spin_thread = threading.Thread(target=executor.spin, daemon=True)
    spin_thread.start()

    try:
        if not probe.task_client.wait_for_server(timeout_sec=WAIT_TIMEOUT_SEC):
            raise RuntimeError('/task/execute Action server unavailable')
        for client in (
                manager.driver_read_position_client,
                manager.driver_execute_command_client,
                controller.read_actuator_position_client,
                controller.stop_actuators_client):
            if not client.wait_for_service(timeout_sec=WAIT_TIMEOUT_SEC):
                raise RuntimeError(
                    client.srv_name + ' unavailable for scene admission smoke'
                )
        _wait_for(
            controller._task_admission_ready,
            WAIT_TIMEOUT_SEC,
            'motion owner task admission readiness',
        )
        _wait_for(
            lambda: probe.scene_publisher.get_subscription_count() >= 2,
            WAIT_TIMEOUT_SEC,
            'scene consumers',
        )

        missing = _run_rejection(
            probe,
            'missing',
            'scene_context_unavailable',
        )

        _publish_and_wait_for_scene(
            probe,
            controller,
            'rejected',
            session_id=probe.session_id('rejected'),
            status='rejected',
            reason='detector_unavailable',
        )
        rejected = _run_rejection(
            probe,
            'rejected',
            'scene_context_rejected',
        )

        _publish_and_wait_for_scene(
            probe,
            controller,
            'observation-required',
            session_id=probe.session_id('observation-required'),
            observation_id='',
        )
        observation_required = _run_rejection(
            probe,
            'observation-required',
            'scene_context_observation_required',
        )

        _publish_and_wait_for_scene(
            probe,
            controller,
            'mismatch',
            session_id='session-scene-someone-else',
        )
        mismatch = _run_rejection(
            probe,
            'mismatch',
            'scene_context_session_mismatch',
        )

        _publish_and_wait_for_scene(
            probe,
            controller,
            'frame-mismatch',
            session_id=probe.session_id('frame-mismatch'),
            frame_id='map',
        )
        frame_mismatch = _run_rejection(
            probe,
            'frame-mismatch',
            'scene_context_frame_mismatch',
        )

        _publish_and_wait_for_scene(
            probe,
            controller,
            'target-missing',
            session_id=probe.session_id('target-missing'),
            object_label='person',
        )
        target_missing = _run_rejection(
            probe,
            'target-missing',
            'scene_context_target_missing',
        )

        _publish_and_wait_for_scene(
            probe,
            controller,
            'confidence-low',
            session_id=probe.session_id('confidence-low'),
            object_confidence=0.59,
        )
        confidence_low = _run_rejection(
            probe,
            'confidence-low',
            'scene_context_target_confidence_low',
        )

        _publish_and_wait_for_scene(
            probe,
            controller,
            'target-out-of-bounds',
            session_id=probe.session_id('target-out-of-bounds'),
            object_x=1.91,
        )
        target_out_of_bounds = _run_rejection(
            probe,
            'target-out-of-bounds',
            'scene_context_target_out_of_bounds',
        )

        _publish_and_wait_for_scene(
            probe,
            controller,
            'stale',
            session_id=probe.session_id('stale'),
        )
        stale_snapshot = controller.scene_admission.snapshot()
        _wait_for(
            lambda: (
                time.monotonic() - stale_snapshot.received_monotonic
                > SCENE_MAX_AGE_SEC + 0.05
            ),
            WAIT_TIMEOUT_SEC,
            'scene context to become stale',
        )
        stale = _run_rejection(
            probe,
            'stale',
            'scene_context_stale',
        )

        lease_wait_recheck = _run_lease_wait_recheck(
            probe,
            controller,
            manager,
        )

        fresh = _run_success(probe, controller, driver)
        elapsed = time.monotonic() - started
        if elapsed >= SCENARIO_TIMEOUT_SEC:
            raise RuntimeError(
                'scene admission smoke exceeded %.1fs' % SCENARIO_TIMEOUT_SEC
            )
        return {
            'missing': missing,
            'rejected': rejected,
            'observation_required': observation_required,
            'session_mismatch': mismatch,
            'frame_mismatch': frame_mismatch,
            'target_missing': target_missing,
            'confidence_low': confidence_low,
            'target_out_of_bounds': target_out_of_bounds,
            'stale': stale,
            'lease_wait_recheck': lease_wait_recheck,
            'fresh': fresh,
            'scene_max_age_sec': SCENE_MAX_AGE_SEC,
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
