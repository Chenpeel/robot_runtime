"""bridge_node 可选扩展装配与生命周期单元测试。"""

import asyncio
import os
from pathlib import Path
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def _install_bridge_node_test_stubs():
    if 'websockets.server' not in sys.modules:
        websockets_module = types.ModuleType('websockets')
        server_module = types.ModuleType('websockets.server')
        exceptions_module = types.ModuleType('websockets.exceptions')

        async def _serve(*args, **kwargs):
            del args, kwargs
            return None

        class _WebSocketServerProtocol:
            pass

        class _ConnectionClosed(Exception):
            pass

        server_module.serve = _serve
        server_module.WebSocketServerProtocol = _WebSocketServerProtocol
        exceptions_module.ConnectionClosed = _ConnectionClosed
        sys.modules['websockets'] = websockets_module
        sys.modules['websockets.server'] = server_module
        sys.modules['websockets.exceptions'] = exceptions_module

    if 'motion_msgs.msg' not in sys.modules:
        motion_msgs_module = types.ModuleType('motion_msgs')
        motion_msgs_msg_module = types.ModuleType('motion_msgs.msg')

        class _ExecutionState:
            pass

        class _MotionCommand:
            pass

        class _TeleopControl:
            pass

        motion_msgs_msg_module.ExecutionState = _ExecutionState
        motion_msgs_msg_module.MotionCommand = _MotionCommand
        motion_msgs_msg_module.TeleopControl = _TeleopControl
        sys.modules['motion_msgs'] = motion_msgs_module
        sys.modules['motion_msgs.msg'] = motion_msgs_msg_module

    if 'rclpy' not in sys.modules:
        rclpy_module = types.ModuleType('rclpy')
        rclpy_module.init = lambda *args, **kwargs: None
        rclpy_module.shutdown = lambda *args, **kwargs: None

        rclpy_node_module = types.ModuleType('rclpy.node')

        class _Node:
            pass

        rclpy_node_module.Node = _Node

        rclpy_executors_module = types.ModuleType('rclpy.executors')

        class _MultiThreadedExecutor:
            def add_node(self, node):
                del node

            def spin(self):
                return None

        rclpy_executors_module.MultiThreadedExecutor = _MultiThreadedExecutor
        sys.modules['rclpy'] = rclpy_module
        sys.modules['rclpy.node'] = rclpy_node_module
        sys.modules['rclpy.executors'] = rclpy_executors_module

    if 'servo_msgs.msg' not in sys.modules:
        servo_msgs_module = types.ModuleType('servo_msgs')
        servo_msgs_msg_module = types.ModuleType('servo_msgs.msg')

        class _ServoState:
            pass

        servo_msgs_msg_module.ServoState = _ServoState
        sys.modules['servo_msgs'] = servo_msgs_module
        sys.modules['servo_msgs.msg'] = servo_msgs_msg_module

    if 'websocket_bridge.debug_aggregator' not in sys.modules:
        debug_aggregator_module = types.ModuleType(
            'websocket_bridge.debug_aggregator'
        )

        class _DebugAggregator:
            def __init__(self, *args, **kwargs):
                del args, kwargs

            def flush(self):
                return None

        debug_aggregator_module.DebugAggregator = _DebugAggregator
        sys.modules['websocket_bridge.debug_aggregator'] = (
            debug_aggregator_module
        )


_install_bridge_node_test_stubs()

from websocket_bridge.bridge_node import WebSocketROS2Bridge


class _Logger:
    def __init__(self):
        self.infos = []
        self.errors = []

    def info(self, message):
        self.infos.append(message)

    def error(self, message):
        self.errors.append(message)


class _Extension:
    def __init__(self, name='extension', events=None, close_failures=0):
        self.name = name
        self.events = events if events is not None else []
        self.close_failures = close_failures
        self.close_attempts = 0
        self.registered_servers = []
        self.execution_states = []

    def register_message_handlers(self, server):
        self.registered_servers.append(server)
        self.events.append(f'{self.name}:register')

    def on_execution_state(self, state):
        self.execution_states.append(state)
        self.events.append(f'{self.name}:state')

    def close(self):
        self.close_attempts += 1
        self.events.append(f'{self.name}:close:{self.close_attempts}')
        if self.close_attempts <= self.close_failures:
            raise RuntimeError(f'{self.name} close failed')


