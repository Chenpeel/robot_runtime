"""Phase 5 语音/感知 bringup 装配合同。"""

import ast
import unittest
from pathlib import Path
from xml.etree import ElementTree


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
CONTEXT_PATH = PACKAGE_ROOT / 'launch' / 'context.launch.py'
FULL_SYSTEM_PATH = PACKAGE_ROOT / 'launch' / 'full_system.launch.py'


def _source(path):
    return path.read_text(encoding='utf-8')


def _launch_defaults(path):
    defaults = {}
    tree = ast.parse(_source(path), filename=str(path))
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'DeclareLaunchArgument'
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            continue
        default = next(
            (
                item.value
                for item in node.keywords
                if item.arg == 'default_value'
            ),
            None,
        )
        if isinstance(default, ast.Constant):
            defaults[str(node.args[0].value)] = default.value
    return defaults


class TestContextLaunchSource(unittest.TestCase):

    def test_context_launch_has_explicit_structured_boundaries(self):
        defaults = _launch_defaults(CONTEXT_PATH)
        source = _source(CONTEXT_PATH)

        self.assertEqual('/speech/intent_input', defaults['speech_input_topic'])
        self.assertEqual('/speech/intent', defaults['speech_intent_topic'])
        self.assertEqual(
            '/perception/detections_input',
            defaults['perception_input_topic'],
        )
        self.assertEqual(
            '/perception/scene_state',
            defaults['perception_scene_topic'],
        )
        self.assertEqual('/task/execute', defaults['task_action_name'])
        self.assertIn("FindPackageShare('speech_interface')", source)
        self.assertIn("FindPackageShare('vision_perception')", source)
        self.assertIn('IfCondition', source)

    def test_full_system_composes_context_as_an_independent_domain(self):
        defaults = _launch_defaults(FULL_SYSTEM_PATH)
        source = _source(FULL_SYSTEM_PATH)

        self.assertEqual('true', defaults['enable_context'])
        self.assertEqual('2.0', defaults['scene_max_age_sec'])
        self.assertEqual('camera_link', defaults['scene_required_frame_id'])
        self.assertEqual('0.6', defaults['scene_target_min_confidence'])
        self.assertEqual('2.0', defaults['scene_target_max_extent_m'])
        self.assertIn("'context.launch.py'", source)
        self.assertIn(
            "condition=IfCondition(LaunchConfiguration('enable_context'))",
            source,
        )
        self.assertIn(
            "'enable_context': LaunchConfiguration('enable_context')",
            source,
        )
        self.assertIn('context_stack', source)

    def test_manifest_declares_real_context_owners(self):
        manifest = ElementTree.parse(PACKAGE_ROOT / 'package.xml').getroot()
        dependencies = {
            str(item.text or '').strip()
            for item in manifest.findall('exec_depend')
        }
        self.assertIn('speech_interface', dependencies)
        self.assertIn('vision_perception', dependencies)


if __name__ == '__main__':
    unittest.main()
