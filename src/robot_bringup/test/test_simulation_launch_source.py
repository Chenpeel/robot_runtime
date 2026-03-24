"""
simulation launch 源码契约测试
"""

import os
import unittest
from pathlib import Path


class TestSimulationLaunchSource(unittest.TestCase):
    """验证 robot_bringup 不再向外暴露仿真域内部 driver-facing 参数。"""

    def test_simulation_launch_hides_driver_topics_from_public_surface(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/simulation.launch.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn(
            "DEFAULT_DRIVER_COMMAND_TOPIC = '/servo/command'",
            source,
        )
        self.assertIn(
            "DEFAULT_DRIVER_STATE_TOPIC = '/servo/state'",
            source,
        )
        self.assertNotIn("DeclareLaunchArgument(\n        'servo_command_topic'", source)
        self.assertNotIn("DeclareLaunchArgument(\n        'servo_state_topic'", source)
        self.assertIn("'servo_command_topic': DEFAULT_DRIVER_COMMAND_TOPIC", source)
        self.assertIn("'servo_state_topic': DEFAULT_DRIVER_STATE_TOPIC", source)

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


if __name__ == '__main__':
    unittest.main()
