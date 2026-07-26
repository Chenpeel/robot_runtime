"""正式 task/motion bringup 装配合同测试。"""

import ast
import unittest
from pathlib import Path
from xml.etree import ElementTree


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _read(relative_path: str) -> str:
    return (PACKAGE_ROOT / relative_path).read_text(encoding='utf-8')


def _tree(relative_path: str) -> ast.AST:
    return ast.parse(_read(relative_path), filename=relative_path)


def _launch_defaults(relative_path: str) -> dict:
    defaults = {}
    for node in ast.walk(_tree(relative_path)):
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
                keyword.value
                for keyword in node.keywords
                if keyword.arg == 'default_value'
            ),
            None,
        )
        if isinstance(default, ast.Constant):
            defaults[str(node.args[0].value)] = default.value
    return defaults


def _include_assignments(relative_path: str) -> dict:
    includes = {}
    for node in ast.walk(_tree(relative_path)):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == 'IncludeLaunchDescription'
        ):
            continue
        packages = [
            child.args[0].value
            for child in ast.walk(node.value)
            if isinstance(child, ast.Call)
            and isinstance(child.func, ast.Name)
            and child.func.id == 'FindPackageShare'
            and child.args
            and isinstance(child.args[0], ast.Constant)
        ]
        launch_files = [
            child.value
            for child in ast.walk(node.value)
            if isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and child.value.endswith('.launch.py')
        ]
        if len(packages) == 1 and len(launch_files) == 1:
            includes[node.targets[0].id] = (packages[0], launch_files[0])
    return includes


def _include_launch_arguments(relative_path: str) -> dict:
    arguments = {}
    for node in ast.walk(_tree(relative_path)):
        if not (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id == 'IncludeLaunchDescription'
        ):
            continue
        launch_arguments = next(
            (
                keyword.value
                for keyword in node.value.keywords
                if keyword.arg == 'launch_arguments'
            ),
            None,
        )
        if not (
            isinstance(launch_arguments, ast.Call)
            and isinstance(launch_arguments.func, ast.Attribute)
            and launch_arguments.func.attr == 'items'
            and isinstance(launch_arguments.func.value, ast.Dict)
        ):
            continue
        mapping = {}
        for key, value in zip(
            launch_arguments.func.value.keys,
            launch_arguments.func.value.values,
        ):
            if not (
                isinstance(key, ast.Constant)
                and isinstance(key.value, str)
                and isinstance(value, ast.Call)
                and isinstance(value.func, ast.Name)
                and value.func.id == 'LaunchConfiguration'
                and value.args
                and isinstance(value.args[0], ast.Constant)
                and isinstance(value.args[0].value, str)
            ):
                continue
            mapping[key.value] = value.args[0].value
        arguments[node.targets[0].id] = mapping
    return arguments


