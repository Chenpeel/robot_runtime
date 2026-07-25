"""BVH 播放请求规范化。"""

from typing import Dict, Optional


def normalize_bvh_play_request(payload) -> Optional[Dict]:
    """规范化显式 ``bvh_play`` 请求，非法请求返回 ``None``。"""
    if not isinstance(payload, dict):
        return None

    request_type = str(payload.get('type') or '').strip().lower()
    if request_type != 'bvh_play':
        return None

    if 'action' not in payload:
        return None

    action = payload.get('action')
    if action is not None and not isinstance(action, str):
        return None

    return {
        'action': action,
        'loop': bool(payload.get('loop', False)),
        'speed_ms': payload.get('speed_ms'),
        'playback_rate': payload.get('playback_rate'),
        'frame_ms': payload.get('frame_ms'),
    }
