"""Register the real-owner scene admission smoke with pytest and colcon."""

import ast
import importlib.util
from pathlib import Path
import sys
import unittest


RUNNER = Path(__file__).with_name('scene_admission_ros_smoke.py')
RUNNER_SOURCE = RUNNER.read_text(encoding='utf-8')


def _module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


ROS_WORKSPACE_READY = all(_module_available(module_name) for module_name in (
    'rclpy',
    'execution_manager.execution_manager_node',
    'parallel_3dof_controller.controller_node',
    'perception_msgs.msg',
    'task_api_msgs.action',
    'task_service_bridge.bridge_node',
))


class TestSceneAdmissionRosSmoke(unittest.TestCase):

    def test_source_contract(self):
        ast.parse(RUNNER_SOURCE, filename=str(RUNNER))
        for required in (
            'ExecutionManagerNode',
            'Parallel3DOFControllerNode',
            'TaskServiceBridgeNode',
            'FakeDriverNode',
            'DelayedStartExecutionManagerNode',
            'SceneAdmissionProbe',
            "Parameter('require_scene_context', value=True)",
            "'/task/execute'",
            "'/perception/scene_state'",
            "'/execution/task/control'",
            "'/execution/task/command'",
            "'/servo/command'",
            "'scene_context_unavailable'",
            "'scene_context_rejected'",
            "'scene_context_session_mismatch'",
            "'scene_context_frame_mismatch'",
            "'scene_context_target_missing'",
            "'scene_context_target_confidence_low'",
            "'scene_context_target_out_of_bounds'",
            "'scene_context_stale'",
            "'lease-race'",
            "'scene_context_observation_required'",
        ):
            self.assertIn(required, RUNNER_SOURCE)

    @unittest.skipUnless(
        ROS_WORKSPACE_READY,
        'requires a built and sourced ROS 2 workspace',
    )
    def test_real_owner_scene_admission_chain(self):
        test_directory = str(RUNNER.parent)
        sys.path.insert(0, test_directory)
        try:
            spec = importlib.util.spec_from_file_location(
                'scene_admission_ros_smoke',
                RUNNER,
            )
            runner = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(runner)
        finally:
            sys.path.remove(test_directory)

        result = runner.run_scenario()
        expected_reasons = {
            'missing': 'scene_context_unavailable',
            'rejected': 'scene_context_rejected',
            'observation_required': 'scene_context_observation_required',
            'session_mismatch': 'scene_context_session_mismatch',
            'frame_mismatch': 'scene_context_frame_mismatch',
            'target_missing': 'scene_context_target_missing',
            'confidence_low': 'scene_context_target_confidence_low',
            'target_out_of_bounds': 'scene_context_target_out_of_bounds',
            'stale': 'scene_context_stale',
        }
        for name, reason in expected_reasons.items():
            rejection = result[name]
            self.assertEqual(reason, rejection['reason'])
            self.assertTrue(rejection['identity_preserved'])
            self.assertTrue(rejection['no_task_control'])
            self.assertTrue(rejection['no_task_motion_command'])
            self.assertTrue(rejection['no_servo_command'])

        lease_wait_recheck = result['lease_wait_recheck']
        self.assertEqual('scene_context_rejected', lease_wait_recheck['reason'])
        self.assertTrue(lease_wait_recheck['identity_preserved'])
        self.assertTrue(lease_wait_recheck['admission_released'])
        self.assertTrue(lease_wait_recheck['lease_cancelled'])
        self.assertTrue(lease_wait_recheck['ordered_start_cancel'])
        self.assertTrue(lease_wait_recheck['cancel_lease_id_present'])
        self.assertTrue(lease_wait_recheck['no_task_motion_command'])
        self.assertTrue(lease_wait_recheck['no_servo_command'])

        fresh = result['fresh']
        self.assertEqual('succeeded', fresh['status'])
        self.assertTrue(fresh['identity_preserved'])
        self.assertTrue(fresh['target_reached'])
        self.assertTrue(fresh['admission_released'])
        self.assertTrue(fresh['task_control_observed'])
        self.assertGreaterEqual(fresh['task_motion_command_count'], 3)
        self.assertGreaterEqual(fresh['servo_command_count'], 3)
        self.assertLessEqual(result['scene_max_age_sec'], 0.3)
        self.assertLess(result['elapsed_sec'], 60.0)


if __name__ == '__main__':
    unittest.main()
