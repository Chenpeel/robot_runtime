"""MotionCommand.speed 公共字段迁移门禁。"""

import ast
import unittest
from pathlib import Path
from typing import List, Tuple


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _message_fields(relative_path: str) -> List[Tuple[str, str]]:
    fields = []
    source = (REPOSITORY_ROOT / relative_path).read_text(encoding='utf-8')
    for raw_line in source.splitlines():
        declaration = raw_line.split('#', 1)[0].strip()
        if not declaration:
            continue
        field_type, field_name = declaration.split()
        fields.append((field_type, field_name))
    return fields


def _python_tree(relative_path: str) -> ast.AST:
    source = (REPOSITORY_ROOT / relative_path).read_text(encoding='utf-8')
    return ast.parse(source, filename=relative_path)


def _attribute_accesses(
    relative_path: str,
    attribute: str,
) -> List[ast.Attribute]:
    tree = _python_tree(relative_path)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute) and node.attr == attribute
    ]


def _dynamic_attribute_accesses(
    relative_path: str,
    function_name: str,
    attribute: str,
) -> List[ast.Call]:
    tree = _python_tree(relative_path)
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == function_name
        and len(node.args) >= 2
        and isinstance(node.args[1], ast.Constant)
        and node.args[1].value == attribute
    ]


class TestMotionCommandSpeedMigration(unittest.TestCase):
    """防止已弃用字段重新进入仓库内置运行链路。"""

    def test_public_field_is_deprecated_during_migration_window(self):
        relative_path = 'src/motion_msgs/msg/MotionCommand.msg'
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding='utf-8')
        fields = _message_fields(relative_path)

        self.assertIn(('uint16', 'duration_ms'), fields)
        self.assertIn(('uint16', 'speed'), fields)
        self.assertIn('DEPRECATED', source)
        self.assertIn('新调用方必须使用 duration_ms', source)

    def test_builtin_producers_do_not_write_speed(self):
        producers = (
            'src/websocket/websocket_bridge/bridge_node.py',
            'src/parallel_3dof_controller/'
            'parallel_3dof_controller/controller_node.py',
            'src/record_load_action/record_load_action/'
            'bvh_websocket_extension.py',
        )

        for relative_path in producers:
            with self.subTest(path=relative_path):
                speed_accesses = _attribute_accesses(relative_path, 'speed')
                writes = [
                    node
                    for node in speed_accesses
                    if isinstance(node.ctx, ast.Store)
                ]
                self.assertEqual([], writes)
                self.assertEqual(
                    [],
                    _dynamic_attribute_accesses(
                        relative_path,
                        'setattr',
                        'speed',
                    ),
                )

    def test_execution_adapter_does_not_read_speed(self):
        relative_path = (
            'src/execution_manager/execution_manager/command_adapter.py'
        )
        source = (REPOSITORY_ROOT / relative_path).read_text(encoding='utf-8')
        speed_accesses = _attribute_accesses(relative_path, 'speed')
        speed_getattr_calls = _dynamic_attribute_accesses(
            relative_path,
            'getattr',
            'speed',
        )

        self.assertEqual([], speed_accesses)
        self.assertEqual([], speed_getattr_calls)
        self.assertIn("getattr(msg, 'duration_ms', 0)", source)

    def test_distinct_speed_contracts_remain_intact(self):
        servo_fields = _message_fields(
            'src/servo_msgs/msg/ServoCommand.msg'
        )
        execution_source = (
            REPOSITORY_ROOT
            / 'src/execution_manager/execution_manager/execution_manager_node.py'
        ).read_text(encoding='utf-8')
        websocket_source = (
            REPOSITORY_ROOT
            / 'src/websocket/websocket_bridge/message_handler.py'
        ).read_text(encoding='utf-8')
        bvh_request_source = (
            REPOSITORY_ROOT
            / 'src/record_load_action/record_load_action/bvh_request.py'
        ).read_text(encoding='utf-8')
        bvh_runtime_source = (
            REPOSITORY_ROOT
            / 'src/record_load_action/record_load_action/bvh_runtime.py'
        ).read_text(encoding='utf-8')

        self.assertIn(('uint16', 'speed'), servo_fields)
        self.assertIn(
            "output_msg.speed = servo_fields['speed']",
            execution_source,
        )
        self.assertIn('"speed": duration_ms', websocket_source)
        self.assertIn(
            "'speed_ms': payload.get('speed_ms')",
            bvh_request_source,
        )
        self.assertIn(
            "speed_ms=request.get('speed_ms')",
            bvh_runtime_source,
        )


if __name__ == '__main__':
    unittest.main()
