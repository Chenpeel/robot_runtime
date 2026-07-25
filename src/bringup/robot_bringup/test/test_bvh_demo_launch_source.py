"""默认 bringup 与可选动作包的隔离契约测试。"""

import unittest
from pathlib import Path


class TestBvhDemoLaunchSource(unittest.TestCase):
    """验证 robot_bringup 不读取或依赖可选动作包源码。"""

    @staticmethod
    def _package_file(relative_path: str) -> str:
        return (
            Path(__file__).resolve().parents[1] / relative_path
        ).read_text(encoding='utf-8')

    def test_teleop_launch_exposes_only_generic_extension_factory(self):
        source = self._package_file('launch/teleop.launch.py')

        self.assertIn("'bridge_extension_factories'", source)
        self.assertIn("default_value=''", source)
        self.assertNotIn('record_load_action', source)
        self.assertNotIn('bvh_websocket_extension', source)

    def test_manifest_does_not_depend_on_optional_action_package(self):
        manifest = self._package_file('package.xml')

        self.assertNotIn('record_load_action', manifest)


if __name__ == '__main__':
    unittest.main()
