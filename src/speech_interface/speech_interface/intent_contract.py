"""语音 JSON 的纯逻辑解析、校验与任务映射。"""

from dataclasses import dataclass
import json
import math
from typing import Any, Callable, Dict, Iterable, Optional


SUPPORTED_TASK_TYPE = 'ankle_pose'
SUPPORTED_TARGET_GROUPS = frozenset({'right_ankle', 'left_ankle'})
POSE_LIMIT_DEG = 30.0
MIN_DURATION_MS = 1
MAX_DURATION_MS = 65535
MIN_POSITION_TOLERANCE = 1
MAX_POSITION_TOLERANCE = 500
MIN_EXECUTION_TIMEOUT_SEC = 0.1
MAX_EXECUTION_TIMEOUT_SEC = 120.0
MAX_CONFIDENCE = 1.0
DEFAULT_MINIMUM_CONFIDENCE = 0.6
MAX_PAYLOAD_CHARS = 65_536
MAX_TEXT_LENGTH = 256

STRING_FIELDS = (
    'intent_id',
    'task_id',
    'trace_id',
    'session_id',
    'task_type',
    'target_group',
)
POSE_FIELDS = ('roll', 'pitch', 'yaw')
INTEGER_FIELDS = ('duration_ms', 'position_tolerance')
FLOAT_FIELDS = ('execution_timeout_sec', 'confidence')
REQUIRED_FIELDS = STRING_FIELDS + POSE_FIELDS + INTEGER_FIELDS + FLOAT_FIELDS


