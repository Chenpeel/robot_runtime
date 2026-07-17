"""BVH WebSocket 播放适配测试。"""

import os
import sys
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


if __name__ == '__main__':
    unittest.main()
