"""
simulation launch 源码契约测试
"""

import os
import unittest
from pathlib import Path


class TestSimulationLaunchSource(unittest.TestCase):
    """验证 robot_bringup 不再向外暴露仿真域内部 driver-facing 参数。"""

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

    def test_simulation_launch_hides_driver_topics_from_public_surface(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation.launch.py'
            )
        ).read_text(encoding='utf-8')

        self._assert_launch_argument_not_declared(source, 'servo_command_topic_arg')
        self._assert_launch_argument_not_declared(source, 'servo_state_topic_arg')
        self.assertNotIn('DEFAULT_DRIVER_COMMAND_TOPIC', source)
        self.assertNotIn('DEFAULT_DRIVER_STATE_TOPIC', source)
        self.assertNotIn("'servo_command_topic':", source)
        self.assertNotIn("'servo_state_topic':", source)

    def test_simulation_launch_hides_isaac_topic_details_from_public_surface(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation.launch.py'
            )
        ).read_text(encoding='utf-8')

        self._assert_launch_argument_declared(source, 'enable_simulation_arg')
        self._assert_launch_argument_not_declared(source, 'enable_isaac_bridge_arg')
        self._assert_launch_argument_not_declared(source, 'isaac_bridge_debug_arg')
        self._assert_launch_argument_not_declared(source, 'isaac_command_topic_arg')
        self._assert_launch_argument_not_declared(source, 'isaac_state_topic_arg')
        self._assert_launch_argument_not_declared(source, 'isaac_enforce_limits_arg')
        self._assert_launch_argument_not_declared(source, 'enable_sim_cpp_bridge_arg')
        self._assert_launch_argument_not_declared(source, 'sim_cpp_bridge_debug_arg')
        self.assertIn(
            "condition=IfCondition(LaunchConfiguration('enable_simulation'))",
            source,
        )
        self.assertIn("'enable_simulation'", source)
        self.assertNotIn("'enable_isaac_bridge':", source)
        self.assertNotIn("'enable_sim_cpp_bridge':", source)
        self.assertNotIn("'isaac_bridge_debug':", source)
        self.assertNotIn("'isaac_command_topic':", source)
        self.assertNotIn("'isaac_state_topic':", source)
        self.assertNotIn("'isaac_enforce_limits':", source)
        self.assertNotIn("'sim_cpp_bridge_debug':", source)

    def test_simulation_launch_hides_sim_domain_topic_details_from_public_surface(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation.launch.py'
            )
        ).read_text(encoding='utf-8')

        self._assert_launch_argument_not_declared(source, 'sim_joint_cmd_topic_arg')
        self._assert_launch_argument_not_declared(source, 'sim_joint_state_fb_topic_arg')
        self._assert_launch_argument_not_declared(source, 'sim_publish_rate_hz_arg')
        self.assertNotIn("'sim_joint_cmd_topic':", source)
        self.assertNotIn("'sim_joint_state_fb_topic':", source)
        self.assertNotIn("'sim_publish_rate_hz':", source)
        self._assert_launch_argument_not_declared(source, 'joint_cmd_topic_arg')
        self._assert_launch_argument_not_declared(
            source,
            'joint_state_fb_topic_arg',
        )
        self._assert_launch_argument_not_declared(source, 'publish_rate_hz_arg')

    def test_full_system_no_longer_passes_driver_topics_into_simulation_launch(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/full_system.launch.py'
            )
        ).read_text(encoding='utf-8')

        self.assertNotIn(
            "'servo_command_topic': '/servo/command'",
            source,
        )
        self.assertNotIn(
            "'servo_state_topic': '/servo/state'",
            source,
        )

    def test_full_system_hides_isaac_topic_details_from_public_surface(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/full_system.launch.py'
            )
        ).read_text(encoding='utf-8')

        self._assert_launch_argument_declared(source, 'enable_simulation_arg')
        self._assert_launch_argument_not_declared(source, 'enable_isaac_bridge_arg')
        self._assert_launch_argument_not_declared(source, 'isaac_bridge_debug_arg')
        self._assert_launch_argument_not_declared(source, 'isaac_command_topic_arg')
        self._assert_launch_argument_not_declared(source, 'isaac_state_topic_arg')
        self._assert_launch_argument_not_declared(source, 'isaac_enforce_limits_arg')
        self._assert_launch_argument_not_declared(source, 'enable_sim_cpp_bridge_arg')
        self._assert_launch_argument_not_declared(source, 'sim_cpp_bridge_debug_arg')
        self.assertIn(
            "'enable_simulation': LaunchConfiguration('enable_simulation')",
            source,
        )
        self.assertNotIn("'enable_isaac_bridge':", source)
        self.assertNotIn("'enable_sim_cpp_bridge':", source)
        self.assertNotIn("'isaac_bridge_debug':", source)
        self.assertNotIn("'isaac_command_topic':", source)
        self.assertNotIn("'isaac_state_topic':", source)
        self.assertNotIn("'isaac_enforce_limits':", source)
        self.assertNotIn("'sim_cpp_bridge_debug':", source)

    def test_full_system_hides_sim_domain_topic_details_from_public_surface(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/full_system.launch.py'
            )
        ).read_text(encoding='utf-8')

        self._assert_launch_argument_not_declared(source, 'sim_joint_cmd_topic_arg')
        self._assert_launch_argument_not_declared(source, 'sim_joint_state_fb_topic_arg')
        self._assert_launch_argument_not_declared(source, 'sim_publish_rate_hz_arg')
        self.assertNotIn("'sim_joint_cmd_topic':", source)
        self.assertNotIn("'sim_joint_state_fb_topic':", source)
        self.assertNotIn("'sim_publish_rate_hz':", source)

    def test_parallel_multi_system_disables_simulation_domain_with_single_switch(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/parallel_3dof_multi_system.launch.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("'enable_simulation': 'false'", source)
        self.assertNotIn("'enable_isaac_bridge': 'false'", source)
        self.assertNotIn("'enable_sim_cpp_bridge': 'false'", source)


if __name__ == '__main__':
    unittest.main()
