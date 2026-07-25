"""motion-level 执行器读取与停止服务的纯逻辑适配。"""


def read_response_fields(driver_response) -> dict:
    """将驱动级读取结果转换为 motion-level 结构化字段。"""
    if driver_response is None:
        return {
            'success': False,
            'position_raw': 0,
            'value_encoding': 'bus_pulse_us',
            'status': 'error',
            'reason': 'driver_service_unavailable',
            'recoverable': True,
            'stamp': None,
        }
    if not bool(driver_response.success):
        reason = str(driver_response.message or '').strip()
        return {
            'success': False,
            'position_raw': 0,
            'value_encoding': 'bus_pulse_us',
            'status': 'error',
            'reason': reason or 'position_read_failed',
            'recoverable': int(driver_response.error_code) != 2,
            'stamp': driver_response.stamp,
        }
    return {
        'success': True,
        'position_raw': int(driver_response.position),
        'value_encoding': 'bus_pulse_us',
        'status': 'ok',
        'reason': '',
        'recoverable': False,
        'stamp': driver_response.stamp,
    }


def stop_summary(actuator_ids, driver_responses) -> dict:
    """聚合停止指令写出结果；不将写成功冒充物理停止确认。"""
    stopped_actuator_ids = []
    unsupported_actuator_ids = []
    reasons = []
    for actuator_id, driver_response in zip(actuator_ids, driver_responses):
        if driver_response is not None and bool(driver_response.success):
            stopped_actuator_ids.append(int(actuator_id))
            continue
        unsupported_actuator_ids.append(int(actuator_id))
        if driver_response is None:
            reasons.append('driver_service_unavailable')
        else:
            reasons.append(str(driver_response.message or 'stop_command_failed'))

    all_sent = bool(actuator_ids) and not unsupported_actuator_ids
    return {
        'accepted': bool(actuator_ids),
        'stop_command_sent': all_sent,
        'stop_confirmed': False,
        'status': 'stop_command_sent' if all_sent else 'stop_command_failed',
        'reason': '' if all_sent else ';'.join(reasons),
        'recoverable': not all_sent,
        'stopped_actuator_ids': stopped_actuator_ids,
        'unsupported_actuator_ids': unsupported_actuator_ids,
    }


def stop_command_for_protocol(protocol: str) -> str:
    """返回现有驱动 router 支持的协议级停止别名。"""
    normalized = str(protocol).strip().lower()
    if normalized == 'lx':
        return 'move_stop'
    if normalized == 'zl':
        return 'stop_motion'
    return 'stop_motion'
