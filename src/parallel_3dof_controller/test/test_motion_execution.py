"""ExecuteMotion 纯逻辑校验、反馈与稳定完成测试。"""

import os
from types import SimpleNamespace
import sys
import threading
import unittest
from pathlib import Path


sys.path.insert(0, os.path.join(
    os.path.dirname(__file__),
    '../parallel_3dof_controller',
))

from motion_execution import ActuatorObservation
from motion_execution import active_task_lease
from motion_execution import is_terminal_task_state
from motion_execution import MotionGoalValidationError
from motion_execution import SingleGoalAdmission
from motion_execution import StablePositionTracker
from motion_execution import evaluate_target_feedback
from motion_execution import normalize_motion_goal
from motion_execution import progress_fraction
from motion_execution import task_start_was_accepted
from motion_execution import task_start_was_rejected
from motion_execution import terminal_task_status


def _goal(**overrides):
    fields = {
        'task_id': 'task-1',
        'trace_id': 'trace-1',
        'session_id': 'session-1',
        'motion_type': 'ankle_pose',
        'target_group': 'right_ankle',
        'roll_deg': 5.0,
        'pitch_deg': -5.0,
        'yaw_deg': 0.0,
        'duration_ms': 100,
        'position_tolerance': 20,
        'execution_timeout_sec': 5.0,
    }
    fields.update(overrides)
    return SimpleNamespace(**fields)


