"""语音/感知结构化事件到外部任务上下文的纯逻辑适配。"""

from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class TaskContextFields:
    """不依赖 ROS 生成类型的上下文快照。"""

    source: str
    event_id: str
    session_id: str
    status: str
    reason: str
    recoverable: bool
    summary: str
    labels: Tuple[str, ...]


def speech_context_fields(message) -> TaskContextFields:
    """保留语音意图身份和状态，不透传边缘 JSON。"""
    task_type = _clean(getattr(message, 'task_type', ''))
    target_group = _clean(getattr(message, 'target_group', ''))
    labels = tuple(value for value in (task_type, target_group) if value)
    summary = 'task_type=%s target_group=%s' % (
        task_type or 'unknown',
        target_group or 'unknown',
    )
    return TaskContextFields(
        source='speech',
        event_id=_clean(getattr(message, 'intent_id', '')),
        session_id=_clean(getattr(message, 'session_id', '')),
        status=_clean(getattr(message, 'status', '')) or 'ready',
        reason=_clean(getattr(message, 'reason', '')),
        recoverable=bool(getattr(message, 'recoverable', False)),
        summary=summary,
        labels=labels,
    )


def perception_context_fields(message) -> TaskContextFields:
    """提取去重对象标签，完整几何仍保留在 perception_msgs 边界。"""
    objects = tuple(getattr(message, 'objects', ()) or ())
    labels = _unique_labels(
        getattr(detected, 'label', '') for detected in objects
    )
    frame_id = _clean(getattr(message, 'frame_id', '')) or 'unknown'
    return TaskContextFields(
        source='perception',
        event_id=_clean(getattr(message, 'observation_id', '')),
        session_id=_clean(getattr(message, 'session_id', '')),
        status=_clean(getattr(message, 'status', '')) or 'ready',
        reason=_clean(getattr(message, 'reason', '')),
        recoverable=bool(getattr(message, 'recoverable', False)),
        summary='objects=%d frame=%s' % (len(objects), frame_id),
        labels=labels,
    )


def _unique_labels(values: Iterable[str]) -> Tuple[str, ...]:
    seen = set()
    labels = []
    for value in values:
        normalized = _clean(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        labels.append(normalized)
    return tuple(labels)


def _clean(value) -> str:
    return str(value or '').strip()
