"""simulation launch contract 源码测试。"""

import os
import unittest
from pathlib import Path


class TestSimulationLaunchContract(unittest.TestCase):
    """固定仿真域对外 contract 的最小统一语义。"""

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

    def test_cpp_bridge_uses_unified_servo_command_topic_name(self):
        top_launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation_bridges.launch.py',
            )
        ).read_text(encoding='utf-8')
        cpp_launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/sim_cpp_bridge.launch.py',
            )
        ).read_text(encoding='utf-8')
        cpp_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../../sim_servo_bridge_cpp/src/sim_servo_bridge_node.cpp',
            )
        ).read_text(encoding='utf-8')
        default_params = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../../sim_servo_bridge_cpp/config/default_params.yaml',
            )
        ).read_text(encoding='utf-8')

        self.assertIn("'sim_cpp_bridge.launch.py'", top_launch_source)
        self.assertIn(
            "'enable_sim_cpp_bridge': LaunchConfiguration('enable_sim_cpp_bridge')",
            top_launch_source,
        )
        self.assertIn(
            "'sim_joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic')",
            top_launch_source,
        )
        self.assertIn(
            "'sim_joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic')",
            top_launch_source,
        )
        self.assertIn(
            "'sim_publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz')",
            top_launch_source,
        )
        self.assertIn("DEFAULT_DRIVER_COMMAND_TOPIC = '/servo/command'", cpp_launch_source)
        self.assertIn("DEFAULT_DRIVER_STATE_TOPIC = '/servo/state'", cpp_launch_source)
        self.assertIn(
            "{'servo_command_topic': DEFAULT_DRIVER_COMMAND_TOPIC}",
            cpp_launch_source,
        )
        self.assertIn(
            "{'servo_state_topic': DEFAULT_DRIVER_STATE_TOPIC}",
            cpp_launch_source,
        )
        self.assertIn(
            "{'sim_joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic')}",
            cpp_launch_source,
        )
        self.assertIn(
            "{'sim_joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic')}",
            cpp_launch_source,
        )
        self.assertIn(
            "{'sim_publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz')}",
            cpp_launch_source,
        )
        self.assertNotIn(
            "{'servo_command_topic': LaunchConfiguration('servo_command_topic')}",
            cpp_launch_source,
        )
        self.assertNotIn(
            "{'servo_state_topic': LaunchConfiguration('servo_state_topic')}",
            cpp_launch_source,
        )
        self.assertNotIn(
            "{'joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic')}",
            cpp_launch_source,
        )
        self.assertNotIn(
            "{'joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic')}",
            cpp_launch_source,
        )
        self.assertNotIn(
            "{'publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz')}",
            cpp_launch_source,
        )
        self.assertIn("executable='sim_servo_bridge_node'", cpp_launch_source)
        self.assertIn(
            '"sim_joint_cmd_topic", "/sim/joint_cmd"',
            cpp_source,
        )
        self.assertIn(
            '"sim_joint_state_fb_topic", "/sim/joint_state_fb"',
            cpp_source,
        )
        self.assertIn(
            '"sim_publish_rate_hz", 50.0',
            cpp_source,
        )
        self.assertIn(
            '"servo_command_topic", "/servo/command"',
            cpp_source,
        )
        self.assertIn(
            '"joint_cmd_topic", ""',
            cpp_source,
        )
        self.assertIn(
            '"joint_state_fb_topic", ""',
            cpp_source,
        )
        self.assertIn(
            '"servo_cmd_topic", ""',
            cpp_source,
        )
        self.assertIn(
            '"publish_rate_hz", -1.0',
            cpp_source,
        )
        self.assertIn(
            'sim_joint_cmd_topic: "/sim/joint_cmd"',
            default_params,
        )
        self.assertIn(
            'sim_joint_state_fb_topic: "/sim/joint_state_fb"',
            default_params,
        )
        self.assertIn(
            'servo_command_topic: "/servo/command"',
            default_params,
        )
        self.assertIn(
            'sim_publish_rate_hz: 50.0',
            default_params,
        )

    def test_launch_surface_keeps_sim_domain_args_visible(self):
        launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation_bridges.launch.py',
            )
        ).read_text(encoding='utf-8')

        self.assertIn("'sim_cpp_bridge.launch.py'", launch_source)
        self._assert_launch_argument_declared(
            launch_source,
            'sim_joint_cmd_topic_arg',
        )
        self._assert_launch_argument_declared(
            launch_source,
            'sim_joint_state_fb_topic_arg',
        )
        self._assert_launch_argument_declared(
            launch_source,
            'sim_publish_rate_hz_arg',
        )
        self._assert_launch_argument_not_declared(
            launch_source,
            'servo_command_topic_arg',
        )
        self._assert_launch_argument_not_declared(
            launch_source,
            'servo_state_topic_arg',
        )
        self.assertNotIn("executable='sim_servo_bridge_node'", launch_source)

    def test_launch_surface_keeps_isaac_bridge_details_local_to_simulation_bridge(self):
        top_launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation_bridges.launch.py',
            )
        ).read_text(encoding='utf-8')
        isaac_launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/isaac_bridge.launch.py',
            )
        ).read_text(encoding='utf-8')

        self._assert_launch_argument_declared(
            top_launch_source,
            'isaac_command_topic_arg',
        )
        self._assert_launch_argument_declared(
            top_launch_source,
            'isaac_bridge_debug_arg',
        )
        self._assert_launch_argument_declared(
            top_launch_source,
            'isaac_state_topic_arg',
        )
        self._assert_launch_argument_declared(
            top_launch_source,
            'isaac_enforce_limits_arg',
        )
        self._assert_launch_argument_declared(
            top_launch_source,
            'sim_cpp_bridge_debug_arg',
        )
        self.assertIn("'isaac_bridge.launch.py'", top_launch_source)
        self.assertIn(
            "'isaac_command_topic': LaunchConfiguration('isaac_command_topic')",
            top_launch_source,
        )
        self.assertIn(
            "'isaac_state_topic': LaunchConfiguration('isaac_state_topic')",
            top_launch_source,
        )
        self.assertIn(
            "'isaac_enforce_limits': LaunchConfiguration('isaac_enforce_limits')",
            top_launch_source,
        )
        self.assertNotIn("executable='isaac_bridge_node'", top_launch_source)
        self.assertIn("executable='isaac_bridge_node'", isaac_launch_source)
        self.assertIn(
            "{'debug': LaunchConfiguration('isaac_bridge_debug')}",
            isaac_launch_source,
        )
        self.assertIn(
            "{'isaac_command_topic': LaunchConfiguration('isaac_command_topic')}",
            isaac_launch_source,
        )
        self.assertIn(
            "{'isaac_state_topic': LaunchConfiguration('isaac_state_topic')}",
            isaac_launch_source,
        )
        self.assertIn(
            "{'enforce_position_limits': LaunchConfiguration('isaac_enforce_limits')}",
            isaac_launch_source,
        )
        self.assertIn(
            "{'debug': LaunchConfiguration('sim_cpp_bridge_debug')}",
            Path(
                os.path.join(
                    os.path.dirname(__file__),
                    '../launch/sim_cpp_bridge.launch.py',
                )
            ).read_text(encoding='utf-8'),
        )


if __name__ == '__main__':
    unittest.main()
