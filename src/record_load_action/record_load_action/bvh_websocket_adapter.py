"""BVH 播放请求的 WebSocket 消息适配。"""

import threading
from typing import Callable, Dict

from .bvh_request import normalize_bvh_play_request
from .bvh_runtime import BvhPlaybackBlockedError
from .bvh_runtime import BvhPlaybackRuntime


class BvhWebSocketPlaybackError(RuntimeError):
    """WebSocket-facing BVH 播放错误。"""

    INVALID_REQUEST = 'invalid_request'
    BLOCKED = 'blocked'
    OPERATION_FAILED = 'operation_failed'

    def __init__(
        self,
        kind: str,
        message: str,
        details: Dict | None = None,
        payload=None,
        cause=None,
        block_context=None,
    ):
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.details = details or {}
        self.payload = payload
        self.cause = cause
        self.block_context = block_context

    @classmethod
    def invalid_request(cls, payload):
        return BvhPlaybackInvalidRequestError(payload)

    @classmethod
    def blocked(cls, payload, cause, block_context=None):
        return cls(
            cls.BLOCKED,
            'BVH playback is blocked',
            details={
                'payload': payload,
                'exception': str(cause),
            },
            payload=payload,
            cause=cause,
            block_context=block_context,
        )

    @classmethod
    def operation_failed(cls, payload, exc):
        cause = getattr(exc, 'cause', None) or exc
        request = getattr(exc, 'request', payload)
        return cls(
            cls.OPERATION_FAILED,
            f'BVH play failed: {str(cause)}',
            details={
                'payload': request,
                'exception': str(cause),
            },
            payload=request,
            cause=cause,
        )


class BvhPlaybackInvalidRequestError(BvhWebSocketPlaybackError):
    """显式 ``bvh_play`` payload 无法规范化。"""

    def __init__(self, payload):
        super().__init__(
            BvhWebSocketPlaybackError.INVALID_REQUEST,
            'BVH action payload invalid',
            details={'received_data': payload},
            payload=payload,
        )


class BvhWebSocketPlaybackAdapter:
    """持有 BVH runtime，并将显式 ``bvh_play`` payload 适配到播放请求。"""

    message_type = 'bvh_play'

    def __init__(
        self,
        publish_callback: Callable[[str, int, int, int], None],
        config_path: str = '',
        logger=None,
        runtime_factory=BvhPlaybackRuntime,
        player_factory=None,
    ):
        runtime_kwargs = {
            'publish_callback': publish_callback,
            'config_path': config_path,
            'logger': logger,
        }
        if player_factory is not None:
            runtime_kwargs['player_factory'] = player_factory
        self._runtime = runtime_factory(**runtime_kwargs)
        self._operation_lock = threading.RLock()
        self._block_context = None

    @property
    def runtime(self):
        """返回底层 runtime，供测试和诊断读取。"""
        return self._runtime

    def handle_play_payload(self, payload: dict) -> Dict:
        """处理 ``bvh_play`` payload，并返回既有 ack 数据。"""
        with self._operation_lock:
            request = normalize_bvh_play_request(payload)
            if request is None:
                raise BvhWebSocketPlaybackError.invalid_request(payload)

            try:
                result = self._runtime.apply_request(request)
            except BvhPlaybackBlockedError as exc:
                raise BvhWebSocketPlaybackError.blocked(
                    payload,
                    exc,
                    block_context=self._block_context,
                ) from exc
            except Exception as exc:
                raise BvhWebSocketPlaybackError.operation_failed(
                    payload,
                    exc,
                ) from exc

            return {
                'status': 'accepted',
                'action': result.get('action'),
                'loop': bool(result.get('loop', False)),
            }

    def set_blocked(self, blocked: bool, block_context=None) -> bool:
        """更新底层 runtime 的播放阻断状态。"""
        with self._operation_lock:
            next_blocked = bool(blocked)
            if next_blocked:
                # 先保存与本次门禁提交对应的上下文。播放请求只能在
                # 同一把锁释放后进入，因此拒绝详情不会与状态切换分裂。
                self._block_context = (
                    dict(block_context)
                    if isinstance(block_context, dict)
                    else block_context
                )

            result = self._runtime.set_blocked(next_blocked)

            if not next_blocked:
                runtime_blocked = bool(
                    getattr(self._runtime, 'blocked', False)
                )
                if not runtime_blocked:
                    self._block_context = None

            return result

    def close(self) -> None:
        """关闭底层 runtime。"""
        with self._operation_lock:
            self._runtime.close()
