#!/usr/bin/env python3
"""Profile selected ROS 2 runtime paths with real in-process DDS traffic."""

import argparse
import contextlib
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import platform
import statistics
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional


EXECUTOR_THREADS = 4
POLL_INTERVAL_SEC = 0.0001


@dataclass(frozen=True)
class ProfileConfig:
    """Shared workload settings for all measured paths."""

    samples: int
    warmup: int
    timeout_sec: float
    motion_l0: float
    motion_l1: float
    motion_l2: float


class ProfileFailure(RuntimeError):
    """A profiling failure with machine-readable progress details."""

    def __init__(
        self,
        path: str,
        stage: str,
        reason: str,
        requested: int,
        completed: int,
        warmup_completed: int,
        timeouts: int,
    ) -> None:
        super().__init__(reason)
        self.details = {
            'path': path,
            'stage': stage,
            'reason': reason,
            'samples_requested': requested,
            'samples_completed': completed,
            'warmup_completed': warmup_completed,
            'timeouts': timeouts,
        }


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            'Measure real rclpy/DDS execution, motion-control, and '
            'simulation hot paths.'
        ),
    )
    parser.add_argument(
        '--samples',
        type=int,
        default=200,
        help='measured closed-loop requests per path (default: 200)',
    )
    parser.add_argument(
        '--warmup',
        type=int,
        default=20,
        help='unmeasured warmup requests per path (default: 20)',
    )
    parser.add_argument(
        '--timeout-sec',
        type=float,
        default=2.0,
        help='discovery and per-request timeout in seconds (default: 2.0)',
    )
    parser.add_argument(
        '--motion-l0',
        type=float,
        default=0.02,
        help='motion owner platform radius in meters (default: 0.02)',
    )
    parser.add_argument(
        '--motion-l1',
        type=float,
        default=0.01,
        help='motion owner moving-platform offset in meters (default: 0.01)',
    )
    parser.add_argument(
        '--motion-l2',
        type=float,
        default=0.03,
        help='motion owner fixed-platform offset in meters (default: 0.03)',
    )
    parser.add_argument(
        '--output',
        type=Path,
        help='optional JSON output file; JSON is always also printed to stdout',
    )
    args = parser.parse_args(argv)
    if args.samples <= 0:
        parser.error('--samples must be greater than zero')
    if args.warmup < 0:
        parser.error('--warmup must be zero or greater')
    if not math.isfinite(args.timeout_sec) or args.timeout_sec <= 0.0:
        parser.error('--timeout-sec must be a finite value greater than zero')
    for option_name in ('motion_l0', 'motion_l1', 'motion_l2'):
        value = getattr(args, option_name)
        if not math.isfinite(value) or value <= 0.0:
            parser.error(
                '--{0} must be a finite value greater than zero'.format(
                    option_name.replace('_', '-'),
                ),
            )
    return args


def _percentile(sorted_values: List[float], quantile: float) -> float:
    if not sorted_values:
        raise ValueError('percentile requires at least one value')
    position = (len(sorted_values) - 1) * quantile
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return (
        sorted_values[lower] * (1.0 - weight)
        + sorted_values[upper] * weight
    )


def _latency_summary(latencies_ns: List[int]) -> Dict[str, float]:
    values_ms = sorted(value / 1_000_000.0 for value in latencies_ns)
    return {
        'p50': _percentile(values_ms, 0.50),
        'p95': _percentile(values_ms, 0.95),
        'p99': _percentile(values_ms, 0.99),
        'max': values_ms[-1],
        'jitter': statistics.pstdev(values_ms),
    }


def _wait_for(predicate: Callable[[], bool], timeout_sec: float) -> bool:
    deadline = time.monotonic() + timeout_sec
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(POLL_INTERVAL_SEC)
    return bool(predicate())


