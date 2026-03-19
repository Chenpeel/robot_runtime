"""
bridge_node 话题常量测试
"""

import os
import unittest
from pathlib import Path


class TestBridgeNodeTopics(unittest.TestCase):
    """测试 bridge_node 的默认命令话题配置"""

    def test_default_command_topic_constant(self):
        """默认命令输出应进入 execution_manager 的 teleop 入口"""
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn(
            "DEFAULT_COMMAND_TOPIC = '/execution/teleop/command'",
            source
        )

    def test_default_teleop_control_topic_constant(self):
        """默认 teleop 控制权输出应进入 execution_manager 的控制入口"""
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn(
            "DEFAULT_TELEOP_CONTROL_TOPIC = '/execution/teleop/control'",
            source
        )
