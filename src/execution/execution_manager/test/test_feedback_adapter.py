"""execution_manager 驱动反馈适配测试。"""

import os
import sys
from types import SimpleNamespace
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../execution_manager'))

from feedback_adapter import ActuatorFeedback
from feedback_adapter import feedback_to_actuator_state_fields
from feedback_adapter import servo_state_to_feedback


class TestFeedbackAdapter(unittest.TestCase):
    @staticmethod
    def _servo_state(servo_type='bus', position=1500, error_code=0):
        return SimpleNamespace(
            servo_type=servo_type,
            servo_id=7,
            position=position,
            load=12,
            temperature=38,
            error_code=error_code,
        )

    def test_bus_feedback_uses_pulse_encoding(self):
        feedback = servo_state_to_feedback(self._servo_state())

        self.assertEqual(
            ActuatorFeedback(
                actuator_type='bus',
                actuator_id=7,
                position_raw=1500,
                value_encoding='bus_pulse_us',
                load=12,
                temperature=38,
                status='ok',
                reason='',
                recoverable=False,
                driver_error_code=0,
            ),
            feedback,
        )

    def test_pca_feedback_uses_tick_encoding(self):
        feedback = servo_state_to_feedback(
            self._servo_state(servo_type='PCA', position=320)
        )

        self.assertEqual('pca', feedback.actuator_type)
        self.assertEqual(320, feedback.position_raw)
        self.assertEqual('pca_tick', feedback.value_encoding)

    def test_unknown_actuator_type_is_not_mislabeled(self):
        feedback = servo_state_to_feedback(
            self._servo_state(servo_type='custom', position=99)
        )

        self.assertEqual('custom', feedback.actuator_type)
        self.assertEqual('', feedback.value_encoding)

    def test_known_driver_error_has_stable_reason(self):
        expectations = {
            1: ('communication_error', True),
            2: ('overload', True),
            3: ('overheat', True),
            4: ('driver_error', False),
        }
        for error_code, (reason, recoverable) in expectations.items():
            with self.subTest(error_code=error_code):
                feedback = servo_state_to_feedback(
                    self._servo_state(error_code=error_code)
                )

                self.assertEqual('error', feedback.status)
                self.assertEqual(reason, feedback.reason)
                self.assertEqual(recoverable, feedback.recoverable)
                self.assertEqual(error_code, feedback.driver_error_code)

    def test_unknown_driver_error_is_not_silently_dropped(self):
        feedback = servo_state_to_feedback(
            self._servo_state(error_code=99)
        )

        self.assertEqual('error', feedback.status)
        self.assertEqual('driver_error_99', feedback.reason)
        self.assertFalse(feedback.recoverable)
        self.assertEqual(99, feedback.driver_error_code)

    def test_motion_message_fields_preserve_driver_diagnostics(self):
        feedback = servo_state_to_feedback(self._servo_state())

        self.assertEqual(
            {
                'actuator_type': 'bus',
                'actuator_id': 7,
                'position_raw': 1500,
                'value_encoding': 'bus_pulse_us',
                'load': 12,
                'temperature': 38,
                'status': 'ok',
                'reason': '',
                'recoverable': False,
                'driver_error_code': 0,
            },
            feedback_to_actuator_state_fields(feedback),
        )


if __name__ == '__main__':
    unittest.main()
