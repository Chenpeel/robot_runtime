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
            "teleop_active": True,
            "motion_active": False,
            "estop_active": False,
        })

        response = asyncio.run(
            handler.handle_message(json.dumps({"type": "status_query"}))
        )

        response_data = json.loads(response)
        self.assertEqual(
            response_data["execution_state"]["mode"],
            "teleop_active",
        )
        self.assertTrue(response_data["current_status"]["movement_active"])
        self.assertTrue(response_data["current_status"]["listening"])
        self.assertEqual(
            response_data["current_status"]["action"],
            "teleop_active",
        )


if __name__ == '__main__':
    unittest.main()
