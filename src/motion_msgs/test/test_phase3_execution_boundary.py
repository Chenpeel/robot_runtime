"""docs/plan.md Phase 3 命令与反馈执行边界合同。"""

import ast
import unittest
from pathlib import Path
from xml.etree import ElementTree


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RUNTIME_DEPENDENCY_TAGS = {
    'build_depend',
    'build_export_depend',
    'depend',
    'exec_depend',
}


def _read(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding='utf-8')


def _manifest(relative_path: str):
    return ElementTree.parse(REPOSITORY_ROOT / relative_path).getroot()


def _manifest_name(relative_path: str) -> str:
    return str(_manifest(relative_path).findtext('name') or '').strip()


def _manifest_dependencies(relative_path: str) -> set:
    return {
        str(element.text or '').strip()
        for element in _manifest(relative_path)
        if element.tag in RUNTIME_DEPENDENCY_TAGS
        and str(element.text or '').strip()
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
                roots.update(alias.name.split('.', 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                roots.add(node.module.split('.', 1)[0])
    return roots


def _imported_names(relative_path: str, module: str) -> set:
    names = set()
    tree = ast.parse(_read(relative_path), filename=relative_path)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


def _ros_factory_message_types(relative_path: str, factory_name: str) -> set:
    message_types = set()
    tree = ast.parse(_read(relative_path), filename=relative_path)
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == factory_name
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            continue
        message_types.add(node.args[0].id)
    return message_types


def _runtime_string_literals(relative_directory: str) -> set:
    literals = set()
    directory = REPOSITORY_ROOT / relative_directory
    for path in directory.rglob('*.py'):
        tree = ast.parse(
            path.read_text(encoding='utf-8'),
            filename=str(path.relative_to(REPOSITORY_ROOT)),
        )
        literals.update(
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        )
    return literals


class TestPhase3ExecutionBoundary(unittest.TestCase):
    """固定上层、执行层和驱动层之间的双向接口边界。"""

    def test_motion_msgs_exports_actuator_state_contract(self):
        message_source = _read('src/motion_msgs/msg/ActuatorState.msg')
        required_fields = {
            'string actuator_type',
            'uint16 actuator_id',
            'uint16 position_raw',
            'string value_encoding',
            'int16 load',
            'int16 temperature',
            'string status',
            'string reason',
            'bool recoverable',
            'uint8 driver_error_code',
            'builtin_interfaces/Time stamp',
        }

        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, message_source)

        self.assertIn(
            '"msg/ActuatorState.msg"',
            _read('src/motion_msgs/CMakeLists.txt'),
        )

    def test_upper_packages_depend_only_on_motion_interface(self):
        upper_packages = {
            'src/websocket': 'src/websocket/websocket_bridge',
            'src/parallel_3dof_controller': (
                'src/parallel_3dof_controller/parallel_3dof_controller'
            ),
            'src/record_load_action': (
                'src/record_load_action/record_load_action'
            ),
        }

        for package_directory, runtime_directory in upper_packages.items():
            with self.subTest(package=package_directory):
                dependencies = _manifest_dependencies(
                    f'{package_directory}/package.xml'
                )
                self.assertIn('motion_msgs', dependencies)
                self.assertNotIn('servo_msgs', dependencies)
                self.assertNotIn(
                    'servo_msgs',
                    _import_roots(runtime_directory),
                )
                self.assertNotIn(
                    '/servo/command',
                    _runtime_string_literals(runtime_directory),
                )

    def test_servo_msgs_runtime_dependencies_are_driver_boundary_only(self):
        owners = set()
        for manifest_path in (REPOSITORY_ROOT / 'src').rglob('package.xml'):
            relative_path = str(manifest_path.relative_to(REPOSITORY_ROOT))
            if 'servo_msgs' in _manifest_dependencies(relative_path):
                owners.add(_manifest_name(relative_path))

        allowed_owners = {
            'execution_manager',
            'sensor_hardware',
            'servo_hardware',
            'sim_joint_bridge_cpp',
            'simulation_bridge',
        }
        required_owners = allowed_owners - {'sensor_hardware'}
        self.assertTrue(
            owners.issubset(allowed_owners),
            msg=f'unexpected servo_msgs owners: {owners - allowed_owners}',
        )
        self.assertTrue(required_owners.issubset(owners))

        self.assertNotIn(
            'motion_msgs',
            _manifest_dependencies('src/hardware/package.xml'),
        )
        self.assertNotIn(
            'motion_msgs',
            _import_roots('src/hardware/servo_hardware'),
        )

    def test_execution_manager_owns_command_and_feedback_adaptation(self):
        node_path = (
            'src/execution_manager/execution_manager/'
            'execution_manager_node.py'
        )
        motion_imports = _imported_names(node_path, 'motion_msgs.msg')
        servo_imports = _imported_names(node_path, 'servo_msgs.msg')
        publishers = _ros_factory_message_types(node_path, 'create_publisher')
        subscriptions = _ros_factory_message_types(
            node_path,
            'create_subscription',
        )

        self.assertTrue(
            {'ActuatorState', 'ExecutionState', 'MotionCommand'}
            .issubset(motion_imports)
        )
        self.assertEqual(
            {'DriverSafetyState', 'ServoCommand', 'ServoState'},
            servo_imports,
        )
        self.assertTrue(
            {'ActuatorState', 'ExecutionState', 'ServoCommand'}
            .issubset(publishers)
        )
        self.assertTrue(
            {'MotionCommand', 'ServoState', 'TeleopControl'}
            .issubset(subscriptions)
        )

    def test_websocket_consumes_execution_feedback_not_driver_feedback(self):
        bridge_path = 'src/websocket/websocket_bridge/bridge_node.py'
        motion_imports = _imported_names(bridge_path, 'motion_msgs.msg')
        subscriptions = _ros_factory_message_types(
            bridge_path,
            'create_subscription',
        )

        self.assertIn('ActuatorState', motion_imports)
        self.assertNotIn('ServoState', _read(bridge_path))
        self.assertIn('ActuatorState', subscriptions)
        self.assertNotIn(
            '/servo/state',
            _runtime_string_literals('src/websocket/websocket_bridge'),
        )

    def test_bringup_wires_execution_feedback_topic(self):
        teleop_source = _read(
            'src/robot_bringup/launch/teleop.launch.py'
        )
        full_system_source = _read(
            'src/robot_bringup/launch/full_system.launch.py'
        )

        self.assertIn("'driver_state_topic': '/servo/state'", teleop_source)
        self.assertGreaterEqual(
            teleop_source.count("'actuator_state_topic':"),
            2,
        )
        self.assertIn(
            "'execution_actuator_state_topic'",
            teleop_source,
        )
        self.assertIn(
            "'execution_actuator_state_topic'",
            full_system_source,
        )


if __name__ == '__main__':
    unittest.main()
