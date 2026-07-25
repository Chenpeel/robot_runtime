"""TaskContextSignal 字段与生成注册合同。"""

import unittest
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MESSAGE_PATH = PACKAGE_ROOT / 'msg' / 'TaskContextSignal.msg'


def _message_fields():
    fields = []
    for raw_line in MESSAGE_PATH.read_text(encoding='utf-8').splitlines():
        declaration = raw_line.split('#', 1)[0].strip()
        if declaration:
            fields.append(declaration)
    return fields


class TestTaskContextSignalContract(unittest.TestCase):
    """防止外部上下文边界退化为自由协议透传。"""

    def test_exact_fields(self):
        self.assertEqual(
            [
                'builtin_interfaces/Time stamp',
                'string source',
                'string event_id',
                'string session_id',
                'string status',
                'string reason',
                'bool recoverable',
                'string summary',
                'string[] labels',
            ],
            _message_fields(),
        )

    def test_build_registration_and_semantics(self):
        cmake_source = (PACKAGE_ROOT / 'CMakeLists.txt').read_text(
            encoding='utf-8'
        )
        message_source = MESSAGE_PATH.read_text(encoding='utf-8')

        self.assertIn('"msg/TaskContextSignal.msg"', cmake_source)
        self.assertIn('find_package(builtin_interfaces REQUIRED)', cmake_source)
        self.assertIn('speech 或 perception', message_source)
        self.assertIn('不承载内部协议原文', message_source)


if __name__ == '__main__':
    unittest.main()
