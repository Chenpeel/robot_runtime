"""parallel_3dof_controller 显式执行时长语义测试。"""

import os
import unittest
from pathlib import Path


class TestMotionCommandFieldsSource(unittest.TestCase):
    """验证 solver 与 controller 只传递显式 duration_ms。"""

    def test_controller_node_sets_value_encoding_and_duration_ms(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../parallel_3dof_controller/controller_node.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("motion_msg.value_encoding = 'bus_pulse_us'", source)
        self.assertIn("motion_msg.duration_ms = duration_ms", source)
        self.assertIn("duration_ms = int(cmd['duration_ms'])", source)
        self.assertNotIn("cmd.get('duration_ms', cmd['speed'])", source)
        self.assertNotIn("motion_msg.speed = duration_ms", source)

    def test_solver_command_dict_only_exposes_explicit_duration_ms(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../parallel_3dof_controller/kinematics_solver.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn("speed: int = 100", source)
        self.assertIn("duration_ms = int(speed)", source)
        self.assertIn("'duration_ms': duration_ms", source)
        self.assertNotIn("'speed': duration_ms", source)


if __name__ == '__main__':
    unittest.main()
