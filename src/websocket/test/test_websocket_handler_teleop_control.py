"""
WebSocketHandler teleop 控制单元测试
"""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from websocket_bridge.websocket_handler import WebSocketHandler


class TestWebSocketHandlerTeleopControl(unittest.TestCase):
    """测试 teleop 控制权相关 WebSocket 消息。"""

    def setUp(self):
        self.handler = WebSocketHandler(device_id='test_device', debug=False)

    def test_handle_teleop_claim_message(self):
        callback_called = False
        received_context = None

        async def claim_callback(context):
            nonlocal callback_called, received_context
            callback_called = True
            received_context = context
            return {
                "execution_state": {
                    "teleop_holder_id": "client-a",
                    "teleop_active": True,
                },
                "known_holder_matches": True,
                "known_teleop_active": True,
            }

        self.handler.register_teleop_claim_handler(claim_callback)

        response = asyncio.run(
            self.handler.handle_message(
                json.dumps({"type": "teleop_claim"}),
                context={"requester_id": "client-a"},
            )
        )

        response_data = json.loads(response)
        self.assertTrue(callback_called)
        self.assertEqual(received_context["requester_id"], "client-a")
        self.assertEqual(response_data["type"], "teleop_claim_ack")
        self.assertEqual(response_data["status"], "requested")
        self.assertEqual(response_data["requester_id"], "client-a")
        self.assertTrue(response_data["known_holder_matches"])
        self.assertTrue(response_data["known_teleop_active"])
        self.assertEqual(
            response_data["execution_state"]["teleop_holder_id"],
            "client-a",
        )

    def test_handle_teleop_release_message(self):
        callback_called = False
        received_context = None

        async def release_callback(context):
            nonlocal callback_called, received_context
            callback_called = True
            received_context = context
            return {
                "execution_state": {
                    "teleop_holder_id": "client-a",
                    "teleop_active": True,
                },
                "known_holder_matches": True,
                "known_teleop_active": True,
            }

        self.handler.register_teleop_release_handler(release_callback)

        response = asyncio.run(
            self.handler.handle_message(
                json.dumps({"type": "teleop_release"}),
                context={"requester_id": "client-a"},
            )
        )

        response_data = json.loads(response)
        self.assertTrue(callback_called)
        self.assertEqual(received_context["requester_id"], "client-a")
        self.assertEqual(response_data["type"], "teleop_release_ack")
        self.assertEqual(response_data["status"], "requested")
        self.assertEqual(response_data["requester_id"], "client-a")
        self.assertTrue(response_data["known_holder_matches"])
        self.assertTrue(response_data["known_teleop_active"])

    def test_supported_commands_include_teleop_control(self):
        commands = self.handler._get_supported_commands()

        self.assertIn("teleop_claim", commands)
        self.assertIn("teleop_release", commands)

    def test_status_query_includes_requester_scoped_teleop_status(self):
        self.handler.update_execution_state({
            "mode": "teleop_active",
            "active_source": "teleop",
            "teleop_holder_id": "client-a",
            "teleop_active": True,
            "motion_active": False,
            "estop_active": False,
        })

        response = asyncio.run(
            self.handler.handle_message(
                json.dumps({"type": "status_query"}),
                context={"requester_id": "client-a"},
            )
        )

        response_data = json.loads(response)
        self.assertEqual(response_data["requester_id"], "client-a")
        self.assertTrue(response_data["known_holder_matches"])
        self.assertTrue(response_data["known_teleop_active"])
        self.assertTrue(response_data["control_confirmed"])
        self.assertEqual(
            response_data["confirmation_source"],
            "execution_state",
        )


if __name__ == '__main__':
    unittest.main()
