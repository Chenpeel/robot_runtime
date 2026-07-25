"""语音 JSON 解析与 ExecuteTask 映射的纯逻辑测试。"""

import json
from math import inf, nan
from types import SimpleNamespace
import unittest

from speech_interface.intent_contract import (
    IntentValidationError,
    MAX_PAYLOAD_CHARS,
    extract_speech_context,
    map_intent_to_task_goal,
    parse_speech_intent,
)


def valid_payload(**overrides):
    document = {
        'intent_id': 'intent-1',
        'task_id': 'task-1',
        'trace_id': 'trace-1',
        'session_id': 'session-1',
        'task_type': 'ankle_pose',
        'target_group': 'right_ankle',
        'roll': 1.5,
        'pitch': -2.5,
        'yaw': 3.5,
        'duration_ms': 800,
        'position_tolerance': 12,
        'execution_timeout_sec': 5.0,
        'confidence': 0.9,
    }
    document.update(overrides)
    return json.dumps(document)


def rejection_reason(payload):
    with unittest.TestCase().assertRaises(IntentValidationError) as raised:
        parse_speech_intent(payload)
    return raised.exception.reason


class IntentParserTest(unittest.TestCase):

    def test_parses_complete_ankle_pose(self):
        intent = parse_speech_intent(valid_payload())

        self.assertEqual(intent.intent_id, 'intent-1')
        self.assertEqual(intent.task_type, 'ankle_pose')
        self.assertEqual(intent.target_group, 'right_ankle')
        self.assertEqual(intent.duration_ms, 800)
        self.assertAlmostEqual(intent.confidence, 0.9)

    def test_requires_json_object_and_rejects_malformed_json(self):
        self.assertEqual(rejection_reason('{'), 'invalid_json')
        self.assertEqual(rejection_reason('[]'), 'json_object_required')
        self.assertEqual(rejection_reason('null'), 'json_object_required')

    def test_rejects_duplicate_unknown_and_missing_fields(self):
        duplicate = valid_payload().replace(
            '"intent_id": "intent-1"',
            '"intent_id": "intent-1", "intent_id": "intent-2"',
        )
        self.assertEqual(rejection_reason(duplicate), 'duplicate_field')
        self.assertEqual(
            rejection_reason(valid_payload(extra='value')),
            'unknown_field',
        )
        document = json.loads(valid_payload())
        del document['trace_id']
        self.assertEqual(
            rejection_reason(json.dumps(document)),
            'trace_id_required',
        )

    def test_rejects_blank_id_unsupported_task_and_target(self):
        cases = (
            ({'intent_id': ' '}, 'intent_id_required'),
            ({'task_id': ''}, 'task_id_required'),
            ({'task_type': 'wave'}, 'unsupported_task_type'),
            ({'target_group': 'both_ankles'}, 'unsupported_target_group'),
        )
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(rejection_reason(valid_payload(**overrides)), reason)

    def test_rejects_non_finite_numbers_including_json_constants(self):
        for field_name in (
                'roll', 'pitch', 'yaw', 'execution_timeout_sec', 'confidence'):
            for value in (nan, inf, -inf):
                with self.subTest(field=field_name, value=value):
                    self.assertEqual(
                        rejection_reason(valid_payload(**{field_name: value})),
                        'non_finite_json_number',
                    )

        huge_integer_payload = valid_payload(roll=10 ** 4000)
        self.assertEqual(
            rejection_reason(huge_integer_payload),
            'roll_not_finite',
        )

    def test_rejects_pose_and_confidence_out_of_range(self):
        cases = (
            ({'roll': -30.01}, 'roll_out_of_range'),
            ({'pitch': 30.01}, 'pitch_out_of_range'),
            ({'yaw': 31.0}, 'yaw_out_of_range'),
            ({'confidence': -0.01}, 'confidence_out_of_range'),
            ({'confidence': 1.01}, 'confidence_out_of_range'),
            ({'confidence': 0.59}, 'confidence_below_minimum'),
        )
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(rejection_reason(valid_payload(**overrides)), reason)

    def test_allows_configured_lower_confidence_threshold(self):
        intent = parse_speech_intent(
            valid_payload(confidence=0.4),
            minimum_confidence=0.3,
        )
        self.assertAlmostEqual(intent.confidence, 0.4)

    def test_rejects_invalid_minimum_confidence_configuration(self):
        for minimum_confidence in (-0.1, 1.1, nan, inf):
            with self.subTest(minimum_confidence=minimum_confidence):
                with self.assertRaises(ValueError):
                    parse_speech_intent(
                        valid_payload(),
                        minimum_confidence=minimum_confidence,
                    )

    def test_rejects_invalid_integer_and_timeout_ranges(self):
        cases = (
            ({'duration_ms': True}, 'duration_ms_integer_required'),
            ({'duration_ms': 1.0}, 'duration_ms_integer_required'),
            ({'duration_ms': 0}, 'duration_ms_out_of_range'),
            ({'duration_ms': 65536}, 'duration_ms_out_of_range'),
            ({'position_tolerance': 0}, 'position_tolerance_out_of_range'),
            ({'position_tolerance': 501}, 'position_tolerance_out_of_range'),
            (
                {'execution_timeout_sec': 0.09},
                'execution_timeout_sec_out_of_range',
            ),
            (
                {'execution_timeout_sec': 120.01},
                'execution_timeout_sec_out_of_range',
            ),
        )
        for overrides, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(rejection_reason(valid_payload(**overrides)), reason)

    def test_extracts_identity_for_semantic_rejection(self):
        context = extract_speech_context(valid_payload(confidence=0.1))
        self.assertEqual(context.intent_id, 'intent-1')
        self.assertEqual(context.task_id, 'task-1')
        self.assertEqual(context.trace_id, 'trace-1')
        self.assertEqual(context.session_id, 'session-1')
        self.assertEqual(context.task_type, 'ankle_pose')
        self.assertEqual(context.target_group, 'right_ankle')
        self.assertIsNone(extract_speech_context('{'))

    def test_rejects_resource_limit_violations(self):
        self.assertEqual(
            rejection_reason(' ' * (MAX_PAYLOAD_CHARS + 1)),
            'payload_too_large',
        )
        self.assertEqual(
            rejection_reason(valid_payload(intent_id='x' * 257)),
            'intent_id_too_long',
        )


class IntentMappingTest(unittest.TestCase):

    def test_maps_only_execute_task_goal_fields(self):
        intent = parse_speech_intent(valid_payload())
        goal = map_intent_to_task_goal(intent, SimpleNamespace)

        self.assertEqual(goal.task_id, intent.task_id)
        self.assertEqual(goal.trace_id, intent.trace_id)
        self.assertEqual(goal.session_id, intent.session_id)
        self.assertEqual(goal.task_type, 'ankle_pose')
        self.assertEqual(goal.target_group, 'right_ankle')
        self.assertEqual(goal.roll_deg, intent.roll)
        self.assertEqual(goal.pitch_deg, intent.pitch)
        self.assertEqual(goal.yaw_deg, intent.yaw)
        self.assertEqual(goal.duration_ms, intent.duration_ms)
        self.assertEqual(goal.position_tolerance, intent.position_tolerance)
        self.assertEqual(
            goal.execution_timeout_sec,
            intent.execution_timeout_sec,
        )
        self.assertFalse(hasattr(goal, 'intent_id'))
        self.assertFalse(hasattr(goal, 'confidence'))


if __name__ == '__main__':
    unittest.main()
