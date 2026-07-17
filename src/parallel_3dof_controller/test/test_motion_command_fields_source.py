"""parallel_3dof_controller MotionCommand 显式语义字段测试。"""

import os
import unittest
from pathlib import Path


class TestMotionCommandFieldsSource(unittest.TestCase):
    """验证 controller_node 只发布显式 motion 语义字段。"""

    def test_controller_node_sets_value_encoding_and_duration_ms(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../parallel_3dof_controller/controller_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("motion_msg.value_encoding = 'bus_pulse_us'", source)
        self.assertIn("motion_msg.duration_ms = duration_ms", source)
        self.assertIn(
            "duration_ms = int(cmd.get('duration_ms', cmd['speed']))",
            source,
        )
        self.assertNotIn("motion_msg.speed = duration_ms", source)


if __name__ == '__main__':
    unittest.main()
