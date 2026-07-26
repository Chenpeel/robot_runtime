"""motion-level 执行器服务适配测试。"""

import os
from types import SimpleNamespace
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../execution_manager'))

from actuator_service_adapter import read_response_fields
from actuator_service_adapter import stop_command_for_protocol
from actuator_service_adapter import stop_summary


class TestActuatorServiceAdapter(unittest.TestCase):
    def test_successful_read_uses_driver_position_and_stamp(self):
        stamp = object()
        fields = read_response_fields(SimpleNamespace(
            success=True,
            position=1675,
            error_code=0,
            message='ok',
            stamp=stamp,
        ))

        self.assertTrue(fields['success'])
        self.assertEqual(1675, fields['position_raw'])
        self.assertEqual('bus_pulse_us', fields['value_encoding'])
        self.assertEqual('ok', fields['status'])
        self.assertIs(stamp, fields['stamp'])

    def test_failed_read_has_stable_error_semantics(self):
        missing = read_response_fields(None)
        failed = read_response_fields(SimpleNamespace(
            success=False,
            position=0,
            error_code=1,
            message='serial timeout',
            stamp='stamp',
        ))

        self.assertEqual('driver_service_unavailable', missing['reason'])
        self.assertTrue(missing['recoverable'])
        self.assertEqual('serial timeout', failed['reason'])
        self.assertTrue(failed['recoverable'])

    def test_stop_write_never_claims_physical_confirmation(self):
        fields = stop_summary(
            [9, 10],
            [
                SimpleNamespace(success=True, message='ok'),
                SimpleNamespace(success=True, message='ok'),
            ],
        )

        self.assertTrue(fields['accepted'])
        self.assertTrue(fields['stop_command_sent'])
        self.assertFalse(fields['stop_confirmed'])
        self.assertEqual([9, 10], fields['stopped_actuator_ids'])

    def test_partial_stop_failure_reports_unsupported_ids(self):
        fields = stop_summary(
            [9, 10],
            [SimpleNamespace(success=True, message='ok'), None],
        )

        self.assertFalse(fields['stop_command_sent'])
        self.assertEqual([9], fields['stopped_actuator_ids'])
        self.assertEqual([10], fields['unsupported_actuator_ids'])
        self.assertIn('driver_service_unavailable', fields['reason'])

    def test_protocol_stop_command_mapping_matches_existing_driver(self):
        self.assertEqual('move_stop', stop_command_for_protocol('lx'))
        self.assertEqual('stop_motion', stop_command_for_protocol('zl'))
        self.assertEqual('stop_motion', stop_command_for_protocol(''))


if __name__ == '__main__':
    unittest.main()
