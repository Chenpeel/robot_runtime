"""结构化 motion goal 的纯逻辑校验与执行反馈聚合。"""

from dataclasses import dataclass
import math
import threading
from typing import Mapping, Optional, Tuple


SUPPORTED_MOTION_TYPE = 'ankle_pose'
SUPPORTED_TARGET_GROUPS = {'left_ankle', 'right_ankle'}
MAX_ABS_ANGLE_DEG = 30.0
TERMINAL_TASK_STATUSES = frozenset({
    'finished',
    'cancelled',
    'expired',
    'blocked',
})


class MotionGoalValidationError(ValueError):
    """结构化 motion goal 校验失败。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class MotionGoalSpec:
    """执行期间使用的规范化 motion goal。"""

    task_id: str
    trace_id: str
    session_id: str
    motion_type: str
    target_group: str
    roll_deg: float
    pitch_deg: float
    yaw_deg: float
    duration_ms: int
    position_tolerance: int
    execution_timeout_sec: float


@dataclass(frozen=True)
class ActuatorObservation:
    """来自 motion-level 位置读取服务的最小执行观察。"""

    position_raw: int
    status: str
    reason: str
    recoverable: bool
    observed_monotonic: float


class SingleGoalAdmission:
    """为 motion Action 提供线程安全的单目标槽位。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
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


def task_state_has_identity(state, spec: MotionGoalSpec) -> bool:
    """检查 task state 是否对应当前 motion goal 的完整身份。"""
    return (
        state is not None
        and str(state.task_id) == spec.task_id
        and str(state.trace_id) == spec.trace_id
        and str(state.session_id) == spec.session_id
    )


def active_task_lease(state, spec: MotionGoalSpec) -> str:
    """仅返回完整身份匹配的活跃 task lease。"""
    if not task_state_has_identity(state, spec) or not bool(state.active):
        return ''
    return str(state.lease_id).strip()


def is_terminal_task_state(state, spec: MotionGoalSpec) -> bool:
    """确认身份一致且 lease 已被 execution_manager 撤销。"""
    return bool(terminal_task_status(state, spec))


def terminal_task_status(state, spec: MotionGoalSpec) -> str:
    """返回身份匹配且 lease 已撤销的稳定终态。"""
    status = str(getattr(state, 'status', '')).strip().lower()
    return (
        status
        if task_state_has_identity(state, spec)
        and not bool(state.active)
        and not str(state.lease_id).strip()
        and status in TERMINAL_TASK_STATUSES
        else ''
    )


def task_start_was_rejected(state, spec: MotionGoalSpec) -> bool:
    """识别 execution_manager 对当前 task start 的显式拒绝。"""
    return (
        state is not None
        and str(state.last_action).strip().lower() == 'start'
        and str(state.last_task_id) == spec.task_id
        and str(state.last_trace_id) == spec.trace_id
        and str(state.last_session_id) == spec.session_id
        and not bool(state.last_action_accepted)
    )


def task_start_was_accepted(state, spec: MotionGoalSpec) -> bool:
    """识别 execution_manager 对当前 task start 的明确准入。"""
    return (
        task_state_has_identity(state, spec)
        and bool(state.active)
        and str(state.last_action).strip().lower() == 'start'
        and str(state.last_task_id) == spec.task_id
        and str(state.last_trace_id) == spec.trace_id
        and str(state.last_session_id) == spec.session_id
        and bool(state.last_action_accepted)
        and bool(str(state.lease_id).strip())
    )


def normalize_motion_goal(request) -> MotionGoalSpec:
    """校验并规范化 ExecuteMotion goal；不接受自由文本或隐式默认目标。"""
    task_id = str(request.task_id).strip()
    trace_id = str(request.trace_id).strip()
    session_id = str(request.session_id).strip()
    motion_type = str(request.motion_type).strip().lower()
    target_group = str(request.target_group).strip().lower()

    required = (
        ('task_id', task_id),
        ('trace_id', trace_id),
        ('session_id', session_id),
    )
    for name, value in required:
        if not value:
            raise MotionGoalValidationError(f'{name}_required')

    if motion_type != SUPPORTED_MOTION_TYPE:
        raise MotionGoalValidationError('unsupported_motion_type')
    if target_group not in SUPPORTED_TARGET_GROUPS:
        raise MotionGoalValidationError('unsupported_target_group')

    angles = (
        ('roll', float(request.roll_deg)),
        ('pitch', float(request.pitch_deg)),
        ('yaw', float(request.yaw_deg)),
    )
    for name, angle in angles:
        if not math.isfinite(angle):
            raise MotionGoalValidationError(f'{name}_not_finite')
        if abs(angle) > MAX_ABS_ANGLE_DEG:
            raise MotionGoalValidationError(f'{name}_out_of_workspace')

    duration_ms = int(request.duration_ms)
    if duration_ms <= 0:
        raise MotionGoalValidationError('duration_ms_required')

    position_tolerance = int(request.position_tolerance)
    if not 1 <= position_tolerance <= 500:
        raise MotionGoalValidationError('position_tolerance_out_of_range')

    execution_timeout_sec = float(request.execution_timeout_sec)
    if not math.isfinite(execution_timeout_sec):
        raise MotionGoalValidationError('execution_timeout_not_finite')
    if not 0.1 <= execution_timeout_sec <= 120.0:
        raise MotionGoalValidationError('execution_timeout_out_of_range')

    return MotionGoalSpec(
        task_id=task_id,
        trace_id=trace_id,
        session_id=session_id,
        motion_type=motion_type,
        target_group=target_group,
        roll_deg=angles[0][1],
        pitch_deg=angles[1][1],
        yaw_deg=angles[2][1],
        duration_ms=duration_ms,
        position_tolerance=position_tolerance,
        execution_timeout_sec=execution_timeout_sec,
    )


def evaluate_target_feedback(
    targets: Mapping[int, int],
    observations: Mapping[int, ActuatorObservation],
    issued_monotonic: float,
    tolerance: int,
) -> Tuple[int, Optional[ActuatorObservation]]:
    """只使用命令发出后的新反馈计算到达数量，并返回首个驱动错误。"""
    reached_count = 0
    first_error = None
    for actuator_id, target_raw in targets.items():
        observation = observations.get(int(actuator_id))
        if observation is None:
            continue
        if observation.observed_monotonic < issued_monotonic:
            continue
        if observation.status == 'error':
            if first_error is None:
                first_error = observation
            continue
        if abs(int(observation.position_raw) - int(target_raw)) <= int(tolerance):
            reached_count += 1
    return reached_count, first_error


def progress_fraction(reached_count: int, target_count: int) -> float:
    """返回稳定在 0..1 的反馈进度。"""
    if target_count <= 0:
        return 0.0
    return max(0.0, min(1.0, float(reached_count) / float(target_count)))


class StablePositionTracker:
    """要求所有目标连续命中指定样本数后才确认完成或停止。"""

    def __init__(self, required_samples: int = 3) -> None:
        if int(required_samples) <= 0:
            raise ValueError('required_samples_must_be_positive')
        self.required_samples = int(required_samples)
        self.consecutive_samples = 0

    def update(self, reached_count: int, target_count: int) -> bool:
        if target_count > 0 and reached_count == target_count:
            self.consecutive_samples += 1
        else:
            self.consecutive_samples = 0
        return self.consecutive_samples >= self.required_samples
