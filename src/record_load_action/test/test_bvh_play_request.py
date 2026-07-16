"""BVH 播放请求规范化测试。"""

import os
import sys
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../record_load_action'))

from bvh_player import normalize_bvh_play_request


class NormalizeBvhPlayRequestTest(unittest.TestCase):
    def test_accepts_explicit_direct_fields(self):
        payload = {
            'type': ' BVH_PLAY ',
            'action': 'walk',
            'loop': 'false',
            'speed_ms': 33,
            'playback_rate': 1.1,
            'frame_ms': 16.7,
        }

        self.assertEqual(
            normalize_bvh_play_request(payload),
            {
                'action': 'walk',
                'loop': True,
                'speed_ms': 33,
                'playback_rate': 1.1,
                'frame_ms': 16.7,
            },
        )

    def test_accepts_explicit_stop(self):
        self.assertEqual(
            normalize_bvh_play_request({
                'type': 'bvh_play',
                'action': None,
            }),
            {
                'action': None,
                'loop': False,
                'speed_ms': None,
                'playback_rate': None,
                'frame_ms': None,
            },
        )

    def test_rejects_nested_action(self):
        self.assertIsNone(normalize_bvh_play_request({
            'type': 'bvh_play',
            'action': {'bvh': 'walk'},
        }))

    def test_rejects_top_level_bvh_alias(self):
        self.assertIsNone(normalize_bvh_play_request({
            'type': 'bvh_play',
            'bvh': 'walk',
        }))

    def test_rejects_wrong_type(self):
        self.assertIsNone(normalize_bvh_play_request({
            'type': 'action',
            'action': 'walk',
        }))

    def test_rejects_missing_action(self):
        self.assertIsNone(normalize_bvh_play_request({
            'type': 'bvh_play',
        }))

    def test_rejects_non_dict(self):
        self.assertIsNone(normalize_bvh_play_request('bvh_play'))


if __name__ == '__main__':
    unittest.main()
