"""
teleop launch 源码契约测试
"""

import os
import unittest
from pathlib import Path


class TestTeleopLaunchSource(unittest.TestCase):
    """验证 teleop.launch.py 仅暴露通用的可选扩展装配面。"""

    def _read_launch(self, file_name: str) -> str:
        return Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch',
                file_name,
            )
        ).read_text(encoding='utf-8')

    def test_bridge_extensions_are_opt_in_by_default(self):
        source = self._read_launch('teleop.launch.py')

        self.assertIn(
            "bridge_extension_factories_arg = DeclareLaunchArgument(",
            source,
        )
        self.assertIn("'bridge_extension_factories'", source)
        self.assertIn("default_value=''", source)
        self.assertIn("'extension_factories': LaunchConfiguration(", source)

    def test_default_teleop_surface_has_no_bvh_wiring(self):
        source = self._read_launch('teleop.launch.py')

        self.assertNotIn("{'bvh_command_topic':", source)
        self.assertNotIn('Demo/BVH入口:', source)
        self.assertIn(
            "{'motion_command_topic': execution_motion_command_topic}",
            source,
        )
        self.assertIn('Motion入口:', source)

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