def _profile_path(
    path_name: str,
    path_description: str,
    implementation_factory: Callable[[], Any],
    probe_factory: Callable[[], Any],
    request_factory: Callable[[Any, int], Any],
    responses_per_request: int,
    config: ProfileConfig,
    executor_factory: Callable[[], Any],
) -> Dict[str, Any]:
    """Run one isolated, closed-loop ROS path and summarize its latency."""
    nodes = []
    executor = None
    spin_thread = None
    warmup_completed = 0
    samples_completed = 0
    timeout_count = 0

    try:
        implementation = implementation_factory()
        nodes.append(implementation)
        probe = probe_factory()
        nodes.append(probe)
        executor = executor_factory()
        for node in nodes:
            executor.add_node(node)
        spin_thread = threading.Thread(
            target=executor.spin,
            name='runtime-profile-{0}'.format(path_name),
            daemon=True,
        )
        spin_thread.start()

        discovered = _wait_for(
            lambda: (
                probe.input_publisher.get_subscription_count() > 0
                and probe.count_publishers(
                    probe.output_subscription.topic_name
                ) > 0
            ),
            config.timeout_sec,
        )
        if not discovered:
            raise ProfileFailure(
                path_name,
                'discovery',
                'publisher/subscriber discovery timed out',
                config.samples,
                samples_completed,
                warmup_completed,
                timeout_count + 1,
            )

        def run_request(sequence: int, stage: str) -> int:
            nonlocal timeout_count
            before = len(probe.arrival_times_ns)
            started_ns = time.perf_counter_ns()
            probe.input_publisher.publish(request_factory(probe, sequence))
            expected = before + responses_per_request
            if not _wait_for(
                    lambda: len(probe.arrival_times_ns) >= expected,
                    config.timeout_sec):
                timeout_count += 1
                raise ProfileFailure(
                    path_name,
                    stage,
                    'request timed out waiting for {0} response(s)'.format(
                        responses_per_request,
                    ),
                    config.samples,
                    samples_completed,
                    warmup_completed,
                    timeout_count,
                )
            completed_ns = probe.arrival_times_ns[expected - 1]
            return completed_ns - started_ns

        for sequence in range(config.warmup):
            run_request(sequence, 'warmup')
            warmup_completed += 1

        reset_component_metrics = getattr(
            implementation,
            'runtime_profile_reset_component_metrics',
            None,
        )
        if reset_component_metrics is not None:
            reset_component_metrics()

        latencies_ns = []
        cpu_started = time.process_time()
        wall_started = time.perf_counter()
        for sequence in range(config.samples):
            latency_ns = run_request(config.warmup + sequence, 'measurement')
            latencies_ns.append(latency_ns)
            samples_completed += 1
        elapsed_sec = time.perf_counter() - wall_started
        process_cpu_sec = time.process_time() - cpu_started

        if len(latencies_ns) != config.samples:
            raise ProfileFailure(
                path_name,
                'sample_validation',
                'insufficient measured samples',
                config.samples,
                len(latencies_ns),
                warmup_completed,
                timeout_count,
            )
        if elapsed_sec <= 0.0:
            raise ProfileFailure(
                path_name,
                'sample_validation',
                'non-positive measurement duration',
                config.samples,
                samples_completed,
                warmup_completed,
                timeout_count,
            )

        result = {
            'path': path_description,
            'samples_requested': config.samples,
            'samples_completed': samples_completed,
            'warmup_requested': config.warmup,
            'warmup_completed': warmup_completed,
            'timeouts': timeout_count,
            'elapsed_sec': elapsed_sec,
            'process_cpu_sec': process_cpu_sec,
            'cpu_percent': process_cpu_sec / elapsed_sec * 100.0,
            'throughput_hz': samples_completed / elapsed_sec,
            'latency_ms': _latency_summary(latencies_ns),
        }
        read_component_metrics = getattr(
            implementation,
            'runtime_profile_component_metrics',
            None,
        )
        if read_component_metrics is not None:
            result['component_metrics'] = read_component_metrics()
        return result
    finally:
        if executor is not None:
            executor.shutdown()
        if spin_thread is not None:
            spin_thread.join(timeout=2.0)
        for node in reversed(nodes):
            node.destroy_node()