class TestMotionExecution(unittest.TestCase):
    def test_normalizes_supported_goal(self):
        spec = normalize_motion_goal(_goal())
        self.assertEqual('ankle_pose', spec.motion_type)
        self.assertEqual('right_ankle', spec.target_group)

    def test_rejects_invalid_identity_type_pose_and_timing(self):
        cases = (
            ({'task_id': ''}, 'task_id_required'),
            ({'trace_id': ''}, 'trace_id_required'),
            ({'session_id': ''}, 'session_id_required'),
            ({'motion_type': 'walk'}, 'unsupported_motion_type'),
            ({'target_group': 'head'}, 'unsupported_target_group'),
            ({'roll_deg': 30.1}, 'roll_out_of_workspace'),
            ({'duration_ms': 0}, 'duration_ms_required'),
            ({'position_tolerance': 0}, 'position_tolerance_out_of_range'),
            ({'execution_timeout_sec': 0.0}, 'execution_timeout_out_of_range'),
        )
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                with self.assertRaises(MotionGoalValidationError) as context:
                    normalize_motion_goal(_goal(**overrides))
                self.assertEqual(reason, context.exception.reason)

    def test_stale_feedback_does_not_complete_target(self):
        targets = {9: 1500, 10: 1600}
        observations = {
            9: ActuatorObservation(1500, 'ok', '', False, 0.9),
            10: ActuatorObservation(1600, 'ok', '', False, 0.9),
        }
        reached, error = evaluate_target_feedback(
            targets,
            observations,
            issued_monotonic=1.0,
            tolerance=10,
        )
        self.assertEqual(0, reached)
        self.assertIsNone(error)

    def test_driver_error_is_propagated(self):
        targets = {9: 1500}
        observation = ActuatorObservation(
            1400,
            'error',
            'overheat',
            True,
            1.1,
        )
        reached, error = evaluate_target_feedback(
            targets,
            {9: observation},
            issued_monotonic=1.0,
            tolerance=10,
        )
        self.assertEqual(0, reached)
        self.assertIs(observation, error)

    def test_completion_requires_consecutive_stable_samples(self):
        tracker = StablePositionTracker(required_samples=3)
        self.assertFalse(tracker.update(3, 3))
        self.assertFalse(tracker.update(3, 3))
        self.assertTrue(tracker.update(3, 3))
        self.assertFalse(tracker.update(2, 3))
        self.assertFalse(tracker.update(3, 3))

    def test_progress_fraction_is_bounded(self):
        self.assertEqual(0.0, progress_fraction(1, 0))
        self.assertEqual(0.5, progress_fraction(1, 2))
        self.assertEqual(1.0, progress_fraction(3, 2))

    def test_stop_confirmation_uses_dedicated_tolerance(self):
        source = (
            Path(__file__).resolve().parents[1]
            / 'parallel_3dof_controller'
            / 'controller_node.py'
        ).read_text(encoding='utf-8')

        self.assertIn("self.declare_parameter('stop_position_tolerance', 1)", source)
        self.assertIn('<= self.stop_position_tolerance', source)
        self.assertNotIn('<= spec.position_tolerance\n', source)

    def test_task_state_requires_full_identity_and_terminal_release(self):
        spec = normalize_motion_goal(_goal())
        active = SimpleNamespace(
            active=True,
            task_id=spec.task_id,
            trace_id=spec.trace_id,
            session_id=spec.session_id,
            lease_id='lease-1',
            status='active',
            last_action='',
            last_task_id='',
            last_action_accepted=True,
        )
        self.assertEqual('lease-1', active_task_lease(active, spec))
        self.assertFalse(is_terminal_task_state(active, spec))

        active.trace_id = 'wrong-trace'
        self.assertEqual('', active_task_lease(active, spec))
        active.trace_id = spec.trace_id
        active.active = False
        active.lease_id = ''
        active.status = 'finished'
        self.assertTrue(is_terminal_task_state(active, spec))
        self.assertEqual('finished', terminal_task_status(active, spec))
        active.lease_id = 'stale-lease'
        self.assertFalse(is_terminal_task_state(active, spec))
        self.assertEqual('', terminal_task_status(active, spec))
        active.lease_id = ''
        active.session_id = 'other-session'
        self.assertFalse(is_terminal_task_state(active, spec))

    def test_task_start_rejection_matches_requested_identity(self):
        spec = normalize_motion_goal(_goal())
        state = SimpleNamespace(
            active=False,
            last_action='start',
            last_task_id=spec.task_id,
            last_trace_id=spec.trace_id,
            last_session_id=spec.session_id,
            last_action_accepted=False,
        )
        self.assertTrue(task_start_was_rejected(state, spec))
        state.active = True
        self.assertTrue(task_start_was_rejected(state, spec))
        state.active = False
        state.last_trace_id = 'old-trace'
        self.assertFalse(task_start_was_rejected(state, spec))
        state.last_trace_id = spec.trace_id
        state.last_session_id = 'old-session'
        self.assertFalse(task_start_was_rejected(state, spec))
        state.last_session_id = spec.session_id
        state.last_task_id = 'other-task'
        self.assertFalse(task_start_was_rejected(state, spec))

    def test_task_lease_requires_explicit_start_acceptance(self):
        spec = normalize_motion_goal(_goal())
        state = SimpleNamespace(
            active=True,
            task_id=spec.task_id,
            trace_id=spec.trace_id,
            session_id=spec.session_id,
            lease_id='lease-1',
            last_action='start',
            last_task_id=spec.task_id,
            last_trace_id=spec.trace_id,
            last_session_id=spec.session_id,
            last_action_accepted=True,
        )
        self.assertTrue(task_start_was_accepted(state, spec))
        state.last_session_id = 'old-session'
        self.assertFalse(task_start_was_accepted(state, spec))
        state.last_session_id = spec.session_id
        state.last_action_accepted = False
        self.assertFalse(task_start_was_accepted(state, spec))

    def test_single_motion_goal_admission_is_thread_safe(self):
        admission = SingleGoalAdmission()
        start = threading.Barrier(9)
        results = []
        results_lock = threading.Lock()

        def compete():
            start.wait()
            acquired = admission.try_acquire()
            with results_lock:
                results.append(acquired)

        threads = [threading.Thread(target=compete) for _ in range(8)]
        for thread in threads:
            thread.start()
        start.wait()
        for thread in threads:
            thread.join(timeout=1.0)

        self.assertEqual(1, results.count(True))
        self.assertEqual(7, results.count(False))
        admission.release()
        self.assertTrue(admission.try_acquire())

    def test_action_source_uses_ros_futures_and_terminal_confirmation(self):
        source = (
            Path(__file__).resolve().parents[1]
            / 'parallel_3dof_controller'
            / 'controller_node.py'
        ).read_text(encoding='utf-8')

        self.assertNotIn('asyncio', source)
        self.assertIn('from rclpy.task import Future', source)
        self.assertIn('def _wait_for_task_terminal', source)
        self.assertIn("'task_admission_release_unconfirmed'", source)
        self.assertIn('self._goal_admission.try_acquire()', source)
        self.assertIn('self._goal_admission.release()', source)
        self.assertIn('executor.shutdown()', source)
        self.assertIn('node.destroy_node()', source)

    def test_action_rejects_goal_until_task_admission_is_ready(self):
        source = (
            Path(__file__).resolve().parents[1]
            / 'parallel_3dof_controller'
            / 'controller_node.py'
        ).read_text(encoding='utf-8')

        callback_start = source.index('def _motion_goal_callback')
        acquire_index = source.index(
            'self._goal_admission.try_acquire()',
            callback_start,
        )
        readiness_index = source.index(
            'if not self._task_admission_ready():',
            callback_start,
        )

        self.assertLess(readiness_index, acquire_index)
        self.assertIn('self._task_state_sequence > 0', source)
        self.assertIn(
            'self.task_control_pub.get_subscription_count() > 0',
            source,
        )

    def test_multi_instances_cannot_own_formal_motion_action(self):
        package_root = Path(__file__).resolve().parents[1]
        node_source = (
            package_root
            / 'parallel_3dof_controller'
            / 'controller_node.py'
        ).read_text(encoding='utf-8')
        multi_launch = (
            package_root / 'launch' / 'parallel_3dof_multi.launch.py'
        ).read_text(encoding='utf-8')

        self.assertIn(
            "self.declare_parameter('enable_motion_action_server', True)",
            node_source,
        )
        self.assertIn('if enable_motion_action_server:', node_source)
        self.assertIn(
            "params['enable_motion_action_server'] = False",
            multi_launch,
        )


if __name__ == '__main__':
    unittest.main()
