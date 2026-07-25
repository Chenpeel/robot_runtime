"""
simulation launch 源码契约测试
"""

import os
import unittest
from pathlib import Path


class TestSimulationLaunchSource(unittest.TestCase):
    """验证 robot_bringup 只暴露最小仿真域入口。"""

    def _read_launch(self, file_name: str) -> str:
        return Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch',
                file_name,
            )
        ).read_text(encoding='utf-8')

    def _assert_launch_argument_declared(self, source: str, variable_name: str):
        self.assertRegex(
            source,
            rf"(?m)^\s*{variable_name}\s*=\s*DeclareLaunchArgument\(",
        )

    def _assert_launch_argument_not_declared(self, source: str, variable_name: str):
        self.assertNotRegex(
            source,
            rf"(?m)^\s*{variable_name}\s*=\s*DeclareLaunchArgument\(",
        )

    def _assert_strings_absent(self, source: str, *patterns: str):
        for pattern in patterns:
            self.assertNotIn(pattern, source)

    def test_simulation_launch_keeps_minimal_simulation_public_surface(self):
        source = self._read_launch('simulation.launch.py')

        self.assertIn("'simulation.launch.py'", source)
        self.assertIn(
            "condition=IfCondition(LaunchConfiguration('enable_simulation'))",
            source,
        )
        self._assert_launch_argument_declared(source, 'enable_simulation_arg')
        for variable_name in (
            'servo_command_topic_arg',
            'servo_state_topic_arg',
            'enable_isaac_bridge_arg',
            'isaac_bridge_debug_arg',
            'isaac_command_topic_arg',
            'isaac_state_topic_arg',
            'isaac_enforce_limits_arg',
            'enable_sim_cpp_bridge_arg',
            'sim_cpp_bridge_debug_arg',
            'sim_joint_bridge_debug_arg',
            'sim_joint_cmd_topic_arg',
            'sim_joint_state_fb_topic_arg',
            'sim_publish_rate_hz_arg',
            'joint_cmd_topic_arg',
            'joint_state_fb_topic_arg',
            'publish_rate_hz_arg',
        ):
            self._assert_launch_argument_not_declared(source, variable_name)

        self._assert_strings_absent(
            source,
            'DEFAULT_DRIVER_COMMAND_TOPIC',
            'DEFAULT_DRIVER_STATE_TOPIC',
            "'servo_command_topic':",
            "'servo_state_topic':",
            "'simulation_bridges.launch.py'",
            "'bridge_stack.launch.py'",
            "'enable_isaac_bridge':",
            "'enable_sim_cpp_bridge':",
            "'isaac_bridge_debug':",
            "'isaac_command_topic':",
            "'isaac_state_topic':",
            "'isaac_enforce_limits':",
            "'sim_joint_bridge_debug':",
            "'sim_cpp_bridge_debug':",
            "'sim_joint_cmd_topic':",
            "'sim_joint_state_fb_topic':",
            "'sim_publish_rate_hz':",
        )

    def test_full_system_keeps_simulation_as_domain_entry(self):
        source = self._read_launch('full_system.launch.py')

        self._assert_launch_argument_declared(source, 'enable_simulation_arg')
        self.assertIn(
            "'enable_simulation': LaunchConfiguration('enable_simulation')",
            source,
        )
        for variable_name in (
            'sim_joint_cmd_topic_arg',
            'sim_joint_state_fb_topic_arg',
            'sim_publish_rate_hz_arg',
            'enable_isaac_bridge_arg',
            'isaac_bridge_debug_arg',
            'isaac_command_topic_arg',
            'isaac_state_topic_arg',
            'isaac_enforce_limits_arg',
            'enable_sim_cpp_bridge_arg',
            'sim_cpp_bridge_debug_arg',
            'sim_joint_bridge_debug_arg',
        ):
            self._assert_launch_argument_not_declared(source, variable_name)

        self._assert_strings_absent(
            source,
            "'servo_command_topic': '/servo/command'",
            "'servo_state_topic': '/servo/state'",
            "'sim_joint_cmd_topic':",
            "'sim_joint_state_fb_topic':",
            "'sim_publish_rate_hz':",
            "'enable_isaac_bridge':",
            "'enable_sim_cpp_bridge':",
            "'isaac_bridge_debug':",
            "'isaac_command_topic':",
            "'isaac_state_topic':",
            "'isaac_enforce_limits':",
            "'sim_joint_bridge_debug':",
            "'sim_cpp_bridge_debug':",
        )

    def test_parallel_multi_system_disables_simulation_domain_with_single_switch(self):
        source = self._read_launch('parallel_3dof_multi_system.launch.py')

        self.assertIn("'enable_simulation': 'false'", source)
        self.assertNotIn("'enable_isaac_bridge': 'false'", source)
        self.assertNotIn("'enable_sim_cpp_bridge': 'false'", source)

    def test_parallel_multi_system_reuses_protocol_cache_default(self):
        source = self._read_launch('parallel_3dof_multi_system.launch.py')

        self.assertIn(
            'from robot_bringup.launch_utils import get_protocol_cache_default',
            source,
        )
        self.assertIn(
            'from robot_bringup.launch_utils import resolve_bus_config_file',
            source,
        )
        self.assertIn(
            'protocol_cache_default = '
            'get_protocol_cache_default(resolve_bus_config_file())',
            source,
        )
        self.assertIn("default_value=protocol_cache_default,", source)
        self.assertNotIn(
            '/root/ros_ws/src/bridges/teleoperation_bridge/config/'
            'bus_protocol_cache.json',
            source,
        )


if __name__ == '__main__':
    unittest.main()
