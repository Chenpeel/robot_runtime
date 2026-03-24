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
        launch_source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation_bridges.launch.py',
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

        self.assertIn("DEFAULT_DRIVER_COMMAND_TOPIC = '/servo/command'", launch_source)
        self.assertIn("DEFAULT_DRIVER_STATE_TOPIC = '/servo/state'", launch_source)
        self.assertIn(
            "{'servo_command_topic': DEFAULT_DRIVER_COMMAND_TOPIC}",
            launch_source,
        )
        self.assertIn(
            "{'servo_state_topic': DEFAULT_DRIVER_STATE_TOPIC}",
            launch_source,
        )
        self.assertIn(
            "{'sim_joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic')}",
            launch_source,
        )
        self.assertIn(
            "{'sim_joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic')}",
            launch_source,
        )
        self.assertIn(
            "{'sim_publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz')}",
            launch_source,
        )
        self.assertNotIn(
            "{'servo_command_topic': LaunchConfiguration('servo_command_topic')}",
            launch_source,
        )
        self.assertNotIn(
            "{'servo_state_topic': LaunchConfiguration('servo_state_topic')}",
            launch_source,
        )
        self.assertNotIn(
            "{'joint_cmd_topic': LaunchConfiguration('sim_joint_cmd_topic')}",
            launch_source,
        )
        self.assertNotIn(
            "{'joint_state_fb_topic': LaunchConfiguration('sim_joint_state_fb_topic')}",
            launch_source,
        )
        self.assertNotIn(
            "{'publish_rate_hz': LaunchConfiguration('sim_publish_rate_hz')}",
            launch_source,
        )
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


if __name__ == '__main__':
    unittest.main()
