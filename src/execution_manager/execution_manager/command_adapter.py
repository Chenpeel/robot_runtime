"""MotionCommand 到内部执行语义的适配层。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ActuatorSetpoint:
    """执行层内部使用的中性执行请求。"""

    actuator_type: str
    actuator_id: int
    target_raw: int
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
        duration_ms=int(msg.speed),
    )


def setpoint_to_servo_fields(setpoint: ActuatorSetpoint) -> dict:
    """将内部 setpoint 转回驱动层需要的字段。"""
    return {
        'servo_type': str(setpoint.actuator_type),
        'servo_id': int(setpoint.actuator_id),
        'position': int(setpoint.target_raw),
        'speed': int(setpoint.duration_ms),
    }
