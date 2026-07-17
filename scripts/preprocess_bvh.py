#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _default_config_path() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    return (
        repo_root
        / 'src'
        / 'record_load_action'
        / 'config'
        / 'bvh_action_map.json'
    )


def _resolve_input_dir(
    config_path: Path,
    override: Optional[Path],
    configured_dir,
) -> Optional[Path]:
    """解析 BVH 输入目录；配置内相对路径以配置文件目录为基准。"""
    raw_path = override if override is not None else configured_dir
    if raw_path is None or not str(raw_path).strip():
        return None

    input_dir = Path(raw_path).expanduser()
    if override is None and not input_dir.is_absolute():
        input_dir = config_path.parent / input_dir
    return input_dir.resolve()


def _load_json(path: Path) -> Dict:
    with path.open('r', encoding='utf-8') as f:
        return json.load(f)


def _save_json(path: Path, data: Dict) -> None:
    with path.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


def _normalize_channel(channel: str) -> str:
    if not channel:
        return ''
    ch = channel.strip()
    upper = ch.upper()
    if upper in ('X', 'Y', 'Z'):
        return f'{upper}rotation'
    if upper in ('XROTATION', 'YROTATION', 'ZROTATION'):
        return f'{upper[0]}rotation'
    return ch


def _parse_bvh(path: Path) -> Tuple[List[Tuple[str, str]], List[List[float]], float]:
    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    channels: List[Tuple[str, str]] = []
    frames: List[List[float]] = []
    current_joint = None
    in_motion = False
    frame_time = 0.0
    total_frames = None

    idx = 0
    while idx < len(lines):
        line = lines[idx].strip()
        if not in_motion:
            if line.startswith('ROOT') or line.startswith('JOINT'):
                parts = line.split()
                if len(parts) >= 2:
                    current_joint = parts[1]
            elif line.startswith('CHANNELS'):
                parts = line.split()
                try:
                    count = int(parts[1])
                except (IndexError, ValueError):
                    count = 0
                for ch in parts[2:2 + count]:
                    channels.append((current_joint, ch))
            elif line.startswith('MOTION'):
                in_motion = True
            idx += 1
            continue

        if line.startswith('Frames:'):
            try:
                total_frames = int(line.split()[1])
            except (IndexError, ValueError):
                total_frames = None
        elif line.startswith('Frame Time:'):
            parts = line.split()
            try:
                frame_time = float(parts[-1])
            except (IndexError, ValueError):
                frame_time = 0.0
            idx += 1
            break
        idx += 1

    channel_count = len(channels)
    if channel_count == 0:
        return channels, frames, frame_time

    buffer: List[float] = []
    for line in lines[idx:]:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            buffer.extend(float(x) for x in stripped.split())
        except ValueError:
            continue

        while len(buffer) >= channel_count:
            frames.append(buffer[:channel_count])
            buffer = buffer[channel_count:]
            if total_frames and len(frames) >= total_frames:
                return channels, frames, frame_time

    return channels, frames, frame_time


