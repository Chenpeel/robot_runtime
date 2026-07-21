"""视觉场景 JSON 严格解析测试。"""

import json
from pathlib import Path
import sys
import unittest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from vision_perception.scene_parser import parse_scene_json  # noqa: E402
from vision_perception.scene_parser import MAX_OBJECTS  # noqa: E402
from vision_perception.scene_parser import MAX_PAYLOAD_CHARS  # noqa: E402


def valid_payload(**overrides):
    payload = {
        'observation_id': 'obs-1',
        'session_id': 'session-1',
        'frame_id': 'camera',
        'objects': [
            {
                'object_id': 'obj-1',
                'label': 'person',
                'confidence': 0.95,
                'x': 1.0,
                'y': -2.0,
                'z': 3.0,
                'size_x': 0.5,
                'size_y': 0.6,
                'size_z': 1.7,
            },
        ],
    }
    payload.update(overrides)
    return json.dumps(payload)


class TestSceneParser(unittest.TestCase):

    def test_accepts_valid_scene(self):
        result = parse_scene_json(valid_payload())
        self.assertTrue(result.accepted)
        self.assertEqual(result.scene.observation_id, 'obs-1')
        self.assertEqual(result.scene.objects[0].object_id, 'obj-1')

    def test_rejects_invalid_json_and_non_object_root(self):
        self.assertEqual(parse_scene_json('{').reason, 'invalid_json')
        self.assertEqual(parse_scene_json('[]').reason, 'root_not_object')

    def test_rejects_duplicate_keys_and_unknown_fields(self):
        duplicate = '{"observation_id":"a","observation_id":"b"}'
        self.assertEqual(parse_scene_json(duplicate).reason, 'duplicate_key')
        self.assertTrue(
            parse_scene_json(valid_payload(extra='not-allowed')).reason
            .startswith('unexpected_field:')
        )

    def test_rejects_missing_fields_and_wrong_collection_type(self):
        payload = json.loads(valid_payload())
        del payload['session_id']
        self.assertEqual(
            parse_scene_json(json.dumps(payload)).reason,
            'session_id_required',
        )
        payload = json.loads(valid_payload(objects={}))
        self.assertEqual(
            parse_scene_json(json.dumps(payload)).reason,
            'objects_list_required',
        )

    def test_rejects_duplicate_object_ids(self):
        payload = json.loads(valid_payload())
        payload['objects'].append(dict(payload['objects'][0]))
        self.assertEqual(
            parse_scene_json(json.dumps(payload)).reason,
            'object_id_not_unique',
        )

    def test_rejects_confidence_and_geometry_boundaries(self):
        for confidence in (-0.01, 1.01):
            payload = json.loads(valid_payload())
            payload['objects'][0]['confidence'] = confidence
            self.assertEqual(
                parse_scene_json(json.dumps(payload)).reason,
                'confidence_out_of_range',
            )
        payload = json.loads(valid_payload())
        payload['objects'][0]['size_x'] = -0.1
        self.assertEqual(
            parse_scene_json(json.dumps(payload)).reason,
            'size_x_negative',
        )

    def test_rejects_non_finite_numbers(self):
        payload = json.loads(valid_payload())
        payload['objects'][0]['x'] = 'NaN'
        self.assertEqual(
            parse_scene_json(json.dumps(payload)).reason,
            'x_number_required',
        )
        self.assertEqual(
            parse_scene_json(
                valid_payload().replace('0.95', 'NaN')
            ).reason,
            'non_finite_number',
        )

    def test_rejects_integer_too_large_for_float_geometry(self):
        payload = json.loads(valid_payload())
        payload['objects'][0]['x'] = 10 ** 1000
        self.assertEqual(
            parse_scene_json(json.dumps(payload)).reason,
            'x_not_finite',
        )

    def test_rejects_values_outside_ros_float32_range(self):
        for field_name in ('x', 'y', 'z', 'size_x', 'size_y', 'size_z'):
            payload = json.loads(valid_payload())
            payload['objects'][0][field_name] = 1e39
            self.assertEqual(
                parse_scene_json(json.dumps(payload)).reason,
                field_name + '_out_of_range',
            )

    def test_rejected_object_content_preserves_scene_identity(self):
        payload = json.loads(valid_payload())
        payload['objects'].append(dict(payload['objects'][0]))
        result = parse_scene_json(json.dumps(payload))
        self.assertFalse(result.accepted)
        self.assertEqual(result.reason, 'object_id_not_unique')
        self.assertEqual(result.identity.observation_id, 'obs-1')
        self.assertEqual(result.identity.session_id, 'session-1')
        self.assertEqual(result.identity.frame_id, 'camera')

    def test_rejects_resource_limit_violations(self):
        self.assertEqual(
            parse_scene_json(' ' * (MAX_PAYLOAD_CHARS + 1)).reason,
            'payload_too_large',
        )
        payload = json.loads(valid_payload())
        payload['objects'] = [
            dict(payload['objects'][0], object_id='obj-%d' % index)
            for index in range(MAX_OBJECTS + 1)
        ]
        self.assertEqual(
            parse_scene_json(json.dumps(payload)).reason,
            'objects_too_many',
        )
        payload = json.loads(valid_payload())
        payload['objects'][0]['label'] = 'x' * 257
        self.assertEqual(
            parse_scene_json(json.dumps(payload)).reason,
            'label_too_long',
        )


if __name__ == '__main__':
    unittest.main()
