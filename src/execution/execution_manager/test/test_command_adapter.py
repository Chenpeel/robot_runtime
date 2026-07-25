"""execution_manager command adapter 测试。"""

import os
import sys
from types import SimpleNamespace


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../execution_manager'))

from command_adapter import ActuatorSetpoint
from command_adapter import motion_command_to_setpoint
from command_adapter import setpoint_to_servo_fields


def test_motion_command_to_setpoint_requires_explicit_duration_ms():
    msg = SimpleNamespace(
        servo_type='bus',
        servo_id=7,
        position=1500,
        value_encoding='',
        duration_ms=0,
    )

    setpoint = motion_command_to_setpoint(msg)

    assert setpoint == ActuatorSetpoint(
        actuator_type='bus',
        actuator_id=7,
        target_raw=1500,
        value_encoding='bus_pulse_us',
        duration_ms=0,
    )


def test_setpoint_to_servo_fields_preserves_driver_values():
    setpoint = ActuatorSetpoint(
        actuator_type='pca',
        actuator_id=3,
        target_raw=320,
        value_encoding='pca_tick',
        duration_ms=80,
    )

    servo_fields = setpoint_to_servo_fields(setpoint)

    assert servo_fields == {
        'servo_type': 'pca',
        'servo_id': 3,
        'position': 320,
        'speed': 80,
    }


def test_motion_command_to_setpoint_uses_explicit_duration_and_encoding():
    msg = SimpleNamespace(
        servo_type='bus',
        servo_id=2,
        position=1800,
        value_encoding='bus_pulse_us',
        duration_ms=45,
    )

    setpoint = motion_command_to_setpoint(msg)

    assert setpoint == ActuatorSetpoint(
        actuator_type='bus',
        actuator_id=2,
        target_raw=1800,
        value_encoding='bus_pulse_us',
        duration_ms=45,
    )


def test_motion_command_to_setpoint_defaults_missing_duration_to_zero():
    msg = SimpleNamespace(
        servo_type='bus',
        servo_id=4,
        position=1600,
        value_encoding='bus_pulse_us',
    )

    setpoint = motion_command_to_setpoint(msg)

    assert setpoint == ActuatorSetpoint(
        actuator_type='bus',
        actuator_id=4,
        target_raw=1600,
        value_encoding='bus_pulse_us',
        duration_ms=0,
    )


def test_motion_command_to_setpoint_normalizes_invalid_duration_to_zero():
    msg = SimpleNamespace(
        servo_type='pca',
        servo_id=5,
        position=300,
        value_encoding='pca_tick',
        duration_ms='invalid',
    )

    setpoint = motion_command_to_setpoint(msg)

    assert setpoint == ActuatorSetpoint(
        actuator_type='pca',
        actuator_id=5,
        target_raw=300,
        value_encoding='pca_tick',
        duration_ms=0,
    )


def test_motion_command_to_setpoint_normalizes_non_positive_duration_to_zero():
    msg = SimpleNamespace(
        servo_type='pca',
        servo_id=5,
        position=300,
        value_encoding='pca_tick',
        duration_ms=-1,
    )

    setpoint = motion_command_to_setpoint(msg)

    assert setpoint == ActuatorSetpoint(
        actuator_type='pca',
        actuator_id=5,
        target_raw=300,
        value_encoding='pca_tick',
        duration_ms=0,
    )
