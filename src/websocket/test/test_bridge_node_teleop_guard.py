"""
bridge_node teleop 命令预校验单元测试
"""

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _install_bridge_node_test_stubs():
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

    if 'record_load_action.bvh_player' not in sys.modules:
        record_load_action_module = types.ModuleType('record_load_action')
        bvh_player_module = types.ModuleType('record_load_action.bvh_player')

        class _BvhActionPlayer:
            def __init__(self, *args, **kwargs):
                del args, kwargs

            def stop(self):
                return None

        bvh_player_module.BvhActionPlayer = _BvhActionPlayer
        sys.modules['record_load_action'] = record_load_action_module
        sys.modules['record_load_action.bvh_player'] = bvh_player_module

    if 'websocket_bridge.ws_server' not in sys.modules:
        ws_server_module = types.ModuleType('websocket_bridge.ws_server')

        class _WebSocketBridgeServer:
            pass

        ws_server_module.WebSocketBridgeServer = _WebSocketBridgeServer
        sys.modules['websocket_bridge.ws_server'] = ws_server_module

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

from websocket_bridge.bridge_node import WebSocketROS2Bridge
from websocket_bridge.error_codes import TeleopControlRejectedException


class TestBridgeNodeTeleopGuard(unittest.TestCase):
    def _bridge(self, execution_state=None):
        return types.SimpleNamespace(
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


if __name__ == '__main__':
    unittest.main()
