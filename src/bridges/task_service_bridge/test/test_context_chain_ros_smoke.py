"""将 Phase 5 context smoke 接入 pytest/colcon。"""

import ast
import importlib.util
from pathlib import Path
import unittest


RUNNER = Path(__file__).with_name('context_chain_ros_smoke.py')
RUNNER_SOURCE = RUNNER.read_text(encoding='utf-8')


class TestContextChainRosSmoke(unittest.TestCase):

    def test_source_contract(self):
        ast.parse(RUNNER_SOURCE, filename=str(RUNNER))
        for required in (
            'SpeechInterfaceNode',
            'VisionPerceptionNode',
            'TaskServiceBridgeNode',
            "'/motion/execute'",
            "'/speech/intent_input'",
            "'/speech/intent'",
            "'/perception/detections_input'",
            "'/perception/scene_state'",
            "'/task/context_signal'",
            "'confidence_below_minimum'",
            "'object_id_not_unique'",
        ):
            self.assertIn(required, RUNNER_SOURCE)

    @unittest.skipUnless(
        importlib.util.find_spec('rclpy') is not None,
        'requires a built and sourced ROS 2 workspace',
    )
    def test_real_action_and_dds_context_chain(self):
        from context_chain_ros_smoke import run_scenario

        result = run_scenario()
        self.assertEqual('task-phase5', result['motion_task_id'])
        self.assertEqual('trace-phase5', result['motion_trace_id'])
        self.assertEqual('session-phase5', result['motion_session_id'])
        self.assertTrue(result['speech_succeeded'])
        self.assertTrue(result['speech_rejected'])
        self.assertTrue(result['perception_ready'])
        self.assertTrue(result['perception_rejected'])
        self.assertEqual(['cup'], result['perception_labels'])
        self.assertLess(result['elapsed_sec'], 12.0)


if __name__ == '__main__':
    unittest.main()
