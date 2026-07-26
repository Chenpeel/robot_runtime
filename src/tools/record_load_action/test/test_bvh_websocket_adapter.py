"""BVH WebSocket 播放适配测试。"""

import os
import sys
import threading
import unittest


sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), '..'),
)

from record_load_action.bvh_runtime import BvhPlaybackBlockedError
from record_load_action.bvh_websocket_adapter import (
    BvhPlaybackInvalidRequestError,
)
from record_load_action.bvh_websocket_adapter import BvhWebSocketPlaybackError
from record_load_action.bvh_websocket_adapter import (
    BvhWebSocketPlaybackAdapter,
)


class _Runtime:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.requests = []
        self.blocked_calls = []
        self.closed = False
        self.exception = None
        self.blocked = False

    def apply_request(self, request):
        self.requests.append(request)
        if self.exception:
            raise self.exception
        return {
            'action': request.get('action'),
            'loop': bool(request.get('loop', False)),
        }

    def set_blocked(self, blocked):
        self.blocked_calls.append(bool(blocked))
        self.blocked = bool(blocked)
        return True

    def close(self):
        self.closed = True


class BvhWebSocketPlaybackAdapterTest(unittest.TestCase):
    def _adapter(self, runtime):
        def _factory(**kwargs):
            runtime.kwargs = kwargs
            return runtime

        return BvhWebSocketPlaybackAdapter(
            publish_callback=lambda *args: None,
            logger='logger',
            runtime_factory=_factory,
        )

    def test_creates_runtime_with_publish_callback_and_logger(self):
        runtime = _Runtime()
        adapter = self._adapter(runtime)

        self.assertIs(adapter.runtime, runtime)
        self.assertIn('publish_callback', runtime.kwargs)
        self.assertEqual(runtime.kwargs['logger'], 'logger')

    def test_normalizes_payload_and_returns_existing_ack_shape(self):
        runtime = _Runtime()
        adapter = self._adapter(runtime)

        result = adapter.handle_play_payload({
            'type': 'bvh_play',
            'action': 'wave',
            'loop': True,
            'speed_ms': 40,
            'playback_rate': 1.25,
            'frame_ms': 16.7,
        })

        self.assertEqual(
            runtime.requests,
            [{
                'action': 'wave',
                'loop': True,
                'speed_ms': 40,
                'playback_rate': 1.25,
                'frame_ms': 16.7,
            }],
        )
        self.assertEqual(
            result,
            {'status': 'accepted', 'action': 'wave', 'loop': True},
        )

    def test_invalid_payload_does_not_reach_runtime(self):
        runtime = _Runtime()
        adapter = self._adapter(runtime)

        with self.assertRaises(BvhPlaybackInvalidRequestError) as ctx:
            adapter.handle_play_payload({
                'type': 'bvh_play',
                'action': {'bvh': 'wave'},
            })

        self.assertEqual(ctx.exception.payload['type'], 'bvh_play')
        self.assertEqual(runtime.requests, [])

    def test_runtime_blocked_error_is_wrapped_for_bridge_mapping(self):
        runtime = _Runtime()
        runtime.exception = BvhPlaybackBlockedError('blocked')
        adapter = self._adapter(runtime)

        with self.assertRaises(BvhWebSocketPlaybackError) as ctx:
            adapter.handle_play_payload({
                'type': 'bvh_play',
                'action': 'wave',
            })

        self.assertEqual(
            ctx.exception.kind,
            BvhWebSocketPlaybackError.BLOCKED,
        )

    def test_runtime_failure_is_wrapped_with_existing_error_details(self):
        runtime = _Runtime()
        runtime.exception = RuntimeError('player failed')
        adapter = self._adapter(runtime)

        with self.assertRaises(BvhWebSocketPlaybackError) as ctx:
            adapter.handle_play_payload({
                'type': 'bvh_play',
                'action': 'wave',
            })

        self.assertEqual(
            ctx.exception.kind,
            BvhWebSocketPlaybackError.OPERATION_FAILED,
        )
        self.assertEqual(ctx.exception.message, 'BVH play failed: player failed')
        self.assertEqual(
            ctx.exception.details,
            {
                'payload': {'type': 'bvh_play', 'action': 'wave'},
                'exception': 'player failed',
            },
        )

    def test_runtime_lifecycle_methods_are_delegated(self):
        runtime = _Runtime()
        adapter = self._adapter(runtime)

        self.assertTrue(adapter.set_blocked(True))
        adapter.close()

        self.assertEqual(runtime.blocked_calls, [True])
        self.assertTrue(runtime.closed)

    def test_blocked_error_keeps_atomic_block_context(self):
        runtime = _Runtime()
        runtime.exception = BvhPlaybackBlockedError('blocked')
        adapter = self._adapter(runtime)
        block_context = {
            'teleop_holder_id': 'client-a',
            'teleop_lease_id': 'lease-1',
        }

        adapter.set_blocked(True, block_context=block_context)

        with self.assertRaises(BvhWebSocketPlaybackError) as ctx:
            adapter.handle_play_payload({
                'type': 'bvh_play',
                'action': 'wave',
            })

        self.assertEqual(ctx.exception.block_context, block_context)
        self.assertIsNot(ctx.exception.block_context, block_context)

    def test_play_waits_for_atomic_block_transition(self):
        class _CoordinatedRuntime(_Runtime):
            def __init__(self):
                super().__init__()
                self.block_entered = threading.Event()
                self.finish_block = threading.Event()
                self.apply_called = threading.Event()

            def set_blocked(self, blocked):
                self.block_entered.set()
                if not self.finish_block.wait(timeout=1.0):
                    raise RuntimeError('block coordination timed out')
                return super().set_blocked(blocked)

            def apply_request(self, request):
                self.apply_called.set()
                if self.blocked:
                    raise BvhPlaybackBlockedError('blocked')
                return super().apply_request(request)

        runtime = _CoordinatedRuntime()
        adapter = self._adapter(runtime)
        block_context = {'teleop_holder_id': 'client-race'}
        outcomes = []

        block_thread = threading.Thread(
            target=lambda: adapter.set_blocked(
                True,
                block_context=block_context,
            ),
        )

        def _play():
            try:
                outcomes.append(adapter.handle_play_payload({
                    'type': 'bvh_play',
                    'action': 'wave',
                }))
            except Exception as exc:
                outcomes.append(exc)

        play_thread = threading.Thread(target=_play)
        block_thread.start()
        self.assertTrue(runtime.block_entered.wait(timeout=1.0))
        play_thread.start()
        try:
            self.assertFalse(runtime.apply_called.wait(timeout=0.02))
        finally:
            runtime.finish_block.set()

        block_thread.join(timeout=1.0)
        play_thread.join(timeout=1.0)

        self.assertFalse(block_thread.is_alive())
        self.assertFalse(play_thread.is_alive())
        self.assertTrue(runtime.apply_called.is_set())
        self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], BvhWebSocketPlaybackError)
        self.assertEqual(
            outcomes[0].kind,
            BvhWebSocketPlaybackError.BLOCKED,
        )
        self.assertEqual(outcomes[0].block_context, block_context)
        self.assertIsNot(outcomes[0].block_context, block_context)

    def test_close_waits_for_active_play_request(self):
        class _CoordinatedRuntime(_Runtime):
            def __init__(self):
                super().__init__()
                self.apply_entered = threading.Event()
                self.finish_apply = threading.Event()
                self.close_called = threading.Event()

            def apply_request(self, request):
                self.apply_entered.set()
                if not self.finish_apply.wait(timeout=1.0):
                    raise RuntimeError('apply coordination timed out')
                return super().apply_request(request)

            def close(self):
                self.close_called.set()
                super().close()

        runtime = _CoordinatedRuntime()
        adapter = self._adapter(runtime)
        play_thread = threading.Thread(
            target=lambda: adapter.handle_play_payload({
                'type': 'bvh_play',
                'action': 'wave',
            }),
        )
        close_thread = threading.Thread(target=adapter.close)

        play_thread.start()
        self.assertTrue(runtime.apply_entered.wait(timeout=1.0))
        close_thread.start()
        try:
            self.assertFalse(runtime.close_called.wait(timeout=0.02))
        finally:
            runtime.finish_apply.set()

        play_thread.join(timeout=1.0)
        close_thread.join(timeout=1.0)

        self.assertFalse(play_thread.is_alive())
        self.assertFalse(close_thread.is_alive())
        self.assertTrue(runtime.close_called.is_set())
        self.assertTrue(runtime.closed)


if __name__ == '__main__':
    unittest.main()