def _parse_servo_id(value) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, str):
        if value.strip().lower() in ('null', 'none', ''):
            return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _expand_joint_map(
    joint_map,
    defaults: Dict,
    joint_alias=None,
    axis_channel_map=None,
    servo_limits=None,
) -> List[Dict]:
    """将兼容格式的关节映射展开为统一的舵机目标描述。"""
    entries: List[Dict] = []
    reverse_alias = {}
    if isinstance(joint_alias, dict):
        for bvh_joint, canonical_joint in joint_alias.items():
            if (
                isinstance(bvh_joint, str)
                and isinstance(canonical_joint, str)
                and canonical_joint not in reverse_alias
            ):
                reverse_alias[canonical_joint] = bvh_joint

    channels_by_axis = {
        'roll': 'Xrotation',
        'pitch': 'Yrotation',
        'yaw': 'Zrotation',
    }
    if isinstance(axis_channel_map, dict):
        for axis_name, channel_name in axis_channel_map.items():
            if isinstance(axis_name, str) and isinstance(channel_name, str):
                channels_by_axis[axis_name.strip().lower()] = _normalize_channel(
                    channel_name
                )

    def _limits_for(servo_id: int) -> Tuple[Optional[float], Optional[float]]:
        if not isinstance(servo_limits, dict):
            return None, None
        limits = servo_limits.get(str(servo_id))
        if limits is None:
            limits = servo_limits.get(servo_id)
        if not isinstance(limits, dict):
            return None, None
        return (
            _coerce_float(limits.get('min'), None),
            _coerce_float(limits.get('max'), None),
        )

    def _append_target(canonical_joint: str, target) -> None:
        if isinstance(target, dict):
            servo_id_value = (
                target.get('servo_id')
                if 'servo_id' in target
                else target.get('id')
            )
            target_joint = (
                target.get('bvh_joint')
                or target.get('joint')
                or target.get('name')
                or canonical_joint
            )
            channel = target.get('channel') or target.get('axis')
            scale = _coerce_float(target.get('scale'), defaults['scale'])
            bias = _coerce_float(target.get('bias'), defaults['bias'])
            min_value = _coerce_float(target.get('min'), defaults['min'])
            max_value = _coerce_float(target.get('max'), defaults['max'])
            servo_type = target.get('servo_type', defaults['servo_type'])
            sign_value = target.get('sign')
            if sign_value is None:
                invert = str(target.get('invert', False)).strip().lower()
                sign = -1.0 if invert in ('1', 'true', 'yes') else 1.0
            else:
                sign = _coerce_float(sign_value, 1.0)
            target_has_limits = 'min' in target or 'max' in target
        else:
            servo_id_value = target
            target_joint = canonical_joint
            channel = None
            scale = defaults['scale']
            bias = defaults['bias']
            min_value = defaults['min']
            max_value = defaults['max']
            servo_type = defaults['servo_type']
            sign = 1.0
            target_has_limits = False

        servo_id = _parse_servo_id(servo_id_value)
        if servo_id is None or not isinstance(target_joint, str):
            return

        if not target_has_limits:
            limit_min, limit_max = _limits_for(servo_id)
            if limit_min is not None:
                min_value = limit_min
            if limit_max is not None:
                max_value = limit_max

        entries.append({
            'bvh_joint': reverse_alias.get(target_joint, target_joint),
            'servo_id': servo_id,
            'channel': _normalize_channel(channel or defaults['channel']),
            'scale': scale,
            'bias': bias,
            'min': min_value,
            'max': max_value,
            'servo_type': servo_type,
            'sign': sign,
        })

    if isinstance(joint_map, list):
        for item in joint_map:
            if not isinstance(item, dict):
                continue
            canonical_joint = (
                item.get('bvh_joint') or item.get('joint') or item.get('name')
            )
            if isinstance(canonical_joint, str):
                _append_target(canonical_joint, item)
        return entries

    if not isinstance(joint_map, dict):
        return entries

    for canonical_joint, mapping in joint_map.items():
        if not isinstance(canonical_joint, str) or mapping is None:
            continue

        axis_targets = []
        if isinstance(mapping, dict):
            for servo_id, axis_reference in mapping.items():
                if (
                    not isinstance(servo_id, str)
                    or not servo_id.isdigit()
                    or not isinstance(axis_reference, str)
                    or '.' not in axis_reference
                ):
                    continue
                joint_name, axis_name = axis_reference.rsplit('.', 1)
                channel = channels_by_axis.get(axis_name.strip().lower())
                if channel:
                    axis_targets.append({
                        'id': servo_id,
                        'bvh_joint': joint_name.strip() or canonical_joint,
                        'channel': channel,
                    })

        if axis_targets:
            for target in axis_targets:
                _append_target(canonical_joint, target)
            continue

        if isinstance(mapping, dict):
            if 'id' in mapping or 'servo_id' in mapping:
                targets = [mapping]
            else:
                targets = list(mapping.values())
        elif isinstance(mapping, list):
            targets = mapping
        else:
            targets = [mapping]

        for target in targets:
            _append_target(canonical_joint, target)

    return entries


def _build_channel_index(channels: List[Tuple[str, str]]) -> Dict[Tuple[str, str], int]:
    index = {}
    for i, (joint, ch) in enumerate(channels):
        index[(joint, _normalize_channel(ch))] = i
    return index


def _coerce_speed_ms(frame_time: float, config: Dict, override: int) -> int:
    if override is not None:
        return max(1, int(override))
    if config.get('default_speed_ms') is not None:
        try:
            return max(1, int(config['default_speed_ms']))
        except (TypeError, ValueError):
            pass
    if frame_time > 0:
        return max(1, int(round(frame_time * 1000)))
    return 33


