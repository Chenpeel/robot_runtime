"""MotionCommand 到内部执行语义的适配层。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ActuatorSetpoint:
    """执行层内部使用的中性执行请求。"""

    actuator_type: str
    actuator_id: int
    target_raw: int
    value_encoding: str
    duration_ms: int


def motion_command_to_setpoint(msg) -> ActuatorSetpoint:
    """
    将 MotionCommand 转换为内部 setpoint。

    这里显式收敛当前过渡语义：
    - ``position`` 在执行层内部视为原始目标值 ``target_raw``
    - ``speed`` 在执行层内部视为运动时长 ``duration_ms``
    """
    return ActuatorSetpoint(
        actuator_type=str(msg.servo_type),
        actuator_id=int(msg.servo_id),
        target_raw=int(msg.position),
        value_encoding=_resolve_value_encoding(
            actuator_type=str(msg.servo_type),
            value_encoding=str(getattr(msg, 'value_encoding', '') or ''),
        ),
        duration_ms=_resolve_duration_ms(
            duration_ms=int(getattr(msg, 'duration_ms', 0) or 0),
            speed=int(msg.speed),
        ),
    )


def setpoint_to_servo_fields(setpoint: ActuatorSetpoint) -> dict:
    """将内部 setpoint 转回驱动层需要的字段。"""
    return {
        'servo_type': str(setpoint.actuator_type),
        'servo_id': int(setpoint.actuator_id),
        'position': int(setpoint.target_raw),
        'speed': int(setpoint.duration_ms),
    }


def _resolve_value_encoding(actuator_type: str, value_encoding: str) -> str:
    normalized_encoding = str(value_encoding).strip().lower()
    if normalized_encoding:
        return normalized_encoding

    normalized_type = str(actuator_type).strip().lower()
    if normalized_type == 'bus':
        return 'bus_pulse_us'
    if normalized_type == 'pca':
        return 'pca_tick'
    return ''


def _resolve_duration_ms(duration_ms: int, speed: int) -> int:
    if int(duration_ms) > 0:
        return int(duration_ms)
    return int(speed)
