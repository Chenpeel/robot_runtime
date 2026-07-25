"""将边缘 JSON 场景输入解析为严格的结构化感知结果。"""

from dataclasses import dataclass
import json
import math
from typing import Any, Dict, List, Optional, Tuple


SCENE_FIELDS = frozenset({
    'observation_id',
    'session_id',
    'frame_id',
    'objects',
})
OBJECT_FIELDS = frozenset({
    'object_id',
    'label',
    'confidence',
    'x',
    'y',
    'z',
    'size_x',
    'size_y',
    'size_z',
})
FLOAT32_MAX = 3.4028234663852886e38
MAX_OBJECTS = 256
MAX_PAYLOAD_CHARS = 1_000_000
MAX_TEXT_LENGTH = 256


class SceneParseError(ValueError):
    """包含稳定拒绝原因的场景解析错误。"""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ParsedObject:
    """严格校验后的目标记录。"""

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
class ParsedScene:
    """严格校验后的场景快照。"""

    observation_id: str
    session_id: str
    frame_id: str
    objects: Tuple[ParsedObject, ...]


@dataclass(frozen=True)
class SceneIdentity:
    """即使对象内容被拒绝，也可安全关联的顶层身份。"""

    observation_id: str = ''
    session_id: str = ''
    frame_id: str = ''


@dataclass(frozen=True)
class ParseResult:
    """解析调用的稳定结果，不把异常泄漏给 ROS 回调。"""

    accepted: bool
    scene: Optional[ParsedScene] = None
    identity: Optional[SceneIdentity] = None
    reason: str = ''


def _reject_constant(value: str) -> None:
    raise SceneParseError('non_finite_number')


def _object_pairs(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise SceneParseError('duplicate_key')
        result[key] = value
    return result


def _required_text(mapping: Dict[str, Any], field_name: str) -> str:
    value = mapping.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise SceneParseError(field_name + '_required')
    value = value.strip()
    if len(value) > MAX_TEXT_LENGTH:
        raise SceneParseError(field_name + '_too_long')
    return value


def _optional_text(mapping: Dict[str, Any], field_name: str) -> str:
    value = mapping.get(field_name)
    if not isinstance(value, str):
        return ''
    value = value.strip()
    if len(value) > MAX_TEXT_LENGTH:
        return ''
    return value


def _scene_identity(mapping: Dict[str, Any]) -> SceneIdentity:
    return SceneIdentity(
        observation_id=_optional_text(mapping, 'observation_id'),
        session_id=_optional_text(mapping, 'session_id'),
        frame_id=_optional_text(mapping, 'frame_id'),
    )


def _finite_number(mapping: Dict[str, Any], field_name: str) -> float:
    value = mapping.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SceneParseError(field_name + '_number_required')
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError):
        raise SceneParseError(field_name + '_not_finite')
    if not math.isfinite(value):
        raise SceneParseError(field_name + '_not_finite')
    return value


def _reject_unknown_fields(
        mapping: Dict[str, Any],
        allowed: frozenset,
) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise SceneParseError('unexpected_field:' + ','.join(unknown))


def _parse_object(raw: Any) -> ParsedObject:
    if not isinstance(raw, dict):
        raise SceneParseError('object_not_object')
    _reject_unknown_fields(raw, OBJECT_FIELDS)
    values = {
        'object_id': _required_text(raw, 'object_id'),
        'label': _required_text(raw, 'label'),
        'confidence': _finite_number(raw, 'confidence'),
        'x': _finite_number(raw, 'x'),
        'y': _finite_number(raw, 'y'),
        'z': _finite_number(raw, 'z'),
        'size_x': _finite_number(raw, 'size_x'),
        'size_y': _finite_number(raw, 'size_y'),
        'size_z': _finite_number(raw, 'size_z'),
    }
    if not 0.0 <= values['confidence'] <= 1.0:
        raise SceneParseError('confidence_out_of_range')
    for field_name in ('x', 'y', 'z'):
        if abs(values[field_name]) > FLOAT32_MAX:
            raise SceneParseError(field_name + '_out_of_range')
    for field_name in ('size_x', 'size_y', 'size_z'):
        if values[field_name] < 0.0:
            raise SceneParseError(field_name + '_negative')
        if values[field_name] > FLOAT32_MAX:
            raise SceneParseError(field_name + '_out_of_range')
    return ParsedObject(**values)


def parse_scene_json(payload: str) -> ParseResult:
    """严格解析 JSON，返回可映射到 ``SceneState`` 的数据。"""
    if not isinstance(payload, str):
        return ParseResult(False, reason='payload_string_required')
    if len(payload) > MAX_PAYLOAD_CHARS:
        return ParseResult(False, reason='payload_too_large')

    try:
        root = json.loads(
            payload,
            object_pairs_hook=_object_pairs,
            parse_constant=_reject_constant,
        )
    except SceneParseError as exc:
        return ParseResult(False, reason=exc.reason)
    except (TypeError, ValueError, OverflowError, RecursionError):
        return ParseResult(False, reason='invalid_json')

    identity = None
    try:
        if not isinstance(root, dict):
            raise SceneParseError('root_not_object')
        identity = _scene_identity(root)
        _reject_unknown_fields(root, SCENE_FIELDS)
        observation_id = _required_text(root, 'observation_id')
        session_id = _required_text(root, 'session_id')
        frame_id = _required_text(root, 'frame_id')
        objects = root.get('objects')
        if not isinstance(objects, list):
            raise SceneParseError('objects_list_required')
        if len(objects) > MAX_OBJECTS:
            raise SceneParseError('objects_too_many')

        parsed_objects = tuple(_parse_object(item) for item in objects)
        object_ids = [item.object_id for item in parsed_objects]
        if len(object_ids) != len(set(object_ids)):
            raise SceneParseError('object_id_not_unique')
        return ParseResult(
            accepted=True,
            scene=ParsedScene(
                observation_id=observation_id,
                session_id=session_id,
                frame_id=frame_id,
                objects=parsed_objects,
            ),
            identity=identity,
        )
    except SceneParseError as exc:
        return ParseResult(False, identity=identity, reason=exc.reason)
