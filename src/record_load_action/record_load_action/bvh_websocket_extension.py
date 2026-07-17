"""BVH 播放的可选 WebSocket/ROS capability 装配。"""

from motion_msgs.msg import MotionCommand
from websocket_bridge.error_codes import ErrorCode
from websocket_bridge.error_codes import TeleopControlRejectedException
from websocket_bridge.error_codes import WebSocketException

from .bvh_websocket_adapter import BvhWebSocketPlaybackAdapter
from .bvh_websocket_adapter import BvhWebSocketPlaybackError


DEFAULT_BVH_COMMAND_TOPIC = '/execution/motion/command'


class BvhWebSocketExtension:
    """将 BVH 播放能力作为可选扩展接入 WebSocket bridge。"""

    def __init__(
        self,
        bridge,
        adapter_factory=BvhWebSocketPlaybackAdapter,
    ):
        self._bridge = bridge
        self._logger = bridge.get_logger()

        self._declare_parameter_once(
            'bvh_command_topic',
            DEFAULT_BVH_COMMAND_TOPIC,
        )
        topic_value = bridge.get_parameter('bvh_command_topic').value
        self._command_topic = str(
            topic_value or DEFAULT_BVH_COMMAND_TOPIC
        ).strip()
        if not self._command_topic:
            self._command_topic = DEFAULT_BVH_COMMAND_TOPIC

        self._command_publisher = bridge.create_publisher(
            MotionCommand,
            self._command_topic,
            10,
        )
        self._playback = adapter_factory(
            publish_callback=self._publish_motion_command,
            logger=self._logger,
        )

    @property
    def command_topic(self) -> str:
        """返回 BVH 动作命令的 ROS topic。"""
        return self._command_topic

    @property
    def playback(self) -> BvhWebSocketPlaybackAdapter:
        """返回播放适配器，供测试与诊断读取。"""
        return self._playback

    def register_message_handlers(self, server) -> None:
        """向通用 WebSocket 服务器注册显式 ``bvh_play`` 消息。"""
        server.set_message_callback(
            self._playback.message_type,
            self.handle_play_payload,
        )

    async def handle_play_payload(
        self,
        payload: dict,
        context: dict | None = None,
    ) -> dict:
        """处理 BVH 播放请求并映射稳定的 WebSocket 错误合同。"""
        del context
        try:
            return self._playback.handle_play_payload(payload)
        except BvhWebSocketPlaybackError as exc:
            if exc.kind == BvhWebSocketPlaybackError.BLOCKED:
                self._raise_teleop_blocked(exc.block_context)

            error_code = (
                ErrorCode.INVALID_PARAMETER_VALUE
                if exc.kind == BvhWebSocketPlaybackError.INVALID_REQUEST
                else ErrorCode.ROS_CALLBACK_FAILED
            )
            raise WebSocketException(
                error_code=error_code,
                message=exc.message,
                details=exc.details,
            ) from exc
        except Exception as exc:
            raise WebSocketException(
                error_code=ErrorCode.ROS_CALLBACK_FAILED,
                message=f'BVH play failed: {str(exc)}',
                details={
                    'payload': payload,
                    'exception': str(exc),
                },
            ) from exc

    def on_execution_state(self, state) -> bool:
        """根据 execution state 原子更新 BVH 播放准入门禁。"""
        snapshot = dict(state) if isinstance(state, dict) else {}
        blocked = bool(
            snapshot.get('teleop_active')
            and snapshot.get('active_source') == 'teleop'
        )

        try:
            return self._playback.set_blocked(
                blocked,
                block_context=snapshot if blocked else None,
            )
        except Exception as exc:
            # execution state 上行不应因播放器停止失败而中断。
            self._logger.error(f'更新 BVH 播放阻断状态失败: {exc}')
            return False

    def close(self) -> None:
        """关闭 BVH runtime；重试次数由 bridge 的通用扩展策略管理。"""
        self._playback.close()

    def _publish_motion_command(
        self,
        servo_type: str,
        servo_id: int,
        position: int,
        speed: int,
    ) -> None:
        msg = MotionCommand()
        msg.servo_type = str(servo_type)
        msg.servo_id = int(servo_id)
        msg.position = int(position)
        msg.value_encoding = self._value_encoding_for_servo_type(servo_type)
        msg.duration_ms = int(speed)
        msg.requester_id = ''
        msg.lease_id = ''
        msg.stamp = self._bridge.get_clock().now().to_msg()
        self._command_publisher.publish(msg)

    def _declare_parameter_once(self, name: str, default_value) -> None:
        has_parameter = getattr(self._bridge, 'has_parameter', None)
        if callable(has_parameter) and has_parameter(name):
            return
        self._bridge.declare_parameter(name, default_value)

    @staticmethod
    def _value_encoding_for_servo_type(servo_type: str) -> str:
        normalized = str(servo_type).strip().lower()
        if normalized == 'bus':
            return 'bus_pulse_us'
        if normalized == 'pca':
            return 'pca_tick'
        return ''

    @staticmethod
    def _raise_teleop_blocked(block_context) -> None:
        state = block_context if isinstance(block_context, dict) else {}
        raise TeleopControlRejectedException(
            message='bvh play rejected: bvh_blocked_by_active_teleop',
            details={
                'reason': 'bvh_blocked_by_active_teleop',
                'teleop_holder_id': str(
                    state.get('teleop_holder_id') or ''
                ),
                'teleop_lease_id': str(
                    state.get('teleop_lease_id') or ''
                ),
                'teleop_active': bool(state.get('teleop_active')),
                'active_source': str(state.get('active_source') or ''),
            },
        )


def create_extension(bridge) -> BvhWebSocketExtension:
    """创建供 ``websocket_bridge`` 动态加载的 BVH capability。"""
    return BvhWebSocketExtension(bridge)
