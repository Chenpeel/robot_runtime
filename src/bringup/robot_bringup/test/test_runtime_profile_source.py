"""Source contracts for the ROS runtime profiling utility."""

import ast
from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
PROFILE_SCRIPT = REPOSITORY_ROOT / 'scripts' / 'profile_runtime_hotpaths.py'


class TestRuntimeProfileSource(unittest.TestCase):
    """Validate the profiler without importing ROS modules on the host."""

    @classmethod
    def setUpClass(cls):
        cls.source = PROFILE_SCRIPT.read_text(encoding='utf-8')
        cls.tree = ast.parse(cls.source, filename=str(PROFILE_SCRIPT))
        cls.string_literals = {
            node.value
            for node in ast.walk(cls.tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }

    def test_cli_exposes_bounded_workload_and_json_output(self):
        option_names = {
            node.args[0].value
            for node in ast.walk(self.tree)
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'add_argument'
                and node.args
                and isinstance(node.args[0], ast.Constant)
            )
        }
        self.assertTrue({
            '--samples',
            '--warmup',
            '--timeout-sec',
            '--motion-l0',
            '--motion-l1',
            '--motion-l2',
            '--output',
        }.issubset(option_names))
        self.assertIn('--samples must be greater than zero', self.string_literals)
        self.assertIn('--warmup must be zero or greater', self.string_literals)
        self.assertIn(
            '--timeout-sec must be a finite value greater than zero',
            self.string_literals,
        )
        self.assertIn('motion_geometry_m', self.string_literals)
        self.assertIn('allow_nan=False', self.source)

    def test_motion_profile_uses_explicit_geometry_overrides(self):
        self.assertIn('motion_owner_factory', self.source)
        self.assertIn("Parameter('l0', value=config.motion_l0)", self.source)
        self.assertIn("Parameter('l1', value=config.motion_l1)", self.source)
        self.assertIn("Parameter('l2', value=config.motion_l2)", self.source)
        self.assertIn('runtime_profile_reset_component_metrics', self.source)
        self.assertIn('runtime_profile_component_metrics', self.source)
        self.assertIn('solver component sample count mismatch', self.string_literals)
        self.assertIn("'component_metrics'", self.source)
        self.assertNotIn(
            "'motion_control',\n            'Vector3 -> "
            "Parallel3DOFControllerNode -> 3 x MotionCommand',\n"
            '            Parallel3DOFControllerNode,',
            self.source,
        )

    def test_profiler_uses_real_ros_nodes_and_dds_publishers(self):
        imported_names = {
            alias.name
            for node in ast.walk(self.tree)
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        self.assertTrue({
            'ExecutionManagerNode',
            'Parallel3DOFControllerNode',
            'SimServoBridge',
            'MultiThreadedExecutor',
            'MotionCommand',
            'ServoCommand',
            'Vector3',
        }.issubset(imported_names))
        self.assertIn('create_publisher', self.source)
        self.assertIn('create_subscription', self.source)
        self.assertIn('executor.spin', self.source)
        self.assertIn('get_subscription_count', self.source)
        self.assertIn('count_publishers', self.source)
        self.assertIn('output_subscription.topic_name', self.source)

    def test_all_three_runtime_paths_have_closed_loop_response_contracts(self):
        self.assertIn(
            'MotionCommand -> ExecutionManagerNode -> ServoCommand',
            self.string_literals,
        )
        self.assertIn(
            'Vector3 -> Parallel3DOFControllerNode -> 3 x MotionCommand',
            self.string_literals,
        )
        self.assertIn(
            'ServoCommand -> SimServoBridge -> ServoCommand',
            self.string_literals,
        )
        self.assertIn("profiles['execution_manager']", self.source)
        self.assertIn("profiles['motion_control']", self.source)
        self.assertIn("profiles['simulation_bridge']", self.source)
        self.assertIn('responses_per_request', self.source)
        self.assertIn('time.perf_counter_ns()', self.source)

    def test_json_contains_environment_and_required_statistics(self):
        required_fields = {
            'environment',
            'samples_requested',
            'samples_completed',
            'warmup_requested',
            'warmup_completed',
            'timeouts',
            'throughput_hz',
            'cpu_percent',
            'p50',
            'p95',
            'p99',
            'max',
            'jitter',
        }
        self.assertTrue(required_fields.issubset(self.string_literals))
        self.assertIn('time.process_time()', self.source)
        self.assertIn('platform.platform()', self.source)
        self.assertIn('ROS_DISTRO', self.string_literals)
        self.assertIn('RMW_IMPLEMENTATION', self.string_literals)

    def test_timeout_or_insufficient_samples_fail_the_process(self):
        function_names = {
            node.name
            for node in ast.walk(self.tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        self.assertIn('_wait_for', function_names)
        self.assertIn('_profile_path', function_names)
        self.assertIn('insufficient measured samples', self.string_literals)
        self.assertIn(
            'request timed out waiting for {0} response(s)',
            self.string_literals,
        )
        self.assertIn("'status': 'failed'", self.source)
        self.assertIn('exit_code = 1', self.source)
        self.assertTrue(any(
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Constant)
            and node.value.value == 1
            for node in ast.walk(self.tree)
        ))


if __name__ == '__main__':
    unittest.main()