class TestBridgeNodeExtensions(unittest.TestCase):
    @staticmethod
    def _new_bridge():
        return object.__new__(WebSocketROS2Bridge)

    @staticmethod
    def _execution_state_message():
        return types.SimpleNamespace(
            mode='idle',
            active_source='',
            teleop_holder_id='',
            teleop_lease_id='',
            estop_active=False,
            teleop_active=False,
            motion_active=False,
            teleop_timeout_sec=0.8,
            motion_timeout_sec=0.5,
            teleop_control_remaining_sec=0.0,
            last_teleop_control_action='',
            last_teleop_control_accepted=False,
            last_teleop_control_reason='',
            teleop_control_accepted_count=0,
            teleop_control_rejected_count=0,
            teleop_accepted_count=0,
            motion_accepted_count=0,
            teleop_rejected_count=0,
            motion_rejected_count=0,
            last_rejection_reason='',
            stamp=types.SimpleNamespace(sec=12, nanosec=500_000_000),
        )

    def test_core_source_and_manifest_do_not_require_action_package(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/bridge_node.py',
            )
        ).read_text(encoding='utf-8')
        manifest = Path(
            os.path.join(os.path.dirname(__file__), '../package.xml')
        ).read_text(encoding='utf-8')

        package_name = 'record_' + 'load_action'
        domain_token = 'b' + 'vh'
        self.assertNotIn(package_name, source)
        self.assertNotIn(package_name, manifest)
        self.assertNotIn(domain_token, source.lower())

    def test_empty_factory_list_loads_no_extensions(self):
        bridge = self._new_bridge()

        self.assertEqual(bridge._load_extensions('  ,  '), [])

    def test_loads_comma_separated_factories_in_order(self):
        bridge = self._new_bridge()
        factory_nodes = []
        first = _Extension('first')
        second = _Extension('second')

        first_module = types.ModuleType('test_bridge_extension_first')
        second_module = types.ModuleType('test_bridge_extension_second')

        def _first_factory(node):
            factory_nodes.append(node)
            return first

        def _second_factory(node):
            factory_nodes.append(node)
            return second

        first_module.create = _first_factory
        second_module.build = _second_factory
        modules = {
            first_module.__name__: first_module,
            second_module.__name__: second_module,
        }

        with mock.patch.dict(sys.modules, modules):
            extensions = bridge._load_extensions(
                ' test_bridge_extension_first:create, '
                'test_bridge_extension_second:build '
            )

        self.assertEqual(extensions, [first, second])
        self.assertEqual(factory_nodes, [bridge, bridge])

    def test_missing_factory_module_fails_fast(self):
        bridge = self._new_bridge()

        with self.assertRaises(ModuleNotFoundError):
            bridge._load_extensions(
                'missing_websocket_extension_for_test:create'
            )

    def test_factory_exception_fails_fast(self):
        bridge = self._new_bridge()
        module = types.ModuleType('test_bridge_extension_failure')

        def _factory(_node):
            raise RuntimeError('factory failed')

        module.create = _factory
        with mock.patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(RuntimeError, 'factory failed'):
                bridge._load_extensions(
                    'test_bridge_extension_failure:create'
                )

    def test_later_factory_failure_closes_loaded_extensions(self):
        bridge = self._new_bridge()
        bridge.get_logger = lambda: _Logger()
        loaded = _Extension('loaded')
        first_module = types.ModuleType('test_loaded_extension')
        second_module = types.ModuleType('test_failing_extension')
        first_module.create = lambda _node: loaded

        def _fail(_node):
            raise RuntimeError('later factory failed')

        second_module.create = _fail
        modules = {
            first_module.__name__: first_module,
            second_module.__name__: second_module,
        }

        with mock.patch.dict(sys.modules, modules):
            with self.assertRaisesRegex(RuntimeError, 'later factory failed'):
                bridge._load_extensions(
                    'test_loaded_extension:create,'
                    'test_failing_extension:create'
                )

        self.assertEqual(loaded.close_attempts, 1)

    def test_extension_contract_is_validated_during_loading(self):
        bridge = self._new_bridge()
        module = types.ModuleType('test_bridge_extension_invalid')
        module.create = lambda _node: object()

        with mock.patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaisesRegex(
                TypeError,
                'register_message_handlers.*on_execution_state.*close',
            ):
                bridge._load_extensions(
                    'test_bridge_extension_invalid:create'
                )

    def test_invalid_extension_with_close_is_rolled_back(self):
        bridge = self._new_bridge()
        close_calls = []
        module = types.ModuleType('test_closable_invalid_extension')
        extension = types.SimpleNamespace(
            close=lambda: close_calls.append('close')
        )
        module.create = lambda _node: extension

        with mock.patch.dict(sys.modules, {module.__name__: module}):
            with self.assertRaises(TypeError):
                bridge._load_extensions(
                    'test_closable_invalid_extension:create'
                )

        self.assertEqual(close_calls, ['close'])

    def test_registers_every_extension_with_websocket_server(self):
        bridge = self._new_bridge()
        first = _Extension('first')
        second = _Extension('second')
        bridge.extensions = [first, second]
        server = object()

        bridge._register_extension_message_handlers(server)

        self.assertEqual(first.registered_servers, [server])
        self.assertEqual(second.registered_servers, [server])

    def test_registration_failure_prevents_websocket_thread_start(self):
        bridge = self._new_bridge()
        bridge.ws_thread = None

        def _raise_registration_error():
            raise ValueError('message type conflict')

        bridge._create_websocket_server = _raise_registration_error

        with self.assertRaisesRegex(ValueError, 'message type conflict'):
            bridge.start_websocket_server()

        self.assertIsNone(bridge.ws_thread)

    def test_extension_state_failure_does_not_block_other_extensions_or_upstream(self):
        events = []

        class _FailingExtension(_Extension):
            def on_execution_state(self, state):
                state['mutated_by_extension'] = True
                events.append('failing:state')
                raise RuntimeError('state failed')

        class _Server:
            def __init__(self):
                self.states = []

            def update_execution_state(self, state):
                self.states.append(dict(state))
                events.append('server:update')

        bridge = self._new_bridge()
        logger = _Logger()
        server = _Server()
        healthy = _Extension('healthy', events=events)
        bridge.extensions = [_FailingExtension(), healthy]
        bridge.latest_execution_state = {}
        bridge.ws_server = server
        bridge.ws_loop = None
        bridge.get_logger = lambda: logger

        bridge.execution_state_callback(self._execution_state_message())

        self.assertEqual(events, [
            'failing:state',
            'healthy:state',
            'server:update',
        ])
        self.assertEqual(len(healthy.execution_states), 1)
        self.assertNotIn(
            'mutated_by_extension',
            healthy.execution_states[0],
        )
        self.assertNotIn('mutated_by_extension', server.states[0])
        self.assertEqual(len(logger.errors), 1)
        self.assertIn('state failed', logger.errors[0])

    def test_shutdown_retries_extensions_before_websocket_cleanup(self):
        events = []
        retrying = _Extension(
            'retrying',
            events=events,
            close_failures=1,
        )
        incomplete = _Extension(
            'incomplete',
            events=events,
            close_failures=2,
        )

        class _Server:
            async def stop(self):
                events.append('server:stop')

        class _Loop:
            def stop(self):
                return None

            def call_soon_threadsafe(self, callback):
                del callback
                events.append('loop:stop')

        class _Future:
            def result(self, timeout):
                self.timeout = timeout

        def _run_coroutine_threadsafe(coroutine, _loop):
            asyncio.run(coroutine)
            return _Future()

        bridge = self._new_bridge()
        logger = _Logger()
        bridge.extensions = [retrying, incomplete]
        bridge.ws_server = _Server()
        bridge.ws_loop = _Loop()
        bridge.ws_thread = None
        bridge.get_logger = lambda: logger

        with mock.patch(
            'websocket_bridge.bridge_node.asyncio.run_coroutine_threadsafe',
            side_effect=_run_coroutine_threadsafe,
        ):
            bridge.shutdown()

        self.assertEqual(retrying.close_attempts, 2)
        self.assertEqual(incomplete.close_attempts, 2)
        self.assertEqual(events[:4], [
            'retrying:close:1',
            'retrying:close:2',
            'incomplete:close:1',
            'incomplete:close:2',
        ])
        self.assertEqual(events[4:], ['server:stop', 'loop:stop'])
        self.assertIn('部分扩展未确认关闭', logger.errors[-1])


if __name__ == '__main__':
    unittest.main()
