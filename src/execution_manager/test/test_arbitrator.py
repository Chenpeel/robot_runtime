"""execution_manager 仲裁逻辑测试。"""

import os
import sys

import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../execution_manager'))

from arbitrator import CommandArbitrator
from arbitrator import CommandFrame


def _command(servo_id: int = 1) -> CommandFrame:
    return CommandFrame(
        servo_type='bus',
        servo_id=servo_id,
        position=1500,
        speed=100,
    )


def test_teleop_preempts_motion_until_timeout():
    arbitrator = CommandArbitrator(
        teleop_timeout_sec=0.5,
        motion_timeout_sec=1.0,
    )

    motion_result = arbitrator.receive_command('motion', _command(), 0.0)
    assert motion_result.accepted is True
    assert motion_result.mode == 'motion_active'

    claim_result = arbitrator.receive_teleop_control(
        'claim',
        0.1,
        requester_id='client-a',
    )
    assert claim_result.accepted is True
    assert claim_result.mode == 'teleop_active'

    teleop_result = arbitrator.receive_command('teleop', _command(), 0.11)
    assert teleop_result.accepted is True
    assert teleop_result.mode == 'teleop_active'

    blocked_motion = arbitrator.receive_command('motion', _command(), 0.2)
    assert blocked_motion.accepted is False
    assert blocked_motion.reason == 'teleop_active'

    state_after_timeout = arbitrator.tick(0.7)
    assert state_after_timeout['mode'] == 'motion_active'
    assert state_after_timeout['active_source'] == 'motion'


def test_estop_blocks_all_sources():
    arbitrator = CommandArbitrator()

    state = arbitrator.set_estop(True, 0.0)
    assert state['mode'] == 'estop'
    assert state['estop_active'] is True

    claim_result = arbitrator.receive_teleop_control(
        'claim',
        0.05,
        requester_id='client-a',
    )
    teleop_result = arbitrator.receive_command('teleop', _command(), 0.1)
    motion_result = arbitrator.receive_command('motion', _command(), 0.1)

    assert claim_result.accepted is False
    assert claim_result.reason == 'estop'
    assert teleop_result.accepted is False
    assert teleop_result.reason == 'estop'
    assert motion_result.accepted is False
    assert motion_result.reason == 'estop'


def test_tick_returns_idle_after_all_timeouts():
    arbitrator = CommandArbitrator(
        teleop_timeout_sec=0.2,
        motion_timeout_sec=0.2,
    )

    arbitrator.receive_teleop_control('claim', 0.0, requester_id='client-a')
    state = arbitrator.tick(0.3)

    assert state['mode'] == 'idle'
    assert state['active_source'] is None
    assert state['teleop_holder_id'] == ''
    assert state['teleop_active'] is False
    assert state['motion_active'] is False


def test_teleop_command_requires_explicit_claim():
    arbitrator = CommandArbitrator()

    teleop_result = arbitrator.receive_command('teleop', _command(), 0.0)

    assert teleop_result.accepted is False
    assert teleop_result.reason == 'teleop_control_not_granted'


