"""ExecuteTask Action 冻结字段与安全语义合同。"""

import unittest
from pathlib import Path
from typing import List


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ACTION_PATH = PACKAGE_ROOT / 'action' / 'ExecuteTask.action'


def _action_sections() -> List[List[str]]:
    sections: List[List[str]] = [[]]
    for raw_line in ACTION_PATH.read_text(encoding='utf-8').splitlines():
        declaration = raw_line.split('#', 1)[0].strip()
        if not declaration:
            continue
        if declaration == '---':
            sections.append([])
            continue
        sections[-1].append(declaration)
    return sections


class TestExecuteTaskActionContract(unittest.TestCase):
    """防止 task goal/result/feedback 接口发生未审查漂移。"""

    def test_exact_goal_result_and_feedback_fields(self):
        self.assertEqual(
            [
                [
                    'string task_id',
                    'string trace_id',
                    'string session_id',
                    'string task_type',
                    'string target_group',
                    'float64 roll_deg',
                    'float64 pitch_deg',
                    'float64 yaw_deg',
                    'uint16 duration_ms',
                    'uint16 position_tolerance',
                    'float32 execution_timeout_sec',
                ],
                [
                    'bool success',
                    'string task_id',
                    'string trace_id',
                    'string session_id',
                    'string status',
                    'string reason',
                    'bool recoverable',
                    'bool target_reached',
                    'bool admission_released',
                    'bool stop_requested',
                    'bool stop_command_sent',
                    'bool stop_confirmed',
                ],
                [
                    'string task_id',
                    'string trace_id',
                    'string session_id',
                    'string status',
                    'string reason',
                    'float32 progress',
                    'uint32 reached_actuator_count',
                    'uint32 target_actuator_count',
                    'bool cancel_requested',
                    'bool stop_command_sent',
                    'bool stop_confirmed',
                ],
            ],
            _action_sections(),
        )

    def test_completion_and_stop_semantics_are_explicit(self):
        source = ACTION_PATH.read_text(encoding='utf-8')

        self.assertIn('完成必须来自 execution_manager 实际位置读取的新采样', source)
        self.assertIn('stop_requested 与 stop_confirmed 必须分离', source)
        self.assertIn('当前没有驱动 stop ack 时', source)
        self.assertIn('stop_confirmed 不得置为 true', source)

    def test_status_values_and_build_registration_are_frozen(self):
        source = ACTION_PATH.read_text(encoding='utf-8')
        cmake_source = (PACKAGE_ROOT / 'CMakeLists.txt').read_text(
            encoding='utf-8'
        )
        package_source = (PACKAGE_ROOT / 'package.xml').read_text(
            encoding='utf-8'
        )

        for status in (
            'succeeded',
            'cancelled',
            'timed_out',
            'failed',
            'rejected',
        ):
            with self.subTest(status=status):
                self.assertIn(status, source)

        self.assertIn('"action/ExecuteTask.action"', cmake_source)
        self.assertIn('find_package(action_msgs REQUIRED)', cmake_source)
        self.assertIn('<depend>action_msgs</depend>', package_source)


if __name__ == '__main__':
    unittest.main()
