"""
bridge_node teleop 命令预校验单元测试
"""

import asyncio
import os
import sys
import threading
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(
    0,
    os.path.join(os.path.dirname(__file__), '../../record_load_action'),
)


def _install_bridge_node_test_stubs():
    if 'websockets.server' not in sys.modules:
        websockets_module = types.ModuleType('websockets')
        server_module = types.ModuleType('websockets.server')
        exceptions_module = types.ModuleType('websockets.exceptions')

        async def _serve(*args, **kwargs):
            del args, kwargs
            return None

        class _WebSocketServerProtocol:
            pass

        class _ConnectionClosed(Exception):
            pass

        server_module.serve = _serve
        server_module.WebSocketServerProtocol = _WebSocketServerProtocol
        exceptions_module.ConnectionClosed = _ConnectionClosed
        sys.modules['websockets'] = websockets_module
        sys.modules['websockets.server'] = server_module
        sys.modules['websockets.exceptions'] = exceptions_module

    if 'motion_msgs.msg' not in sys.modules:
        motion_msgs_module = types.ModuleType('motion_msgs')
        motion_msgs_msg_module = types.ModuleType('motion_msgs.msg')

        class _ExecutionState:
            pass

        class _MotionCommand:
            pass

        class _TeleopControl:
            pass

        motion_msgs_msg_module.ExecutionState = _ExecutionState
        motion_msgs_msg_module.MotionCommand = _MotionCommand
        motion_msgs_msg_module.TeleopControl = _TeleopControl
        sys.modules['motion_msgs'] = motion_msgs_module
        sys.modules['motion_msgs.msg'] = motion_msgs_msg_module

    if 'rclpy' not in sys.modules:
        rclpy_module = types.ModuleType('rclpy')
        rclpy_module.init = lambda *args, **kwargs: None
        rclpy_module.shutdown = lambda *args, **kwargs: None

        rclpy_node_module = types.ModuleType('rclpy.node')

        class _Node:
            pass

        rclpy_node_module.Node = _Node

        rclpy_executors_module = types.ModuleType('rclpy.executors')

        class _MultiThreadedExecutor:
            def add_node(self, node):
                del node

            def spin(self):
                return None

        rclpy_executors_module.MultiThreadedExecutor = _MultiThreadedExecutor

        sys.modules['rclpy'] = rclpy_module
        sys.modules['rclpy.node'] = rclpy_node_module
        sys.modules['rclpy.executors'] = rclpy_executors_module

    if 'servo_msgs.msg' not in sys.modules:
        servo_msgs_module = types.ModuleType('servo_msgs')
        servo_msgs_msg_module = types.ModuleType('servo_msgs.msg')

        class _ServoState:
            pass

        servo_msgs_msg_module.ServoState = _ServoState
        sys.modules['servo_msgs'] = servo_msgs_module
        sys.modules['servo_msgs.msg'] = servo_msgs_msg_module

    if 'websocket_bridge.debug_aggregator' not in sys.modules:
        debug_aggregator_module = types.ModuleType(
            'websocket_bridge.debug_aggregator'
        )

        class _DebugAggregator:
            def __init__(self, *args, **kwargs):
                del args, kwargs

            def flush(self):
                return None

        debug_aggregator_module.DebugAggregator = _DebugAggregator
        sys.modules['websocket_bridge.debug_aggregator'] = (
            debug_aggregator_module
        )


_install_bridge_node_test_stubs()

from record_load_action.bvh_runtime import BvhPlaybackRuntime
from record_load_action.bvh_websocket_adapter import (
    BvhPlaybackInvalidRequestError,
)
from record_load_action.bvh_websocket_adapter import BvhWebSocketPlaybackError
from record_load_action.bvh_websocket_adapter import BvhWebSocketPlaybackAdapter
from websocket_bridge.bridge_node import WebSocketROS2Bridge
from websocket_bridge.error_codes import ErrorCode
from websocket_bridge.error_codes import TeleopControlRejectedException
from websocket_bridge.error_codes import WebSocketException


