"""record_load_action BVH 配置解析测试。"""

import os
import sys


sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../record_load_action'))

import bvh_player
from bvh_player import BvhActionPlayer


def test_bvh_config_resolves_from_record_package(monkeypatch, tmp_path):
    """BVH 配置默认只从 record_load_action 侧解析。"""
    share_dir = tmp_path / 'record_load_action'
    config_dir = share_dir / 'config'
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / 'bvh_action_map.json'
    config_file.write_text('{}', encoding='utf-8')

    def fake_get_package_share_directory(name: str) -> str:
        if name == 'record_load_action':
            return str(share_dir)
        raise RuntimeError(f'unexpected share lookup: {name}')

    monkeypatch.setattr(
        bvh_player,
        'get_package_share_directory',
        fake_get_package_share_directory,
    )

    player = BvhActionPlayer(lambda *_: None)
    resolved = player._resolve_config_path('')

    assert str(config_file) == resolved
