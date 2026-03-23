"""
WebSocketHandler execution_state 单元测试
"""

import asyncio
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from websocket_bridge.websocket_handler import WebSocketHandler


class TestWebSocketHandlerExecutionState(unittest.TestCase):
    """测试执行层状态快照会进入 WebSocket 状态响应。"""

    def test_status_query_includes_execution_state_snapshot(self):
        handler = WebSocketHandler(device_id='test_device', debug=False)
        handler.update_execution_state({
            "mode": "teleop_active",
            "active_source": "teleop",
            "teleop_holder_id": "client-a",
            "teleop_lease_id": "lease-1",
            "teleop_active": True,
            "motion_active": False,
            "estop_active": False,
            "teleop_control_remaining_sec": 0.42,
            "last_teleop_control_action": "claim",
            "last_teleop_control_accepted": True,
            "last_teleop_control_reason": "accepted",
            "teleop_control_accepted_count": 1,
            "teleop_control_rejected_count": 0,
        })

        response = asyncio.run(
            handler.handle_message(
                json.dumps({"type": "status_query"}),
                context={"requester_id": "client-a", "lease_id": "lease-1"},
            )
        )

        response_data = json.loads(response)
        self.assertEqual(
            response_data["execution_state"]["mode"],
            "teleop_active",
        )
        self.assertEqual(
            response_data["execution_state"]["last_teleop_control_action"],
            "claim",
        )
        self.assertEqual(
            response_data["execution_state"]["teleop_holder_id"],
            "client-a",
        )
        self.assertEqual(
            response_data["execution_state"]["teleop_lease_id"],
            "lease-1",
        )
        self.assertAlmostEqual(
            response_data["execution_state"]["teleop_control_remaining_sec"],
            0.42,
        )
        self.assertTrue(
            response_data["execution_state"]["last_teleop_control_accepted"]
        )
        self.assertTrue(response_data["current_status"]["movement_active"])
        self.assertTrue(response_data["current_status"]["listening"])
        self.assertEqual(
            response_data["current_status"]["action"],
            "teleop_active",
        )
        self.assertEqual(response_data["requester_id"], "client-a")
        self.assertEqual(response_data["teleop_lease_id"], "lease-1")
        self.assertTrue(response_data["known_holder_matches"])
        self.assertTrue(response_data["known_lease_matches"])
        self.assertTrue(response_data["known_teleop_active"])
        self.assertTrue(response_data["control_confirmed"])
        self.assertEqual(
            response_data["confirmation_source"],
            "execution_state",
        )


if __name__ == '__main__':
    unittest.main()
