"""结构化场景进入 motion owner 前的线程安全准入。"""

from collections import deque
from dataclasses import dataclass
import math
from threading import RLock
from typing import Callable, Deque, Iterable, Optional, Set, Tuple


@dataclass(frozen=True)
class SceneObjectSnapshot:
    """motion 准入需要的不可变目标几何。"""

    object_id: str
    label: str
    confidence: float
    x: float
    y: float
    z: float
    size_x: float
    size_y: float
    size_z: float


@dataclass(frozen=True)
class SceneSnapshot:
    """只保留 motion 准入需要的场景身份、状态和对象几何。"""

    observation_id: str
    session_id: str
    frame_id: str
    objects: Tuple[SceneObjectSnapshot, ...]
    status: str
    reason: str
    received_monotonic: float


@dataclass(frozen=True)
class SceneAdmissionDecision:
    """稳定的场景准入结果。"""

    accepted: bool
    reason: str


class SceneGeometryPolicy:
    """对目标对象的 frame、置信度和三维包围盒做 fail-closed 判断。"""

    def __init__(
            self,
            *,
            required_frame_id: str = 'camera_link',
            minimum_confidence: float = 0.6,
            maximum_extent_m: float = 2.0,
    ) -> None:
        normalized_frame = str(required_frame_id or '').strip()
        confidence = float(minimum_confidence)
        extent = float(maximum_extent_m)
        if not normalized_frame:
            raise ValueError('scene required frame must not be empty')
        if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
            raise ValueError('scene minimum confidence must be within [0, 1]')
        if not math.isfinite(extent) or extent <= 0.0:
            raise ValueError('scene maximum extent must be finite and positive')
        self._required_frame_id = normalized_frame
        self._minimum_confidence = confidence
        self._maximum_extent_m = extent

    def evaluate(
            self,
            snapshot: SceneSnapshot,
            target_group: str,
    ) -> SceneAdmissionDecision:
        """要求唯一目标对象位于配置的三维安全包络内。"""
        if not snapshot.frame_id:
            return SceneAdmissionDecision(False, 'scene_context_frame_required')
        if snapshot.frame_id != self._required_frame_id:
            return SceneAdmissionDecision(False, 'scene_context_frame_mismatch')
        if not snapshot.objects:
            return SceneAdmissionDecision(False, 'scene_context_objects_required')

        object_ids = [item.object_id.strip() for item in snapshot.objects]
        if any(not object_id for object_id in object_ids):
            return SceneAdmissionDecision(
                False,
                'scene_context_object_identity_required',
            )
        if len(object_ids) != len(set(object_ids)):
            return SceneAdmissionDecision(
                False,
                'scene_context_object_identity_not_unique',
            )
        if any(not self._object_is_finite(item) for item in snapshot.objects):
            return SceneAdmissionDecision(
                False,
                'scene_context_object_geometry_invalid',
            )

        normalized_target = str(target_group or '').strip()
        targets = [
            item for item in snapshot.objects
            if item.label.strip() == normalized_target
        ]
        if not targets:
            return SceneAdmissionDecision(False, 'scene_context_target_missing')
        if len(targets) != 1:
            return SceneAdmissionDecision(
                False,
                'scene_context_target_not_unique',
            )

        target = targets[0]
        if target.confidence < self._minimum_confidence:
            return SceneAdmissionDecision(
                False,
                'scene_context_target_confidence_low',
            )
        sizes = (target.size_x, target.size_y, target.size_z)
        if any(size <= 0.0 for size in sizes):
            return SceneAdmissionDecision(
                False,
                'scene_context_target_size_invalid',
            )
        centers = (target.x, target.y, target.z)
        if any(
                abs(center) + size / 2.0 > self._maximum_extent_m
                for center, size in zip(centers, sizes)):
            return SceneAdmissionDecision(
                False,
                'scene_context_target_out_of_bounds',
            )
        return SceneAdmissionDecision(True, 'scene_context_ready')

    @staticmethod
    def _object_is_finite(item: SceneObjectSnapshot) -> bool:
        values = (
            item.confidence,
            item.x,
            item.y,
            item.z,
            item.size_x,
            item.size_y,
            item.size_z,
        )
        return (
            all(math.isfinite(float(value)) for value in values)
            and 0.0 <= item.confidence <= 1.0
            and item.size_x >= 0.0
            and item.size_y >= 0.0
            and item.size_z >= 0.0
        )


