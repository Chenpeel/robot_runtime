"""驱动层 ServoState 到上层执行器反馈的适配层。"""

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ActuatorFeedback:
    """execution_manager 内部使用的中性执行器反馈。"""

    actuator_type: str
    actuator_id: int
    position_raw: int
    value_encoding: str
    load: int
    temperature: int
    status: str
    reason: str
    recoverable: bool
    driver_error_code: int


def servo_state_to_feedback(msg) -> ActuatorFeedback:
    """将驱动层 ServoState 转换为执行层内部反馈。"""
    actuator_type = str(msg.servo_type).strip().lower()
    driver_error_code = int(msg.error_code)
    status, reason, recoverable = _status_from_error_code(driver_error_code)
    return ActuatorFeedback(
        actuator_type=actuator_type,
        actuator_id=int(msg.servo_id),
        position_raw=int(msg.position),
        value_encoding=_value_encoding_for_type(actuator_type),
        load=int(msg.load),
        temperature=int(msg.temperature),
        status=status,
        reason=reason,
        recoverable=recoverable,
        driver_error_code=driver_error_code,
    )


def feedback_to_actuator_state_fields(feedback: ActuatorFeedback) -> dict:
    """构造 motion_msgs/ActuatorState 所需的普通字段。"""
    return {
        'actuator_type': feedback.actuator_type,
        'actuator_id': feedback.actuator_id,
        'position_raw': feedback.position_raw,
        'value_encoding': feedback.value_encoding,
        'load': feedback.load,
        'temperature': feedback.temperature,
        'status': feedback.status,
        'reason': feedback.reason,
        'recoverable': feedback.recoverable,
        'driver_error_code': feedback.driver_error_code,
    }


def _value_encoding_for_type(actuator_type: str) -> str:
    if actuator_type == 'bus':
        return 'bus_pulse_us'
    if actuator_type == 'pca':
        return 'pca_tick'
    return ''


def _status_from_error_code(error_code: int) -> Tuple[str, str, bool]:
    if error_code == 0:
        return 'ok', '', False

    reasons = {
        1: 'communication_error',
        2: 'overload',
        3: 'overheat',
        4: 'driver_error',
    }
    reason = reasons.get(error_code, f'driver_error_{error_code}')
    return 'error', reason, error_code in (1, 2, 3)
