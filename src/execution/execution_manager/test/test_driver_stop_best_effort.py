"""驱动级 stop 的逐执行器 best-effort 行为测试。"""

import asyncio
import os
from threading import RLock
from types import SimpleNamespace
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from execution_manager.execution_manager_node import ExecutionManagerNode
except ModuleNotFoundError as exc:
    raise unittest.SkipTest(f'ROS 2 test dependencies unavailable: {exc}')


class _FakeClient:
    def __init__(self, request_kind):
        self.request_kind = request_kind
        self.requests = []

    def service_is_ready(self):
        return True

    def call_async(self, request):
        self.requests.append(request)
        return self.request_kind, int(request.servo_id)


class _StopHarness:
    def __init__(self, responses):
        self.driver_read_position_client = _FakeClient('read')
        self.driver_execute_command_client = _FakeClient('stop')
        self.arbitrator_lock = RLock()
        self._active_stop_operation_ids = set()
        self.responses = responses

    async def _await_driver_response(self, pending_future):
        return self.responses[pending_future]


class _SnapshotArbitrator:
    @staticmethod
    def snapshot(unused_now_sec):
        return {'estop_active': False}


class _FinishHarness:
    def __init__(self):
        self.arbitrator_lock = RLock()
        self.arbitrator = _SnapshotArbitrator()
        self._active_stop_operation_ids = {7}
        self._latched_stop_fault_reason = ''
        self.release_started = asyncio.Event()
        self.release_allowed = asyncio.Event()
        self.published = []

    @staticmethod
    def _now_sec():
        return 0.0

    async def _request_driver_safety_release(self):
        self.release_started.set()
        await self.release_allowed.wait()
        return True, '', 'release-stamp'

    def _publish_driver_safety(self, active, reason, stamp=None):
        self.published.append((active, reason, stamp))

    def _latch_stop_fault(self, operation_id, reason):
        raise AssertionError((operation_id, reason))


class _ClockNow:
    def __init__(self, nanoseconds):
        self.nanoseconds = nanoseconds


class _Clock:
    def __init__(self, nanoseconds):
        self.nanoseconds = nanoseconds

    def now(self):
        return _ClockNow(self.nanoseconds)


class _StampHarness:
    def __init__(self):
        self.arbitrator_lock = RLock()
        self._last_driver_safety_stamp_ns = 0
        self.clock = _Clock(100)

    def get_clock(self):
        return self.clock


def _protocol_response(protocol='lx'):
    return SimpleNamespace(success=True, protocol=protocol)


def _stop_response():
    return SimpleNamespace(success=True, message='ok')


class TestDriverStopBestEffort(unittest.TestCase):
    def test_stop_token_is_held_until_driver_release_ack(self):
        harness = _FinishHarness()

        async def exercise():
            task = asyncio.create_task(
                ExecutionManagerNode._finish_stop_operation(harness, 7)
            )
            await harness.release_started.wait()
            self.assertEqual({7}, harness._active_stop_operation_ids)
            self.assertEqual([], harness.published)
            harness.release_allowed.set()
            await task

        asyncio.run(exercise())

        self.assertEqual(set(), harness._active_stop_operation_ids)
        self.assertEqual(
            [(False, '', 'release-stamp')],
            harness.published,
        )

    def test_driver_safety_authority_stamp_is_strictly_monotonic(self):
        harness = _StampHarness()

        first = ExecutionManagerNode._next_driver_safety_stamp(harness)
        second = ExecutionManagerNode._next_driver_safety_stamp(harness)

        first_ns = first.sec * 1_000_000_000 + first.nanosec
        second_ns = second.sec * 1_000_000_000 + second.nanosec
        self.assertEqual(100, first_ns)
        self.assertEqual(101, second_ns)

    def test_read_timeout_does_not_skip_remaining_actuator_stops(self):
        harness = _StopHarness({
            ('read', 1): (None, True),
            ('read', 2): (_protocol_response('lx'), False),
            ('read', 3): (_protocol_response('zl'), False),
            ('stop', 2): (_stop_response(), False),
            ('stop', 3): (_stop_response(), False),
        })

        responses, timed_out = asyncio.run(
            ExecutionManagerNode._stop_driver_actuators(
                harness,
                [1, 2, 3],
            )
        )

        self.assertTrue(timed_out)
        self.assertIsNone(responses[0])
        self.assertTrue(responses[1].success)
        self.assertTrue(responses[2].success)
        self.assertEqual(
            [1, 2, 3],
            [request.servo_id for request in harness.driver_read_position_client.requests],
        )
        self.assertEqual(
            [2, 3],
            [request.servo_id for request in harness.driver_execute_command_client.requests],
        )

    def test_write_timeout_does_not_skip_remaining_actuator_stops(self):
        harness = _StopHarness({
            ('read', 1): (_protocol_response('lx'), False),
            ('read', 2): (_protocol_response('zl'), False),
            ('read', 3): (_protocol_response('lx'), False),
            ('stop', 1): (None, True),
            ('stop', 2): (_stop_response(), False),
            ('stop', 3): (_stop_response(), False),
        })

        responses, timed_out = asyncio.run(
            ExecutionManagerNode._stop_driver_actuators(
                harness,
                [1, 2, 3],
            )
        )

        self.assertTrue(timed_out)
        self.assertIsNone(responses[0])
        self.assertTrue(responses[1].success)
        self.assertTrue(responses[2].success)
        self.assertEqual(
            [1, 2, 3],
            [request.servo_id for request in harness.driver_execute_command_client.requests],
        )
        self.assertEqual('move_stop', harness.driver_execute_command_client.requests[0].command)
        self.assertEqual('stop_motion', harness.driver_execute_command_client.requests[1].command)


if __name__ == '__main__':
    unittest.main()
