"""docs/plan.md Phase 4A 正式任务执行准入边界合同。"""

import ast
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _read(relative_path: str) -> str:
    return (REPOSITORY_ROOT / relative_path).read_text(encoding='utf-8')


def _message_fields(relative_path: str) -> list:
    fields = []
    for line in _read(relative_path).splitlines():
        field = line.split('#', 1)[0].strip()
        if field:
            fields.append(field)
    return fields


def _imported_names(relative_path: str, module: str) -> set:
    tree = ast.parse(_read(relative_path), filename=relative_path)
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            names.update(alias.name for alias in node.names)
    return names


def _ros_factory_message_types(relative_path: str, factory_name: str) -> set:
    tree = ast.parse(_read(relative_path), filename=relative_path)
    result = set()
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == factory_name
            and node.args
            and isinstance(node.args[0], ast.Name)
        ):
            continue
        result.add(node.args[0].id)
    return result


class TestPhase4TaskAdmissionBoundary(unittest.TestCase):
    """固定正式 task、teleop、普通 motion 与驱动层之间的入口边界。"""

    def test_motion_msgs_exports_task_control_and_state(self):
        cmake = _read('src/motion_msgs/CMakeLists.txt')
        self.assertIn('"msg/TaskExecutionControl.msg"', cmake)
        self.assertIn('"msg/TaskExecutionState.msg"', cmake)

        self.assertEqual(
            [
                'string action',
                'string task_id',
                'string trace_id',
                'string session_id',
                'string lease_id',
                'builtin_interfaces/Time stamp',
            ],
            _message_fields(
                'src/motion_msgs/msg/TaskExecutionControl.msg'
            ),
        )
        state_fields = _message_fields(
            'src/motion_msgs/msg/TaskExecutionState.msg'
        )
        for field in (
            'bool active',
            'string task_id',
            'string trace_id',
            'string session_id',
            'string lease_id',
            'float32 lease_remaining_sec',
            'string status',
            'string reason',
            'bool recoverable',
            'string last_command_requester_id',
            'bool last_command_accepted',
            'string last_command_reason',
            'uint32 command_rejected_count',
        ):
            with self.subTest(field=field):
                self.assertIn(field, state_fields)

    def test_existing_command_and_execution_state_layouts_remain_stable(self):
        self.assertEqual(
            [
                'string servo_type',
                'uint16 servo_id',
                'uint16 position',
                'uint16 speed',
                'string value_encoding',
                'uint16 duration_ms',
                'string requester_id',
                'string lease_id',
                'builtin_interfaces/Time stamp',
            ],
            _message_fields('src/motion_msgs/msg/MotionCommand.msg'),
        )
        self.assertEqual(
            [
                'string mode',
                'string active_source',
                'string teleop_holder_id',
                'string teleop_lease_id',
                'bool estop_active',
                'bool teleop_active',
                'bool motion_active',
                'float32 teleop_timeout_sec',
                'float32 motion_timeout_sec',
                'float32 teleop_control_remaining_sec',
                'string last_teleop_control_action',
                'bool last_teleop_control_accepted',
                'string last_teleop_control_reason',
                'uint32 teleop_control_accepted_count',
                'uint32 teleop_control_rejected_count',
                'uint32 teleop_accepted_count',
                'uint32 motion_accepted_count',
                'uint32 teleop_rejected_count',
                'uint32 motion_rejected_count',
                'string last_rejection_reason',
                'builtin_interfaces/Time stamp',
            ],
            _message_fields('src/motion_msgs/msg/ExecutionState.msg'),
        )

    def test_execution_manager_owns_task_admission_and_state(self):
        node_path = (
            'src/execution_manager/execution_manager/'
            'execution_manager_node.py'
        )
        imports = _imported_names(node_path, 'motion_msgs.msg')
        publishers = _ros_factory_message_types(node_path, 'create_publisher')
        subscriptions = _ros_factory_message_types(
            node_path,
            'create_subscription',
        )

        self.assertTrue(
            {'MotionCommand', 'TaskExecutionControl', 'TaskExecutionState'}
            .issubset(imports)
        )
        self.assertIn('TaskExecutionState', publishers)
        self.assertTrue(
            {'MotionCommand', 'TaskExecutionControl'}
            .issubset(subscriptions)
        )
        arbitrator = _read(
            'src/execution_manager/execution_manager/arbitrator.py'
        )
        self.assertIn("self.mode = 'task_active'", arbitrator)
        self.assertIn("self.active_source = 'task'", arbitrator)
        self.assertIn("return self._reject(source, 'task_active')", arbitrator)
        self.assertIn("'task_control_replay'", arbitrator)
        self.assertIn('self.last_motion_time = None', arbitrator)

    def test_ros_pub_sub_smoke_is_colcon_discoverable(self):
        runner = _read(
            'src/execution_manager/test/task_admission_ros_smoke.py'
        )
        pytest_entry = _read(
            'src/execution_manager/test/test_task_admission_ros_smoke.py'
        )

        self.assertIn('def run_scenario()', runner)
        self.assertIn('def test_task_admission_ros_pub_sub()', pytest_entry)
        self.assertIn('run_scenario()', pytest_entry)

    def test_launches_wire_task_topics_and_timeout(self):
        launch_paths = (
            'src/execution_manager/launch/execution_manager.launch.py',
            'src/robot_bringup/launch/teleop.launch.py',
            'src/robot_bringup/launch/full_system.launch.py',
        )
        required_tokens = (
            'task_command_topic',
            'task_control_topic',
            'task_state_topic',
            'task_timeout_sec',
        )
        for path in launch_paths:
            source = _read(path)
            for token in required_tokens:
                with self.subTest(path=path, token=token):
                    self.assertIn(token, source)

    def test_bvh_blocks_task_window_but_websocket_is_not_task_entry(self):
        extension = _read(
            'src/record_load_action/record_load_action/'
            'bvh_websocket_extension.py'
        )
        bridge = _read('src/websocket/websocket_bridge/bridge_node.py')

        self.assertIn("'bvh_blocked_by_active_task'", extension)
        self.assertIn("snapshot.get('active_source') == 'task'", extension)
        self.assertNotIn('TaskExecutionControl', bridge)
        self.assertNotIn('/execution/task/command', bridge)
        self.assertNotIn('/execution/task/control', bridge)

    def test_no_placeholder_external_task_entry_is_claimed(self):
        self.assertFalse((REPOSITORY_ROOT / 'src/task_api_msgs').exists())
        self.assertFalse((REPOSITORY_ROOT / 'src/task_service_bridge').exists())

        runtime_literals = set()
        for path in (REPOSITORY_ROOT / 'src').rglob('*.py'):
            tree = ast.parse(
                path.read_text(encoding='utf-8'),
                filename=str(path.relative_to(REPOSITORY_ROOT)),
            )
            runtime_literals.update(
                node.value
                for node in ast.walk(tree)
                if isinstance(node, ast.Constant)
                and isinstance(node.value, str)
            )
        external_task_action = '/task/' + 'execute'
        self.assertNotIn(external_task_action, runtime_literals)


if __name__ == '__main__':
    unittest.main()
