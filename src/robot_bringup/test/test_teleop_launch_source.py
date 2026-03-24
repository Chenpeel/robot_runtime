"""
teleop launch 源码契约测试
"""

import os
import unittest
from pathlib import Path


class TestTeleopLaunchSource(unittest.TestCase):
    """验证 teleop.launch.py 的 BVH/demo 接线不会退回 teleop 入口。"""

    def test_bridge_node_routes_bvh_to_motion_topic(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../launch/teleop.launch.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn(
            "{'bvh_command_topic': execution_motion_command_topic}",
            source,
        )
        self.assertIn('Demo/BVH入口:', source)


if __name__ == '__main__':
    unittest.main()
