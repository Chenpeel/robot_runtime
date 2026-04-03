"""
teleop launch 源码契约测试
"""

import os
import unittest
from pathlib import Path


class TestTeleopLaunchSource(unittest.TestCase):
    """验证 teleop.launch.py 的 BVH/demo 接线不会退回 teleop 入口。"""

    def _read_launch(self, file_name: str) -> str:
        return Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch',
                file_name,
            )
        ).read_text(encoding='utf-8')

    def test_bridge_node_routes_bvh_to_motion_topic(self):
        source = self._read_launch('teleop.launch.py')

        self.assertIn(
            "{'bvh_command_topic': execution_motion_command_topic}",
            source,
        )
        self.assertIn('Demo/BVH入口:', source)

    def test_teleop_launch_no_longer_exposes_bvh_config_path(self):
        source = self._read_launch('teleop.launch.py')

        self.assertNotIn("bvh_action_file_arg = DeclareLaunchArgument(", source)
        self.assertNotIn(
            "{'bvh_action_file': LaunchConfiguration('bvh_action_file')}",
            source,
        )

    def test_full_system_no_longer_exposes_bvh_config_path(self):
        source = self._read_launch('full_system.launch.py')

        self.assertNotIn("bvh_action_file_arg = DeclareLaunchArgument(", source)
        self.assertNotIn(
            "'bvh_action_file': LaunchConfiguration('bvh_action_file')",
            source,
        )


if __name__ == '__main__':
    unittest.main()