class TestTaskLaunchSource(unittest.TestCase):
    """固定正式 task/motion 纵向链的唯一 bringup owner。"""

    def test_task_launch_composes_exactly_three_runtime_owners(self):
        includes = _include_assignments('launch/task.launch.py')

        self.assertEqual(
            {
                'execution_manager_stack': (
                    'execution_manager',
                    'execution_manager.launch.py',
                ),
                'motion_owner_stack': (
                    'parallel_3dof_controller',
                    'parallel_3dof_controller.launch.py',
                ),
                'task_bridge_stack': (
                    'task_service_bridge',
                    'task_service_bridge.launch.py',
                ),
            },
            includes,
        )

    def test_task_launch_fixes_actions_topics_and_services(self):
        defaults = _launch_defaults('launch/task.launch.py')
        launch_arguments = _include_launch_arguments('launch/task.launch.py')

        self.assertEqual('/task/execute', defaults.get('task_action_name'))
        self.assertEqual('/motion/execute', defaults.get('motion_action_name'))
        self.assertEqual('true', defaults.get('enable_context'))
        self.assertEqual('/speech/intent', defaults.get('speech_intent_topic'))
        self.assertEqual(
            '/perception/scene_state',
            defaults.get('perception_scene_topic'),
        )
        self.assertEqual('2.0', defaults.get('scene_max_age_sec'))
        self.assertEqual(
            'camera_link',
            defaults.get('scene_required_frame_id'),
        )
        self.assertEqual('0.6', defaults.get('scene_target_min_confidence'))
        self.assertEqual('2.0', defaults.get('scene_target_max_extent_m'))
        self.assertEqual('/task/context_signal', defaults.get('task_context_topic'))
        self.assertEqual(
            '/execution/task/command',
            defaults.get('task_command_topic'),
        )
        self.assertEqual(
            '/execution/task/control',
            defaults.get('task_control_topic'),
        )
        self.assertEqual(
            '/execution/task/state',
            defaults.get('task_state_topic'),
        )
        self.assertEqual(
            '/execution/read_actuator_position',
            defaults.get('read_actuator_position_service'),
        )
        self.assertEqual(
            '/execution/stop_actuators',
            defaults.get('stop_actuators_service'),
        )
        self.assertEqual(
            '/servo/read_position',
            defaults.get('driver_read_position_service'),
        )
        self.assertEqual(
            '/servo/execute_command',
            defaults.get('driver_execute_command_service'),
        )
        self.assertEqual(
            '/servo/driver_safety',
            defaults.get('driver_safety_topic'),
        )
        self.assertEqual(
            '/servo/set_driver_safety',
            defaults.get('driver_safety_service'),
        )
        self.assertEqual('2.0', defaults.get('driver_service_timeout_sec'))

        execution_arguments = launch_arguments['execution_manager_stack']
        motion_arguments = launch_arguments['motion_owner_stack']
        bridge_arguments = launch_arguments['task_bridge_stack']

        self.assertEqual('task_action_name', bridge_arguments['task_action_name'])
        self.assertEqual(
            'motion_action_name',
            bridge_arguments['motion_action_name'],
        )
        for interface_name in (
            'enable_context',
            'speech_intent_topic',
            'perception_scene_topic',
            'task_context_topic',
        ):
            self.assertEqual(interface_name, bridge_arguments[interface_name])
        self.assertEqual(
            'motion_action_name',
            motion_arguments['motion_action_name'],
        )
        self.assertEqual(
            'enable_context',
            motion_arguments['require_scene_context'],
        )
        self.assertEqual(
            'perception_scene_topic',
            motion_arguments['scene_state_topic'],
        )
        self.assertEqual(
            'scene_max_age_sec',
            motion_arguments['scene_max_age_sec'],
        )
        for interface_name in (
            'scene_required_frame_id',
            'scene_target_min_confidence',
            'scene_target_max_extent_m',
        ):
            self.assertEqual(interface_name, motion_arguments[interface_name])
        for interface_name in (
            'task_command_topic',
            'task_control_topic',
            'task_state_topic',
            'read_actuator_position_service',
            'stop_actuators_service',
        ):
            self.assertEqual(
                interface_name,
                execution_arguments[interface_name],
            )
            self.assertEqual(interface_name, motion_arguments[interface_name])
        self.assertEqual(
            'driver_service_timeout_sec',
            execution_arguments['driver_service_timeout_sec'],
        )
        self.assertEqual(
            'driver_safety_topic',
            execution_arguments['driver_safety_topic'],
        )
        self.assertEqual(
            'driver_safety_service',
            execution_arguments['driver_safety_service'],
        )

    def test_execution_manager_is_optional_only_at_the_task_boundary(self):
        source = _read('launch/task.launch.py')

        self.assertIn(
            "condition=IfCondition(LaunchConfiguration('enable_execution_manager'))",
            source,
        )
        self.assertNotIn("condition=IfCondition(LaunchConfiguration('debug'))", source)

    def test_full_system_disables_teleop_manager_and_includes_task_stack(self):
        source = _read('launch/full_system.launch.py')
        includes = _include_assignments('launch/full_system.launch.py')

        self.assertEqual(
            ('robot_bringup', 'task.launch.py'),
            includes.get('task_stack'),
        )
        self.assertIn("'enable_execution_manager': 'false'", source)
        self.assertEqual(1, source.count("'enable_execution_manager': 'false'"))
        self.assertIn(
            "'enable_execution_manager': LaunchConfiguration('enable_execution_manager')",
            source,
        )
        self.assertIn(
            "'driver_safety_topic': LaunchConfiguration('driver_safety_topic')",
            source,
        )
        self.assertIn(
            "'enable_context': LaunchConfiguration('enable_context')",
            source,
        )

    def test_standalone_teleop_still_owns_manager_by_default(self):
        defaults = _launch_defaults('launch/teleop.launch.py')
        source = _read('launch/teleop.launch.py')

        self.assertEqual('true', defaults.get('enable_execution_manager'))
        self.assertIn("package='execution_manager'", source)
        self.assertIn(
            "condition=IfCondition(LaunchConfiguration('enable_execution_manager'))",
            source,
        )

    def test_hardware_stack_wires_driver_safety_to_both_layers(self):
        defaults = _launch_defaults('launch/hardware.launch.py')
        source = _read('launch/hardware.launch.py')

        self.assertEqual(
            '/servo/driver_safety',
            defaults.get('driver_safety_topic'),
        )
        self.assertEqual(
            2,
            source.count(
                "{'driver_safety_topic': "
                "LaunchConfiguration('driver_safety_topic')}"
            ),
        )
        self.assertEqual(
            1,
            source.count(
                "{'driver_safety_service': "
                "LaunchConfiguration('driver_safety_service')}"
            ),
        )

    def test_manifest_declares_formal_task_runtime_dependencies(self):
        manifest = ElementTree.fromstring(_read('package.xml'))
        dependencies = {
            str(element.text or '').strip()
            for element in manifest.findall('exec_depend')
        }

        self.assertIn('task_api_msgs', dependencies)
        self.assertIn('task_service_bridge', dependencies)
        self.assertIn('parallel_3dof_controller', dependencies)
        self.assertIn('execution_manager', dependencies)

    def test_multi_system_keeps_single_formal_motion_owner(self):
        multi_launch = (
            PACKAGE_ROOT.parents[1]
            / 'control'
            / 'parallel_3dof_controller'
            / 'launch'
            / 'parallel_3dof_multi.launch.py'
        ).read_text(encoding='utf-8')

        self.assertIn(
            "params['enable_motion_action_server'] = False",
            multi_launch,
        )


if __name__ == '__main__':
    unittest.main()
