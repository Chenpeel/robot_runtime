"""docs/plan.md Phase 2 拆包完成合同。"""

import ast
import json
import unittest
from pathlib import Path
from xml.etree import ElementTree


REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
RUNTIME_DEPENDENCY_TAGS = {
    'build_depend',
    'build_export_depend',
    'depend',
    'exec_depend',
}


def _read(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding='utf-8')


def _python_tree(relative_path: str) -> ast.AST:
    return ast.parse(_read(relative_path), filename=relative_path)


def _string_literals(relative_path: str) -> set:
    return {
        node.value
        for node in ast.walk(_python_tree(relative_path))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _import_roots(relative_directory: str) -> set:
    roots = set()
    directory = REPOSITORY_ROOT / relative_directory
    for path in directory.rglob('*.py'):
        tree = ast.parse(
            path.read_text(encoding='utf-8'),
            filename=str(path.relative_to(REPOSITORY_ROOT)),
        )
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(
                    alias.name.split('.', 1)[0]
                    for alias in node.names
                )
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split('.', 1)[0])
    return roots


def _manifest(relative_path: str):
    return ElementTree.parse(REPOSITORY_ROOT / relative_path).getroot()


def _manifest_name(relative_path: str) -> str:
    return str(_manifest(relative_path).findtext('name') or '').strip()


def _manifest_dependencies(relative_path: str) -> set:
    root = _manifest(relative_path)
    return {
        str(element.text or '').strip()
        for element in root
        if element.tag in RUNTIME_DEPENDENCY_TAGS
        and str(element.text or '').strip()
    }


def _setup_console_scripts(relative_path: str) -> dict:
    for node in ast.walk(_python_tree(relative_path)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'setup'
        ):
            continue
        for keyword in node.keywords:
            if keyword.arg != 'entry_points':
                continue
            entry_points = ast.literal_eval(keyword.value)
            scripts = entry_points.get('console_scripts', [])
            return {
                name.strip(): target.strip()
                for name, target in (
                    script.split('=', 1)
                    for script in scripts
                )
            }
    raise AssertionError(f'setup() entry_points missing: {relative_path}')


def _node_package_executables(relative_path: str) -> set:
    pairs = set()
    for node in ast.walk(_python_tree(relative_path)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'Node'
        ):
            continue
        keywords = {keyword.arg: keyword.value for keyword in node.keywords}
        package = keywords.get('package')
        executable = keywords.get('executable')
        if (
            isinstance(package, ast.Constant)
            and isinstance(package.value, str)
            and isinstance(executable, ast.Constant)
            and isinstance(executable.value, str)
        ):
            pairs.add((package.value, executable.value))
    return pairs


def _launch_argument_defaults(relative_path: str) -> dict:
    defaults = {}
    for node in ast.walk(_python_tree(relative_path)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == 'DeclareLaunchArgument'
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            continue
        default_value = next(
            (
                keyword.value
                for keyword in node.keywords
                if keyword.arg == 'default_value'
            ),
            None,
        )
        if isinstance(default_value, ast.Constant):
            defaults[str(node.args[0].value)] = default_value.value
    return defaults


def _include_target(node: ast.AST):
    packages = []
    launch_files = []
    for child in ast.walk(node):
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == 'FindPackageShare'
            and child.args
            and isinstance(child.args[0], ast.Constant)
            and isinstance(child.args[0].value, str)
        ):
            packages.append(child.args[0].value)
        elif (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and child.value.endswith('.launch.py')
        ):
            launch_files.append(child.value)
    if len(packages) == 1 and len(launch_files) == 1:
        return packages[0], launch_files[0]
    return None


def _returned_include_targets(relative_path: str) -> set:
    tree = _python_tree(relative_path)
    include_targets = {}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == 'IncludeLaunchDescription'
        ):
            continue
        target = _include_target(node.value)
        if target is not None:
            include_targets[node.targets[0].id] = target

    returned_names = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Return)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == 'LaunchDescription'
            and node.value.args
            and isinstance(node.value.args[0], (ast.List, ast.Tuple))
        ):
            continue
        returned_names.update(
            element.id
            for element in node.value.args[0].elts
            if isinstance(element, ast.Name)
        )

    return {
        target
        for name, target in include_targets.items()
        if name in returned_names
    }


def _connected_packages(relative_path: str) -> set:
    packages = {
        package
        for package, _ in _node_package_executables(relative_path)
    }
    packages.update(
        package
        for package, _ in _returned_include_targets(relative_path)
    )
    return packages


def _json_tokens(value) -> set:
    if isinstance(value, dict):
        tokens = {str(key) for key in value}
        for child in value.values():
            tokens.update(_json_tokens(child))
        return tokens
    if isinstance(value, list):
        tokens = set()
        for child in value:
            tokens.update(_json_tokens(child))
        return tokens
    if isinstance(value, str):
        return {value}
    return set()


