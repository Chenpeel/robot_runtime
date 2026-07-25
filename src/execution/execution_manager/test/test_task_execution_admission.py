"""正式 task 与 teleop/motion 的跨入口执行准入测试。"""

import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../execution_manager'))

from arbitrator import CommandArbitrator


class TestTaskExecutionAdmission(unittest.TestCase):
    @staticmethod
    def _arbitrator(**kwargs):
        return CommandArbitrator(
            task_timeout_sec=1.0,
            task_lease_id_factory=lambda: 'task-lease-1',
            **kwargs,
        )

    @staticmethod
    def _start(arbitrator, now_sec=0.0, **overrides):
        fields = {
            'task_id': 'task-1',
            'trace_id': 'trace-1',
            'session_id': 'session-1',
        }
        fields.update(overrides)
        return arbitrator.receive_task_control('start', now_sec, **fields)

    def test_start_requires_complete_trace_identity(self):
        cases = (
            ({'task_id': ''}, 'task_id_required'),
            ({'trace_id': ''}, 'task_trace_id_required'),
            ({'session_id': ''}, 'task_session_id_required'),
        )

        for overrides, reason in cases:
            with self.subTest(reason=reason):
                arbitrator = self._arbitrator()
                result = self._start(arbitrator, **overrides)
                self.assertFalse(result.accepted)
                self.assertEqual(reason, result.reason)

    def test_start_generates_lease_and_publishes_task_identity(self):
        arbitrator = self._arbitrator()

        result = self._start(arbitrator)
        state = arbitrator.snapshot(0.0)

        self.assertTrue(result.accepted)
        self.assertEqual('task_active', result.mode)
        self.assertEqual('task', result.active_source)
        self.assertTrue(state['task_active'])
        self.assertEqual('task-1', state['task_id'])
        self.assertEqual('trace-1', state['task_trace_id'])
        self.assertEqual('session-1', state['task_session_id'])
        self.assertEqual('task-lease-1', state['task_lease_id'])
        self.assertEqual(1.0, state['task_control_remaining_sec'])
        self.assertEqual('active', state['task_status'])
        self.assertFalse(state['task_recoverable'])

    def test_external_task_rejection_preserves_full_request_identity(self):
        arbitrator = self._arbitrator()

        result = arbitrator.reject_task_control(
            'start',
            0.0,
            'task-1',
            'trace-1',
            'session-1',
            'task_stop_pending',
        )
        state = arbitrator.snapshot(0.0)

        self.assertFalse(result.accepted)
        self.assertEqual('task_stop_pending', result.reason)
        self.assertEqual('task-1', state['last_task_control_task_id'])
        self.assertEqual('trace-1', state['last_task_control_trace_id'])
        self.assertEqual('session-1', state['last_task_control_session_id'])
        self.assertTrue(state['task_recoverable'])

    def test_new_start_identity_survives_expiring_old_lease_refresh(self):
        lease_ids = iter(('old-lease', 'new-lease'))
        arbitrator = CommandArbitrator(
            task_timeout_sec=1.0,
            task_lease_id_factory=lambda: next(lease_ids),
        )
        self._start(arbitrator)

        result = self._start(
            arbitrator,
            now_sec=1.1,
            task_id='task-2',
            trace_id='trace-2',
            session_id='session-2',
        )
        state = arbitrator.snapshot(1.1)

        self.assertTrue(result.accepted)
        self.assertEqual('task-2', state['task_id'])
        self.assertEqual('trace-2', state['task_trace_id'])
        self.assertEqual('session-2', state['task_session_id'])
        self.assertEqual('task-2', state['last_task_control_task_id'])
        self.assertEqual('trace-2', state['last_task_control_trace_id'])
        self.assertEqual('session-2', state['last_task_control_session_id'])
        self.assertEqual('new-lease', state['task_lease_id'])

    def test_external_stop_gate_rejects_all_execution_sources(self):
        arbitrator = self._arbitrator()

        for source in ('task', 'teleop', 'motion'):
            with self.subTest(source=source):
                result = arbitrator.reject_command(
                    source,
                    0.0,
                    'requester-1',
                    'stop_operation_pending',
                )
                self.assertFalse(result.accepted)
                self.assertEqual('stop_operation_pending', result.reason)

    def test_task_start_preempts_ordinary_teleop_lease(self):
        arbitrator = self._arbitrator(lease_id_factory=lambda: 'teleop-lease')
        arbitrator.receive_teleop_control(
            'claim',
            0.0,
            requester_id='operator-1',
        )

        result = self._start(arbitrator, now_sec=0.1)
        state = arbitrator.snapshot(0.1)

        self.assertTrue(result.accepted)
        self.assertEqual('task_active', state['mode'])
        self.assertEqual('', state['teleop_holder_id'])
        self.assertEqual('', state['teleop_lease_id'])

    def test_task_blocks_teleop_claim_and_ordinary_motion(self):
        arbitrator = self._arbitrator()
        self._start(arbitrator)

        teleop = arbitrator.receive_teleop_control(
            'claim',
            0.1,
            requester_id='operator-1',
        )
        motion = arbitrator.receive_command('motion', 0.1)

        self.assertFalse(teleop.accepted)
        self.assertEqual('task_active', teleop.reason)
        self.assertFalse(motion.accepted)
        self.assertEqual('task_active', motion.reason)

    def test_task_command_requires_matching_task_and_lease(self):
        arbitrator = self._arbitrator()
        self._start(arbitrator)

        cases = (
            ({}, 'task_requester_id_required'),
            ({'requester_id': 'other-task'}, 'task_control_not_holder'),
            ({'requester_id': 'task-1'}, 'task_lease_required'),
            (
                {'requester_id': 'task-1', 'lease_id': 'wrong-lease'},
                'task_lease_mismatch',
            ),
        )
        for fields, reason in cases:
            with self.subTest(reason=reason):
                result = arbitrator.receive_command('task', 0.1, **fields)
                state = arbitrator.snapshot(0.1)
                self.assertFalse(result.accepted)
                self.assertEqual(reason, result.reason)
                self.assertEqual(
                    fields.get('requester_id', ''),
                    state['last_task_command_requester_id'],
                )
                self.assertFalse(state['last_task_command_accepted'])
                self.assertEqual(reason, state['last_task_command_reason'])

        accepted = arbitrator.receive_command(
            'task',
            0.2,
            requester_id='task-1',
            lease_id='task-lease-1',
        )
        state = arbitrator.snapshot(0.2)
        self.assertTrue(accepted.accepted)
        self.assertEqual('task_active', accepted.mode)
        self.assertEqual('task-1', state['last_task_command_requester_id'])
        self.assertTrue(state['last_task_command_accepted'])
        self.assertEqual('accepted', state['last_task_command_reason'])

    def test_active_task_cannot_be_replaced_or_restarted_without_lease(self):
        arbitrator = self._arbitrator()
        self._start(arbitrator)

        other_task = self._start(
            arbitrator,
            now_sec=0.1,
            task_id='task-2',
        )
        missing_lease = self._start(arbitrator, now_sec=0.2)
        idempotent = self._start(
            arbitrator,
            now_sec=0.3,
            lease_id='task-lease-1',
        )

        self.assertEqual('task_control_held_by_other_task', other_task.reason)
        self.assertEqual('task_lease_required', missing_lease.reason)
        self.assertTrue(idempotent.accepted)

    def test_keepalive_extends_lease_and_finish_clears_it(self):
        arbitrator = self._arbitrator()
        self._start(arbitrator)

        keepalive = arbitrator.receive_task_control(
            'keepalive',
            0.8,
            task_id='task-1',
            trace_id='trace-1',
            session_id='session-1',
            lease_id='task-lease-1',
        )
        self.assertTrue(keepalive.accepted)
        self.assertAlmostEqual(
            0.8,
            arbitrator.snapshot(1.0)['task_control_remaining_sec'],
        )

        finish = arbitrator.receive_task_control(
            'finish',
            1.1,
            task_id='task-1',
            trace_id='trace-1',
            session_id='session-1',
            lease_id='task-lease-1',
        )
        state = arbitrator.snapshot(1.1)
        self.assertTrue(finish.accepted)
        self.assertFalse(state['task_active'])
        self.assertEqual('task-1', state['task_id'])
        self.assertEqual('trace-1', state['task_trace_id'])
        self.assertEqual('session-1', state['task_session_id'])
        self.assertEqual('', state['task_lease_id'])
        self.assertEqual('finish', state['last_task_control_action'])
        self.assertEqual('finished', state['task_status'])

    def test_cancel_revokes_future_task_commands(self):
        arbitrator = self._arbitrator()
        self._start(arbitrator)

        cancel = arbitrator.receive_task_control(
            'cancel',
            0.2,
            task_id='task-1',
            trace_id='trace-1',
            session_id='session-1',
            lease_id='task-lease-1',
        )
        rejected = arbitrator.receive_command(
            'task',
            0.3,
            requester_id='task-1',
            lease_id='task-lease-1',
        )

        self.assertTrue(cancel.accepted)
        self.assertFalse(rejected.accepted)
        self.assertEqual('task_control_not_granted', rejected.reason)
        state = arbitrator.snapshot(0.3)
        self.assertEqual('task-1', state['task_id'])
        self.assertEqual('trace-1', state['task_trace_id'])
        self.assertEqual('session-1', state['task_session_id'])
        self.assertEqual('cancelled', state['task_status'])

    def test_timeout_clears_task_and_restores_ordinary_motion(self):
        arbitrator = self._arbitrator()
        self._start(arbitrator)

        expired = arbitrator.tick(1.1)
        motion = arbitrator.receive_command('motion', 1.2)

        self.assertFalse(expired['task_active'])
        self.assertEqual('task-1', expired['task_id'])
        self.assertEqual('trace-1', expired['task_trace_id'])
        self.assertEqual('session-1', expired['task_session_id'])
        self.assertEqual('', expired['task_lease_id'])
        self.assertEqual('expired', expired['task_status'])
        self.assertEqual('task_lease_expired', expired['last_task_control_reason'])
        self.assertTrue(expired['task_recoverable'])
        self.assertTrue(motion.accepted)
        self.assertEqual('motion_active', motion.mode)

    def test_estop_clears_leases_and_requires_fresh_start(self):
        arbitrator = self._arbitrator(lease_id_factory=lambda: 'teleop-lease')
        self._start(arbitrator)

        state = arbitrator.set_estop(True, 0.1)
        blocked = arbitrator.receive_command(
            'task',
            0.2,
            requester_id='task-1',
            lease_id='task-lease-1',
        )
        released = arbitrator.set_estop(False, 0.3)
        stale = arbitrator.receive_command(
            'task',
            0.4,
            requester_id='task-1',
            lease_id='task-lease-1',
        )

        self.assertTrue(state['estop_active'])
        self.assertEqual('', state['task_lease_id'])
        self.assertEqual('', state['teleop_lease_id'])
        self.assertEqual('task-1', state['task_id'])
        self.assertEqual('trace-1', state['task_trace_id'])
        self.assertEqual('session-1', state['task_session_id'])
        self.assertEqual('blocked', state['task_status'])
        self.assertEqual('estop', state['task_state_reason'])
        self.assertTrue(state['task_recoverable'])
        self.assertFalse(released['estop_active'])
        self.assertEqual('blocked', released['task_status'])
        self.assertEqual('estop', released['task_state_reason'])
        self.assertEqual('estop', released['last_task_control_action'])
        self.assertEqual('estop', blocked.reason)
        self.assertEqual('task_control_not_granted', stale.reason)

    def test_driver_stop_timeout_estop_is_nonrecoverable(self):
        arbitrator = self._arbitrator()
        self._start(arbitrator)

        state = arbitrator.set_estop(
            True,
            0.1,
            reason='driver_stop_timeout',
        )

        self.assertTrue(state['estop_active'])
        self.assertEqual('driver_stop_timeout', state['estop_reason'])
        self.assertEqual('driver_stop_timeout', state['task_state_reason'])
        self.assertEqual('blocked', state['task_status'])
        self.assertFalse(state['task_recoverable'])

    def test_terminal_task_identity_rejects_delayed_start_replay(self):
        arbitrator = self._arbitrator()
        self._start(arbitrator)
        arbitrator.receive_task_control(
            'finish',
            0.1,
            task_id='task-1',
            trace_id='trace-1',
            session_id='session-1',
            lease_id='task-lease-1',
        )

        replay = self._start(arbitrator, now_sec=0.2)
        fresh = self._start(
            arbitrator,
            now_sec=0.3,
            task_id='task-2',
            trace_id='trace-2',
            session_id='session-2',
        )

        self.assertFalse(replay.accepted)
        self.assertEqual('task_control_replay', replay.reason)
        self.assertTrue(fresh.accepted)
        self.assertEqual('task-2', arbitrator.snapshot(0.3)['task_id'])

    def test_task_start_discards_preempted_motion_activity_window(self):
        arbitrator = self._arbitrator()
        arbitrator.receive_command('motion', 0.0)
        self._start(arbitrator, now_sec=0.1)
        arbitrator.receive_task_control(
            'finish',
            0.2,
            task_id='task-1',
            trace_id='trace-1',
            session_id='session-1',
            lease_id='task-lease-1',
        )

        state = arbitrator.snapshot(0.2)
        self.assertEqual('idle', state['mode'])
        self.assertFalse(state['motion_active'])

    def test_task_operation_requires_full_identity_and_lease(self):
        arbitrator = self._arbitrator()
        self._start(arbitrator)

        cases = (
            ({'task_id': ''}, 'task_id_required'),
            ({'trace_id': ''}, 'task_trace_id_required'),
            ({'session_id': ''}, 'task_session_id_required'),
            ({'lease_id': ''}, 'task_lease_required'),
            ({'lease_id': 'wrong'}, 'task_lease_mismatch'),
        )
        base = {
            'task_id': 'task-1',
            'trace_id': 'trace-1',
            'session_id': 'session-1',
            'lease_id': 'task-lease-1',
        }
        for overrides, reason in cases:
            fields = dict(base)
            fields.update(overrides)
            result = arbitrator.validate_task_operation(0.1, **fields)
            self.assertFalse(result.accepted)
            self.assertEqual(reason, result.reason)

        accepted = arbitrator.validate_task_operation(0.1, **base)
        self.assertTrue(accepted.accepted)
        self.assertEqual('accepted', accepted.reason)


if __name__ == '__main__':
    unittest.main()