def _environment(rclpy_module: Any, profile_namespace: str) -> Dict[str, Any]:
    requested_rmw = os.environ.get('RMW_IMPLEMENTATION', '')
    try:
        from rclpy.utilities import get_rmw_implementation_identifier

        resolved_rmw = get_rmw_implementation_identifier()
    except (ImportError, AttributeError, RuntimeError):
        resolved_rmw = requested_rmw or 'unknown'
    return {
        'platform': platform.platform(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'cpu_count': os.cpu_count(),
        'python_version': platform.python_version(),
        'python_implementation': platform.python_implementation(),
        'ros_distro': os.environ.get('ROS_DISTRO', 'unknown'),
        'rmw_implementation_requested': requested_rmw or 'default',
        'rmw_implementation_resolved': resolved_rmw,
        'rclpy_version': getattr(rclpy_module, '__version__', 'unknown'),
        'pid': os.getpid(),
        'executor_threads': EXECUTOR_THREADS,
        'profile_namespace': profile_namespace,
    }


def _ros_arguments(profile_namespace: str) -> List[str]:
    endpoints = (
        '/execution/teleop/command',
        '/execution/teleop/control',
        '/execution/task/command',
        '/execution/task/control',
        '/execution/motion/command',
        '/execution/actuator_state',
        '/execution/state',
        '/execution/task/state',
        '/execution/read_actuator_position',
        '/execution/stop_actuators',
        '/execution/estop',
        '/motion/execute',
        '/servo/command',
        '/servo/state',
        '/servo/read_position',
        '/servo/execute_command',
        '/servo/driver_safety',
        '/servo/set_driver_safety',
        '/sim/servo_command',
        '/sim/servo_state',
        '/ankle_controller_node/ankle_rpy',
        '/ankle_controller_node/ankle_theta',
    )
    arguments = ['--ros-args', '-p', 'enable_motion_action_server:=false']
    for endpoint in endpoints:
        arguments.extend([
            '-r',
            '{0}:={1}{0}'.format(endpoint, profile_namespace),
        ])
    return arguments


def _run_profiles(config: ProfileConfig) -> Dict[str, Any]:
    try:
        from execution_manager.execution_manager_node import ExecutionManagerNode
        from geometry_msgs.msg import Vector3
        from motion_msgs.msg import MotionCommand
        import rclpy
        from rclpy.executors import MultiThreadedExecutor
        from rclpy.node import Node
        from rclpy.parameter import Parameter
        from servo_msgs.msg import ServoCommand
        from simulation_bridge.sim_servo_bridge_node import SimServoBridge
        from parallel_3dof_controller.controller_node import (
            Parallel3DOFControllerNode,
        )
    except (ImportError, ModuleNotFoundError) as exc:
        raise ProfileFailure(
            'runtime',
            'ros_import',
            'ROS 2 runtime import failed: {0}'.format(exc),
            config.samples,
            0,
            0,
            0,
        ) from exc

    profile_namespace = '/runtime_profile_{0}'.format(os.getpid())
    # Keep node logs and legacy solver prints away from the JSON stdout stream.
    os.environ['RCUTILS_LOGGING_USE_STDOUT'] = '0'
    rclpy.init(args=_ros_arguments(profile_namespace))

    class _ExecutionProbe(Node):
        def __init__(self) -> None:
            super().__init__('runtime_profile_execution_probe')
            self.arrival_times_ns = []
            self.input_publisher = self.create_publisher(
                MotionCommand,
                '/execution/motion/command',
                50,
            )
            self.output_subscription = self.create_subscription(
                ServoCommand,
                '/servo/command',
                self._record_output,
                50,
            )

        def _record_output(self, unused_message: Any) -> None:
            self.arrival_times_ns.append(time.perf_counter_ns())

    class _MotionProbe(Node):
        def __init__(self) -> None:
            super().__init__('runtime_profile_motion_probe')
            self.arrival_times_ns = []
            self.input_publisher = self.create_publisher(
                Vector3,
                '/ankle_controller_node/ankle_rpy',
                10,
            )
            self.output_subscription = self.create_subscription(
                MotionCommand,
                '/execution/motion/command',
                self._record_output,
                50,
            )

        def _record_output(self, unused_message: Any) -> None:
            self.arrival_times_ns.append(time.perf_counter_ns())

    class _SimulationProbe(Node):
        def __init__(self) -> None:
            super().__init__('runtime_profile_simulation_probe')
            self.arrival_times_ns = []
            self.input_publisher = self.create_publisher(
                ServoCommand,
                '/sim/servo_command',
                50,
            )
            self.output_subscription = self.create_subscription(
                ServoCommand,
                '/servo/command',
                self._record_output,
                50,
            )

        def _record_output(self, unused_message: Any) -> None:
            self.arrival_times_ns.append(time.perf_counter_ns())

    def execution_request(probe: Any, sequence: int) -> Any:
        message = MotionCommand()
        message.servo_type = 'bus'
        message.servo_id = 7
        message.position = 1400 + sequence % 201
        message.value_encoding = 'bus_pulse_us'
        message.duration_ms = 100
        message.requester_id = ''
        message.lease_id = ''
        message.stamp = probe.get_clock().now().to_msg()
        return message

    def motion_request(unused_probe: Any, sequence: int) -> Any:
        message = Vector3()
        message.x = float(sequence % 11 - 5) * 0.1
        message.y = float(sequence % 7 - 3) * 0.1
        message.z = float(sequence % 5 - 2) * 0.1
        return message

    def simulation_request(probe: Any, sequence: int) -> Any:
        message = ServoCommand()
        message.servo_type = 'bus'
        message.servo_id = 7
        message.position = 1400 + sequence % 201
        message.speed = 100
        message.stamp = probe.get_clock().now().to_msg()
        return message

    def executor_factory() -> Any:
        return MultiThreadedExecutor(num_threads=EXECUTOR_THREADS)

    def motion_owner_factory() -> Any:
        node = Parallel3DOFControllerNode(parameter_overrides=[
            Parameter('l0', value=config.motion_l0),
            Parameter('l1', value=config.motion_l1),
            Parameter('l2', value=config.motion_l2),
        ])
        solver_latencies_ns = []
        solve = node.solver.rpy_to_servo_commands

        def timed_solve(*args: Any, **kwargs: Any) -> Any:
            started_ns = time.perf_counter_ns()
            try:
                return solve(*args, **kwargs)
            finally:
                solver_latencies_ns.append(
                    time.perf_counter_ns() - started_ns,
                )

        def reset_component_metrics() -> None:
            solver_latencies_ns.clear()

        def read_component_metrics() -> Dict[str, Any]:
            if len(solver_latencies_ns) != config.samples:
                raise ProfileFailure(
                    'motion_control',
                    'component_metrics',
                    'solver component sample count mismatch',
                    config.samples,
                    len(solver_latencies_ns),
                    config.warmup,
                    0,
                )
            return {
                'solver': {
                    'samples': len(solver_latencies_ns),
                    'latency_ms': _latency_summary(solver_latencies_ns),
                },
            }

        node.solver.rpy_to_servo_commands = timed_solve
        node.runtime_profile_reset_component_metrics = reset_component_metrics
        node.runtime_profile_component_metrics = read_component_metrics
        return node

    profiles = {}
    try:
        profiles['execution_manager'] = _profile_path(
            'execution_manager',
            'MotionCommand -> ExecutionManagerNode -> ServoCommand',
            ExecutionManagerNode,
            _ExecutionProbe,
            execution_request,
            1,
            config,
            executor_factory,
        )
        profiles['motion_control'] = _profile_path(
            'motion_control',
            'Vector3 -> Parallel3DOFControllerNode -> 3 x MotionCommand',
            motion_owner_factory,
            _MotionProbe,
            motion_request,
            3,
            config,
            executor_factory,
        )
        profiles['simulation_bridge'] = _profile_path(
            'simulation_bridge',
            'ServoCommand -> SimServoBridge -> ServoCommand',
            SimServoBridge,
            _SimulationProbe,
            simulation_request,
            1,
            config,
            executor_factory,
        )
        return {
            'schema_version': 1,
            'status': 'ok',
            'environment': _environment(rclpy, profile_namespace),
            'configuration': {
                'samples': config.samples,
                'warmup': config.warmup,
                'timeout_sec': config.timeout_sec,
                'motion_geometry_m': {
                    'l0': config.motion_l0,
                    'l1': config.motion_l1,
                    'l2': config.motion_l2,
                },
                'measurement_mode': 'closed_loop_one_request_at_a_time',
                'cpu_percent_definition': (
                    'process_cpu_time_over_wall_time_x100'
                ),
                'jitter_definition': (
                    'population_standard_deviation_of_latency_ms'
                ),
                'percentile_method': 'linear_interpolation_rank_n_minus_1',
            },
            'profiles': profiles,
        }
    finally:
        if rclpy.ok():
            rclpy.shutdown()


def _emit_result(payload: Dict[str, Any], output: Optional[Path]) -> bool:
    serialized = json.dumps(
        payload,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    )
    print(serialized)
    if output is None:
        return True
    try:
        output_path = output.expanduser()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(serialized + '\n', encoding='utf-8')
    except OSError as exc:
        print('failed to write --output: {0}'.format(exc), file=sys.stderr)
        return False
    return True


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    config = ProfileConfig(
        samples=args.samples,
        warmup=args.warmup,
        timeout_sec=args.timeout_sec,
        motion_l0=args.motion_l0,
        motion_l1=args.motion_l1,
        motion_l2=args.motion_l2,
    )
    exit_code = 0
    try:
        with contextlib.redirect_stdout(sys.stderr):
            payload = _run_profiles(config)
    except ProfileFailure as exc:
        exit_code = 1
        payload = {
            'schema_version': 1,
            'status': 'failed',
            'configuration': {
                'samples': config.samples,
                'warmup': config.warmup,
                'timeout_sec': config.timeout_sec,
                'motion_geometry_m': {
                    'l0': config.motion_l0,
                    'l1': config.motion_l1,
                    'l2': config.motion_l2,
                },
            },
            'failure': exc.details,
        }
    except Exception as exc:  # Keep unexpected ROS failures machine-readable.
        exit_code = 1
        payload = {
            'schema_version': 1,
            'status': 'failed',
            'configuration': {
                'samples': config.samples,
                'warmup': config.warmup,
                'timeout_sec': config.timeout_sec,
                'motion_geometry_m': {
                    'l0': config.motion_l0,
                    'l1': config.motion_l1,
                    'l2': config.motion_l2,
                },
            },
            'failure': {
                'path': 'runtime',
                'stage': 'unexpected_exception',
                'reason': '{0}: {1}'.format(type(exc).__name__, exc),
                'samples_requested': config.samples,
                'samples_completed': 0,
                'warmup_completed': 0,
                'timeouts': 0,
            },
        }

    if not _emit_result(payload, args.output):
        return 1
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
