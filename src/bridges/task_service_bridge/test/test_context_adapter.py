"""结构化语音/感知上下文适配测试。"""

from types import SimpleNamespace
import unittest

from task_service_bridge.context_adapter import (
    perception_context_fields,
    speech_context_fields,
)


class TestSpeechContextAdapter(unittest.TestCase):

    def test_preserves_identity_status_and_typed_labels(self):
        fields = speech_context_fields(SimpleNamespace(
            intent_id='intent-1',
            session_id='session-1',
            task_type='ankle_pose',
            target_group='left_ankle',
            status='accepted',
            reason='',
            recoverable=False,
        ))

        self.assertEqual('speech', fields.source)
        self.assertEqual('intent-1', fields.event_id)
        self.assertEqual('session-1', fields.session_id)
        self.assertEqual('accepted', fields.status)
        self.assertEqual(
            ('ankle_pose', 'left_ankle'),
            fields.labels,
        )
        self.assertNotIn('{', fields.summary)

    def test_defaults_missing_status_without_inventing_identity(self):
        fields = speech_context_fields(SimpleNamespace())
        self.assertEqual('', fields.event_id)
        self.assertEqual('ready', fields.status)
        self.assertEqual((), fields.labels)


class TestPerceptionContextAdapter(unittest.TestCase):

    def test_deduplicates_labels_and_keeps_scene_status(self):
        fields = perception_context_fields(SimpleNamespace(
            observation_id='obs-1',
            session_id='session-1',
            frame_id='camera_link',
            objects=[
                SimpleNamespace(label='cup'),
                SimpleNamespace(label=' cup '),
                SimpleNamespace(label='table'),
                SimpleNamespace(label=''),
            ],
            status='ready',
            reason='',
            recoverable=False,
        ))

        self.assertEqual('perception', fields.source)
        self.assertEqual('obs-1', fields.event_id)
        self.assertEqual(('cup', 'table'), fields.labels)
        self.assertEqual('objects=4 frame=camera_link', fields.summary)

    def test_rejected_scene_reason_is_preserved(self):
        fields = perception_context_fields(SimpleNamespace(
            status='rejected',
            reason='duplicate_object_id',
            recoverable=True,
            objects=[],
        ))
        self.assertEqual('rejected', fields.status)
        self.assertEqual('duplicate_object_id', fields.reason)
        self.assertTrue(fields.recoverable)


if __name__ == '__main__':
    unittest.main()
