"""robot_bringup launch helpers."""

import json
import os
from pathlib import Path

from ament_index_python.packages import PackageNotFoundError
from ament_index_python.packages import get_package_share_directory

DEFAULT_SERVO_MAP = {
    "/dev/ttyAMA0": [1, 2],
    "/dev/ttyAMA1": [7, 3, 9, 10, 11],
    "/dev/ttyAMA2": [4, 5],
    "/dev/ttyAMA3": [8, 6, 12, 13, 14],
}


def resolve_bus_config_file():
    """Resolve the bus servo config file path."""
    installed_config_file = ''
    try:
        pkg_share = get_package_share_directory('websocket_bridge')
        installed_config_file = os.path.join(pkg_share, 'config', 'bus_servo_map.json')
    except PackageNotFoundError:
        installed_config_file = ''

    workspace_source_config_file = (
        '/root/ros_ws/src/bridges/teleoperation_bridge/config/'
        'bus_servo_map.json'
    )
    cwd_source_config_file = os.path.join(
        Path.cwd(),
        'src',
        'bridges',
        'teleoperation_bridge',
        'config',
        'bus_servo_map.json',
    )
    repo_source_config_file = os.path.join(
        Path(__file__).resolve().parents[3],
        'bridges',
        'teleoperation_bridge',
        'config',
        'bus_servo_map.json',
    )
    config_candidates = [
        workspace_source_config_file,
        cwd_source_config_file,
        repo_source_config_file,
        installed_config_file,
    ]
    return next(
        (path for path in config_candidates if path and os.path.exists(path)),
        repo_source_config_file,
    )


def load_servo_map():
    """Load bus servo mapping from config."""
    config_file = resolve_bus_config_file()
    if os.path.exists(config_file):
        with open(config_file, 'r', encoding='utf-8') as file_obj:
            servo_map = json.load(file_obj)
        print(f"✓ 已加载舵机映射配置: {config_file}")
        print(f"  配置内容: {servo_map}")
        return config_file, servo_map

    print(f"⚠ 警告: 舵机映射配置文件不存在: {config_file}")
    print("  将使用默认配置")
    return config_file, DEFAULT_SERVO_MAP


def get_protocol_cache_default(config_file):
    """Return the default protocol cache file path."""
    return os.path.join(os.path.dirname(config_file), 'bus_protocol_cache.json')
