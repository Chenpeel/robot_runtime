"""视觉感知包的依赖、launch 和驱动边界合同。"""

import ast
from pathlib import Path
import unittest
from xml.etree import ElementTree


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
NODE_PATH = PACKAGE_ROOT / 'vision_perception' / 'vision_perception_node.py'
LAUNCH_PATH = PACKAGE_ROOT / 'launch' / 'vision_perception.launch.py'


class TestVisionPerceptionSourceBoundary(unittest.TestCase):

    def test_node_uses_only_structured_perception_output(self):
        source = NODE_PATH.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(NODE_PATH))
        import_roots = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                import_roots.update(
                    alias.name.split('.', 1)[0]
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                import_roots.add(node.module.split('.', 1)[0])

        self.assertIn('perception_msgs', import_roots)
        self.assertIn('std_msgs', import_roots)
        self.assertNotIn('task_api_msgs', import_roots)
        self.assertNotIn('motion_msgs', import_roots)
        self.assertNotIn('servo_msgs', import_roots)
        self.assertNotIn('/task/', source)
        self.assertNotIn('/motion/', source)
        self.assertNotIn('/servo/', source)
        self.assertIn('SceneState', source)
        self.assertIn('scene_topic', source)

    def test_package_manifest_has_no_control_layer_dependency(self):
        manifest = ElementTree.parse(PACKAGE_ROOT / 'package.xml').getroot()
        dependencies = {
            element.text.strip()
            for element in manifest
            if element.tag in {'depend', 'exec_depend'}
            and element.text
        }
        self.assertEqual(
            dependencies,
            {'perception_msgs', 'rclpy', 'std_msgs'},
        )

    def test_launch_exposes_input_and_structured_scene_topics(self):
        source = LAUNCH_PATH.read_text(encoding='utf-8')
        self.assertIn("'input_topic'", source)
        self.assertIn("'/perception/detections_input'", source)
        self.assertIn("'scene_topic'", source)
        self.assertIn("'/perception/scene_state'", source)
        self.assertIn("package='vision_perception'", source)
        self.assertIn("executable='vision_perception_node'", source)


if __name__ == '__main__':
    unittest.main()
