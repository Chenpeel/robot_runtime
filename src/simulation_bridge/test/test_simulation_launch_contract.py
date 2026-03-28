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

    def test_public_simulation_launch_exposes_domain_contract(self):
        public_launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation.launch.py',
            )
        ).read_text(encoding='utf-8')

        self.assertIn("'sim_servo_bridge.launch.py'", public_launch_source)
        self.assertIn("'sim_joint_bridge.launch.py'", public_launch_source)
        self.assertNotIn("'isaac_bridge.launch.py'", public_launch_source)
        self.assertNotIn("'sim_cpp_bridge.launch.py'", public_launch_source)
        self.assertNotIn("'bridge_stack.launch.py'", public_launch_source)
        self._assert_launch_argument_declared(
            public_launch_source,
            'enable_sim_servo_bridge_arg',
        )
        self._assert_launch_argument_declared(
            public_launch_source,
            'enable_sim_joint_bridge_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'enable_isaac_bridge_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'enable_sim_cpp_bridge_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'isaac_command_topic_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'isaac_bridge_debug_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'isaac_state_topic_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'isaac_enforce_limits_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'sim_cpp_bridge_debug_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'sim_joint_cmd_topic_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'sim_joint_state_fb_topic_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'sim_publish_rate_hz_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'servo_command_topic_arg',
        )
        self._assert_launch_argument_not_declared(
            public_launch_source,
            'servo_state_topic_arg',
        )
        self.assertNotIn("'sim_joint_cmd_topic':", public_launch_source)
        self.assertNotIn("'sim_joint_state_fb_topic':", public_launch_source)
        self.assertNotIn("'sim_publish_rate_hz':", public_launch_source)
        self.assertIn(
            "'enable_sim_servo_bridge': LaunchConfiguration('enable_sim_servo_bridge')",
            public_launch_source,
        )
        self.assertIn(
            "'enable_sim_joint_bridge': LaunchConfiguration('enable_sim_joint_bridge')",
            public_launch_source,
        )
        self.assertNotIn("'enable_isaac_bridge':", public_launch_source)
        self.assertNotIn("'enable_sim_cpp_bridge':", public_launch_source)
        self.assertNotIn("'isaac_command_topic':", public_launch_source)
        self.assertNotIn("'isaac_state_topic':", public_launch_source)
        self.assertNotIn("'isaac_enforce_limits':", public_launch_source)
        self.assertNotIn("'isaac_bridge_debug':", public_launch_source)
        self.assertNotIn("'sim_cpp_bridge_debug':", public_launch_source)

    def test_public_simulation_launch_routes_to_cpp_bridge_with_unified_servo_contract(self):
        public_launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation.launch.py',
            )
        ).read_text(encoding='utf-8')
        cpp_launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/sim_joint_bridge.launch.py',
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

        self.assertIn("'sim_joint_bridge.launch.py'", public_launch_source)
        self.assertIn(
            "'enable_sim_joint_bridge': LaunchConfiguration('enable_sim_joint_bridge')",
            public_launch_source,
        )
        self.assertNotIn("'enable_sim_cpp_bridge':", public_launch_source)
        self.assertNotIn("'sim_joint_cmd_topic':", public_launch_source)
        self.assertNotIn("'sim_joint_state_fb_topic':", public_launch_source)
        self.assertNotIn("'sim_publish_rate_hz':", public_launch_source)
        self.assertNotIn(
            "'sim_cpp_bridge_debug': LaunchConfiguration('sim_cpp_bridge_debug')",
            public_launch_source,
        )
        self.assertNotIn("executable='sim_servo_bridge_node'", public_launch_source)
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
        self.assertIn(
            "{'debug': LaunchConfiguration('sim_cpp_bridge_debug')}",
            cpp_launch_source,
        )
        self._assert_launch_argument_declared(
            cpp_launch_source,
            'enable_sim_joint_bridge_arg',
        )
        self._assert_launch_argument_not_declared(
            cpp_launch_source,
            'enable_sim_cpp_bridge_arg',
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
        self.assertNotIn(
            '"joint_cmd_topic", ""',
            cpp_source,
        )
        self.assertNotIn(
            '"joint_state_fb_topic", ""',
            cpp_source,
        )
        self.assertNotIn(
            '"servo_cmd_topic", ""',
            cpp_source,
        )
        self.assertNotIn(
            '"publish_rate_hz", -1.0',
            cpp_source,
        )
        self.assertNotIn(
            'parameter joint_cmd_topic is deprecated',
            cpp_source,
        )
        self.assertNotIn(
            'parameter joint_state_fb_topic is deprecated',
            cpp_source,
        )
        self.assertNotIn(
            'parameter servo_cmd_topic is deprecated',
            cpp_source,
        )
        self.assertNotIn(
            'parameter publish_rate_hz is deprecated',
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

    def test_public_simulation_launch_routes_to_isaac_bridge_with_local_details(self):
        public_launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation.launch.py',
            )
        ).read_text(encoding='utf-8')
        isaac_launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/sim_servo_bridge.launch.py',
            )
        ).read_text(encoding='utf-8')
        isaac_node_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../simulation_bridge/isaac_bridge_node.py',
            )
        ).read_text(encoding='utf-8')

        self.assertIn("'sim_servo_bridge.launch.py'", public_launch_source)
        self.assertIn(
            "'enable_sim_servo_bridge': LaunchConfiguration('enable_sim_servo_bridge')",
            public_launch_source,
        )
        self.assertNotIn("'enable_isaac_bridge':", public_launch_source)
        self.assertNotIn("'isaac_command_topic':", public_launch_source)
        self.assertNotIn("'isaac_state_topic':", public_launch_source)
        self.assertNotIn("'isaac_enforce_limits':", public_launch_source)
        self.assertNotIn("'isaac_bridge_debug':", public_launch_source)
        self.assertNotIn("executable='isaac_bridge_node'", public_launch_source)
        self.assertIn("executable='isaac_bridge_node'", isaac_launch_source)
        self.assertIn(
            "{'debug': LaunchConfiguration('isaac_bridge_debug')}",
            isaac_launch_source,
        )
        self._assert_launch_argument_declared(
            isaac_launch_source,
            'enable_sim_servo_bridge_arg',
        )
        self._assert_launch_argument_not_declared(
            isaac_launch_source,
            'enable_isaac_bridge_arg',
        )
        self.assertIn(
            "{'sim_servo_command_topic': LaunchConfiguration('sim_servo_command_topic')}",
            isaac_launch_source,
        )
        self.assertIn(
            "{'sim_servo_state_topic': LaunchConfiguration('sim_servo_state_topic')}",
            isaac_launch_source,
        )
        self.assertNotIn(
            "{'isaac_command_topic': LaunchConfiguration('isaac_command_topic')}",
            isaac_launch_source,
        )
        self.assertNotIn(
            "{'isaac_state_topic': LaunchConfiguration('isaac_state_topic')}",
            isaac_launch_source,
        )
        self.assertIn(
            "{'enforce_position_limits': LaunchConfiguration('isaac_enforce_limits')}",
            isaac_launch_source,
        )
        self.assertIn(
            "self.declare_parameter('sim_servo_command_topic', '/sim/servo_command')",
            isaac_node_source,
        )
        self.assertIn(
            "self.declare_parameter('sim_servo_state_topic', '/sim/servo_state')",
            isaac_node_source,
        )
        self.assertIn(
            "self.sim_servo_command_topic = self.get_parameter(",
            isaac_node_source,
        )
        self.assertIn(
            "'sim_servo_command_topic'",
            isaac_node_source,
        )
        self.assertIn(
            "self.sim_servo_state_topic = self.get_parameter(",
            isaac_node_source,
        )
        self.assertIn(
            "'sim_servo_state_topic'",
            isaac_node_source,
        )
        self.assertNotIn(
            "self.declare_parameter('isaac_command_topic'",
            isaac_node_source,
        )
        self.assertNotIn(
            "self.declare_parameter('isaac_state_topic'",
            isaac_node_source,
        )


if __name__ == '__main__':
    unittest.main()
