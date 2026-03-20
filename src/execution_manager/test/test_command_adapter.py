"""execution_manager command adapter 测试。"""

import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../execution_manager'))

from command_adapter import ActuatorSetpoint
from command_adapter import motion_command_to_setpoint
from command_adapter import setpoint_to_servo_fields


def test_motion_command_to_setpoint_uses_internal_duration_semantics():
    msg = SimpleNamespace(
        servo_type='bus',
        servo_id=7,
        position=1500,
        speed=120,
    )

    setpoint = motion_command_to_setpoint(msg)

    assert setpoint == ActuatorSetpoint(
        actuator_type='bus',
        actuator_id=7,
        target_raw=1500,
        duration_ms=120,
    )


def test_setpoint_to_servo_fields_preserves_driver_values():
    setpoint = ActuatorSetpoint(
        actuator_type='pca',
        actuator_id=3,
        target_raw=320,
        duration_ms=80,
    )

    servo_fields = setpoint_to_servo_fields(setpoint)

    assert servo_fields == {
        'servo_type': 'pca',
        'servo_id': 3,
        'position': 320,
        'speed': 80,
    }
