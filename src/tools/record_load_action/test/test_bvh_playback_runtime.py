"""BVH 播放运行时测试。"""

import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from record_load_action.bvh_runtime import BvhPlaybackBlockedError
from record_load_action.bvh_runtime import BvhPlaybackClosedError
from record_load_action.bvh_runtime import BvhPlaybackOperationError
from record_load_action.bvh_runtime import BvhPlaybackRuntime


class _FakePlayer:
    def __init__(self):
        self.play_calls = []
        self.stop_calls = 0
        self.play_result = True
        self.stop_results = []
        self.play_error = None
        self.stop_error = None

    def play(self, action, **kwargs):
        self.play_calls.append((action, kwargs))
        if self.play_error is not None:
            raise self.play_error
        return self.play_result

    def stop(self):
        self.stop_calls += 1
        if self.stop_error is not None:
            raise self.stop_error
        if self.stop_results:
            return self.stop_results.pop(0)
        return True


class _PlayerFactory:
    def __init__(self, player):
        self.player = player
        self.calls = []

    def __call__(self, publish_callback, **kwargs):
        self.calls.append((publish_callback, kwargs))
        return self.player


class BvhPlaybackRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.player = _FakePlayer()
        self.factory = _PlayerFactory(self.player)
        self.publish_callback = lambda *_: None
        self.logger = object()
        self.runtime = BvhPlaybackRuntime(
            self.publish_callback,
            config_path='/tmp/actions.json',
            logger=self.logger,
            player_factory=self.factory,
        )

    def test_runtime_creates_and_owns_player(self):
        self.assertIs(self.runtime.player, self.player)
        self.assertEqual(
            self.factory.calls,
            [(
                self.publish_callback,
                {
                    'config_path': '/tmp/actions.json',
                    'logger': self.logger,
                },
            )],
        )
        self.assertFalse(self.runtime.blocked)
        self.assertFalse(self.runtime.closed)
        self.assertFalse(self.runtime.close_complete)

    def test_apply_request_forwards_all_playback_fields(self):
        request = {
            'action': 'walking',
            'loop': 1,
            'speed_ms': 42,
            'playback_rate': 1.25,
            'frame_ms': 16.7,
        }

        result = self.runtime.apply_request(request)

        self.assertEqual(result, {'action': 'walking', 'loop': True})
        self.assertEqual(
            self.player.play_calls,
            [(
                'walking',
                {
                    'loop': True,
                    'speed_ms': 42,
                    'playback_rate': 1.25,
                    'frame_ms': 16.7,
                },
            )],
        )

    def test_blocked_runtime_rejects_new_playback(self):
        self.runtime.set_blocked(True)

        with self.assertRaises(BvhPlaybackBlockedError):
            self.runtime.apply_request({'action': 'walking'})

        self.assertEqual(self.player.play_calls, [])

    def test_closed_runtime_rejects_new_playback(self):
        self.runtime.close()

        with self.assertRaises(BvhPlaybackClosedError):
            self.runtime.apply_request({'action': 'walking'})

        self.assertEqual(self.player.play_calls, [])

    def test_stop_requests_bypass_blocked_and_closed_states(self):
        self.runtime.set_blocked(True)
        self.assertEqual(
            self.runtime.apply_request({'action': '', 'loop': 1}),
            {'action': '', 'loop': True},
        )
        self.runtime.close()
        self.assertEqual(
            self.runtime.apply_request({'action': 'null'}),
            {'action': 'null', 'loop': False},
        )
        self.assertEqual(
            self.runtime.apply_request({'action': None}),
            {'action': None, 'loop': False},
        )

        # close 复用已经完成的 blocked stop，不重复触发播放器。
        self.assertEqual(self.player.stop_calls, 4)

    def test_block_transition_stops_once_and_unblock_restores_playback(self):
        self.assertTrue(self.runtime.set_blocked(True))
        self.assertFalse(self.runtime.set_blocked(True))
        self.assertEqual(self.player.stop_calls, 1)

        self.assertTrue(self.runtime.set_blocked(False))
        self.assertFalse(self.runtime.set_blocked(False))
        self.runtime.apply_request({'action': 'walking'})
        self.assertTrue(self.runtime.set_blocked(True))

        self.assertTrue(self.runtime.blocked)
        self.assertEqual(self.player.stop_calls, 2)
        self.assertEqual(len(self.player.play_calls), 1)

    def test_same_blocked_state_retries_after_false_stop_result(self):
        self.player.stop_results = [False, True]

        with self.assertRaises(BvhPlaybackOperationError) as caught:
            self.runtime.set_blocked(True)

        self.assertIsNone(caught.exception.cause)
        self.assertTrue(self.runtime.blocked)
        with self.assertRaises(BvhPlaybackBlockedError):
            self.runtime.apply_request({'action': 'walking'})

        # 返回值仍表示 blocked 状态是否变化；本次只补完 stop。
        self.assertFalse(self.runtime.set_blocked(True))
        self.assertFalse(self.runtime.set_blocked(True))
        self.assertEqual(self.player.stop_calls, 2)

    def test_same_blocked_state_retries_after_stop_exception(self):
        cause = RuntimeError('worker did not stop')
        self.player.stop_error = cause

        with self.assertRaises(BvhPlaybackOperationError) as caught:
            self.runtime.set_blocked(True)

        self.assertIs(caught.exception.cause, cause)
        self.assertIs(caught.exception.__cause__, cause)
        self.assertTrue(self.runtime.blocked)

        self.player.stop_error = None
        self.assertFalse(self.runtime.set_blocked(True))
        self.assertFalse(self.runtime.set_blocked(True))
        self.assertEqual(self.player.stop_calls, 2)

    def test_close_is_idempotent_after_success(self):
        self.runtime.close()
        self.runtime.close()

        self.assertTrue(self.runtime.blocked)
        self.assertTrue(self.runtime.closed)
        self.assertTrue(self.runtime.close_complete)
        self.assertEqual(self.player.stop_calls, 1)

    def test_close_reuses_completed_block_stop(self):
        self.runtime.set_blocked(True)

        self.runtime.close()
        self.runtime.close()

        self.assertTrue(self.runtime.blocked)
        self.assertTrue(self.runtime.closed)
        self.assertTrue(self.runtime.close_complete)
        self.assertEqual(self.player.stop_calls, 1)

    def test_close_retries_incomplete_block_stop(self):
        self.player.stop_results = [False, True]

        with self.assertRaises(BvhPlaybackOperationError):
            self.runtime.set_blocked(True)

        self.runtime.close()
        self.runtime.close()

        self.assertTrue(self.runtime.blocked)
        self.assertTrue(self.runtime.closed)
        self.assertTrue(self.runtime.close_complete)
        self.assertEqual(self.player.stop_calls, 2)

    def test_closed_runtime_cannot_be_unblocked(self):
        self.runtime.close()

        self.assertFalse(self.runtime.set_blocked(False))

        self.assertTrue(self.runtime.blocked)
        self.assertTrue(self.runtime.closed)
        self.assertTrue(self.runtime.close_complete)
        self.assertEqual(self.player.stop_calls, 1)

    def test_close_retries_after_stop_failure(self):
        self.player.stop_results = [False, True]

        with self.assertRaises(BvhPlaybackOperationError):
            self.runtime.close()

        self.assertTrue(self.runtime.blocked)
        self.assertTrue(self.runtime.closed)
        self.assertFalse(self.runtime.close_complete)

        self.runtime.close()
        self.runtime.close()

        self.assertTrue(self.runtime.close_complete)
        self.assertEqual(self.player.stop_calls, 2)

    def test_explicit_stop_completes_failed_close(self):
        self.player.stop_results = [False, True]

        with self.assertRaises(BvhPlaybackOperationError):
            self.runtime.close()

        self.runtime.apply_request({'action': None})
        self.runtime.close()

        self.assertTrue(self.runtime.blocked)
        self.assertTrue(self.runtime.closed)
        self.assertTrue(self.runtime.close_complete)
        self.assertEqual(self.player.stop_calls, 2)

    def test_false_play_result_raises_operation_error(self):
        request = {'action': 'walking'}
        self.player.play_result = False

        with self.assertRaises(BvhPlaybackOperationError) as caught:
            self.runtime.apply_request(request)

        self.assertIs(caught.exception.request, request)
        self.assertIsNone(caught.exception.cause)

    def test_play_exception_is_wrapped_with_request_and_cause(self):
        request = {'action': 'walking'}
        cause = ValueError('invalid action')
        self.player.play_error = cause

        with self.assertRaises(BvhPlaybackOperationError) as caught:
            self.runtime.apply_request(request)

        self.assertIs(caught.exception.request, request)
        self.assertIs(caught.exception.cause, cause)
        self.assertIs(caught.exception.__cause__, cause)

    def test_stop_exception_is_wrapped_with_request_and_cause(self):
        request = {'action': None}
        cause = RuntimeError('worker did not stop')
        self.player.stop_error = cause

        with self.assertRaises(BvhPlaybackOperationError) as caught:
            self.runtime.apply_request(request)

        self.assertIs(caught.exception.request, request)
        self.assertIs(caught.exception.cause, cause)
        self.assertIs(caught.exception.__cause__, cause)


if __name__ == '__main__':
    unittest.main()