class TestPhase2BoundaryCompletion(unittest.TestCase):
    """固定 Phase 2 四项拆包结果，避免职责重新混回默认主链。"""

    def test_simulation_responsibility_is_outside_websocket_package(self):
        websocket_dependencies = _manifest_dependencies(
            'src/bridges/teleoperation_bridge/package.xml'
        )
        websocket_imports = _import_roots(
            'src/bridges/teleoperation_bridge/websocket_bridge'
        )
        simulation_dependencies = _manifest_dependencies(
            'src/bridges/simulation_bridge/package.xml'
        )
        simulation_imports = _import_roots(
            'src/bridges/simulation_bridge/simulation_bridge'
        )
        simulation_packages = {
            'sim_joint_bridge_cpp',
            'simulation_bridge',
        }

        self.assertEqual(
            'websocket_bridge',
            _manifest_name(
                'src/bridges/teleoperation_bridge/package.xml'
            ),
        )
        self.assertEqual(
            'simulation_bridge',
            _manifest_name('src/bridges/simulation_bridge/package.xml'),
        )
        self.assertTrue(simulation_packages.isdisjoint(websocket_dependencies))
        self.assertTrue(simulation_packages.isdisjoint(websocket_imports))
        self.assertNotIn('websocket_bridge', simulation_dependencies)
        self.assertNotIn('websocket_bridge', simulation_imports)

        websocket_scripts = _setup_console_scripts(
            'src/bridges/teleoperation_bridge/setup.py'
        )
        simulation_scripts = _setup_console_scripts(
            'src/bridges/simulation_bridge/setup.py'
        )
        self.assertEqual(
            'websocket_bridge.bridge_node:main',
            websocket_scripts.get('bridge_node'),
        )
        self.assertEqual(
            'simulation_bridge.sim_servo_bridge_node:main',
            simulation_scripts.get('sim_servo_bridge_node'),
        )
        self.assertTrue(websocket_scripts)
        self.assertTrue(simulation_scripts)
        self.assertTrue(
            all(
                target.startswith('websocket_bridge.')
                for target in websocket_scripts.values()
            )
        )
        self.assertTrue(
            all(
                target.startswith('simulation_bridge.')
                for target in simulation_scripts.values()
            )
        )
        self.assertEqual(
            [],
            [
                str(path.relative_to(REPOSITORY_ROOT))
                for path in (
                    REPOSITORY_ROOT
                    / 'src/bridges/teleoperation_bridge/websocket_bridge/'
                    'isaac_bridge_node.py',
                    REPOSITORY_ROOT
                    / 'src/bridges/teleoperation_bridge/websocket_bridge/'
                    'isaac_bridge_utils.py',
                )
                if path.exists()
            ],
        )

        simulation_literals = _string_literals(
            'src/bringup/robot_bringup/launch/simulation.launch.py'
        )
        self.assertIn('simulation_bridge', simulation_literals)
        self.assertIn('simulation.launch.py', simulation_literals)

    def test_sensor_hardware_is_an_independent_package(self):
        self.assertEqual(
            'sensor_hardware',
            _manifest_name('src/execution/sensor_hardware/package.xml'),
        )
        self.assertEqual(
            'servo_hardware',
            _manifest_name('src/execution/servo_hardware/package.xml'),
        )

        servo_dependencies = _manifest_dependencies(
            'src/execution/servo_hardware/package.xml'
        )
        sensor_dependencies = _manifest_dependencies(
            'src/execution/sensor_hardware/package.xml'
        )
        servo_scripts = _setup_console_scripts(
            'src/execution/servo_hardware/setup.py'
        )
        sensor_scripts = _setup_console_scripts(
            'src/execution/sensor_hardware/setup.py'
        )
        old_sensor_sources = [
            str(path.relative_to(REPOSITORY_ROOT))
            for path in (
                REPOSITORY_ROOT
                / 'src/execution/servo_hardware/sensor_hardware/__init__.py',
                REPOSITORY_ROOT
                / 'src/execution/servo_hardware/sensor_hardware/imu_driver.py',
                REPOSITORY_ROOT
                / 'src/execution/servo_hardware/sensor_hardware/'
                'imu_serial_driver.py',
            )
            if path.exists()
        ]

        self.assertNotIn('sensor_hardware', servo_dependencies)
        self.assertNotIn('sensor_msgs', servo_dependencies)
        self.assertIn('sensor_msgs', sensor_dependencies)
        self.assertTrue(
            {'imu_driver', 'imu_serial_driver'}.isdisjoint(servo_scripts)
        )
        self.assertTrue(
            all(
                not target.startswith('sensor_hardware.')
                for target in servo_scripts.values()
            )
        )
        self.assertEqual([], old_sensor_sources)

        self.assertEqual(
            'sensor_hardware.imu_driver:main',
            sensor_scripts.get('imu_driver'),
        )
        self.assertEqual(
            'sensor_hardware.imu_serial_driver:main',
            sensor_scripts.get('imu_serial_driver'),
        )

        hardware_nodes = _node_package_executables(
            'src/bringup/robot_bringup/launch/hardware.launch.py'
        )
        self.assertIn(
            ('sensor_hardware', 'imu_serial_driver'),
            hardware_nodes,
        )
        self.assertTrue(
            all(
                not (
                    package == 'servo_hardware'
                    and executable.startswith('imu')
                )
                for package, executable in hardware_nodes
            )
        )

    def test_action_playback_is_opt_in_from_the_default_stack(self):
        for manifest_path in (
            'src/bringup/robot_bringup/package.xml',
            'src/bridges/teleoperation_bridge/package.xml',
        ):
            with self.subTest(manifest=manifest_path):
                self.assertNotIn(
                    'record_load_action',
                    _manifest_dependencies(manifest_path),
                )

        for launch_path in (
            'src/bringup/robot_bringup/launch/full_system.launch.py',
            'src/bringup/robot_bringup/launch/teleop.launch.py',
        ):
            with self.subTest(launch=launch_path):
                self.assertNotIn('record_load_action', _read(launch_path))

        websocket_imports = _import_roots(
            'src/bridges/teleoperation_bridge/websocket_bridge'
        )
        bringup_imports = _import_roots(
            'src/bringup/robot_bringup/robot_bringup'
        )
        self.assertNotIn('record_load_action', websocket_imports)
        self.assertNotIn('record_load_action', bringup_imports)
        teleop_defaults = _launch_argument_defaults(
            'src/bringup/robot_bringup/launch/teleop.launch.py'
        )
        self.assertEqual('', teleop_defaults.get('bridge_extension_factories'))

        schema = json.loads(
            _read(
                'src/bridges/teleoperation_bridge/config/'
                'std_web2ros_stream.json'
            )
        )
        self.assertNotIn('bvh_play', _json_tokens(schema))

        demo_literals = _string_literals(
            'src/tools/record_load_action/launch/'
            'bvh_websocket_demo.launch.py'
        )
        self.assertIn('robot_bringup', demo_literals)
        self.assertIn('teleop.launch.py', demo_literals)
        self.assertIn(
            'record_load_action.bvh_websocket_extension:create_extension',
            demo_literals,
        )

    def test_full_system_composes_runtime_domain_launches(self):
        full_system_path = (
            'src/bringup/robot_bringup/launch/full_system.launch.py'
        )
        returned_includes = _returned_include_targets(full_system_path)
        expected_includes = {
            ('robot_bringup', 'hardware.launch.py'),
            ('robot_bringup', 'simulation.launch.py'),
            ('robot_bringup', 'task.launch.py'),
            ('robot_bringup', 'teleop.launch.py'),
            ('robot_bringup', 'context.launch.py'),
        }

        self.assertEqual(expected_includes, returned_includes)

        setup_literals = _string_literals(
            'src/bringup/robot_bringup/setup.py'
        )
        self.assertIn('launch/*.launch.py', setup_literals)
        bringup_dependencies = _manifest_dependencies(
            'src/bringup/robot_bringup/package.xml'
        )
        self.assertTrue(
            {
                'sensor_hardware',
                'servo_hardware',
                'simulation_bridge',
                'speech_interface',
                'vision_perception',
                'websocket_bridge',
            }.issubset(bringup_dependencies)
        )

        domain_packages = {
            'hardware.launch.py': {
                'required': {'sensor_hardware', 'servo_hardware'},
                'forbidden': {'simulation_bridge', 'websocket_bridge'},
            },
            'teleop.launch.py': {
                'required': {'execution_manager', 'websocket_bridge'},
                'forbidden': {
                    'sensor_hardware',
                    'servo_hardware',
                    'simulation_bridge',
                },
            },
            'simulation.launch.py': {
                'required': {'simulation_bridge'},
                'forbidden': {
                    'sensor_hardware',
                    'servo_hardware',
                    'websocket_bridge',
                },
            },
            'task.launch.py': {
                'required': {
                    'execution_manager',
                    'parallel_3dof_controller',
                    'task_service_bridge',
                },
                'forbidden': {
                    'sensor_hardware',
                    'servo_hardware',
                    'simulation_bridge',
                    'websocket_bridge',
                },
            },
        }
        for launch_name, expected in domain_packages.items():
            with self.subTest(launch=launch_name):
                connected_packages = _connected_packages(
                    f'src/bringup/robot_bringup/launch/{launch_name}'
                )
                self.assertTrue(
                    expected['required'].issubset(connected_packages)
                )
                self.assertTrue(
                    expected['forbidden'].isdisjoint(connected_packages)
                )

    def test_user_entrypoints_do_not_reference_removed_phase2_interfaces(self):
        readme = _read('README.md')
        simulation_test_script = _read('scripts/sim_bridge_co_test.sh')
        launch_case = simulation_test_script.split('    launch)', 1)[1].split(
            '        ;;', 1
        )[0]

        self.assertNotIn(
            'ros2 run simulation_bridge isaac_bridge_node',
            readme,
        )
        self.assertIn(
            'ros2 run simulation_bridge sim_servo_bridge_node',
            readme,
        )
        self.assertNotIn('enable_sim_cpp_bridge:=', launch_case)
        self.assertNotIn('enable_isaac_bridge:=', launch_case)
        self.assertIn('enable_simulation:=true', launch_case)


if __name__ == '__main__':
    unittest.main()