class SceneAdmissionGate:
    """拒绝身份、状态、新鲜度或对象几何不满足要求的场景。"""

    def __init__(
            self,
            max_age_sec: float,
            replay_window: int = 256,
            geometry_policy: Optional[SceneGeometryPolicy] = None,
    ) -> None:
        normalized_age = float(max_age_sec)
        if not math.isfinite(normalized_age) or normalized_age <= 0.0:
            raise ValueError('scene max age must be finite and positive')
        self._max_age_sec = normalized_age
        self._lock = RLock()
        self._snapshot: Optional[SceneSnapshot] = None
        self._seen_order: Deque[str] = deque()
        self._seen_ids: Set[str] = set()
        self._replay_window = max(1, int(replay_window))
        self._geometry_policy = geometry_policy or SceneGeometryPolicy()

    def update(
            self,
            *,
            observation_id: str,
            session_id: str,
            frame_id: str,
            objects: Iterable[SceneObjectSnapshot],
            status: str,
            reason: str,
            received_monotonic: float,
    ) -> bool:
        """提交最新场景；重复非空 observation 不刷新新鲜度。"""
        normalized_id = str(observation_id or '').strip()
        received = float(received_monotonic)
        if not math.isfinite(received):
            return False
        with self._lock:
            if normalized_id and normalized_id in self._seen_ids:
                return False
            self._snapshot = SceneSnapshot(
                observation_id=normalized_id,
                session_id=str(session_id or '').strip(),
                frame_id=str(frame_id or '').strip(),
                objects=tuple(objects or ()),
                status=str(status or '').strip().lower(),
                reason=str(reason or '').strip(),
                received_monotonic=received,
            )
            if normalized_id:
                self._seen_order.append(normalized_id)
                self._seen_ids.add(normalized_id)
                while len(self._seen_order) > self._replay_window:
                    expired_id = self._seen_order.popleft()
                    self._seen_ids.discard(expired_id)
        return True

    def evaluate(
            self,
            *,
            session_id: str,
            target_group: str,
            now_monotonic: float,
    ) -> SceneAdmissionDecision:
        """按状态、新鲜度和 session 身份做 fail-closed 准入。"""
        now = float(now_monotonic)
        with self._lock:
            return self._evaluate_snapshot(session_id, target_group, now)

    def commit_if_accepted(
            self,
            *,
            session_id: str,
            target_group: str,
            now_monotonic: Callable[[], float],
            commit: Callable[[], None],
    ) -> SceneAdmissionDecision:
        """仅在最新场景准入通过时，原子提交一批同步命令。"""
        with self._lock:
            now = float(now_monotonic())
            decision = self._evaluate_snapshot(session_id, target_group, now)
            if decision.accepted:
                commit()
            return decision

    def _evaluate_snapshot(
            self,
            session_id: str,
            target_group: str,
            now_monotonic: float,
    ) -> SceneAdmissionDecision:
        """在调用方已持有锁时，基于当前快照给出准入决定。"""
        snapshot = self._snapshot
        if snapshot is None:
            return SceneAdmissionDecision(False, 'scene_context_unavailable')
        if snapshot.status != 'ok':
            return SceneAdmissionDecision(False, 'scene_context_rejected')
        if not snapshot.observation_id:
            return SceneAdmissionDecision(
                False,
                'scene_context_observation_required',
            )
        if not snapshot.session_id:
            return SceneAdmissionDecision(False, 'scene_context_session_required')
        if snapshot.session_id != str(session_id or '').strip():
            return SceneAdmissionDecision(
                False,
                'scene_context_session_mismatch',
            )
        age_sec = now_monotonic - snapshot.received_monotonic
        if not math.isfinite(now_monotonic) or age_sec < 0.0:
            return SceneAdmissionDecision(False, 'scene_context_clock_invalid')
        if age_sec > self._max_age_sec:
            return SceneAdmissionDecision(False, 'scene_context_stale')
        return self._geometry_policy.evaluate(snapshot, target_group)

    def snapshot(self) -> Optional[SceneSnapshot]:
        """返回不可变快照，供诊断和集成测试等待更新。"""
        with self._lock:
            return self._snapshot
