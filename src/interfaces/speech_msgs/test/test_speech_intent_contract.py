"""SpeechIntent 消息字段与构建注册合同。"""

from pathlib import Path
import unittest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
MESSAGE_PATH = PACKAGE_ROOT / 'msg' / 'SpeechIntent.msg'


def _message_fields():
    fields = []
    for raw_line in MESSAGE_PATH.read_text(encoding='utf-8').splitlines():
        declaration = raw_line.split('#', 1)[0].strip()
        if declaration:
            fields.append(declaration)
    return fields


class SpeechIntentContractTest(unittest.TestCase):
    """防止结构化语音意图接口发生未审查漂移。"""

    def test_exact_fields(self):
        self.assertEqual(
            [
                'builtin_interfaces/Time stamp',
                'string intent_id',
                'string task_id',
                'string trace_id',
                'string session_id',
                'string task_type',
                'string target_group',
                'float64 roll',
                'float64 pitch',
                'float64 yaw',
                'uint16 duration_ms',
                'uint16 position_tolerance',
                'float32 execution_timeout_sec',
                'float32 confidence',
                'string status',
                'string reason',
                'bool recoverable',
            ],
            _message_fields(),
        )

    def test_interface_is_registered_with_runtime_dependencies(self):
        cmake_source = (PACKAGE_ROOT / 'CMakeLists.txt').read_text(
            encoding='utf-8'
        )
        package_source = (PACKAGE_ROOT / 'package.xml').read_text(
            encoding='utf-8'
        )

        self.assertIn('"msg/SpeechIntent.msg"', cmake_source)
        self.assertIn('find_package(builtin_interfaces REQUIRED)', cmake_source)
        self.assertIn('DEPENDENCIES builtin_interfaces', cmake_source)
        self.assertIn('<depend>builtin_interfaces</depend>', package_source)
        self.assertIn(
            '<member_of_group>rosidl_interface_packages</member_of_group>',
            package_source,
        )
        self.assertIn('TIMEOUT 60', cmake_source)


if __name__ == '__main__':
    unittest.main()
