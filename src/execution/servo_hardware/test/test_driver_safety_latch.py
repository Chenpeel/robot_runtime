"""Test the driver safety latch and stale-command fence."""

from pathlib import Path

from servo_hardware.safety_latch import (
    DriverSafetyLatch,
    is_motion_command,
    is_stop_command,
    ros_time_to_ns,
)


class _Stamp:
    def __init__(self, sec=0, nanosec=0):
        self.sec = sec
        self.nanosec = nanosec


def test_default_path_accepts_stamped_and_legacy_zero_stamp_commands():
    latch = DriverSafetyLatch()

    assert latch.admit(0) is True
    assert latch.admit(10) is True
    assert latch.latched is False


def test_stop_immediately_latches_and_blocks_late_or_new_moves():
    latch = DriverSafetyLatch()

    assert latch.admit(stamp_ns=0, is_stop=True, now_ns=100) is True
    assert latch.latched is True
    assert latch.fence_ns == 100
    assert latch.admit(90) is False
    assert latch.admit(110) is False
    assert latch.admit(0, is_stop=True, now_ns=120) is True
    assert latch.fence_ns == 120


def test_stale_release_cannot_bypass_stop_fault_latch():
    latch = DriverSafetyLatch()
    latch.activate(100)

    assert latch.observe_authority(False, stamp_ns=80, now_ns=130) is False
    assert latch.latched is True
    assert latch.observe_authority(True, stamp_ns=140, now_ns=160) is True
    assert latch.observe_authority(False, stamp_ns=140, now_ns=170) is False
    assert latch.latched is True


def test_authoritative_release_keeps_stale_fence_and_allows_new_move():
    latch = DriverSafetyLatch()
    latch.activate(100)
    latch.observe_authority(True, stamp_ns=110, now_ns=150)

    assert latch.observe_authority(False, stamp_ns=160, now_ns=170) is True
    assert latch.latched is False
    assert latch.admit(0) is False
    assert latch.admit(100) is False
    assert latch.admit(110) is False
    assert latch.admit(161) is True


def test_authority_messages_must_be_strictly_monotonic_for_release():
    latch = DriverSafetyLatch()
    latch.activate(100)

    assert latch.observe_authority(False, stamp_ns=150, now_ns=160) is True
    latch.activate(170)
    assert latch.observe_authority(False, stamp_ns=150, now_ns=180) is False
    assert latch.latched is True
    assert latch.observe_authority(False, stamp_ns=190, now_ns=200) is True


def test_ros_time_conversion_is_total_and_uses_nanoseconds():
    assert ros_time_to_ns(_Stamp(sec=2, nanosec=3)) == 2_000_000_003
    assert ros_time_to_ns(None) == 0
    assert ros_time_to_ns(object()) == 0


def test_protocol_stop_always_enters_latch_and_remains_allowed():
    latch = DriverSafetyLatch()

    assert latch.admit_protocol_command("move_stop", now_ns=100) is True
    assert latch.latched is True
    assert latch.admit_protocol_command("stop-motion", now_ns=120) is True
    assert latch.fence_ns == 120


def test_protocol_motion_commands_and_aliases_are_blocked_while_active():
    latch = DriverSafetyLatch()
    latch.activate(100)
    motion_commands = (
        "move",
        "send_position",
        "move_command",
        "move_time_write",
        "move_time_wait_write",
        "move_start",
        "motion_continue",
        "continue_motion",
    )

    for command in motion_commands:
        assert is_motion_command(command) is True
        assert latch.admit_protocol_command(
            command,
            now_ns=110,
            stamp_ns=105,
        ) is False

    assert is_stop_command("encode_move_stop") is True
    assert is_stop_command("servo_stop_motion") is True
    assert latch.admit_protocol_command("read_position", now_ns=110) is True


def test_protocol_motion_recovers_only_after_authoritative_release():
    latch = DriverSafetyLatch()
    latch.activate(100)

    assert latch.admit_protocol_command("move_start", now_ns=110) is False
    assert latch.observe_authority(False, stamp_ns=120, now_ns=130) is True
    assert latch.admit_protocol_command(
        "move_start",
        now_ns=140,
        stamp_ns=90,
    ) is False
    assert latch.admit_protocol_command(
        "move_start",
        now_ns=140,
        stamp_ns=121,
    ) is True


def test_router_preserves_service_command_stamp_for_port_fence():
    source = (
        Path(__file__).resolve().parents[1]
        / 'servo_hardware'
        / 'bus_protocol_router.py'
    ).read_text(encoding='utf-8')

    assert 'req.stamp = stamp' in source
    assert 'stamp=request.stamp' in source
    assert '"/servo/set_driver_safety"' in source
    assert 'self.safety_clients' in source


def test_driver_safety_interfaces_are_registered_and_stamped():
    repository_src = Path(__file__).resolve().parents[3]
    servo_msgs = repository_src / 'interfaces' / 'servo_msgs'
    state_source = (
        servo_msgs / 'msg' / 'DriverSafetyState.msg'
    ).read_text(encoding='utf-8')
    service_source = (
        servo_msgs / 'srv' / 'ExecuteBusCommand.srv'
    ).read_text(encoding='utf-8')
    safety_service_source = (
        servo_msgs / 'srv' / 'SetDriverSafety.srv'
    ).read_text(encoding='utf-8')
    cmake_source = (servo_msgs / 'CMakeLists.txt').read_text(encoding='utf-8')

    assert 'bool estop_active' in state_source
    assert 'string reason' in state_source
    assert 'builtin_interfaces/Time stamp' in state_source
    assert 'int32[] params\nbuiltin_interfaces/Time stamp\n---' in service_source
    assert 'bool estop_active' in safety_service_source
    assert 'bool success' in safety_service_source
    assert '"msg/DriverSafetyState.msg"' in cmake_source
    assert '"srv/SetDriverSafety.srv"' in cmake_source
