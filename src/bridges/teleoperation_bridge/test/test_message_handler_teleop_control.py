"""
MessageHandler teleop 控制消息单元测试
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from websocket_bridge.message_handler import MessageHandler
from websocket_bridge.message_handler import MessageType


class TestMessageHandlerTeleopControl(unittest.TestCase):
    """测试 teleop claim/release 消息识别。"""

    def setUp(self):
        self.handler = MessageHandler(debug=False)

    def test_get_message_type_teleop_claim(self):
        msg_type = self.handler.get_message_type({"type": "teleop_claim"})
        self.assertEqual(msg_type, MessageType.TELEOP_CLAIM)

    def test_get_message_type_teleop_release(self):
        msg_type = self.handler.get_message_type({"type": "teleop_release"})
        self.assertEqual(msg_type, MessageType.TELEOP_RELEASE)


if __name__ == '__main__':
    unittest.main()
