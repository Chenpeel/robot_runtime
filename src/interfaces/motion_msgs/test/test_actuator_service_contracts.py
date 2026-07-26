"""执行器真实位置读取与停止确认 Service 合同。"""

import unittest
from pathlib import Path
from typing import List


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _service_sections(filename: str) -> List[List[str]]:
    path = PACKAGE_ROOT / 'srv' / filename
    sections: List[List[str]] = [[]]
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        declaration = raw_line.split('#', 1)[0].strip()
        if not declaration:
            continue
        if declaration == '---':
            sections.append([])
            continue
        sections[-1].append(declaration)
    return sections


class TestActuatorServiceContracts(unittest.TestCase):
    """冻结位置读取、停止请求及真实停止确认边界。"""

    def test_read_actuator_position_exact_fields(self):
        self.assertEqual(
            [
                [
                    'string task_id',
                    'string trace_id',
                    'string session_id',
                    'string lease_id',
                    'string actuator_type',
                    'uint16 actuator_id',
                ],
                [
                    'bool success',
                    'uint16 position_raw',
                    'string value_encoding',
                    'string status',
                    'string reason',
                    'bool recoverable',
                    'builtin_interfaces/Time stamp',
                ],
            ],
            _service_sections('ReadActuatorPosition.srv'),
        )

    def test_stop_actuators_exact_fields(self):
        self.assertEqual(
            [
                [
                    'string task_id',
                    'string trace_id',
                    'string session_id',
                    'string lease_id',
                    'string actuator_type',
                    'uint16[] actuator_ids',
                ],
                [
                    'bool accepted',
                    'bool stop_command_sent',
                    'bool stop_confirmed',
                    'string status',
                    'string reason',
                    'bool recoverable',
                    'uint16[] stopped_actuator_ids',
                    'uint16[] unsupported_actuator_ids',
                    'builtin_interfaces/Time stamp',
                ],
            ],
            _service_sections('StopActuators.srv'),
        )

    def test_read_and_stop_safety_semantics_are_explicit(self):
        read_source = (
            PACKAGE_ROOT / 'srv' / 'ReadActuatorPosition.srv'
        ).read_text(encoding='utf-8')
        stop_source = (
            PACKAGE_ROOT / 'srv' / 'StopActuators.srv'
        ).read_text(encoding='utf-8')

        self.assertIn('来自实际位置读取', read_source)
        self.assertIn('不能复用命令目标值', read_source)
        self.assertIn('只表示停止指令已经写出', stop_source)
        self.assertIn('只能来自后续真实稳定位置采样', stop_source)
        self.assertIn('stop_confirmed 保持为 false', stop_source)

    def test_services_are_registered_with_builtin_interfaces(self):
        cmake_source = (PACKAGE_ROOT / 'CMakeLists.txt').read_text(
            encoding='utf-8'
        )
        package_source = (PACKAGE_ROOT / 'package.xml').read_text(
            encoding='utf-8'
        )

        self.assertIn('"srv/ReadActuatorPosition.srv"', cmake_source)
        self.assertIn('"srv/StopActuators.srv"', cmake_source)
        self.assertIn(
            'DEPENDENCIES action_msgs builtin_interfaces',
            cmake_source,
        )
        self.assertIn('<depend>builtin_interfaces</depend>', package_source)


if __name__ == '__main__':
    unittest.main()
