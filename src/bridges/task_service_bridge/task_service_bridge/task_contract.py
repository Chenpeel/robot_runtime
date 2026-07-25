"""任务 Action 的纯逻辑校验、映射与单目标准入。"""

from dataclasses import dataclass
import math
from threading import Lock
from typing import Any, Callable


SUPPORTED_TASK_TYPE = 'ankle_pose'
SUPPORTED_TARGET_GROUPS = frozenset({'right_ankle', 'left_ankle'})
POSE_LIMIT_DEG = 30.0
MIN_POSITION_TOLERANCE = 1
MAX_POSITION_TOLERANCE = 500
MIN_EXECUTION_TIMEOUT_SEC = 0.1
MAX_EXECUTION_TIMEOUT_SEC = 120.0

GOAL_FIELDS = (
    'task_id',
    'trace_id',
    'session_id',
    'target_group',
    'roll_deg',
    'pitch_deg',
    'yaw_deg',
    'duration_ms',
    'position_tolerance',
    'execution_timeout_sec',
)
FEEDBACK_FIELDS = (
    'task_id',
    'trace_id',
    'session_id',
    'status',
    'reason',
    'progress',
    'reached_actuator_count',
    'target_actuator_count',
    'cancel_requested',
    'stop_command_sent',
    'stop_confirmed',
)
RESULT_FIELDS = (
    'success',
    'task_id',
    'trace_id',
    'session_id',
    'status',
    'reason',
    'recoverable',
    'target_reached',
    'admission_released',
    'stop_requested',
    'stop_command_sent',
    'stop_confirmed',
)


@dataclass(frozen=True)
class ValidationResult:
    """任务请求校验结果。"""

    accepted: bool
    reason: str = ''


def validate_task_goal(goal: Any) -> ValidationResult:
    """校验外部任务请求，不依赖 ROS 消息运行时。"""
    for field_name in ('task_id', 'trace_id', 'session_id'):
        if not str(getattr(goal, field_name, '')).strip():
            return ValidationResult(False, field_name + '_required')

    if getattr(goal, 'task_type', '') != SUPPORTED_TASK_TYPE:
        return ValidationResult(False, 'unsupported_task_type')
    if getattr(goal, 'target_group', '') not in SUPPORTED_TARGET_GROUPS:
        return ValidationResult(False, 'unsupported_target_group')

    for field_name in ('roll_deg', 'pitch_deg', 'yaw_deg'):
        value = getattr(goal, field_name, math.nan)
        if not math.isfinite(value):
            return ValidationResult(False, field_name + '_not_finite')
        if abs(value) > POSE_LIMIT_DEG:
            return ValidationResult(False, field_name + '_out_of_range')

    if getattr(goal, 'duration_ms', 0) <= 0:
        return ValidationResult(False, 'duration_ms_out_of_range')

    position_tolerance = getattr(goal, 'position_tolerance', 0)
    if not (
            MIN_POSITION_TOLERANCE
            <= position_tolerance
            <= MAX_POSITION_TOLERANCE):
        return ValidationResult(False, 'position_tolerance_out_of_range')

    execution_timeout_sec = getattr(goal, 'execution_timeout_sec', math.nan)
    if not math.isfinite(execution_timeout_sec):
        return ValidationResult(False, 'execution_timeout_sec_not_finite')
    if not (
            MIN_EXECUTION_TIMEOUT_SEC
            <= execution_timeout_sec
            <= MAX_EXECUTION_TIMEOUT_SEC):
        return ValidationResult(False, 'execution_timeout_sec_out_of_range')

    return ValidationResult(True)


def map_task_goal(task_goal: Any, motion_goal_factory: Callable[[], Any]) -> Any:
    """把通过校验的 ExecuteTask Goal 显式映射为 ExecuteMotion Goal。"""
    motion_goal = motion_goal_factory()
    for field_name in GOAL_FIELDS:
        setattr(motion_goal, field_name, getattr(task_goal, field_name))
    motion_goal.motion_type = task_goal.task_type
    return motion_goal


def map_motion_feedback(
        motion_feedback: Any,
        task_feedback_factory: Callable[[], Any],
) -> Any:
    """逐字段映射 ExecuteMotion Feedback。"""
    task_feedback = task_feedback_factory()
    for field_name in FEEDBACK_FIELDS:
        setattr(task_feedback, field_name, getattr(motion_feedback, field_name))
    return task_feedback


def map_motion_result(
        motion_result: Any,
        task_result_factory: Callable[[], Any],
) -> Any:
    """逐字段映射 ExecuteMotion Result。"""
    task_result = task_result_factory()
    for field_name in RESULT_FIELDS:
        setattr(task_result, field_name, getattr(motion_result, field_name))
    return task_result


def rejected_result(
    task_result_factory: Callable[[], Any],
    reason: str,
    request: Any = None,
) -> Any:
    """构造桥接层失败时的稳定拒绝结果。"""
    task_result = task_result_factory()
    task_result.success = False
    for field_name in ('task_id', 'trace_id', 'session_id'):
        setattr(
            task_result,
            field_name,
            str(getattr(request, field_name, '') or ''),
        )
    task_result.status = 'rejected'
    task_result.reason = reason
    task_result.recoverable = True
    task_result.target_reached = False
    task_result.admission_released = True
    task_result.stop_requested = False
    task_result.stop_command_sent = False
    task_result.stop_confirmed = False
    return task_result


class SingleGoalAdmission:
    """线程安全的一次单目标准入槽位。"""

    def __init__(self) -> None:
        self._lock = Lock()
        self._occupied = False

    def try_acquire(self) -> bool:
        with self._lock:
            if self._occupied:
                return False
            self._occupied = True
            return True

    def release(self) -> None:
        with self._lock:
            self._occupied = False

    @property
    def occupied(self) -> bool:
        with self._lock:
            return self._occupied
