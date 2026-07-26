"""任务桥纯逻辑合同测试。"""

from concurrent.futures import ThreadPoolExecutor
from math import inf, nan
from types import SimpleNamespace
import unittest

from task_service_bridge.task_contract import (
    FEEDBACK_FIELDS,
    RESULT_FIELDS,
    SingleGoalAdmission,
    map_motion_feedback,
    map_motion_result,
    map_task_goal,
    rejected_result,
    validate_task_goal,
)


def valid_goal(**overrides):
    values = {
        'task_id': 'task-1',
        'trace_id': 'trace-1',
        'session_id': 'session-1',
        'task_type': 'ankle_pose',
        'target_group': 'right_ankle',
        'roll_deg': 10.0,
        'pitch_deg': -20.0,
        'yaw_deg': 30.0,
        'duration_ms': 500,
        'position_tolerance': 20,
        'execution_timeout_sec': 5.0,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TaskValidationTest(unittest.TestCase):

    def test_accepts_supported_boundary_values(self):
        for target_group in ('right_ankle', 'left_ankle'):
            result = validate_task_goal(valid_goal(
                target_group=target_group,
                roll_deg=-30.0,
                pitch_deg=30.0,
                yaw_deg=0.0,
                duration_ms=1,
                position_tolerance=500,
                execution_timeout_sec=120.0,
            ))
            self.assertTrue(result.accepted)

    def test_requires_task_trace_and_session_identity(self):
        for field_name in ('task_id', 'trace_id', 'session_id'):
            for value in ('', '   '):
                result = validate_task_goal(valid_goal(**{field_name: value}))
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, field_name + '_required')

    def test_rejects_unsupported_task_type_and_target(self):
        result = validate_task_goal(valid_goal(task_type='walk'))
        self.assertEqual(result.reason, 'unsupported_task_type')
        result = validate_task_goal(valid_goal(target_group='head'))
        self.assertEqual(result.reason, 'unsupported_target_group')

    def test_rejects_nonfinite_or_out_of_range_pose(self):
        for field_name in ('roll_deg', 'pitch_deg', 'yaw_deg'):
            for value, suffix in ((nan, '_not_finite'), (inf, '_not_finite'),
                                  (-30.1, '_out_of_range'),
                                  (30.1, '_out_of_range')):
                result = validate_task_goal(valid_goal(**{field_name: value}))
                self.assertFalse(result.accepted)
                self.assertEqual(result.reason, field_name + suffix)

    def test_rejects_invalid_duration_tolerance_and_timeout(self):
        cases = (
            ({'duration_ms': 0}, 'duration_ms_out_of_range'),
            ({'position_tolerance': 0}, 'position_tolerance_out_of_range'),
            ({'position_tolerance': 501}, 'position_tolerance_out_of_range'),
            ({'execution_timeout_sec': nan},
             'execution_timeout_sec_not_finite'),
            ({'execution_timeout_sec': 0.09},
             'execution_timeout_sec_out_of_range'),
            ({'execution_timeout_sec': 120.1},
             'execution_timeout_sec_out_of_range'),
        )
        for overrides, reason in cases:
            result = validate_task_goal(valid_goal(**overrides))
            self.assertFalse(result.accepted)
            self.assertEqual(result.reason, reason)


class TaskMappingTest(unittest.TestCase):

    def test_maps_goal_and_task_type_explicitly(self):
        task_goal = valid_goal()
        motion_goal = map_task_goal(task_goal, SimpleNamespace)
        self.assertEqual(motion_goal.motion_type, 'ankle_pose')
        self.assertFalse(hasattr(motion_goal, 'task_type'))
        for field_name in (
                'task_id', 'trace_id', 'session_id', 'target_group',
                'roll_deg', 'pitch_deg', 'yaw_deg', 'duration_ms',
                'position_tolerance', 'execution_timeout_sec'):
            self.assertEqual(
                getattr(motion_goal, field_name),
                getattr(task_goal, field_name),
            )

    def test_maps_feedback_field_for_field(self):
        source = SimpleNamespace(**{
            name: index for index, name in enumerate(FEEDBACK_FIELDS)
        })
        target = map_motion_feedback(source, SimpleNamespace)
        for field_name in FEEDBACK_FIELDS:
            self.assertEqual(
                getattr(target, field_name),
                getattr(source, field_name),
            )

    def test_maps_result_field_for_field(self):
        source = SimpleNamespace(**{
            name: index for index, name in enumerate(RESULT_FIELDS)
        })
        target = map_motion_result(source, SimpleNamespace)
        for field_name in RESULT_FIELDS:
            self.assertEqual(
                getattr(target, field_name),
                getattr(source, field_name),
            )

    def test_bridge_rejection_is_not_success(self):
        result = rejected_result(SimpleNamespace, 'motion_goal_rejected')
        self.assertFalse(result.success)
        self.assertEqual(result.status, 'rejected')
        self.assertEqual(result.reason, 'motion_goal_rejected')
        self.assertTrue(result.recoverable)
        self.assertTrue(result.admission_released)
        self.assertFalse(result.target_reached)
        self.assertFalse(result.stop_confirmed)
        self.assertEqual(result.task_id, '')
        self.assertEqual(result.trace_id, '')
        self.assertEqual(result.session_id, '')

    def test_bridge_rejection_preserves_request_identity(self):
        request = valid_goal()
        result = rejected_result(
            SimpleNamespace,
            'motion_action_unavailable',
            request,
        )
        self.assertEqual(result.task_id, request.task_id)
        self.assertEqual(result.trace_id, request.trace_id)
        self.assertEqual(result.session_id, request.session_id)


class SingleGoalAdmissionTest(unittest.TestCase):

    def test_only_one_concurrent_acquire_succeeds(self):
        admission = SingleGoalAdmission()
        with ThreadPoolExecutor(max_workers=8) as executor:
            outcomes = list(executor.map(
                lambda unused: admission.try_acquire(),
                range(32),
            ))
        self.assertEqual(outcomes.count(True), 1)
        self.assertEqual(outcomes.count(False), 31)

    def test_release_allows_next_goal(self):
        admission = SingleGoalAdmission()
        self.assertTrue(admission.try_acquire())
        self.assertFalse(admission.try_acquire())
        admission.release()
        self.assertTrue(admission.try_acquire())


if __name__ == '__main__':
    unittest.main()
