"""BVH 播放器的传输层无关运行时编排。"""

import threading
from typing import Callable, Dict, Optional

from .bvh_player import BvhActionPlayer


class BvhPlaybackRuntimeError(RuntimeError):
    """BVH 播放运行时错误基类。"""


class BvhPlaybackBlockedError(BvhPlaybackRuntimeError):
    """当前运行时不允许启动新播放。"""


class BvhPlaybackClosedError(BvhPlaybackRuntimeError):
    """已关闭的运行时不再接受新播放。"""


class BvhPlaybackOperationError(BvhPlaybackRuntimeError):
    """底层播放器操作失败。"""

    def __init__(self, message: str, request: Optional[Dict], cause=None):
        super().__init__(message)
        self.request = request
        self.cause = cause


class BvhPlaybackRuntime:
    """持有并串行化 ``BvhActionPlayer`` 的生命周期操作。"""

    def __init__(
        self,
        publish_callback: Callable[[str, int, int, int], None],
        config_path: str = '',
        logger=None,
        player_factory=BvhActionPlayer,
    ):
        self._lock = threading.RLock()
        self._blocked = False
        self._blocked_stop_complete = False
        self._closed = False
        self._close_complete = False
        self._player = player_factory(
            publish_callback,
            config_path=config_path,
            logger=logger,
        )

    @property
    def player(self) -> BvhActionPlayer:
        """返回由运行时创建并持有的播放器。"""
        return self._player

    @property
    def blocked(self) -> bool:
        """返回当前是否禁止启动新播放。"""
        with self._lock:
            return self._blocked

    @property
    def closed(self) -> bool:
        """返回运行时是否已进入关闭终态。"""
        with self._lock:
            return self._closed

    @property
    def close_complete(self) -> bool:
        """返回底层播放器是否已成功停止。"""
        with self._lock:
            return self._close_complete

    def apply_request(self, request: Dict) -> Dict:
        """将已规范化的播放请求应用到底层播放器。"""
        with self._lock:
            action = request.get('action')
            loop = bool(request.get('loop', False))

            # 停止是安全收敛操作，即使已阻断或关闭也必须允许。
            if action in (None, '', 'null'):
                self._stop_player(request)
                if self._blocked:
                    self._blocked_stop_complete = True
                if self._closed:
                    self._close_complete = True
                return {'action': action, 'loop': loop}

            if self._closed:
                raise BvhPlaybackClosedError(
                    'BVH playback runtime is closed'
                )
            if self._blocked:
                raise BvhPlaybackBlockedError(
                    'BVH playback runtime is blocked'
                )

            try:
                result = self._player.play(
                    action,
                    loop=loop,
                    speed_ms=request.get('speed_ms'),
                    playback_rate=request.get('playback_rate'),
                    frame_ms=request.get('frame_ms'),
                )
            except Exception as exc:
                raise BvhPlaybackOperationError(
                    'Failed to start BVH playback',
                    request,
                    exc,
                ) from exc

            if result is False:
                raise BvhPlaybackOperationError(
                    'Failed to start BVH playback',
                    request,
                    None,
                )

            return {'action': action, 'loop': loop}

    def set_blocked(self, blocked: bool) -> bool:
        """更新启动阻断状态，进入阻断时停止当前播放。"""
        with self._lock:
            next_blocked = bool(blocked)

            # close 后 blocked 是终态门禁，忽略迟到的解除阻断回调。
            if not next_blocked and self._closed:
                return False

            if not next_blocked:
                if not self._blocked:
                    return False

                self._blocked = False
                # 解除阻断会结束当前 epoch；下次进入时必须重新 stop。
                self._blocked_stop_complete = False
                return True

            state_changed = not self._blocked
            if state_changed:
                # 先生效阻断状态，保证 stop 失败时也不会接受新播放。
                self._blocked = True
                self._blocked_stop_complete = False

            if not self._blocked_stop_complete:
                self._stop_player(None)
                self._blocked_stop_complete = True

            return state_changed

    def close(self) -> None:
        """关闭运行时；未完成的关闭可在后续调用中重试。"""
        with self._lock:
            if self._close_complete:
                return

            # closed/blocked 是终态门禁；复用当前 blocked epoch 的 stop
            # 完成态，失败时保持 incomplete，供后续 close/set_blocked 重试。
            self._closed = True
            if not self._blocked:
                self._blocked = True
                self._blocked_stop_complete = False

            if not self._blocked_stop_complete:
                self._stop_player(None)
                self._blocked_stop_complete = True

            self._close_complete = True

    def _stop_player(self, request: Optional[Dict]) -> None:
        try:
            result = self._player.stop()
        except Exception as exc:
            raise BvhPlaybackOperationError(
                'Failed to stop BVH playback',
                request,
                exc,
            ) from exc

        if result is False:
            raise BvhPlaybackOperationError(
                'Failed to stop BVH playback',
                request,
                None,
            )
