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

    def test_execution_state_mapping_includes_teleop_control_feedback(self):
        """execution_state 映射应包含 teleop 控制权反馈字段"""
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("'teleop_control_remaining_sec'", source)
        self.assertIn("'teleop_holder_id'", source)
        self.assertIn("'last_teleop_control_action'", source)
        self.assertIn("'last_teleop_control_accepted'", source)
        self.assertIn("'last_teleop_control_reason'", source)

    def test_teleop_control_publish_includes_requester_id(self):
        """teleop 控制话题发布应包含 requester_id"""
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("msg.requester_id", source)

    def test_motion_command_publish_includes_explicit_semantic_fields(self):
        """MotionCommand 发布应双写新语义字段"""
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("msg.value_encoding", source)
        self.assertIn("msg.duration_ms", source)