def main() -> None:
    parser = argparse.ArgumentParser(description='Preprocess BVH into action map frames')
    parser.add_argument('--config', type=Path, default=_default_config_path(),
                        help='Path to bvh_action_map.json')
    parser.add_argument('--output', type=Path, default=None,
                        help='Output path (defaults to --config)')
    parser.add_argument('--input-dir', type=Path, default=None,
                        help='Directory containing *.bvh files')
    parser.add_argument('--all', action='store_true',
                        help='Process all *.bvh files in the input directory')
    parser.add_argument('--speed-ms', type=int, default=None,
                        help='Override speed ms for each command')

    args = parser.parse_args()
    config_path = args.config
    if not config_path.exists():
        raise SystemExit(f'Config file not found: {config_path}')

    config = _load_json(config_path)
    input_dir = _resolve_input_dir(
        config_path=config_path,
        override=args.input_dir,
        configured_dir=config.get('bvh_dir'),
    )
    if input_dir is None:
        raise SystemExit('Missing --input-dir and no bvh_dir in config')

    if not input_dir.exists():
        raise SystemExit(f'BVH directory not found: {input_dir}')

    if args.all:
        action_names = sorted(p.stem for p in input_dir.glob('*.bvh'))
    else:
        bvh_list = config.get('bvh_list') or []
        action_names = [name for name in bvh_list if isinstance(name, str) and name]

    if not action_names:
        raise SystemExit('No BVH actions to process')

    defaults = {
        'channel': _normalize_channel(config.get('default_channel', 'Zrotation')),
        'scale': float(config.get('default_scale', 10.0)),
        'bias': float(config.get('default_bias', 1500.0)),
        'min': float(config.get('default_min', 500.0)),
        'max': float(config.get('default_max', 2500.0)),
        'servo_type': config.get('default_servo_type', 'bus')
    }

    joint_map = config.get('joint_map') or {}
    mapping_entries = _expand_joint_map(
        joint_map,
        defaults,
        joint_alias=config.get('joint_alias'),
        axis_channel_map=config.get('axis_channel_map'),
        servo_limits=config.get('servo_limits'),
    )
    if not mapping_entries:
        raise SystemExit('joint_map is empty or unsupported')

    bvh_data = config.get('bvh_data')
    if not isinstance(bvh_data, dict):
        bvh_data = {}

    for action in action_names:
        bvh_path = input_dir / f'{action}.bvh'
        if not bvh_path.exists():
            print(f'Skip: BVH file not found {bvh_path}')
            continue

        channels, frames, frame_time = _parse_bvh(bvh_path)
        if not frames:
            print(f'Skip: BVH has no frames {bvh_path}')
            continue

        channel_index = _build_channel_index(channels)
        speed_ms = _coerce_speed_ms(frame_time, config, args.speed_ms)
        fps = int(round(1.0 / frame_time)) if frame_time > 0 else 0

        entries_with_index = []
        for entry in mapping_entries:
            idx = channel_index.get((entry['bvh_joint'], entry['channel']))
            if idx is None:
                continue
            enriched = dict(entry)
            enriched['index'] = idx
            entries_with_index.append(enriched)

        if not entries_with_index:
            print(f'Skip: BVH has no matching joint channels {bvh_path}')
            continue

        action_frames: List[List[Dict]] = []
        for frame_values in frames:
            frame_cmds: List[Dict] = []
            for entry in entries_with_index:
                angle = frame_values[entry['index']]
                pos = (
                    entry['bias']
                    + entry['scale'] * angle * entry['sign']
                )
                pos = max(entry['min'], min(entry['max'], pos))
                cmd = {
                    'id': entry['servo_id'],
                    'position': int(round(pos)),
                    'speed': speed_ms,
                    'servo_type': entry['servo_type']
                }
                frame_cmds.append(cmd)
            action_frames.append(frame_cmds)

        bvh_data[action] = {
            'fps': fps,
            'frames': action_frames,
            'source': str(bvh_path)
        }

        print(f'Generated action: {action} (frames={len(action_frames)}, fps={fps})')

    config['bvh_data'] = bvh_data
    if args.input_dir:
        config['bvh_dir'] = str(input_dir)

    output_path = args.output or config_path
    _save_json(output_path, config)
    print(f'Wrote output: {output_path}')


if __name__ == '__main__':
    main()
