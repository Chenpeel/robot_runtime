"""任务桥包的源码边界测试。"""

from pathlib import Path
import unittest
from xml.etree import ElementTree


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
NODE_SOURCE = (
    PACKAGE_ROOT / 'task_service_bridge' / 'bridge_node.py'
).read_text(encoding='utf-8')
PACKAGE_XML = (PACKAGE_ROOT / 'package.xml').read_text(encoding='utf-8')
SETUP_SOURCE = (PACKAGE_ROOT / 'setup.py').read_text(encoding='utf-8')
LAUNCH_SOURCE = (
    PACKAGE_ROOT / 'launch' / 'task_service_bridge.launch.py'
).read_text(encoding='utf-8')


class TaskBridgeSourceBoundaryTest(unittest.TestCase):

    def test_has_single_external_server_and_internal_client(self):
        self.assertEqual(NODE_SOURCE.count('ActionServer('), 1)
        self.assertEqual(NODE_SOURCE.count('ActionClient('), 1)
        self.assertIn("'/task/execute'", NODE_SOURCE)
        self.assertIn("'/motion/execute'", NODE_SOURCE)

    def test_uses_nonblocking_action_callback_configuration(self):
        self.assertIn('ReentrantCallbackGroup', NODE_SOURCE)
        self.assertIn('MultiThreadedExecutor', NODE_SOURCE)
        self.assertIn('async def _execute_callback', NODE_SOURCE)
        self.assertIn('await motion_goal_handle.get_result_async()', NODE_SOURCE)

    def test_external_cancel_propagates_to_motion_goal(self):
        self.assertIn('cancel_callback=self._cancel_callback', NODE_SOURCE)
        self.assertIn('motion_goal_handle.cancel_goal_async()', NODE_SOURCE)
        self.assertIn('goal_handle.is_cancel_requested', NODE_SOURCE)
        self.assertIn('self._admission.occupied', NODE_SOURCE)
        self.assertIn('goal_handle is not external_goal_handle', NODE_SOURCE)
        self.assertIn('await motion_goal_handle.get_result_async()', NODE_SOURCE)

    def test_does_not_bypass_motion_action_boundary(self):
        manifest = ElementTree.fromstring(PACKAGE_XML)
        runtime_dependencies = ''.join(
            str(element.text or '')
            for tag in ('depend', 'exec_depend')
            for element in manifest.findall(tag)
        )
        package_and_node = runtime_dependencies + NODE_SOURCE
        for forbidden in (
                'servo_msgs', 'MotionCommand', 'ServoCommand',
                'TaskExecutionControl', "'/servo/"):
            self.assertNotIn(forbidden, package_and_node)

        self.assertEqual(NODE_SOURCE.count('create_publisher('), 1)
        self.assertIn('TaskContextSignal', NODE_SOURCE)
        self.assertIn('SpeechIntent', NODE_SOURCE)
        self.assertIn('SceneState', NODE_SOURCE)

    def test_launch_and_entry_point_expose_bridge(self):
        self.assertIn('task_service_bridge_node = ', SETUP_SOURCE)
        self.assertIn("default_value='/task/execute'", LAUNCH_SOURCE)
        self.assertIn("default_value='/motion/execute'", LAUNCH_SOURCE)
        self.assertIn("default_value='true'", LAUNCH_SOURCE)
        self.assertIn("'enable_context'", LAUNCH_SOURCE)
        self.assertIn("default_value='/speech/intent'", LAUNCH_SOURCE)
        self.assertIn("default_value='/perception/scene_state'", LAUNCH_SOURCE)
        self.assertIn("default_value='/task/context_signal'", LAUNCH_SOURCE)

    def test_context_pub_sub_are_conditionally_enabled(self):
        self.assertIn("declare_parameter('enable_context', True)", NODE_SOURCE)
        self.assertIn('if enable_context:', NODE_SOURCE)
        self.assertIn('if self._context_publisher is None:', NODE_SOURCE)


if __name__ == '__main__':
    unittest.main()
