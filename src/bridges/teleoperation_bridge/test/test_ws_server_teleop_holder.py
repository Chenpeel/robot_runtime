"""ws_server teleop holder 生命周期 source-based 测试。"""

import os
import unittest
from pathlib import Path


class TestWsServerTeleopHolderSource(unittest.TestCase):
    """验证 ws_server 已接入断连自动释放 holder。"""

    def test_ws_server_releases_teleop_on_disconnect(self):
        source = Path(
            os.path.join(
                os.path.dirname(__file__),
                '../websocket_bridge/ws_server.py'
            )
        ).read_text(encoding='utf-8')

        self.assertIn(
            'await self._release_teleop_for_client(websocket)',
            source,
        )
        self.assertIn(
            'async def _release_teleop_for_client',
            source,
        )
        self.assertIn(
            'self.handler._invoke_callback',
            source,
        )


if __name__ == '__main__':
    unittest.main()
