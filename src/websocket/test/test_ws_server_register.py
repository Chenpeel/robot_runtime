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
        server.client_info[websocket_a] = {"id": "client-a", "name": "a"}
        server.client_info[websocket_b] = {"id": "client-b", "name": "b"}
        server.update_execution_state({
            "mode": "teleop_active",
            "active_source": "teleop",
            "teleop_holder_id": "client-a",
            "teleop_active": True,
            "motion_active": False,
            "estop_active": False,
        })

        await server.broadcast_status({
            "type": "execution_state",
            "execution_state": {
                "teleop_holder_id": "client-a",
                "teleop_active": True,
            },
        })

        data_a = websocket_a.sent_messages[0]["data"]
        data_b = websocket_b.sent_messages[0]["data"]

        self.assertEqual(data_a["requester_id"], "client-a")
        self.assertTrue(data_a["known_holder_matches"])
        self.assertTrue(data_a["known_teleop_active"])
        self.assertTrue(data_a["control_confirmed"])
        self.assertEqual(data_b["requester_id"], "client-b")
        self.assertFalse(data_b["known_holder_matches"])
        self.assertTrue(data_b["known_teleop_active"])
        self.assertFalse(data_b["control_confirmed"])


if __name__ == '__main__':
    unittest.main()