def test_keepalive_extends_claim_window_and_release_clears_lease():
    arbitrator = CommandArbitrator(teleop_timeout_sec=0.5)
    requester_id = 'client-a'

    keepalive_without_claim = arbitrator.receive_teleop_control(
        'keepalive',
        0.0,
        requester_id=requester_id,
    )
    assert keepalive_without_claim.accepted is False
    assert keepalive_without_claim.reason == 'teleop_control_not_granted'

    claim_result = arbitrator.receive_teleop_control(
        'claim',
        0.1,
        requester_id=requester_id,
    )
    assert claim_result.accepted is True
    assert claim_result.mode == 'teleop_active'

    keepalive_result = arbitrator.receive_teleop_control(
        'keepalive',
        0.4,
        requester_id=requester_id,
    )
    assert keepalive_result.accepted is True
    assert keepalive_result.mode == 'teleop_active'

    state_after_keepalive = arbitrator.tick(0.8)
    assert state_after_keepalive['teleop_active'] is True
    assert state_after_keepalive['active_source'] == 'teleop'
    assert state_after_keepalive['teleop_holder_id'] == requester_id
    assert state_after_keepalive['last_teleop_control_action'] == 'keepalive'
    assert state_after_keepalive['last_teleop_control_accepted'] is True
    assert state_after_keepalive['last_teleop_control_reason'] == 'accepted'
    assert state_after_keepalive['teleop_control_accepted_count'] == 2
    assert state_after_keepalive['teleop_control_rejected_count'] == 1
    assert state_after_keepalive['teleop_control_remaining_sec'] == pytest.approx(
        0.1
    )

    release_result = arbitrator.receive_teleop_control(
        'release',
        0.81,
        requester_id=requester_id,
    )
    assert release_result.accepted is True
    assert release_result.mode == 'idle'

    state = arbitrator.tick(0.82)
    assert state['teleop_active'] is False
    assert state['active_source'] is None
    assert state['teleop_holder_id'] == ''
    assert state['last_teleop_control_action'] == 'release'
    assert state['last_teleop_control_accepted'] is True
    assert state['last_teleop_control_reason'] == 'accepted'
    assert state['teleop_control_accepted_count'] == 3
    assert state['teleop_control_remaining_sec'] == 0.0


def test_teleop_control_feedback_tracks_rejections():
    arbitrator = CommandArbitrator(teleop_timeout_sec=0.5)

    result = arbitrator.receive_teleop_control(
        'unsupported',
        0.0,
        requester_id='client-a',
    )

    assert result.accepted is False
    assert result.reason == 'unsupported_teleop_control_action'

    state = arbitrator.snapshot(0.0)
    assert state['last_teleop_control_action'] == 'unsupported'
    assert state['last_teleop_control_accepted'] is False
    assert state['last_teleop_control_reason'] == 'unsupported_teleop_control_action'
    assert state['teleop_control_accepted_count'] == 0
    assert state['teleop_control_rejected_count'] == 1
    assert state['last_rejection_reason'] == 'unsupported_teleop_control_action'


def test_other_holder_cannot_claim_keepalive_or_release_active_lease():
    arbitrator = CommandArbitrator(teleop_timeout_sec=0.5)

    claim_result = arbitrator.receive_teleop_control(
        'claim',
        0.0,
        requester_id='client-a',
    )
    assert claim_result.accepted is True

    other_claim = arbitrator.receive_teleop_control(
        'claim',
        0.1,
        requester_id='client-b',
    )
    assert other_claim.accepted is False
    assert other_claim.reason == 'teleop_control_held_by_other'

    other_keepalive = arbitrator.receive_teleop_control(
        'keepalive',
        0.2,
        requester_id='client-b',
    )
    assert other_keepalive.accepted is False
    assert other_keepalive.reason == 'teleop_control_not_holder'

    other_release = arbitrator.receive_teleop_control(
        'release',
        0.3,
        requester_id='client-b',
    )
    assert other_release.accepted is False
    assert other_release.reason == 'teleop_control_not_holder'

    state = arbitrator.snapshot(0.3)
    assert state['teleop_holder_id'] == 'client-a'


def test_same_holder_can_reclaim_after_timeout_or_reclaim_while_active():
    arbitrator = CommandArbitrator(teleop_timeout_sec=0.5)

    first_claim = arbitrator.receive_teleop_control(
        'claim',
        0.0,
        requester_id='client-a',
    )
    assert first_claim.accepted is True

    second_claim = arbitrator.receive_teleop_control(
        'claim',
        0.2,
        requester_id='client-a',
    )
    assert second_claim.accepted is True
    assert second_claim.mode == 'teleop_active'

    timed_out_state = arbitrator.tick(0.8)
    assert timed_out_state['teleop_holder_id'] == ''
    assert timed_out_state['teleop_active'] is False

    reclaimed = arbitrator.receive_teleop_control(
        'claim',
        0.81,
        requester_id='client-b',
    )
    assert reclaimed.accepted is True
    assert reclaimed.mode == 'teleop_active'

    state = arbitrator.snapshot(0.81)
    assert state['teleop_holder_id'] == 'client-b'
