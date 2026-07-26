"""Connect the formal task chain ROS smoke to unittest/pytest/colcon."""

import ast
import importlib.util
from pathlib import Path
import unittest


RUNNER = Path(__file__).with_name('task_chain_ros_smoke.py')
RUNNER_SOURCE = RUNNER.read_text(encoding='utf-8')
SCENARIO_TIMEOUT_SEC = 25.0


class TaskChainRosSmokeTest(unittest.TestCase):

    def test_task_chain_smoke_source_contract(self) -> None:
        ast.parse(RUNNER_SOURCE, filename=str(RUNNER))
        for required in (
            'ExecutionManagerNode',
            'Parallel3DOFControllerNode',
            'TaskServiceBridgeNode',
            'FakeDriverNode',
            "'/task/execute'",
            "'/servo/read_position'",
            "'/servo/execute_command'",
            "'/servo/command'",
            'cancel_goal_async()',
            'non_target_read_count',
            'minimum_target_reads()',
            'minimum_stop_reads()',
            'block_next_stop()',
            'defer_next_moves(3)',
            'DriverSafetyLatch',
            "'/servo/driver_safety'",
            "'/servo/set_driver_safety'",
            'late_move_rejected',
            'remaining_actuators_stopped',
            "'task_stop_pending'",
            'set_estop(True)',
            "'driver_stop_timeout'",
            'controller._task_admission_ready',
        ):
            self.assertIn(required, RUNNER_SOURCE)
        self.assertIn('MultiThreadedExecutor', RUNNER_SOURCE)
        self.assertIn('POSITION_STEP', RUNNER_SOURCE)
        estop_source = RUNNER_SOURCE.split(
            'def _run_estop_scenario',
            1,
        )[1].split('def _run_driver_timeout_fault_scenario', 1)[0]
        self.assertLess(
            estop_source.index('probe.set_estop(True)'),
            estop_source.index('driver.wait_for_deferred_moves()'),
        )

    @unittest.skipUnless(
        importlib.util.find_spec('rclpy') is not None,
        'requires a built and sourced ROS 2 task-chain workspace',
    )
    def test_formal_task_action_chain_ros_smoke(self) -> None:
        from task_chain_ros_smoke import run_scenario

        result = run_scenario()
        success = result['success']
        cancel = result['cancel']
        delayed_stop = result['delayed_stop']
        estop = result['estop']
        driver_timeout = result['driver_timeout']

        self.assertTrue(success['goal_accepted'])
        self.assertGreater(success['feedback_count'], 1)
        self.assertTrue(success['identity_preserved'])
        self.assertTrue(success['not_completed_before_target'])
        self.assertGreaterEqual(success['stable_target_samples'], 3)
        self.assertTrue(success['lease_cleared'])
        self.assertTrue(success['concurrent_task_rejected'])
        self.assertEqual(success['motion_rejection'], 'task_active')
        self.assertEqual(success['teleop_rejection'], 'task_active')

        self.assertTrue(cancel['goal_accepted'])
        self.assertTrue(cancel['cancel_propagated'])
        self.assertEqual(cancel['stop_command_count'], 3)
        self.assertTrue(cancel['stop_confirmed'])
        self.assertGreaterEqual(cancel['stable_stop_samples'], 4)
        self.assertTrue(cancel['lease_cleared'])
        self.assertTrue(cancel['identity_preserved'])

        self.assertTrue(delayed_stop['source_cancelled'])
        self.assertTrue(delayed_stop['new_task_blocked'])
        self.assertEqual(delayed_stop['blocked_reason'], 'task_stop_pending')
        self.assertTrue(delayed_stop['no_command_during_pending_stop'])
        self.assertTrue(delayed_stop['recovered_after_stop'])
        self.assertTrue(delayed_stop['release_acknowledged'])

        self.assertTrue(estop['goal_accepted'])
        self.assertEqual(estop['stop_command_count'], 3)
        self.assertTrue(estop['all_actuators_stopped'])
        self.assertTrue(estop['lease_cleared'])
        self.assertTrue(estop['action_aborted'])
        self.assertTrue(estop['late_move_rejected'])
        self.assertEqual(estop['late_move_rejected_count'], 3)
        self.assertTrue(estop['active_move_rejected'])
        self.assertTrue(estop['target_unchanged_after_stop'])
        self.assertTrue(estop['recovered_after_release'])
        self.assertTrue(estop['release_acknowledged'])

        self.assertEqual(
            driver_timeout['fault_reason'],
            'driver_stop_timeout',
        )
        self.assertTrue(driver_timeout['estop_latched'])
        self.assertTrue(driver_timeout['stop_token_retained'])
        self.assertTrue(driver_timeout['new_task_blocked'])
        self.assertTrue(driver_timeout['no_command_after_fault'])
        self.assertTrue(driver_timeout['all_stop_ids_attempted'])
        self.assertTrue(driver_timeout['remaining_actuators_stopped'])
        self.assertEqual(driver_timeout['remaining_stop_command_count'], 2)
        self.assertTrue(driver_timeout['driver_safety_latched'])
        self.assertLess(result['elapsed_sec'], SCENARIO_TIMEOUT_SEC)


if __name__ == '__main__':
    unittest.main()
