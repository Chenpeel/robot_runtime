"""BVH 可选 WebSocket capability 测试。"""

import asyncio
import json
import os
import sys
import types
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), '../../websocket'),
)


if 'motion_msgs.msg' not in sys.modules:
    motion_msgs_module = types.ModuleType('motion_msgs')
    motion_msgs_msg_module = types.ModuleType('motion_msgs.msg')

    class _MotionCommand:
        pass

    motion_msgs_msg_module.MotionCommand = _MotionCommand
    sys.modules['motion_msgs'] = motion_msgs_module
    sys.modules['motion_msgs.msg'] = motion_msgs_msg_module


from record_load_action.bvh_websocket_adapter import BvhWebSocketPlaybackError
from record_load_action.bvh_websocket_extension import BvhWebSocketExtension
from record_load_action.bvh_websocket_extension import create_extension
from websocket_bridge.error_codes import ErrorCode
from websocket_bridge.error_codes import TeleopControlRejectedException
from websocket_bridge.error_codes import WebSocketException
from websocket_bridge.websocket_handler import WebSocketHandler


class _Logger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)


class _Publisher:
    def __init__(self):
        self.messages = []

    def publish(self, message):
        self.messages.append(message)


class _Bridge:
    def __init__(self, parameters=None):
        self.parameters = dict(parameters or {})
        self.declarations = []
        self.publisher_calls = []
        self.publisher = _Publisher()
        self.logger = _Logger()

    def has_parameter(self, name):
        return name in self.parameters

    def declare_parameter(self, name, default_value):
        if name in self.parameters:
            raise RuntimeError(f'parameter already declared: {name}')
        self.parameters[name] = default_value
        self.declarations.append((name, default_value))

    def get_parameter(self, name):
        return types.SimpleNamespace(value=self.parameters[name])

    def create_publisher(self, message_type, topic, qos):
        self.publisher_calls.append((message_type, topic, qos))
        return self.publisher

    def get_logger(self):
        return self.logger

    @staticmethod
    def get_clock():
        now = types.SimpleNamespace(to_msg=lambda: 'fake-stamp')
        return types.SimpleNamespace(now=lambda: now)


class _Adapter:
    message_type = 'bvh_play'

    def __init__(self, publish_callback, logger):
        self.publish_callback = publish_callback
        self.logger = logger
        self.result = {
            'status': 'accepted',
            'action': 'wave',
            'loop': False,
        }
        self.exception = None
        self.blocked_calls = []
        self.block_context = None
        self.close_calls = 0
        self.close_exception = None

    def handle_play_payload(self, payload):
        if self.exception is not None:
            raise self.exception
        return dict(self.result)

    def set_blocked(self, blocked, block_context=None):
        self.blocked_calls.append((bool(blocked), block_context))
        self.block_context = block_context
        return True

    def close(self):
        self.close_calls += 1
        if self.close_exception is not None:
            raise self.close_exception


class _Server:
    def __init__(self):
        self.callbacks = []

    def set_message_callback(self, message_type, callback):
        self.callbacks.append((message_type, callback))


class _HandlerServer:
    def __init__(self, handler):
        self.handler = handler

    def set_message_callback(self, message_type, callback):
        self.handler.register_message_handler(message_type, callback)


