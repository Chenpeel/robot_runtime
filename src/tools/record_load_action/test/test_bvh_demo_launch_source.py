"""BVH WebSocket demo launch 与样例归属测试。"""

import json
from pathlib import Path
import unittest


class TestBvhDemoLaunchSource(unittest.TestCase):
    """验证 BVH demo 只由动作资源包显式装配。"""

    @staticmethod
    def _package_root() -> Path:
        return Path(__file__).resolve().parents[1]

    def test_demo_launch_enables_extension_on_motion_entry(self):
        source = (
            self._package_root()
            / 'launch'
            / 'bvh_websocket_demo.launch.py'
        ).read_text(encoding='utf-8')

        self.assertIn("FindPackageShare('robot_bringup')", source)
        self.assertIn("'teleop.launch.py'", source)
        self.assertIn(
            "'record_load_action.bvh_websocket_extension:create_extension'",
            source,
        )
        self.assertIn(
            "'execution_motion_command_topic': '/execution/motion/command'",
            source,
        )
        self.assertNotIn('bvh_action_file', source)

    def test_installed_request_sample_uses_known_direct_action(self):
        root = self._package_root()
        sample = json.loads(
            (root / 'config' / 'bvh_play_request.json').read_text(
                encoding='utf-8'
            )
        )
        action_map = json.loads(
            (root / 'config' / 'bvh_action_map.json').read_text(
                encoding='utf-8'
            )
        )
        setup_source = (root / 'setup.py').read_text(encoding='utf-8')

        self.assertEqual(sample['type'], 'bvh_play')
        self.assertIn(sample['action'], action_map['bvh_list'])
        self.assertNotIsInstance(sample['action'], dict)
        self.assertNotIn('bvh', sample)
        self.assertIn("glob('config/*.json')", setup_source)
        self.assertIn("glob('launch/*.launch.py')", setup_source)


if __name__ == '__main__':
    unittest.main()
