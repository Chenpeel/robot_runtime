"""BVH 播放请求的 WebSocket 消息适配。"""

from typing import Callable, Dict

from .bvh_request import normalize_bvh_play_request
from .bvh_runtime import BvhPlaybackRuntime


class BvhPlaybackInvalidRequestError(ValueError):
    """显式 ``bvh_play`` payload 无法规范化。"""

    def __init__(self, payload):
        super().__init__('Invalid BVH play payload')
        self.payload = payload


class BvhWebSocketPlaybackAdapter:
    """持有 BVH runtime，并将显式 ``bvh_play`` payload 适配到播放请求。"""

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

    @property
    def runtime(self):
        """返回底层 runtime，供测试和诊断读取。"""
        return self._runtime

    def handle_play_payload(self, payload: dict) -> Dict:
        """处理 ``bvh_play`` payload，并返回既有 ack 数据。"""
        request = normalize_bvh_play_request(payload)
        if request is None:
            raise BvhPlaybackInvalidRequestError(payload)

        result = self._runtime.apply_request(request)

        return {
            'status': 'accepted',
            'action': result.get('action'),
            'loop': bool(result.get('loop', False)),
        }

    def set_blocked(self, blocked: bool) -> bool:
        """更新底层 runtime 的播放阻断状态。"""
        return self._runtime.set_blocked(blocked)

    def close(self) -> None:
        """关闭底层 runtime。"""
        self._runtime.close()
