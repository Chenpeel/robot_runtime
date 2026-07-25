"""websocket_bridge package - WebSocket通信桥接包"""

from importlib import import_module

__all__ = [
    'WebSocketBridgeServer',
    'WebSocketHandler',
    'MessageHandler',
    'StreamSchemas',
    'ErrorCode',
    'ErrorResponse',
    'SuccessResponse',
    'WebSocketException',
    'WebSocketROS2Bridge',
]

_LAZY_IMPORTS = {
    'WebSocketBridgeServer': ('.ws_server', 'WebSocketBridgeServer'),
    'WebSocketHandler': ('.websocket_handler', 'WebSocketHandler'),
    'MessageHandler': ('.message_handler', 'MessageHandler'),
    'StreamSchemas': ('.stream_schemas', 'StreamSchemas'),
    'ErrorCode': ('.error_codes', 'ErrorCode'),
    'ErrorResponse': ('.error_codes', 'ErrorResponse'),
    'SuccessResponse': ('.error_codes', 'SuccessResponse'),
    'WebSocketException': ('.error_codes', 'WebSocketException'),
    'WebSocketROS2Bridge': ('.bridge_node', 'WebSocketROS2Bridge'),
}


def __getattr__(name):
    """Lazy-load package exports to avoid optional dependency coupling."""
    if name not in _LAZY_IMPORTS:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')

    module_name, attr_name = _LAZY_IMPORTS[name]
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
