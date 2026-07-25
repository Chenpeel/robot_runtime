"""motion owner 的结构化场景准入测试。"""

import os
import sys
import threading
import unittest


sys.path.insert(0, os.path.join(
    os.path.dirname(__file__),
    '../parallel_3dof_controller',
))

from scene_admission import SceneAdmissionGate  # noqa: E402
from scene_admission import SceneGeometryPolicy  # noqa: E402
from scene_admission import SceneObjectSnapshot  # noqa: E402


def scene_object(**overrides):
    fields = {
        'object_id': 'target-1',
        'label': 'right_ankle',
        'confidence': 0.95,
        'x': 0.2,
        'y': -0.1,
        'z': 0.8,
        'size_x': 0.2,
        'size_y': 0.2,
        'size_z': 0.3,
    }
    fields.update(overrides)
    return SceneObjectSnapshot(**fields)


class TestSceneAdmissionGate(unittest.TestCase):

    def setUp(self):
        self.gate = SceneAdmissionGate(max_age_sec=2.0)

    def _update(self, **overrides):
        fields = {
            'observation_id': 'observation-1',
            'session_id': 'session-1',
            'frame_id': 'camera_link',
            'objects': (scene_object(),),
            'status': 'ok',
            'reason': '',
            'received_monotonic': 10.0,
        }
        fields.update(overrides)
        return self.gate.update(**fields)

    def _reason(
            self,
            session_id='session-1',
            target_group='right_ankle',
            now_monotonic=10.1,
    ):
        return self.gate.evaluate(
            session_id=session_id,
            target_group=target_group,
            now_monotonic=now_monotonic,
        ).reason

    def test_fails_closed_without_scene(self):
        self.assertEqual('scene_context_unavailable', self._reason())

    def test_rejects_scene_status_session_and_age(self):
        self._update(status='rejected', reason='object_id_not_unique')
        self.assertEqual('scene_context_rejected', self._reason())

        self._update(observation_id='observation-2', session_id='')
        self.assertEqual('scene_context_session_required', self._reason())

        self._update(observation_id='observation-3')
        self.assertEqual(
            'scene_context_session_mismatch',
            self._reason(session_id='session-2'),
        )
        self.assertEqual(
            'scene_context_stale',
            self._reason(now_monotonic=12.01),
        )

    def test_rejects_ok_scene_without_observation_identity(self):
        self._update(observation_id='')
        self.assertEqual(
            'scene_context_observation_required',
            self._reason(),
        )

    def test_accepts_fresh_matching_scene(self):
        self.assertTrue(self._update())
        decision = self.gate.evaluate(
            session_id='session-1',
            target_group='right_ankle',
            now_monotonic=11.0,
        )
        self.assertTrue(decision.accepted)
        self.assertEqual('scene_context_ready', decision.reason)

    def test_duplicate_observation_does_not_refresh_snapshot(self):
        self.assertTrue(self._update())
        self.assertFalse(self._update(received_monotonic=11.0))
        self.assertEqual(
            'scene_context_stale',
            self._reason(now_monotonic=12.1),
        )

    def test_atomic_commit_rechecks_current_scene(self):
        self._update(status='rejected')
        committed = []

        decision = self.gate.commit_if_accepted(
            session_id='session-1',
            target_group='right_ankle',
            now_monotonic=lambda: 10.1,
            commit=lambda: committed.append('command'),
        )

        self.assertFalse(decision.accepted)
        self.assertEqual('scene_context_rejected', decision.reason)
        self.assertEqual([], committed)

    def test_atomic_commit_prevents_scene_update_between_batch_commands(self):
        self._update()
        timeline = []
        update_threads = []
        update_started = threading.Event()
        update_finished = threading.Event()

        def update_scene():
            update_started.set()
            self.gate.update(
                observation_id='observation-rejected',
                session_id='session-1',
                frame_id='camera_link',
                objects=(scene_object(),),
                status='rejected',
                reason='detector_unavailable',
                received_monotonic=10.2,
            )
            timeline.append('update')
            update_finished.set()

        def publish_batch():
            timeline.append('command-1')
            updater = threading.Thread(target=update_scene)
            update_threads.append(updater)
            updater.start()
            self.assertTrue(update_started.wait(timeout=1.0))
            self.assertFalse(update_finished.wait(timeout=0.05))
            timeline.extend(('command-2', 'command-3'))

        decision = self.gate.commit_if_accepted(
            session_id='session-1',
            target_group='right_ankle',
            now_monotonic=lambda: 10.1,
            commit=publish_batch,
        )

        self.assertTrue(decision.accepted)
        self.assertTrue(update_finished.wait(timeout=1.0))
        update_threads[0].join(timeout=1.0)
        self.assertEqual(
            ['command-1', 'command-2', 'command-3', 'update'],
            timeline,
        )

    def test_updates_and_reads_are_thread_safe(self):
        errors = []

        def writer(index):
            try:
                self.gate.update(
                    observation_id='observation-%d' % index,
                    session_id='session-1',
                    frame_id='camera_link',
                    objects=(scene_object(object_id='target-%d' % index),),
                    status='ok',
                    reason='',
                    received_monotonic=10.0 + index / 1000.0,
                )
            except Exception as exc:  # pragma: no cover - failure collection
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(index,))
                   for index in range(32)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=1.0)

        self.assertFalse(errors)
        self.assertIsNotNone(self.gate.snapshot())

    def test_rejects_invalid_configuration(self):
        for max_age_sec in (0.0, -1.0, float('nan'), float('inf')):
            with self.subTest(max_age_sec=max_age_sec):
                with self.assertRaises(ValueError):
                    SceneAdmissionGate(max_age_sec=max_age_sec)

        invalid_policies = (
            {'required_frame_id': ''},
            {'minimum_confidence': -0.1},
            {'minimum_confidence': 1.1},
            {'maximum_extent_m': 0.0},
            {'maximum_extent_m': float('inf')},
        )
        for fields in invalid_policies:
            with self.subTest(fields=fields):
                with self.assertRaises(ValueError):
                    SceneGeometryPolicy(**fields)

    def test_rejects_frame_and_object_identity_boundaries(self):
        self._update(frame_id='')
        self.assertEqual('scene_context_frame_required', self._reason())
        self._update(observation_id='observation-2', frame_id='map')
        self.assertEqual('scene_context_frame_mismatch', self._reason())
        self._update(observation_id='observation-3', objects=())
        self.assertEqual('scene_context_objects_required', self._reason())
        self._update(
            observation_id='observation-4',
            objects=(scene_object(object_id=''),),
        )
        self.assertEqual(
            'scene_context_object_identity_required',
            self._reason(),
        )
        duplicate = scene_object()
        self._update(
            observation_id='observation-5',
            objects=(duplicate, duplicate),
        )
        self.assertEqual(
            'scene_context_object_identity_not_unique',
            self._reason(),
        )

    def test_rejects_target_selection_and_confidence_boundaries(self):
        self._update(objects=(scene_object(label='person'),))
        self.assertEqual('scene_context_target_missing', self._reason())
        self._update(
            observation_id='observation-2',
            objects=(
                scene_object(object_id='target-1'),
                scene_object(object_id='target-2'),
            ),
        )
        self.assertEqual('scene_context_target_not_unique', self._reason())
        self._update(
            observation_id='observation-3',
            objects=(scene_object(confidence=0.59),),
        )
        self.assertEqual(
            'scene_context_target_confidence_low',
            self._reason(),
        )

    def test_rejects_invalid_or_out_of_bounds_target_geometry(self):
        for field_name, value, reason in (
                ('x', float('nan'), 'scene_context_object_geometry_invalid'),
                ('size_x', -0.1, 'scene_context_object_geometry_invalid'),
                ('size_x', 0.0, 'scene_context_target_size_invalid'),
                ('x', 1.91, 'scene_context_target_out_of_bounds')):
            with self.subTest(field_name=field_name, value=value):
                self._update(
                    observation_id='observation-' + field_name + str(value),
                    objects=(scene_object(**{field_name: value}),),
                )
                self.assertEqual(reason, self._reason())


if __name__ == '__main__':
    unittest.main()
