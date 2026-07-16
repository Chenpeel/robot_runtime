"""
WebSocketHandler BVH 播放错误映射测试
"""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from websocket_bridge.error_codes import TeleopControlRejectedException
from websocket_bridge.websocket_handler import WebSocketHandler


class TestWebSocketHandlerBvhGuard(unittest.TestCase):
    def setUp(self):
        self.handler = WebSocketHandler(device_id='test_device', debug=False)

    def test_bvh_play_returns_explicit_error_when_teleop_rejected(self):
        async def bvh_callback(payload):
            del payload
            raise TeleopControlRejectedException(
                message='bvh play rejected: bvh_blocked_by_active_teleop',
                details={'reason': 'bvh_blocked_by_active_teleop'},
            )

        self.handler.register_message_handler("bvh_play", bvh_callback)

        response = asyncio.run(
            self.handler.handle_message(
                json.dumps({
                    "type": "bvh_play",
                    "action": "wave",
                }),
            )
        )

        response_data = json.loads(response)
        self.assertEqual(response_data["type"], "error")
        self.assertEqual(response_data["error_name"], "TELEOP_CONTROL_REJECTED")
        self.assertEqual(
            response_data["details"]["reason"],
            "bvh_blocked_by_active_teleop",
        )

    def test_registered_bvh_extension_precedes_servo_content_inference(self):
        received_payloads = []

        async def bvh_callback(payload):
            received_payloads.append(payload)
            return {
                'status': 'accepted',
                'action': payload.get('action'),
                'loop': bool(payload.get('loop', False)),
            }

        self.handler.register_message_handler('bvh_play', bvh_callback)

        response = asyncio.run(
            self.handler.handle_message(
                json.dumps({
                    "type": "bvh_play",
                    "id": "request-1",
                    "action": "wave",
                    "loop": True,
                }),
            )
        )

        response_data = json.loads(response)
        self.assertEqual(response_data["type"], "bvh_play_ack")
        self.assertEqual(response_data["status"], "accepted")
        self.assertEqual(response_data["action"], "wave")
        self.assertTrue(response_data["loop"])
        self.assertEqual(
            received_payloads,
            [{
                "type": "bvh_play",
                "id": "request-1",
                "action": "wave",
                "loop": True,
            }],
        )


if __name__ == '__main__':
    unittest.main()