class IntentValidationError(ValueError):
    """携带稳定 reason 的语音意图校验错误。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class SpeechIntentContext:
    """语义拒绝时仍可安全保留的意图身份与标签。"""

    intent_id: str = ''
    task_id: str = ''
    trace_id: str = ''
    session_id: str = ''
    task_type: str = ''
    target_group: str = ''


@dataclass(frozen=True)
class SpeechIntentData:
    """与 ROS 生成代码无关的已校验语音意图。"""

    intent_id: str
    task_id: str
    trace_id: str
    session_id: str
    task_type: str
    target_group: str
    roll: float
    pitch: float
    yaw: float
    duration_ms: int
    position_tolerance: int
    execution_timeout_sec: float
    confidence: float


def _reject_json_constant(value: str) -> None:
    del value
    raise IntentValidationError('non_finite_json_number')


def _strict_object(pairs: Iterable[Any]) -> Dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise IntentValidationError('duplicate_field')
        result[key] = value
    return result


def _load_json_object(payload: str) -> Dict[str, Any]:
    if not isinstance(payload, str):
        raise IntentValidationError('payload_must_be_string')
    if len(payload) > MAX_PAYLOAD_CHARS:
        raise IntentValidationError('payload_too_large')
    try:
        document = json.loads(
            payload,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_strict_object,
        )
    except IntentValidationError:
        raise
    except (TypeError, ValueError, OverflowError, RecursionError):
        raise IntentValidationError('invalid_json')

    if not isinstance(document, dict):
        raise IntentValidationError('json_object_required')
    return document


def _required_string(document: Dict[str, Any], field_name: str) -> str:
    value = document.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise IntentValidationError(field_name + '_required')
    value = value.strip()
    if len(value) > MAX_TEXT_LENGTH:
        raise IntentValidationError(field_name + '_too_long')
    return value


def _optional_string(document: Dict[str, Any], field_name: str) -> str:
    value = document.get(field_name)
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if len(value) > MAX_TEXT_LENGTH:
        return ''
    return value


def extract_speech_context(payload: str) -> Optional[SpeechIntentContext]:
    """从可解析对象提取拒绝链身份；歧义或损坏 JSON 不保留身份。"""
    try:
        document = _load_json_object(payload)
    except IntentValidationError:
        return None
    return SpeechIntentContext(**{
        field_name: _optional_string(document, field_name)
        for field_name in STRING_FIELDS
    })


def _required_number(document: Dict[str, Any], field_name: str) -> float:
    value = document.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IntentValidationError(field_name + '_number_required')
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        raise IntentValidationError(field_name + '_not_finite')
    if not math.isfinite(result):
        raise IntentValidationError(field_name + '_not_finite')
    return result


def _required_integer(document: Dict[str, Any], field_name: str) -> int:
    value = document.get(field_name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise IntentValidationError(field_name + '_integer_required')
    return value


def parse_speech_intent(
        payload: str,
        minimum_confidence: float = DEFAULT_MINIMUM_CONFIDENCE,
) -> SpeechIntentData:
    """严格解析单个平铺 JSON 对象并返回通过范围校验的意图。"""
    if (
            not math.isfinite(minimum_confidence)
            or not 0.0 <= minimum_confidence <= MAX_CONFIDENCE):
        raise ValueError('minimum_confidence must be finite and within [0, 1]')

    document = _load_json_object(payload)
    unknown_fields = set(document) - set(REQUIRED_FIELDS)
    if unknown_fields:
        raise IntentValidationError('unknown_field')
    for field_name in REQUIRED_FIELDS:
        if field_name not in document:
            raise IntentValidationError(field_name + '_required')

    strings = {
        field_name: _required_string(document, field_name)
        for field_name in STRING_FIELDS
    }
    if strings['task_type'] != SUPPORTED_TASK_TYPE:
        raise IntentValidationError('unsupported_task_type')
    if strings['target_group'] not in SUPPORTED_TARGET_GROUPS:
        raise IntentValidationError('unsupported_target_group')

    pose = {
        field_name: _required_number(document, field_name)
        for field_name in POSE_FIELDS
    }
    for field_name, value in pose.items():
        if abs(value) > POSE_LIMIT_DEG:
            raise IntentValidationError(field_name + '_out_of_range')

    duration_ms = _required_integer(document, 'duration_ms')
    if not MIN_DURATION_MS <= duration_ms <= MAX_DURATION_MS:
        raise IntentValidationError('duration_ms_out_of_range')

    position_tolerance = _required_integer(document, 'position_tolerance')
    if not (
            MIN_POSITION_TOLERANCE
            <= position_tolerance
            <= MAX_POSITION_TOLERANCE):
        raise IntentValidationError('position_tolerance_out_of_range')

    execution_timeout_sec = _required_number(
        document,
        'execution_timeout_sec',
    )
    if not (
            MIN_EXECUTION_TIMEOUT_SEC
            <= execution_timeout_sec
            <= MAX_EXECUTION_TIMEOUT_SEC):
        raise IntentValidationError('execution_timeout_sec_out_of_range')

    confidence = _required_number(document, 'confidence')
    if not 0.0 <= confidence <= MAX_CONFIDENCE:
        raise IntentValidationError('confidence_out_of_range')
    if confidence < minimum_confidence:
        raise IntentValidationError('confidence_below_minimum')

    return SpeechIntentData(
        intent_id=strings['intent_id'],
        task_id=strings['task_id'],
        trace_id=strings['trace_id'],
        session_id=strings['session_id'],
        task_type=strings['task_type'],
        target_group=strings['target_group'],
        roll=pose['roll'],
        pitch=pose['pitch'],
        yaw=pose['yaw'],
        duration_ms=duration_ms,
        position_tolerance=position_tolerance,
        execution_timeout_sec=execution_timeout_sec,
        confidence=confidence,
    )


def map_intent_to_task_goal(
        intent: SpeechIntentData,
        goal_factory: Callable[[], Any],
) -> Any:
    """将已校验意图显式映射到唯一正式 ExecuteTask Goal。"""
    goal = goal_factory()
    for field_name in (
            'task_id', 'trace_id', 'session_id', 'task_type', 'target_group',
            'duration_ms', 'position_tolerance', 'execution_timeout_sec'):
        setattr(goal, field_name, getattr(intent, field_name))
    goal.roll_deg = intent.roll
    goal.pitch_deg = intent.pitch
    goal.yaw_deg = intent.yaw
    return goal
