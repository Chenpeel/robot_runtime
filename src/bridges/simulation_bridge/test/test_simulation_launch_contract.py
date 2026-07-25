"""simulation launch contract 源码测试。"""

import os
import unittest
from pathlib import Path


class TestSimulationLaunchContract(unittest.TestCase):
    """固定仿真域对外 contract 的最小统一语义。"""

    def _read_source(self, *relative_parts: str) -> str:
        return Path(
            os.path.join(
                os.path.dirname(__file__),
                *relative_parts,
            )
        ).read_text(encoding='utf-8')

    def _assert_launch_argument_not_declared(self, source: str, variable_name: str):
        self.assertNotRegex(
            source,
            rf"(?m)^\s*{variable_name}\s*=\s*DeclareLaunchArgument\(",
        )

    def _assert_strings_present(self, source: str, *patterns: str):
        for pattern in patterns:
            self.assertIn(pattern, source)

    def _assert_strings_absent(self, source: str, *patterns: str):
        for pattern in patterns:
            self.assertNotIn(pattern, source)

    def test_public_simulation_launch_stays_minimal_domain_entry(self):
        public_launch_source = self._read_source('../launch/simulation.launch.py')

        self._assert_strings_present(
            public_launch_source,
            "'sim_servo_bridge.launch.py'",
            "'sim_joint_bridge.launch.py'",
        )
        for variable_name in (
            'enable_sim_servo_bridge_arg',
            'enable_sim_joint_bridge_arg',
            'enable_isaac_bridge_arg',
            'enable_sim_cpp_bridge_arg',
            'isaac_command_topic_arg',
            'isaac_bridge_debug_arg',
            'isaac_state_topic_arg',
            'isaac_enforce_limits_arg',
            'sim_cpp_bridge_debug_arg',
            'sim_joint_cmd_topic_arg',
            'sim_joint_state_fb_topic_arg',
            'sim_publish_rate_hz_arg',
            'servo_command_topic_arg',
            'servo_state_topic_arg',
        ):
            self._assert_launch_argument_not_declared(public_launch_source, variable_name)

        self._assert_strings_absent(
            public_launch_source,
            "'isaac_bridge.launch.py'",
            "'sim_cpp_bridge.launch.py'",
            "'bridge_stack.launch.py'",
            "IfCondition(",
            "'enable_sim_servo_bridge':",
            "'enable_sim_joint_bridge':",
            "'enable_isaac_bridge':",
            "'enable_sim_cpp_bridge':",
            "'isaac_command_topic':",
            "'isaac_state_topic':",
            "'isaac_enforce_limits':",
            "'isaac_bridge_debug':",
            "'sim_servo_enforce_limits':",
            "'sim_servo_bridge_debug':",
            "'sim_joint_bridge_debug':",
            "'sim_cpp_bridge_debug':",
            "'sim_joint_cmd_topic':",
            "'sim_joint_state_fb_topic':",
            "'sim_publish_rate_hz':",
            "'servo_command_topic':",
            "'servo_state_topic':",
        )

    def test_sim_joint_bridge_keeps_internal_defaults_inside_child_launch(self):
        cpp_launch_source = self._read_source('../launch/sim_joint_bridge.launch.py')
        cpp_source = self._read_source(
            '../../sim_joint_bridge_cpp/src/sim_joint_bridge_node.cpp',
        )
        default_params = self._read_source(
            '../../sim_joint_bridge_cpp/config/default_params.yaml',
        )

        self._assert_strings_present(
            cpp_launch_source,
            "package='sim_joint_bridge_cpp'",
            "executable='sim_joint_bridge_node'",
            "name='sim_joint_bridge'",
            "FindPackageShare('sim_joint_bridge_cpp')",
            "'default_params.yaml'",
        )
        for variable_name in (
            'enable_sim_joint_bridge_arg',
            'sim_joint_bridge_debug_arg',
            'sim_joint_cmd_topic_arg',
            'sim_joint_state_fb_topic_arg',
            'sim_publish_rate_hz_arg',
            'enable_sim_cpp_bridge_arg',
            'sim_cpp_bridge_debug_arg',
        ):
            self._assert_launch_argument_not_declared(cpp_launch_source, variable_name)

        self._assert_strings_absent(
            cpp_launch_source,
            "package='sim_servo_bridge_cpp'",
            "LaunchConfiguration('enable_sim_joint_bridge')",
            "LaunchConfiguration('sim_joint_bridge_debug')",
            "{'sim_joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic')}",
            "{'sim_joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic')}",
            "{'sim_publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz')}",
            "{'servo_command_topic': DEFAULT_DRIVER_COMMAND_TOPIC}",
            "{'servo_state_topic': DEFAULT_DRIVER_STATE_TOPIC}",
        )
        self._assert_strings_present(
            cpp_source,
            '"sim_joint_cmd_topic", "/sim/joint_cmd"',
            '"sim_joint_state_fb_topic", "/sim/joint_state_fb"',
            '"sim_publish_rate_hz", 50.0',
            '"servo_type", "bus"',
            '"default_speed", 100',
            '"servo_command_topic", "/servo/command"',
            'msg->servo_type != servo_type_',
        )
        self._assert_strings_absent(
            cpp_source,
            '"joint_cmd_topic", ""',
            '"joint_state_fb_topic", ""',
            '"servo_cmd_topic", ""',
            '"publish_rate_hz", -1.0',
            'parameter joint_cmd_topic is deprecated',
            'parameter joint_state_fb_topic is deprecated',
            'parameter servo_cmd_topic is deprecated',
            'parameter publish_rate_hz is deprecated',
        )
        self._assert_strings_present(
            default_params,
            'sim_joint_bridge:',
            'sim_joint_cmd_topic: "/sim/joint_cmd"',
            'sim_joint_state_fb_topic: "/sim/joint_state_fb"',
            'sim_publish_rate_hz: 50.0',
            'servo_command_topic: "/servo/command"',
            'servo_state_topic: "/servo/state"',
            'default_speed: 100',
            'debug: false',
            'servo_type: "bus"',
        )
        self._assert_strings_absent(default_params, 'sim_servo_bridge:')

    def test_sim_servo_bridge_keeps_internal_defaults_inside_child_launch(self):
        sim_servo_launch_source = self._read_source(
            '../launch/sim_servo_bridge.launch.py',
        )
        default_params = self._read_source('../config/default_params.yaml')
        sim_servo_node_source = self._read_source(
            '../simulation_bridge/sim_servo_bridge_node.py',
        )

        self._assert_strings_present(
            sim_servo_launch_source,
            "package='simulation_bridge'",
            "executable='sim_servo_bridge_node'",
            "name='sim_servo_bridge'",
            "FindPackageShare('simulation_bridge')",
            "'default_params.yaml'",
        )
        for variable_name in (
            'enable_sim_servo_bridge_arg',
            'sim_servo_command_topic_arg',
            'sim_servo_state_topic_arg',
            'sim_servo_bridge_debug_arg',
            'sim_servo_enforce_limits_arg',
            'enable_isaac_bridge_arg',
            'isaac_bridge_debug_arg',
            'isaac_enforce_limits_arg',
        ):
            self._assert_launch_argument_not_declared(
                sim_servo_launch_source,
                variable_name,
            )

        self._assert_strings_absent(
            sim_servo_launch_source,
            "LaunchConfiguration('enable_sim_servo_bridge')",
            "LaunchConfiguration('sim_servo_bridge_debug')",
            "LaunchConfiguration('sim_servo_enforce_limits')",
            "{'sim_servo_command_topic': LaunchConfiguration('sim_servo_command_topic')}",
            "{'sim_servo_state_topic': LaunchConfiguration('sim_servo_state_topic')}",
            "{'isaac_command_topic': LaunchConfiguration('isaac_command_topic')}",
            "{'isaac_state_topic': LaunchConfiguration('isaac_state_topic')}",
            "{'servo_command_topic': DEFAULT_DRIVER_COMMAND_TOPIC}",
            "{'servo_state_topic': DEFAULT_DRIVER_STATE_TOPIC}",
            "{'enforce_position_limits': LaunchConfiguration('sim_servo_enforce_limits')}",
        )
        self._assert_strings_present(
            default_params,
            'sim_servo_bridge:',
            'default_speed: 100',
            'servo_command_topic: "/servo/command"',
            'servo_state_topic: "/servo/state"',
            'enforce_position_limits: true',
            'debug: false',
        )
        self._assert_strings_present(
            sim_servo_node_source,
            "self.declare_parameter('sim_servo_command_topic', '/sim/servo_command')",
            "self.declare_parameter('sim_servo_state_topic', '/sim/servo_state')",
            "'sim_servo_command_topic'",
            "'sim_servo_state_topic'",
        )
        self._assert_strings_absent(
            sim_servo_node_source,
            "self.declare_parameter('isaac_command_topic'",
            "self.declare_parameter('isaac_state_topic'",
        )


if __name__ == '__main__':
    unittest.main()
