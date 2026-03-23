"""
WebSocketBridgeServer register 回包单元测试
"""

import json
import os
import sys
import types
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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

from websocket_bridge.ws_server import WebSocketBridgeServer
from websocket_bridge.error_codes import TeleopControlRejectedException


class _FakeWebSocket:
    def __init__(self):
        self.sent_messages = []

    async def send(self, message: str):
        self.sent_messages.append(json.loads(message))


class TestWebSocketBridgeServerRegister(unittest.IsolatedAsyncioTestCase):
    async def test_register_response_includes_requester_identity(self):
        server = WebSocketBridgeServer(device_id='test_device', debug=False)
        websocket = _FakeWebSocket()
        server.clients.add(websocket)

        await server._handle_register(
            websocket,
            {"type": "register", "name": "client-a"},
        )

        response_data = websocket.sent_messages[0]
        self.assertEqual(response_data["type"], "connected")
        self.assertEqual(response_data["clientName"], "client-a")
        self.assertIn("clientId", response_data)
        self.assertEqual(
            response_data["requester_id"],
            response_data["clientId"],
        )
        self.assertTrue(response_data["requester_id"])

    async def test_execution_state_broadcast_is_requester_scoped(self):
        server = WebSocketBridgeServer(device_id='test_device', debug=False)
        websocket_a = _FakeWebSocket()
        websocket_b = _FakeWebSocket()
        server.clients.update({websocket_a, websocket_b})
        server.client_info[websocket_a] = {
            "id": "client-a",
            "name": "a",
            "teleop_lease_id": '',
        }
        server.client_info[websocket_b] = {
            "id": "client-b",
            "name": "b",
            "teleop_lease_id": '',
        }
        server.update_execution_state({
            "mode": "teleop_active",
            "active_source": "teleop",
            "teleop_holder_id": "client-a",
            "teleop_lease_id": "lease-1",
            "teleop_active": True,
            "motion_active": False,
            "estop_active": False,
        })

        await server.broadcast_status({
            "type": "execution_state",
            "execution_state": {
                "teleop_holder_id": "client-a",
                "teleop_lease_id": "lease-1",
                "teleop_active": True,
            },
        })

        data_a = websocket_a.sent_messages[0]["data"]
        data_b = websocket_b.sent_messages[0]["data"]

        self.assertEqual(data_a["requester_id"], "client-a")
        self.assertEqual(data_a["teleop_lease_id"], "lease-1")
        self.assertTrue(data_a["known_holder_matches"])
        self.assertFalse(data_a["known_lease_matches"])
        self.assertTrue(data_a["known_teleop_active"])
        self.assertTrue(data_a["control_confirmed"])
        self.assertEqual(data_b["requester_id"], "client-b")
        self.assertEqual(data_b["teleop_lease_id"], "lease-1")
        self.assertFalse(data_b["known_holder_matches"])
        self.assertFalse(data_b["known_lease_matches"])
        self.assertTrue(data_b["known_teleop_active"])
        self.assertFalse(data_b["control_confirmed"])
        self.assertEqual(
            server.client_info[websocket_a]["teleop_lease_id"],
            "lease-1",
        )
        self.assertEqual(server.client_info[websocket_b]["teleop_lease_id"], '')
        self.assertEqual(
            server._build_client_context(websocket_a)["lease_id"],
            "lease-1",
        )

    async def test_disconnect_release_uses_cached_lease_id(self):
        server = WebSocketBridgeServer(device_id='test_device', debug=False)
        websocket = _FakeWebSocket()
        server.client_info[websocket] = {
            "id": "client-a",
            "name": "a",
            "teleop_lease_id": "lease-1",
        }

        received_context = None

        async def release_callback(context):
            nonlocal received_context
            received_context = context

        server.handler.register_teleop_release_handler(release_callback)

        await server._release_teleop_for_client(websocket)

        self.assertEqual(received_context["requester_id"], "client-a")
        self.assertEqual(received_context["lease_id"], "lease-1")

    async def test_direct_servo_command_uses_cached_context(self):
        server = WebSocketBridgeServer(device_id='test_device', debug=False)
        websocket = _FakeWebSocket()
        server.client_info[websocket] = {
            "id": "client-a",
            "name": "a",
            "teleop_lease_id": "lease-1",
        }

        received_command = None
        received_context = None

        async def servo_callback(command, context):
            nonlocal received_command, received_context
            received_command = command
            received_context = context

        server.handler.register_servo_command_handler(servo_callback)

        await server._handle_servo_control_direct(
            {
                "servo_type": "bus",
                "servo_id": 1,
                "position": 1500,
                "speed": 100,
            },
            context=server._build_client_context(websocket),
        )

        self.assertEqual(received_command["servo_id"], 1)
        self.assertEqual(received_context["requester_id"], "client-a")
        self.assertEqual(received_context["lease_id"], "lease-1")

    async def test_direct_servo_command_returns_error_response_on_rejection(self):
        server = WebSocketBridgeServer(device_id='test_device', debug=False)
        websocket = _FakeWebSocket()
        server.client_info[websocket] = {
            "id": "client-a",
            "name": "a",
            "teleop_lease_id": "lease-1",
        }

        async def servo_callback(command, context):
            del command, context
            raise TeleopControlRejectedException(
                message='teleop command rejected: teleop_control_not_holder',
                details={'reason': 'teleop_control_not_holder'},
            )

        server.handler.register_servo_command_handler(servo_callback)

        error_response = await server._handle_servo_control_direct(
            {
                "servo_type": "bus",
                "servo_id": 1,
                "position": 1500,
                "speed": 100,
            },
            context=server._build_client_context(websocket),
        )

        response_data = json.loads(error_response)
        self.assertEqual(response_data["type"], "error")
        self.assertEqual(response_data["error_name"], "TELEOP_CONTROL_REJECTED")
        self.assertEqual(
            response_data["details"]["reason"],
            "teleop_control_not_holder",
        )

    async def test_direct_servo_command_surfaces_lease_required_reason(self):
        server = WebSocketBridgeServer(device_id='test_device', debug=False)
        websocket = _FakeWebSocket()
        server.client_info[websocket] = {
            "id": "client-a",
            "name": "a",
            "teleop_lease_id": '',
        }

        async def servo_callback(command, context):
            del command, context
            raise TeleopControlRejectedException(
                message='teleop command rejected: teleop_control_lease_required',
                details={'reason': 'teleop_control_lease_required'},
            )

        server.handler.register_servo_command_handler(servo_callback)

        error_response = await server._handle_servo_control_direct(
            {
                "servo_type": "bus",
                "servo_id": 1,
                "position": 1500,
                "speed": 100,
            },
            context=server._build_client_context(websocket),
        )

        response_data = json.loads(error_response)
        self.assertEqual(response_data["type"], "error")
        self.assertEqual(response_data["error_name"], "TELEOP_CONTROL_REJECTED")
        self.assertEqual(
            response_data["details"]["reason"],
            "teleop_control_lease_required",
        )


if __name__ == '__main__':
    unittest.main()
