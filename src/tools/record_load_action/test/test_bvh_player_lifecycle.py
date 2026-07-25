"""BvhActionPlayer worker 生命周期与并发控制测试。"""

import os
import sys
import threading
import unittest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../record_load_action'))

from bvh_player import BvhActionPlayer


class _InlineActionPlayer(BvhActionPlayer):
    """使用内存配置执行真实 ``_run``，避免测试依赖文件 IO。"""

    def __init__(self, publish_callback, action_data, **kwargs):
        super().__init__(publish_callback, **kwargs)
        self._action_data = action_data

    def _load_config(self):
        return {'bvh_data': {'wave': self._action_data}}, '<memory>'


class _ControlledPlayer(BvhActionPlayer):
    """将 worker 主体替换为测试提供的同步场景。"""

    def __init__(self, runner, **kwargs):
        super().__init__(lambda *_: None, **kwargs)
        self._runner = runner

    def _run(self, action, loop, speed_ms, playback_rate, frame_ms,
             local_stop_event):
        self._runner(action, local_stop_event)


class _RecordingLogger:
    def __init__(self):
        self.errors = []

    def error(self, message):
        self.errors.append(message)


class BvhActionPlayerLifecycleTest(unittest.TestCase):
    def assert_player_idle(self, player):
        with player._state_lock:
            self.assertIsNone(player._thread)
            self.assertIsNone(player._stop_event)

    def test_stop_interrupts_frame_and_fixed_waits(self):
        scenarios = (
            {
                'name': 'frame delay',
                'action_data': {
                    'frame_delay_ms': 10_000,
                    'frames': [[{'id': 1, 'position': 10}]],
                },
            },
            {
                'name': 'fixed delay',
                'action_data': {
                    'frames': [[{'id': 1, 'position': 10}]],
                },
            },
        )

        for scenario in scenarios:
            with self.subTest(scenario['name']):
                published = threading.Event()
                player = _InlineActionPlayer(
                    lambda *_: published.set(),
                    scenario['action_data'],
                    stop_timeout_sec=0.03,
                )

                self.assertTrue(player.play('wave'))
                self.assertTrue(published.wait(1.0))
                self.assertTrue(player.stop())
                self.assert_player_idle(player)

    def test_natural_completion_clears_owned_state(self):
        entered = threading.Event()
        release = threading.Event()

        def runner(_action, _stop_event):
            entered.set()
            release.wait(1.0)

        player = _ControlledPlayer(runner, stop_timeout_sec=0.05)
        self.assertTrue(player.play('once'))
        self.assertTrue(entered.wait(1.0))
        with player._state_lock:
            worker = player._thread
        self.assertIsNotNone(worker)

        release.set()
        worker.join(1.0)

        self.assertFalse(worker.is_alive())
        self.assert_player_idle(player)
        self.assertTrue(player.stop())
        self.assertTrue(player.stop())

    def test_stop_from_publish_prevents_remaining_frame_commands(self):
        callback_finished = threading.Event()
        published_ids = []
        callback_stop_results = []
        player = None

        def publish(_servo_type, servo_id, _position, _speed):
            published_ids.append(servo_id)
            callback_stop_results.append(player.stop())
            callback_finished.set()

        player = _InlineActionPlayer(
            publish,
            {
                'frame_delay_ms': 10_000,
                'frames': [[
                    {'id': 1, 'position': 10},
                    {'id': 2, 'position': 20},
                ]],
            },
            stop_timeout_sec=0.03,
        )

        self.assertTrue(player.play('wave'))
        self.assertTrue(callback_finished.wait(1.0))
        self.assertTrue(player.stop())

        self.assertEqual([False], callback_stop_results)
        self.assertEqual([1], published_ids)
        self.assert_player_idle(player)

    def test_timed_out_worker_is_retained_and_replacement_rejected(self):
        old_worker_started = threading.Barrier(2)
        release_old_worker = threading.Event()
        started_actions = []
        started_actions_lock = threading.Lock()

        def runner(action, _stop_event):
            with started_actions_lock:
                started_actions.append(action)
            if action == 'old':
                old_worker_started.wait(timeout=1.0)
                release_old_worker.wait(1.0)

        player = _ControlledPlayer(runner, stop_timeout_sec=0.02)
        self.assertTrue(player.play('old'))
        old_worker_started.wait(timeout=1.0)
        with player._state_lock:
            old_worker = player._thread
            old_generation = player._generation

        self.assertFalse(player.stop())
        with player._state_lock:
            self.assertIs(player._thread, old_worker)
            self.assertTrue(player._stop_event.is_set())

        self.assertFalse(player.play('replacement'))
        with started_actions_lock:
            self.assertEqual(['old'], started_actions)
        with player._state_lock:
            self.assertIs(player._thread, old_worker)
            self.assertEqual(old_generation, player._generation)

        release_old_worker.set()
        old_worker.join(1.0)
        self.assertFalse(old_worker.is_alive())
        self.assert_player_idle(player)
        self.assertTrue(player.stop())
        self.assertTrue(player.stop())

    def test_concurrent_play_is_serialized_without_double_worker(self):
        call_barrier = threading.Barrier(3)
        state_lock = threading.Lock()
        worker_entered = {
            'first': threading.Event(),
            'second': threading.Event(),
        }
        active_workers = 0
        max_active_workers = 0
        play_results = {}

        def runner(action, stop_event):
            nonlocal active_workers, max_active_workers
            with state_lock:
                active_workers += 1
                max_active_workers = max(max_active_workers, active_workers)
            worker_entered[action].set()
            try:
                stop_event.wait(1.0)
            finally:
                with state_lock:
                    active_workers -= 1

        player = _ControlledPlayer(runner, stop_timeout_sec=0.1)

        def invoke_play(action):
            call_barrier.wait(timeout=1.0)
            play_results[action] = player.play(action)

        callers = [
            threading.Thread(target=invoke_play, args=(action,))
            for action in ('first', 'second')
        ]
        for caller in callers:
            caller.start()
        call_barrier.wait(timeout=1.0)
        for caller in callers:
            caller.join(1.0)

        self.assertTrue(all(not caller.is_alive() for caller in callers))
        self.assertEqual({'first': True, 'second': True}, play_results)
        self.assertTrue(worker_entered['first'].wait(1.0))
        self.assertTrue(worker_entered['second'].wait(1.0))
        with state_lock:
            self.assertEqual(1, max_active_workers)

        self.assertTrue(player.stop())
        self.assertTrue(player.stop())
        self.assert_player_idle(player)

    def test_worker_exception_is_logged_and_state_cleared(self):
        entered = threading.Event()
        release = threading.Event()
        logger = _RecordingLogger()

        def runner(_action, _stop_event):
            entered.set()
            release.wait(1.0)
            raise RuntimeError('worker boom')

        player = _ControlledPlayer(
            runner,
            logger=logger,
            stop_timeout_sec=0.05,
        )
        self.assertTrue(player.play('broken'))
        self.assertTrue(entered.wait(1.0))
        with player._state_lock:
            worker = player._thread

        release.set()
        worker.join(1.0)

        self.assertFalse(worker.is_alive())
        self.assert_player_idle(player)
        self.assertTrue(any('worker boom' in message for message in logger.errors))


if __name__ == '__main__':
    unittest.main()
