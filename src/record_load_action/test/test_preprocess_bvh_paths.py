"""BVH 预处理脚本的资源所有权、路径解析与真实转换测试。"""

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPOSITORY_ROOT / 'scripts/preprocess_bvh.py'
SPEC = importlib.util.spec_from_file_location('preprocess_bvh', SCRIPT_PATH)
PREPROCESS_BVH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPROCESS_BVH)


class TestPreprocessBvhPaths(unittest.TestCase):
    """确保离线工具从 record_load_action 正确解析并转换 BVH 资源。"""

    def test_default_config_belongs_to_record_load_action(self):
        config_path = PREPROCESS_BVH._default_config_path()

        self.assertEqual(
            REPOSITORY_ROOT
            / 'src/record_load_action/config/bvh_action_map.json',
            config_path,
        )
        self.assertTrue(config_path.is_file())

    def test_configured_relative_directory_uses_config_parent(self):
        config_path = Path('/tmp/preprocess-config/nested/actions.json')

        input_dir = PREPROCESS_BVH._resolve_input_dir(
            config_path=config_path,
            override=None,
            configured_dir='../bvh',
        )

        self.assertEqual(
            Path('/tmp/preprocess-config/bvh').resolve(),
            input_dir,
        )

    def test_explicit_input_directory_takes_precedence(self):
        override = REPOSITORY_ROOT / 'src/record_load_action/config/bvh'

        input_dir = PREPROCESS_BVH._resolve_input_dir(
            config_path=Path('/tmp/unrelated/actions.json'),
            override=override,
            configured_dir='../wrong-directory',
        )

        self.assertEqual(override.resolve(), input_dir)

    def test_missing_directory_configuration_is_explicit(self):
        self.assertIsNone(
            PREPROCESS_BVH._resolve_input_dir(
                config_path=Path('/tmp/config.json'),
                override=None,
                configured_dir='',
            )
        )

    def test_current_mapping_schema_expands_alias_axis_and_direction(self):
        defaults = {
            'channel': 'Zrotation',
            'scale': 10.0,
            'bias': 1500.0,
            'min': 500.0,
            'max': 2500.0,
            'servo_type': 'bus',
        }
        entries = PREPROCESS_BVH._expand_joint_map(
            {
                'hip.R': {
                    'pitch_target': {
                        'id': 1,
                        'channel': 'Y',
                        'invert': True,
                    },
                    'roll_target': {
                        'id': 2,
                        'channel': 'Xrotation',
                        'invert': True,
                        'sign': 0.5,
                        'min': 600,
                        'max': 2400,
                    },
                },
                'ankle.R': {
                    'right_ankle_joint': '9',
                    '9': 'ankle.R.yaw',
                },
            },
            defaults,
            joint_alias={
                'thigh.R': 'hip.R',
                'foot.R': 'ankle.R',
            },
            axis_channel_map={'yaw': 'Zrotation'},
            servo_limits={
                '1': {'min': 1000, 'max': 2000},
                '9': {'min': 1167, 'max': 1833},
            },
        )
        entries_by_id = {entry['servo_id']: entry for entry in entries}

        self.assertEqual({1, 2, 9}, set(entries_by_id))
        self.assertEqual('thigh.R', entries_by_id[1]['bvh_joint'])
        self.assertEqual('Yrotation', entries_by_id[1]['channel'])
        self.assertEqual(-1.0, entries_by_id[1]['sign'])
        self.assertEqual(1000.0, entries_by_id[1]['min'])
        self.assertEqual(2000.0, entries_by_id[1]['max'])
        self.assertEqual(0.5, entries_by_id[2]['sign'])
        self.assertEqual(600.0, entries_by_id[2]['min'])
        self.assertEqual(2400.0, entries_by_id[2]['max'])
        self.assertEqual('foot.R', entries_by_id[9]['bvh_joint'])
        self.assertEqual('Zrotation', entries_by_id[9]['channel'])
        self.assertEqual(1167.0, entries_by_id[9]['min'])
        self.assertEqual(1833.0, entries_by_id[9]['max'])

    def test_default_config_generates_all_bundled_actions(self):
        config = json.loads(
            PREPROCESS_BVH._default_config_path().read_text(encoding='utf-8')
        )
        expected_actions = {
            action
            for action in config['bvh_list']
            if isinstance(action, str) and action
        }
        expected_servo_ids = {
            int(servo_id)
            for servo_id in config['servo_limits']
        }
        input_dir = PREPROCESS_BVH._resolve_input_dir(
            config_path=PREPROCESS_BVH._default_config_path(),
            override=None,
            configured_dir=config['bvh_dir'],
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            output_path = Path(temporary_directory) / 'actions.frames.json'
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), '--output', str(output_path)],
                cwd=temporary_directory,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )

            self.assertEqual(0, result.returncode, msg=result.stderr)
            generated = json.loads(output_path.read_text(encoding='utf-8'))
            self.assertEqual(expected_actions, set(generated['bvh_data']))
            for action_name in expected_actions:
                with self.subTest(action=action_name):
                    frames = generated['bvh_data'][action_name]['frames']
                    self.assertTrue(frames)
                    self.assertTrue(all(frame for frame in frames))
                    reference_name = config['bvh_action_files'][
                        f'{action_name}.bvh'
                    ]
                    reference = json.loads(
                        (input_dir / reference_name).read_text(encoding='utf-8')
                    )
                    self.assertEqual(reference['frames'], frames)
                    for frame in frames:
                        self.assertEqual(len(expected_servo_ids), len(frame))
                        self.assertEqual(
                            expected_servo_ids,
                            {command['id'] for command in frame},
                        )
                        for command in frame:
                            limits = config['servo_limits'][str(command['id'])]
                            self.assertLessEqual(
                                limits['min'], command['position']
                            )
                            self.assertLessEqual(
                                command['position'], limits['max']
                            )


if __name__ == '__main__':
    unittest.main()
