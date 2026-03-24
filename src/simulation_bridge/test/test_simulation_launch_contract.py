"""simulation launch contract 源码测试。"""

import os
import unittest
from pathlib import Path


class TestSimulationLaunchContract(unittest.TestCase):
    """固定仿真域对外 contract 的最小统一语义。"""

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

        self.assertIn(
            "{'servo_command_topic': LaunchConfiguration('servo_command_topic')}",
            launch_source,
        )
        self.assertIn(
            '"servo_command_topic", "/servo/command"',
            cpp_source,
        )
        self.assertIn(
            '"servo_cmd_topic", ""',
            cpp_source,
        )
        self.assertIn(
            'servo_command_topic: "/servo/command"',
            default_params,
        )


if __name__ == '__main__':
    unittest.main()
