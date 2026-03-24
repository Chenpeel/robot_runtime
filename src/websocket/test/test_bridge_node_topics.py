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

    def test_default_bvh_command_topic_constant(self):
        """BVH/demo 默认应走 motion 执行入口，而不是复用 teleop 入口"""
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn(
            "DEFAULT_BVH_COMMAND_TOPIC = '/execution/motion/command'",
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
        self.assertIn("'teleop_lease_id'", source)
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
        self.assertIn("msg.lease_id", source)

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
        self.assertIn("msg.requester_id", source)
        self.assertIn("msg.lease_id", source)

    def test_bvh_publish_uses_dedicated_motion_topic(self):
        """BVH/demo 应通过独立 motion publisher 下发，避免复用 teleop 入口"""
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("self.bvh_command_pub = self.create_publisher(", source)
        self.assertIn("self.bvh_command_pub.publish(msg)", source)

    def test_teleop_ack_payload_includes_execution_snapshot(self):
        """teleop ack 应携带当前 execution_state 快照语义"""
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("def _build_teleop_ack_payload", source)
        self.assertIn("'teleop_lease_id': current_lease_id", source)
        self.assertIn("'execution_state': execution_state", source)
        self.assertIn("'known_holder_matches': holder_matches", source)
        self.assertIn("'known_lease_matches': lease_matches", source)
        self.assertIn("'known_teleop_active': teleop_active", source)

    def test_teleop_command_is_prevalidated_against_execution_state(self):
        """teleop servo 命令应先按 execution_state 做 holder/lease 预校验"""
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("self._ensure_teleop_command_allowed(", source)
        self.assertIn("TeleopControlRejectedException", source)
        self.assertIn("'teleop_requester_id_required'", source)
        self.assertIn("'teleop_control_not_holder'", source)
        self.assertIn("'teleop_control_lease_required'", source)
        self.assertIn("'teleop_control_lease_mismatch'", source)