class BvhWebSocketExtensionTest(unittest.TestCase):
    @staticmethod
    def _extension(bridge=None):
        return BvhWebSocketExtension(
            bridge or _Bridge(),
            adapter_factory=_Adapter,
        )

    def test_factory_returns_core_extension_contract(self):
        bridge = _Bridge()

        extension = create_extension(bridge)
        try:
            self.assertTrue(callable(extension.register_message_handlers))
            self.assertTrue(callable(extension.on_execution_state))
            self.assertTrue(callable(extension.close))
        finally:
            extension.close()

    def test_declares_default_motion_topic_and_honors_existing_override(self):
        default_bridge = _Bridge()
        default_extension = self._extension(default_bridge)

        self.assertEqual(
            default_bridge.declarations,
            [('bvh_command_topic', '/execution/motion/command')],
        )
        self.assertEqual(
            default_bridge.publisher_calls[0][1:],
            ('/execution/motion/command', 10),
        )
        self.assertEqual(
            default_extension.command_topic,
            '/execution/motion/command',
        )

        custom_bridge = _Bridge({'bvh_command_topic': '/demo/motion'})
        custom_extension = self._extension(custom_bridge)

        self.assertEqual(custom_bridge.declarations, [])
        self.assertEqual(custom_extension.command_topic, '/demo/motion')
        self.assertEqual(
            custom_bridge.publisher_calls[0][1:],
            ('/demo/motion', 10),
        )

    def test_registers_explicit_bvh_play_handler(self):
        extension = self._extension()
        server = _Server()

        extension.register_message_handlers(server)

        self.assertEqual(len(server.callbacks), 1)
        self.assertEqual(server.callbacks[0][0], 'bvh_play')
        self.assertIs(server.callbacks[0][1].__self__, extension)

    def test_registered_handler_keeps_existing_ack_contract(self):
        extension = self._extension()
        handler = WebSocketHandler(device_id='robot', debug=False)
        extension.register_message_handlers(_HandlerServer(handler))

        response = asyncio.run(handler.handle_message(json.dumps({
            'type': 'bvh_play',
            'action': 'wave',
        })))
        payload = json.loads(response)

        self.assertEqual(payload['type'], 'bvh_play_ack')
        self.assertEqual(payload['status'], 'accepted')
        self.assertEqual(payload['action'], 'wave')
        self.assertFalse(payload['loop'])

    def test_publishes_motion_command_with_explicit_semantics(self):
        bridge = _Bridge()
        extension = self._extension(bridge)

        cases = (
            ('bus', 'bus_pulse_us'),
            ('pca', 'pca_tick'),
        )
        for servo_type, expected_encoding in cases:
            with self.subTest(servo_type=servo_type):
                extension.playback.publish_callback(
                    servo_type,
                    7,
                    1500,
                    42,
                )
                msg = bridge.publisher.messages[-1]
                self.assertEqual(msg.servo_type, servo_type)
                self.assertEqual(msg.servo_id, 7)
                self.assertEqual(msg.position, 1500)
                self.assertEqual(msg.value_encoding, expected_encoding)
                self.assertEqual(msg.duration_ms, 42)
                self.assertEqual(msg.speed, 42)
                self.assertEqual(msg.requester_id, '')
                self.assertEqual(msg.lease_id, '')
                self.assertEqual(msg.stamp, 'fake-stamp')

    def test_invalid_request_maps_to_invalid_parameter_value(self):
        extension = self._extension()
        extension.playback.exception = (
            BvhWebSocketPlaybackError.invalid_request({'type': 'bvh_play'})
        )

        with self.assertRaises(WebSocketException) as ctx:
            asyncio.run(extension.handle_play_payload({'type': 'bvh_play'}))

        self.assertEqual(
            ctx.exception.error_code,
            ErrorCode.INVALID_PARAMETER_VALUE,
        )
        self.assertEqual(
            ctx.exception.details,
            {'received_data': {'type': 'bvh_play'}},
        )

    def test_operation_failure_maps_to_ros_callback_failed(self):
        extension = self._extension()
        payload = {'type': 'bvh_play', 'action': 'wave'}
        extension.playback.exception = (
            BvhWebSocketPlaybackError.operation_failed(
                payload,
                RuntimeError('player failed'),
            )
        )

        with self.assertRaises(WebSocketException) as ctx:
            asyncio.run(extension.handle_play_payload(payload))

        self.assertEqual(
            ctx.exception.error_code,
            ErrorCode.ROS_CALLBACK_FAILED,
        )
        self.assertEqual(ctx.exception.message, 'BVH play failed: player failed')
        self.assertEqual(
            ctx.exception.details,
            {'payload': payload, 'exception': 'player failed'},
        )

    def test_teleop_interlock_rejects_with_atomic_state_snapshot(self):
        extension = self._extension()
        state = {
            'teleop_holder_id': 'client-a',
            'teleop_lease_id': 'lease-1',
            'teleop_active': True,
            'active_source': 'teleop',
        }

        self.assertTrue(extension.on_execution_state(state))
        state['teleop_holder_id'] = 'mutated-after-submit'
        extension.playback.exception = BvhWebSocketPlaybackError.blocked(
            {'type': 'bvh_play', 'action': 'wave'},
            RuntimeError('blocked'),
            block_context=extension.playback.block_context,
        )

        with self.assertRaises(TeleopControlRejectedException) as ctx:
            asyncio.run(extension.handle_play_payload({
                'type': 'bvh_play',
                'action': 'wave',
            }))

        self.assertEqual(
            ctx.exception.details,
            {
                'reason': 'bvh_blocked_by_active_teleop',
                'teleop_holder_id': 'client-a',
                'teleop_lease_id': 'lease-1',
                'teleop_active': True,
                'active_source': 'teleop',
            },
        )

    def test_non_teleop_state_unblocks_capability(self):
        extension = self._extension()

        extension.on_execution_state({
            'teleop_active': True,
            'active_source': 'teleop',
        })
        extension.on_execution_state({
            'teleop_active': False,
            'active_source': 'motion',
        })

        self.assertEqual(extension.playback.blocked_calls[0][0], True)
        self.assertEqual(extension.playback.blocked_calls[1], (False, None))

    def test_interlock_failure_is_logged_without_escaping(self):
        extension = self._extension()

        def _raise_stop_failure(*args, **kwargs):
            del args, kwargs
            raise RuntimeError('stop failed')

        extension.playback.set_blocked = _raise_stop_failure

        result = extension.on_execution_state({
            'teleop_active': True,
            'active_source': 'teleop',
        })

        self.assertFalse(result)
        self.assertIn('stop failed', extension.playback.logger.errors[0])

    def test_close_delegates_once_and_leaves_retry_to_core(self):
        extension = self._extension()
        extension.playback.close_exception = RuntimeError('close failed')

        with self.assertRaisesRegex(RuntimeError, 'close failed'):
            extension.close()

        self.assertEqual(extension.playback.close_calls, 1)


if __name__ == '__main__':
    unittest.main()
