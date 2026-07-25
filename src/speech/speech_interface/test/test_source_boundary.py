"""speech_interface 的包、launch 与运行时边界测试。"""

from pathlib import Path
import unittest
from xml.etree import ElementTree


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
NODE_SOURCE = (
    PACKAGE_ROOT / 'speech_interface' / 'speech_interface_node.py'
).read_text(encoding='utf-8')
CONTRACT_SOURCE = (
    PACKAGE_ROOT / 'speech_interface' / 'intent_contract.py'
).read_text(encoding='utf-8')
PACKAGE_SOURCE = (PACKAGE_ROOT / 'package.xml').read_text(encoding='utf-8')
SETUP_SOURCE = (PACKAGE_ROOT / 'setup.py').read_text(encoding='utf-8')
LAUNCH_SOURCE = (
    PACKAGE_ROOT / 'launch' / 'speech_interface.launch.py'
).read_text(encoding='utf-8')


class SpeechInterfaceBoundaryTest(unittest.TestCase):

    def test_runtime_dependencies_stop_at_formal_task_boundary(self):
        manifest = ElementTree.fromstring(PACKAGE_SOURCE)
        dependencies = {
            str(element.text or '').strip()
            for tag in ('depend', 'exec_depend')
            for element in manifest.findall(tag)
        }
        self.assertEqual(
            {
                'rclpy', 'speech_msgs', 'std_msgs', 'task_api_msgs',
                'launch', 'launch_ros',
            },
            dependencies,
        )
        runtime_source = NODE_SOURCE + CONTRACT_SOURCE
        for forbidden in (
                'servo_msgs', 'motion_msgs', 'ServoCommand', 'MotionCommand',
                '/servo/'):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, runtime_source)

    def test_uses_json_parser_structured_topic_and_single_task_client(self):
        self.assertIn('json.loads(', CONTRACT_SOURCE)
        self.assertIn('parse_constant=', CONTRACT_SOURCE)
        self.assertIn('object_pairs_hook=', CONTRACT_SOURCE)
        self.assertEqual(NODE_SOURCE.count('ActionClient('), 1)
        self.assertIn('ExecuteTask', NODE_SOURCE)
        self.assertIn("'/task/execute'", NODE_SOURCE)
        self.assertIn("'/speech/intent'", NODE_SOURCE)
        self.assertIn('SpeechIntent', NODE_SOURCE)

    def test_stable_action_failure_and_result_reasons_are_present(self):
        for reason in (
                'task_action_unavailable',
                'task_goal_rejected',
                'task_goal_send_failed',
                'task_goal_response_failed',
                'task_result_unavailable'):
            with self.subTest(reason=reason):
                self.assertIn(reason, NODE_SOURCE)
        self.assertIn('result.status', NODE_SOURCE)
        self.assertIn('result.reason', NODE_SOURCE)
        self.assertIn('result.recoverable', NODE_SOURCE)

    def test_launch_and_entry_point_expose_only_expected_surface(self):
        self.assertIn('speech_interface_node = ', SETUP_SOURCE)
        self.assertIn("default_value='/speech/intent_input'", LAUNCH_SOURCE)
        self.assertIn("default_value='/speech/intent'", LAUNCH_SOURCE)
        self.assertIn("default_value='/task/execute'", LAUNCH_SOURCE)
        self.assertIn('task_server_wait_timeout_sec', LAUNCH_SOURCE)
        self.assertIn("default_value='2.0'", LAUNCH_SOURCE)
        self.assertIn('minimum_confidence', LAUNCH_SOURCE)
        self.assertIn("default_value='0.6'", LAUNCH_SOURCE)


if __name__ == '__main__':
    unittest.main()
