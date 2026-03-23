"""
WebSocketHandler servo_control 上下文单元测试
"""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from websocket_bridge.error_codes import TeleopControlRejectedException
from websocket_bridge.websocket_handler import WebSocketHandler


class TestWebSocketHandlerServoContext(unittest.TestCase):
    def setUp(self):
        self.handler = WebSocketHandler(device_id='test_device', debug=False)

    def test_servo_control_passes_requester_and_lease_context(self):
        received_command = None
        received_context = None

        async def servo_callback(command, context):
            nonlocal received_command, received_context
            received_command = command
            received_context = context

        self.handler.register_servo_command_handler(servo_callback)

        response = asyncio.run(
            self.handler.handle_message(
                json.dumps({
                    "type": "servo_control",
                    "servo_type": "bus",
                    "servo_id": 1,
                    "position": 10,
                    "speed": 120,
                }),
                context={
                    "requester_id": "client-a",
                    "lease_id": "lease-1",
                },
            )
        )

        response_data = json.loads(response)
        self.assertEqual(response_data["type"], "servo_control_ack")
        self.assertEqual(received_command["servo_id"], 1)
        self.assertEqual(received_context["requester_id"], "client-a")
        self.assertEqual(received_context["lease_id"], "lease-1")

    def test_servo_control_returns_explicit_error_when_teleop_rejected(self):
        async def servo_callback(command, context):
            del command, context
            raise TeleopControlRejectedException(
                message='teleop command rejected: teleop_control_not_granted',
                details={'reason': 'teleop_control_not_granted'},
            )

        self.handler.register_servo_command_handler(servo_callback)

        response = asyncio.run(
            self.handler.handle_message(
                json.dumps({
                    "type": "servo_control",
                    "servo_type": "bus",
                    "servo_id": 1,
                    "position": 10,
                    "speed": 120,
                }),
                context={"requester_id": "client-a"},
            )
        )

        response_data = json.loads(response)
        self.assertEqual(response_data["type"], "error")
        self.assertEqual(response_data["error_name"], "TELEOP_CONTROL_REJECTED")
        self.assertEqual(
            response_data["details"]["reason"],
            "teleop_control_not_granted",
        )

    def test_servo_control_surfaces_identity_required_reason(self):
        async def servo_callback(command, context):
            del command, context
            raise TeleopControlRejectedException(
                message='teleop command rejected: teleop_requester_id_required',
                details={'reason': 'teleop_requester_id_required'},
            )

        self.handler.register_servo_command_handler(servo_callback)

        response = asyncio.run(
            self.handler.handle_message(
                json.dumps({
                    "type": "servo_control",
                    "servo_type": "bus",
                    "servo_id": 1,
                    "position": 10,
                    "speed": 120,
                }),
            )
        )

        response_data = json.loads(response)
        self.assertEqual(response_data["type"], "error")
        self.assertEqual(response_data["error_name"], "TELEOP_CONTROL_REJECTED")
        self.assertEqual(
            response_data["details"]["reason"],
            "teleop_requester_id_required",
        )


if __name__ == '__main__':
    unittest.main()