class TestBridgeNodeTeleopGuard(unittest.TestCase):
    def _bridge(self, execution_state=None):
        return types.SimpleNamespace(
            _bvh_gate_lock=threading.RLock(),
            latest_execution_state=execution_state or {},
        )

    @staticmethod
    def _fake_clock():
        class _Now:
            def to_msg(self):
                return 'fake-stamp'

        class _Clock:
            def now(self):
                return _Now()

        return _Clock()

    @staticmethod
    def _fake_publisher():
        class _Publisher:
            def __init__(self):
                self.messages = []

            def publish(self, msg):
                self.messages.append(msg)

        return _Publisher()

    @staticmethod
    def _fake_logger():
        class _Logger:
            def error(self, *args, **kwargs):
                del args, kwargs

            def info(self, *args, **kwargs):
                del args, kwargs

        return _Logger()

    @staticmethod
    def _fake_logger():
        class _Logger:
            def error(self, *args, **kwargs):
                del args, kwargs

        return _Logger()

    def _servo_bridge(self):
        bridge = self._bridge(
            {
                'teleop_holder_id': 'client-a',
                'teleop_lease_id': 'lease-1',
                'teleop_active': True,
                'active_source': 'teleop',
            }
        )
        bridge.teleop_command_pub = self._fake_publisher()
        bridge.bvh_command_pub = self._fake_publisher()
        bridge.get_clock = self._fake_clock
        bridge.get_logger = self._fake_logger
        bridge.debug = False
        bridge._debug_log = lambda *args, **kwargs: None
        bridge._coerce_float = WebSocketROS2Bridge._coerce_float
        bridge._coerce_uint16 = WebSocketROS2Bridge._coerce_uint16
        bridge._map_angle_to_pulse = WebSocketROS2Bridge._map_angle_to_pulse
        bridge._motion_value_encoding_for_servo_type = (
            WebSocketROS2Bridge._motion_value_encoding_for_servo_type
        )
        bridge._resolve_duration_ms = WebSocketROS2Bridge._resolve_duration_ms
        bridge._extract_requester_id = WebSocketROS2Bridge._extract_requester_id
        bridge._extract_lease_id = WebSocketROS2Bridge._extract_lease_id
        bridge._normalize_motion_position = (
            lambda **kwargs: WebSocketROS2Bridge._normalize_motion_position(
                bridge,
                **kwargs,
            )
        )
        bridge._ensure_teleop_command_allowed = (
            lambda requester_id, lease_id: (
                WebSocketROS2Bridge._ensure_teleop_command_allowed(
                    bridge,
                    requester_id,
                    lease_id,
                )
            )
        )
        bridge._build_motion_command = (
            lambda **kwargs: WebSocketROS2Bridge._build_motion_command(
                bridge,
                **kwargs,
            )
        )
        return bridge

    def test_missing_identity_without_active_teleop_is_not_granted(self):
        bridge = self._bridge()

        with self.assertRaises(TeleopControlRejectedException) as ctx:
            WebSocketROS2Bridge._ensure_teleop_command_allowed(bridge, '', '')

        self.assertEqual(
            ctx.exception.details['reason'],
            'teleop_control_not_granted',
        )

    def test_missing_requester_id_is_rejected_for_active_teleop(self):
        bridge = self._bridge(
            {
                'teleop_holder_id': 'client-a',
                'teleop_lease_id': 'lease-1',
                'teleop_active': True,
                'active_source': 'teleop',
            }
        )

        with self.assertRaises(TeleopControlRejectedException) as ctx:
            WebSocketROS2Bridge._ensure_teleop_command_allowed(
                bridge,
                '',
                '',
            )

        self.assertEqual(
            ctx.exception.details['reason'],
            'teleop_requester_id_required',
        )

    def test_missing_lease_id_is_rejected_when_execution_state_has_lease(self):
        bridge = self._bridge(
            {
                'teleop_holder_id': 'client-a',
                'teleop_lease_id': 'lease-1',
                'teleop_active': True,
                'active_source': 'teleop',
            }
        )

        with self.assertRaises(TeleopControlRejectedException) as ctx:
            WebSocketROS2Bridge._ensure_teleop_command_allowed(
                bridge,
                'client-a',
                '',
            )

        self.assertEqual(
            ctx.exception.details['reason'],
            'teleop_control_lease_required',
        )

    def test_matching_requester_and_lease_is_allowed(self):
        bridge = self._bridge(
            {
                'teleop_holder_id': 'client-a',
                'teleop_lease_id': 'lease-1',
                'teleop_active': True,
                'active_source': 'teleop',
            }
        )

        result = WebSocketROS2Bridge._ensure_teleop_command_allowed(
            bridge,
            'client-a',
            'lease-1',
        )

        self.assertIsNone(result)

    def test_handle_servo_command_prefers_duration_ms_and_value_encoding(self):
        bridge = self._servo_bridge()

        asyncio.run(
            WebSocketROS2Bridge.handle_servo_command(
                bridge,
                {
                    "servo_type": "bus",
                    "servo_id": 2,
                    "position": 1500,
                    "value_encoding": "bus_pulse_us",
                    "duration_ms": 45,
                    "speed": 120,
                },
                context={
                    "requester_id": "client-a",
                    "lease_id": "lease-1",
                },
            )
        )

        self.assertEqual(len(bridge.teleop_command_pub.messages), 1)
        msg = bridge.teleop_command_pub.messages[0]
        self.assertEqual(msg.servo_type, "bus")
        self.assertEqual(msg.servo_id, 2)
        self.assertEqual(msg.position, 1500)
        self.assertEqual(msg.value_encoding, "bus_pulse_us")
        self.assertEqual(msg.duration_ms, 45)
        self.assertEqual(msg.speed, 45)
        self.assertEqual(msg.requester_id, "client-a")
        self.assertEqual(msg.lease_id, "lease-1")

    def test_handle_servo_command_keeps_legacy_angle_fallback(self):
        bridge = self._servo_bridge()

        asyncio.run(
            WebSocketROS2Bridge.handle_servo_command(
                bridge,
                {
                    "servo_type": "bus",
                    "servo_id": 1,
                    "position": 90,
                    "speed": 70,
                },
                context={
                    "requester_id": "client-a",
                    "lease_id": "lease-1",
                },
            )
        )

        self.assertEqual(len(bridge.teleop_command_pub.messages), 1)
        msg = bridge.teleop_command_pub.messages[0]
        self.assertEqual(msg.position, 1500)
        self.assertEqual(msg.value_encoding, "bus_pulse_us")
        self.assertEqual(msg.duration_ms, 70)
        self.assertEqual(msg.speed, 70)

    def test_bvh_command_uses_motion_publisher_with_empty_identity(self):
        teleop_pub = self._fake_publisher()
        bvh_pub = self._fake_publisher()
        bridge = types.SimpleNamespace()
        bridge.teleop_command_pub = teleop_pub
        bridge.bvh_command_pub = bvh_pub
        bridge.get_clock = self._fake_clock
        bridge._motion_value_encoding_for_servo_type = (
            WebSocketROS2Bridge._motion_value_encoding_for_servo_type
        )
        bridge._build_motion_command = (
            lambda **kwargs: WebSocketROS2Bridge._build_motion_command(
                bridge,
                **kwargs,
            )
        )

        WebSocketROS2Bridge._publish_bvh_command(
            bridge,
            'bus',
            1,
            1500,
            80,
        )

        self.assertEqual(len(teleop_pub.messages), 0)
        self.assertEqual(len(bvh_pub.messages), 1)
        msg = bvh_pub.messages[0]
        self.assertEqual(msg.servo_type, 'bus')
        self.assertEqual(msg.servo_id, 1)
        self.assertEqual(msg.position, 1500)
        self.assertEqual(msg.value_encoding, 'bus_pulse_us')
        self.assertEqual(msg.duration_ms, 80)
        self.assertEqual(msg.speed, 80)
        self.assertEqual(msg.requester_id, '')
        self.assertEqual(msg.lease_id, '')

    def test_normalize_motion_position_keeps_raw_bus_pulse(self):
        bridge = types.SimpleNamespace()
        bridge._coerce_float = WebSocketROS2Bridge._coerce_float
        bridge._coerce_uint16 = WebSocketROS2Bridge._coerce_uint16
        bridge._map_angle_to_pulse = WebSocketROS2Bridge._map_angle_to_pulse

        position = WebSocketROS2Bridge._normalize_motion_position(
            bridge,
            'bus',
            1500,
            'bus_pulse_us',
        )

        self.assertEqual(position, 1500)

    def test_handle_servo_command_converts_bus_angle_and_prefers_duration_ms(self):
        teleop_pub = self._fake_publisher()
        bridge = self._bridge(
            {
                'teleop_holder_id': 'client-a',
                'teleop_lease_id': 'lease-1',
                'teleop_active': True,
                'active_source': 'teleop',
            }
        )
        bridge.teleop_command_pub = teleop_pub
        bridge.get_clock = self._fake_clock
        bridge.get_logger = self._fake_logger
        bridge.debug = False
        bridge._debug_log = lambda *args, **kwargs: None
        bridge._coerce_float = WebSocketROS2Bridge._coerce_float
        bridge._coerce_uint16 = WebSocketROS2Bridge._coerce_uint16
        bridge._map_angle_to_pulse = WebSocketROS2Bridge._map_angle_to_pulse
        bridge._motion_value_encoding_for_servo_type = (
            WebSocketROS2Bridge._motion_value_encoding_for_servo_type
        )
        bridge._resolve_duration_ms = WebSocketROS2Bridge._resolve_duration_ms
        bridge._normalize_motion_position = (
            lambda servo_type, raw_position, value_encoding: (
                WebSocketROS2Bridge._normalize_motion_position(
                    bridge,
                    servo_type,
                    raw_position,
                    value_encoding,
                )
            )
        )
        bridge._build_motion_command = (
            lambda **kwargs: WebSocketROS2Bridge._build_motion_command(
                bridge,
                **kwargs,
            )
        )
        bridge._extract_requester_id = WebSocketROS2Bridge._extract_requester_id
        bridge._extract_lease_id = WebSocketROS2Bridge._extract_lease_id
        bridge._ensure_teleop_command_allowed = (
            lambda requester_id, lease_id: (
                WebSocketROS2Bridge._ensure_teleop_command_allowed(
                    bridge,
                    requester_id,
                    lease_id,
                )
            )
        )

        asyncio.run(
            WebSocketROS2Bridge.handle_servo_command(
                bridge,
                {
                    'servo_type': 'bus',
                    'servo_id': 1,
                    'position': 45,
                    'speed': 120,
                    'duration_ms': 45,
                },
                context={
                    'requester_id': 'client-a',
                    'lease_id': 'lease-1',
                },
            )
        )

        self.assertEqual(len(teleop_pub.messages), 1)
        msg = teleop_pub.messages[0]
        self.assertEqual(
            msg.position,
            WebSocketROS2Bridge._map_angle_to_pulse(45),
        )
        self.assertEqual(msg.value_encoding, 'bus_pulse_us')
        self.assertEqual(msg.duration_ms, 45)
        self.assertEqual(msg.speed, 45)
        self.assertEqual(msg.requester_id, 'client-a')
        self.assertEqual(msg.lease_id, 'lease-1')

    def test_bvh_play_is_rejected_when_teleop_is_active(self):
        class _Playback:
            def __init__(self):
                self.requests = []

            def handle_play_payload(self, payload):
                self.requests.append(payload)
                raise BvhWebSocketPlaybackError.blocked(
                    payload,
                    RuntimeError('blocked'),
                )

        bridge = self._bridge(
            {
                'teleop_holder_id': 'client-a',
                'teleop_lease_id': 'lease-1',
                'teleop_active': True,
                'active_source': 'teleop',
            }
        )
        bridge.bvh_playback = _Playback()
        bridge._raise_bvh_play_blocked = (
            lambda: WebSocketROS2Bridge._raise_bvh_play_blocked(bridge)
        )

        with self.assertRaises(TeleopControlRejectedException) as ctx:
            asyncio.run(
                WebSocketROS2Bridge.handle_bvh_play(
                    bridge,
                    {'type': 'bvh_play', 'action': 'wave'},
                )
            )

        self.assertEqual(
            ctx.exception.details['reason'],
            'bvh_blocked_by_active_teleop',
        )
        self.assertEqual(
            bridge.bvh_playback.requests,
            [{'type': 'bvh_play', 'action': 'wave'}],
        )

    def test_bvh_play_normalizes_request_and_returns_ack_data(self):
        class _Playback:
            def __init__(self):
                self.payloads = []

            def handle_play_payload(self, payload):
                self.payloads.append(payload)
                return {
                    'status': 'accepted',
                    'action': payload.get('action'),
                    'loop': bool(payload.get('loop', False)),
                }

        bridge = self._bridge()
        bridge.bvh_playback = _Playback()

        result = asyncio.run(
            WebSocketROS2Bridge.handle_bvh_play(
                bridge,
                {
                    'type': 'bvh_play',
                    'action': 'wave',
                    'loop': True,
                    'speed_ms': 40,
                    'playback_rate': 1.25,
                    'frame_ms': 16.7,
                },
            )
        )

        self.assertEqual(
            result,
            {
                'status': 'accepted',
                'action': 'wave',
                'loop': True,
            },
        )
        self.assertEqual(
            bridge.bvh_playback.payloads,
            [{
                'type': 'bvh_play',
                'action': 'wave',
                'loop': True,
                'speed_ms': 40,
                'playback_rate': 1.25,
                'frame_ms': 16.7,
            }],
        )

    def test_bvh_play_rejects_invalid_request_before_runtime(self):
        class _Playback:
            def handle_play_payload(self, payload):
                raise BvhPlaybackInvalidRequestError(payload)

        bridge = self._bridge()
        bridge.bvh_playback = _Playback()

        with self.assertRaises(WebSocketException) as ctx:
            asyncio.run(
                WebSocketROS2Bridge.handle_bvh_play(
                    bridge,
                    {
                        'type': 'bvh_play',
                        'action': {'bvh': 'wave'},
                    },
                )
            )

        self.assertEqual(
            ctx.exception.error_code,
            ErrorCode.INVALID_PARAMETER_VALUE,
        )

    def test_bvh_runtime_failure_keeps_existing_error_contract(self):
        class _Playback:
            def handle_play_payload(self, payload):
                del payload
                raise BvhWebSocketPlaybackError.operation_failed(
                    {'type': 'bvh_play', 'action': 'wave'},
                    RuntimeError('player failed'),
                )

        bridge = self._bridge()
        bridge.bvh_playback = _Playback()

        with self.assertRaises(WebSocketException) as ctx:
            asyncio.run(
                WebSocketROS2Bridge.handle_bvh_play(
                    bridge,
                    {'type': 'bvh_play', 'action': 'wave'},
                )
            )

        self.assertEqual(
            ctx.exception.error_code,
            ErrorCode.ROS_CALLBACK_FAILED,
        )
        self.assertEqual(ctx.exception.message, 'BVH play failed: player failed')
        self.assertEqual(
            ctx.exception.details,
            {
                'payload': {'type': 'bvh_play', 'action': 'wave'},
                'exception': 'player failed',
            },
        )

    def test_bvh_runtime_false_lifecycle_result_maps_to_callback_failure(self):
        class _FalsePlayer:
            def __init__(self, *args, **kwargs):
                del args, kwargs

            def play(self, *args, **kwargs):
                del args, kwargs
                return False

            def stop(self):
                return False

        cases = (
            ('wave', 'Failed to start BVH playback'),
            (None, 'Failed to stop BVH playback'),
        )
        for action, expected_message in cases:
            with self.subTest(action=action):
                bridge = self._bridge()
                bridge.bvh_playback = BvhWebSocketPlaybackAdapter(
                    publish_callback=lambda *args: None,
                    runtime_factory=(
                        lambda **kwargs: BvhPlaybackRuntime(
                            player_factory=_FalsePlayer,
                            **kwargs,
                        )
                    ),
                )

                with self.assertRaises(WebSocketException) as ctx:
                    asyncio.run(
                        WebSocketROS2Bridge.handle_bvh_play(
                            bridge,
                            {'type': 'bvh_play', 'action': action},
                        )
                    )

                self.assertEqual(
                    ctx.exception.error_code,
                    ErrorCode.ROS_CALLBACK_FAILED,
                )
                self.assertEqual(
                    ctx.exception.message,
                    f'BVH play failed: {expected_message}',
                )

    def test_bvh_stop_remains_allowed_while_teleop_is_active(self):
        class _Playback:
            def __init__(self):
                self.payloads = []

            def handle_play_payload(self, payload):
                self.payloads.append(payload)
                return {
                    'status': 'accepted',
                    'action': payload.get('action'),
                    'loop': False,
                }

        bridge = self._bridge(
            {
                'teleop_holder_id': 'client-a',
                'teleop_lease_id': 'lease-1',
                'teleop_active': True,
                'active_source': 'teleop',
            }
        )
        bridge.bvh_playback = _Playback()

        result = asyncio.run(
            WebSocketROS2Bridge.handle_bvh_play(
                bridge,
                {'type': 'bvh_play', 'action': None},
            )
        )

        self.assertEqual(
            bridge.bvh_playback.payloads,
            [{'type': 'bvh_play', 'action': None}],
        )
        self.assertEqual(
            result,
            {'status': 'accepted', 'action': None, 'loop': False},
        )

    def test_execution_state_callback_blocks_bvh_playback_when_teleop_is_active(self):
        class _Playback:
            def __init__(self):
                self.blocked_calls = []

            def set_blocked(self, blocked):
                self.blocked_calls.append(blocked)
                return len(self.blocked_calls) == 1

        class _Logger:
            def error(self, *args, **kwargs):
                del args, kwargs

        bridge = self._bridge()
        bridge.bvh_playback = _Playback()
        bridge.ws_server = None
        bridge.ws_loop = None
        bridge.debug = False
        bridge._debug_log = lambda *args, **kwargs: None
        bridge._teleop_control_is_active = (
            lambda: WebSocketROS2Bridge._teleop_control_is_active(bridge)
        )
        bridge._execution_state_msg_to_dict = (
            lambda msg: WebSocketROS2Bridge._execution_state_msg_to_dict(msg)
        )
        bridge.get_logger = lambda: _Logger()

        msg = types.SimpleNamespace(
            mode='teleop_active',
            active_source='teleop',
            teleop_holder_id='client-a',
            teleop_lease_id='lease-1',
            estop_active=False,
            teleop_active=True,
            motion_active=False,
            teleop_timeout_sec=0.8,
            motion_timeout_sec=0.5,
            teleop_control_remaining_sec=0.4,
            last_teleop_control_action='claim',
            last_teleop_control_accepted=True,
            last_teleop_control_reason='accepted',
            teleop_control_accepted_count=1,
            teleop_control_rejected_count=0,
            teleop_accepted_count=1,
            motion_accepted_count=0,
            teleop_rejected_count=0,
            motion_rejected_count=0,
            last_rejection_reason='',
            stamp=types.SimpleNamespace(sec=1, nanosec=0),
        )

        WebSocketROS2Bridge.execution_state_callback(bridge, msg)

        self.assertEqual(bridge.bvh_playback.blocked_calls, [True])
        self.assertTrue(bridge.latest_execution_state['teleop_active'])

    def test_bvh_request_waits_for_atomic_runtime_block_transition(self):
        class _ObservedRLock:
            def __init__(self):
                self._lock = threading.RLock()
                self.request_waiting = threading.Event()

            def __enter__(self):
                if threading.current_thread().name == 'bvh-request':
                    self.request_waiting.set()
                self._lock.acquire()
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                del exc_type, exc_value, traceback
                self._lock.release()

        class _Playback:
            def __init__(self):
                self.blocked = False
                self.set_blocked_entered = threading.Event()
                self.finish_set_blocked = threading.Event()
                self.handle_called = threading.Event()

            def set_blocked(self, blocked):
                self.set_blocked_entered.set()
                if not self.finish_set_blocked.wait(timeout=2.0):
                    raise RuntimeError('set_blocked coordination timed out')
                self.blocked = bool(blocked)
                return True

            def handle_play_payload(self, payload):
                del payload
                self.handle_called.set()
                if self.blocked:
                    raise BvhWebSocketPlaybackError.blocked(
                        {'type': 'bvh_play', 'action': 'wave'},
                        RuntimeError('blocked'),
                    )
                return {
                    'status': 'accepted',
                    'action': 'wave',
                    'loop': False,
                }

        class _Logger:
            def error(self, *args, **kwargs):
                del args, kwargs

        gate = _ObservedRLock()
        playback = _Playback()
        bridge = self._bridge()
        bridge._bvh_gate_lock = gate
        bridge.bvh_playback = playback
        bridge.ws_server = None
        bridge.ws_loop = None
        bridge.debug = False
        bridge._debug_log = lambda *args, **kwargs: None
        bridge._teleop_control_is_active = (
            lambda: WebSocketROS2Bridge._teleop_control_is_active(bridge)
        )
        bridge._execution_state_msg_to_dict = (
            lambda msg: WebSocketROS2Bridge._execution_state_msg_to_dict(msg)
        )
        bridge._raise_bvh_play_blocked = (
            lambda: WebSocketROS2Bridge._raise_bvh_play_blocked(bridge)
        )
        bridge.get_logger = lambda: _Logger()

        msg = types.SimpleNamespace(
            mode='teleop_active',
            active_source='teleop',
            teleop_holder_id='client-race',
            teleop_lease_id='lease-race',
            estop_active=False,
            teleop_active=True,
            motion_active=False,
            teleop_timeout_sec=0.8,
            motion_timeout_sec=0.5,
            teleop_control_remaining_sec=0.4,
            last_teleop_control_action='claim',
            last_teleop_control_accepted=True,
            last_teleop_control_reason='accepted',
            teleop_control_accepted_count=1,
            teleop_control_rejected_count=0,
            teleop_accepted_count=1,
            motion_accepted_count=0,
            teleop_rejected_count=0,
            motion_rejected_count=0,
            last_rejection_reason='',
            stamp=types.SimpleNamespace(sec=1, nanosec=0),
        )
        outcomes = []

        callback_thread = threading.Thread(
            target=WebSocketROS2Bridge.execution_state_callback,
            args=(bridge, msg),
            name='execution-state',
        )

        def _request_bvh():
            try:
                outcomes.append(
                    asyncio.run(
                        WebSocketROS2Bridge.handle_bvh_play(
                            bridge,
                            {'type': 'bvh_play', 'action': 'wave'},
                        )
                    )
                )
            except Exception as exc:  # 由主线程断言具体拒绝类型和快照。
                outcomes.append(exc)

        request_thread = threading.Thread(
            target=_request_bvh,
            name='bvh-request',
        )

        callback_thread.start()
        self.assertTrue(playback.set_blocked_entered.wait(timeout=1.0))
        request_thread.start()
        try:
            self.assertTrue(gate.request_waiting.wait(timeout=1.0))
            self.assertFalse(playback.handle_called.is_set())
        finally:
            playback.finish_set_blocked.set()

        callback_thread.join(timeout=1.0)
        request_thread.join(timeout=1.0)
        self.assertFalse(callback_thread.is_alive())
        self.assertFalse(request_thread.is_alive())
        self.assertTrue(playback.handle_called.is_set())
        self.assertEqual(len(outcomes), 1)
        self.assertIsInstance(outcomes[0], TeleopControlRejectedException)
        self.assertEqual(
            outcomes[0].details,
            {
                'reason': 'bvh_blocked_by_active_teleop',
                'teleop_holder_id': 'client-race',
                'teleop_lease_id': 'lease-race',
                'teleop_active': True,
                'active_source': 'teleop',
            },
        )

    def test_runtime_block_failure_does_not_skip_execution_state_update(self):
        class _Playback:
            def set_blocked(self, blocked):
                del blocked
                raise RuntimeError('stop failed')

        class _Server:
            def __init__(self):
                self.states = []

            def update_execution_state(self, state):
                self.states.append(state)

        class _Logger:
            def __init__(self):
                self.errors = []

            def error(self, message):
                self.errors.append(message)

        logger = _Logger()
        server = _Server()
        bridge = self._bridge()
        bridge.bvh_playback = _Playback()
        bridge.ws_server = server
        bridge.ws_loop = None
        bridge.debug = False
        bridge._debug_log = lambda *args, **kwargs: None
        bridge._teleop_control_is_active = (
            lambda: WebSocketROS2Bridge._teleop_control_is_active(bridge)
        )
        bridge._execution_state_msg_to_dict = (
            lambda msg: WebSocketROS2Bridge._execution_state_msg_to_dict(msg)
        )
        bridge.get_logger = lambda: logger

        msg = types.SimpleNamespace(
            mode='teleop_active',
            active_source='teleop',
            teleop_holder_id='client-a',
            teleop_lease_id='lease-1',
            estop_active=False,
            teleop_active=True,
            motion_active=False,
            teleop_timeout_sec=0.8,
            motion_timeout_sec=0.5,
            teleop_control_remaining_sec=0.4,
            last_teleop_control_action='claim',
            last_teleop_control_accepted=True,
            last_teleop_control_reason='accepted',
            teleop_control_accepted_count=1,
            teleop_control_rejected_count=0,
            teleop_accepted_count=1,
            motion_accepted_count=0,
            teleop_rejected_count=0,
            motion_rejected_count=0,
            last_rejection_reason='',
            stamp=types.SimpleNamespace(sec=1, nanosec=0),
        )

        WebSocketROS2Bridge.execution_state_callback(bridge, msg)

        self.assertTrue(bridge.latest_execution_state['teleop_active'])
        self.assertEqual(len(server.states), 1)
        self.assertIn('stop failed', logger.errors[0])

    def test_shutdown_retries_runtime_close_before_websocket_cleanup(self):
        calls = []

        class _Runtime:
            def __init__(self):
                self.attempts = 0

            def close(self):
                self.attempts += 1
                calls.append(f'runtime-{self.attempts}')
                if self.attempts == 1:
                    raise RuntimeError('first close failed')

        class _Server:
            async def stop(self):
                calls.append('websocket')

        class _Loop:
            def stop(self):
                return None

            def call_soon_threadsafe(self, callback):
                del callback
                calls.append('loop-stop')

        class _Future:
            def result(self, timeout):
                del timeout

        class _Logger:
            def __init__(self):
                self.errors = []

            def info(self, *args, **kwargs):
                del args, kwargs

            def error(self, message):
                self.errors.append(message)

        def _run_coroutine_threadsafe(coroutine, loop):
            del loop
            asyncio.run(coroutine)
            return _Future()

        logger = _Logger()
        bridge = types.SimpleNamespace(
            bvh_playback=_Runtime(),
            ws_server=_Server(),
            ws_loop=_Loop(),
            ws_thread=None,
            get_logger=lambda: logger,
        )

        with mock.patch.object(
            asyncio,
            'run_coroutine_threadsafe',
            _run_coroutine_threadsafe,
        ):
            WebSocketROS2Bridge.shutdown(bridge)

        self.assertEqual(
            calls,
            ['runtime-1', 'runtime-2', 'websocket', 'loop-stop'],
        )
        self.assertEqual(len(logger.errors), 1)
        self.assertIn('first close failed', logger.errors[0])

    def test_shutdown_reports_incomplete_runtime_close(self):
        class _Runtime:
            def __init__(self):
                self.attempts = 0

            def close(self):
                self.attempts += 1
                raise RuntimeError('close still failing')

        class _Logger:
            def __init__(self):
                self.infos = []
                self.errors = []

            def info(self, message):
                self.infos.append(message)

            def error(self, message):
                self.errors.append(message)

        logger = _Logger()
        runtime = _Runtime()
        bridge = types.SimpleNamespace(
            bvh_playback=runtime,
            ws_server=None,
            ws_loop=None,
            ws_thread=None,
            get_logger=lambda: logger,
        )

        WebSocketROS2Bridge.shutdown(bridge)

        self.assertEqual(runtime.attempts, 2)
        self.assertFalse(any('节点已关闭' in item for item in logger.infos))
        self.assertIn('未确认关闭', logger.errors[-1])


if __name__ == '__main__':
    unittest.main()
