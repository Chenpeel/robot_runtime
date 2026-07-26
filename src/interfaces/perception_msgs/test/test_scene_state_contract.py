"""感知消息字段和构建注册合同。"""

import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _fields(relative_path):
    fields = []
    source = (PACKAGE_ROOT / relative_path).read_text(encoding='utf-8')
    for raw_line in source.splitlines():
        declaration = raw_line.split('#', 1)[0].strip()
        if declaration:
            fields.append(declaration)
    return fields


class TestSceneStateContract(unittest.TestCase):
    """防止结构化感知接口发生未审查漂移。"""

    def test_detected_object_fields_are_frozen(self):
        self.assertEqual(
            [
                'string object_id',
                'string label',
                'float32 confidence',
                'float32 x',
                'float32 y',
                'float32 z',
                'float32 size_x',
                'float32 size_y',
                'float32 size_z',
            ],
            _fields('msg/DetectedObject.msg'),
        )

    def test_scene_state_fields_are_frozen(self):
        self.assertEqual(
            [
                'builtin_interfaces/Time stamp',
                'string observation_id',
                'string session_id',
                'string frame_id',
                'DetectedObject[] objects',
                'string status',
                'string reason',
                'bool recoverable',
            ],
            _fields('msg/SceneState.msg'),
        )

    def test_interfaces_are_registered_with_builtin_time_dependency(self):
        cmake_source = (PACKAGE_ROOT / 'CMakeLists.txt').read_text(
            encoding='utf-8'
        )
        package_source = (PACKAGE_ROOT / 'package.xml').read_text(
            encoding='utf-8'
        )
        self.assertIn('"msg/DetectedObject.msg"', cmake_source)
        self.assertIn('"msg/SceneState.msg"', cmake_source)
        self.assertIn('DEPENDENCIES builtin_interfaces', cmake_source)
        self.assertIn('<depend>builtin_interfaces</depend>', package_source)
        self.assertIn('TIMEOUT 60', cmake_source)


if __name__ == '__main__':
    unittest.main()
