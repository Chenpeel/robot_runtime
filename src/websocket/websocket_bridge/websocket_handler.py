"""
WebSocket 处理器 - 与 ROS 2 集成
"""

import inspect
import json
import time
import asyncio
from typing import Optional, Dict, Any, Callable
from .message_handler import MessageHandler, MessageType
from .error_codes import (
    ErrorCode,
    ErrorResponse,
    SuccessResponse,
    InvalidServoCommandException,
    ServoCommandFailedException,
    WebSocketException,
)
from .logger import get_logger

logger = get_logger(__name__)


class WebSocketHandler:
    """
    WebSocket 通信处理器
    
    1. 维护 WebSocket 连接
    2. 解析来自 Web 的消息
    3. 转发到 ROS 2 话题
    4. 订阅 ROS 2 状态并回传 Web
    """
    
    def __init__(self, device_id: str = "default", debug: bool = False,
                 debug_logger=None):
        """
        初始化 WebSocket 处理器

        Args:
            device_id: 设备 ID
            debug: 是否启用调试日志
        """
        self.device_id = device_id
        self.debug = debug
        self.message_handler = MessageHandler(debug=debug)
        self.debug_logger = debug_logger
        
        # ROS 2 相关的回调
        self.on_servo_command = None  # Callable[[dict], None]
        self.on_heartbeat = None  # Callable[[dict], None]
        self.on_teleop_claim = None  # Callable[[dict], None]
        self.on_teleop_release = None  # Callable[[dict], None]
        self.on_status_query = None  # Callable[[dict], None]
        self.message_callbacks = {}
        
        # 状态管理
        self.servo_state = {}
        self.system_state = {
            "cpu_temp": 0,
            "free_memory": 0,
            "uptime": 0
        }
        self.execution_state = {}
        self.last_heartbeat = time.time()

    def _debug(self, category, message):
        if not self.debug:
            return
        if self.debug_logger:
            self.debug_logger.record(category, message)
        else:
            print(f"[WebSocketHandler] {message}")
    
    def register_servo_command_handler(self, callback: Callable):
        """
        注册舵机命令回调
        
        Args:
            callback: async def callback(servo_cmd: dict) -> None
        """
        self.on_servo_command = callback
    
    def register_heartbeat_handler(self, callback: Callable):
        """
        注册心跳处理回调
        
        Args:
            callback: async def callback() -> None
        """
        self.on_heartbeat = callback
    
    def register_status_query_handler(self, callback: Callable):
        """
        注册状态查询回调
        
        Args:
            callback: async def callback() -> dict
        """
        self.on_status_query = callback

    def register_teleop_claim_handler(self, callback: Callable):
        """注册 teleop 控制权申请回调。"""
        self.on_teleop_claim = callback

    def register_teleop_release_handler(self, callback: Callable):
        """注册 teleop 控制权释放回调。"""
        self.on_teleop_release = callback

    def register_message_handler(self, msg_type: str, callback: Callable):
        """
        为特定消息类型注册处理器
        
        Args:
            msg_type: 消息类型 (如 "servo_control", "heartbeat" 等)
            callback: async def callback(data: dict) -> Optional[str]
        """
        normalized_type = str(msg_type).strip().lower()
        if not normalized_type:
            raise ValueError('消息类型不能为空')
        if self._is_builtin_message_type(normalized_type):
            raise ValueError(f"内建消息类型不可由扩展注册: {normalized_type!r}")
        if normalized_type in self.message_callbacks:
            raise ValueError(f"消息类型已注册: {normalized_type!r}")
        self.message_callbacks[normalized_type] = callback
        self.message_handler.register_handler(normalized_type, callback)
    
    async def handle_message(
        self,
        raw_message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        处理接收到的 WebSocket 消息
        
        Args:
            raw_message: 原始 JSON 字符串
            
        Returns:
            str: 响应消息，或 None
        """
        # 解析消息
        data = self.message_handler.parse_message(raw_message)
        if data is None:
            return None

        explicit_message_type = self._get_explicit_message_type(data)
        if (
            explicit_message_type
            and explicit_message_type in self.message_callbacks
            and not self._is_builtin_message_type(explicit_message_type)
        ):
            return await self._handle_registered_message(data, context)

        # 获取消息类型
        msg_type = self.message_handler.get_message_type(data)
        
        self._debug("ws_handler", f"处理消息: {msg_type.value}")
        
        # 根据消息类型分发
        if msg_type == MessageType.HEARTBEAT:
            return await self._handle_heartbeat(data, context)
        elif msg_type == MessageType.SERVO_CONTROL:
            return await self._handle_servo_control(data, context)
        elif msg_type == MessageType.TELEOP_CLAIM:
            return await self._handle_teleop_claim(data, context)
        elif msg_type == MessageType.TELEOP_RELEASE:
            return await self._handle_teleop_release(data, context)
        elif msg_type == MessageType.STATUS_QUERY:
            return await self._handle_status_query(data, context)
        elif msg_type == MessageType.REGISTER:
            return await self._handle_register(data)
        elif msg_type == MessageType.BROADCAST:
            return await self._handle_broadcast(data, context)
        elif msg_type == MessageType.PRIVATE:
            return await self._handle_private(data, context)
        else:
            return await self._handle_registered_message(data, context)
    
    async def _handle_heartbeat(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """处理心跳消息"""
        self.last_heartbeat = time.time()
        
        if self.on_heartbeat:
            try:
                await self._invoke_callback(self.on_heartbeat, context)
            except Exception as e:
                print(f"[WebSocketHandler] 心跳回调失败: {e}")
        
        response = {
            "type": "heartbeat",
            "status": "online",
            "device_id": self.device_id,
            "timestamp": int(time.time())
        }
        
        self._debug("ws_handler", "发送心跳响应")

        return json.dumps(response, ensure_ascii=False)

    async def _handle_teleop_claim(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """处理 teleop 控制权申请。"""
        del data
        ack_payload = self._default_teleop_ack_payload(context)

        if self.on_teleop_claim:
            try:
                callback_payload = await self._invoke_callback(
                    self.on_teleop_claim,
                    context,
                )
                if isinstance(callback_payload, dict):
                    ack_payload.update(callback_payload)
            except Exception as e:
                return ErrorResponse.create(
                    error_code=ErrorCode.ROS_CALLBACK_FAILED,
                    message=f"teleop claim failed: {str(e)}",
                    details={"exception": str(e)},
                    device_id=self.device_id
                )

        return SuccessResponse.create(
            response_type="teleop_claim_ack",
            data=ack_payload,
            device_id=self.device_id
        )

    async def _handle_teleop_release(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """处理 teleop 控制权释放。"""
        del data
        ack_payload = self._default_teleop_ack_payload(context)

        if self.on_teleop_release:
            try:
                callback_payload = await self._invoke_callback(
                    self.on_teleop_release,
                    context,
                )
                if isinstance(callback_payload, dict):
                    ack_payload.update(callback_payload)
            except Exception as e:
                return ErrorResponse.create(
                    error_code=ErrorCode.ROS_CALLBACK_FAILED,
                    message=f"teleop release failed: {str(e)}",
                    details={"exception": str(e)},
                    device_id=self.device_id
                )

        return SuccessResponse.create(
            response_type="teleop_release_ack",
            data=ack_payload,
            device_id=self.device_id
        )
    
    async def _handle_servo_control(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """处理舵机控制命令"""
        servo_cmd = self.message_handler.parse_servo_control(data)

        if servo_cmd is None:
            print(f"[WebSocketHandler] 无法解析舵机控制命令: {data}")
            return ErrorResponse.create(
                error_code=ErrorCode.INVALID_SERVO_COMMAND,
                message="舵机控制命令格式无效",
                details={"received_data": data},
                device_id=self.device_id
            )

        self._debug("ws_handler", f"解析舵机命令: {servo_cmd}")

        # 调用 ROS 2 命令处理器
        if self.on_servo_command:
            try:
                await self._invoke_callback_with_context(
                    self.on_servo_command,
                    servo_cmd,
                    context,
                )
            except WebSocketException as e:
                return e.to_response(self.device_id)
            except Exception as e:
                print(f"[WebSocketHandler] 舵机命令处理失败: {e}")
                return ErrorResponse.create(
                    error_code=ErrorCode.SERVO_COMMAND_FAILED,
                    message=f"舵机命令执行失败: {str(e)}",
                    details={"command": servo_cmd, "exception": str(e)},
                    device_id=self.device_id
                )

        # 返回确认响应
        return SuccessResponse.create(
            response_type="servo_control_ack",
            data={
                "status": "accepted",
                "command": servo_cmd
            },
            device_id=self.device_id
        )

    async def _handle_registered_message(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """按显式消息类型调用可选扩展处理器。"""
        message_type = self._get_explicit_message_type(data)
        callback = self.message_callbacks.get(message_type)
        if callback is None:
            return None

        try:
            callback_result = await self._invoke_callback_with_context(
                callback,
                data,
                context,
            )
        except WebSocketException as e:
            return e.to_response(self.device_id)
        except Exception as e:
            return ErrorResponse.create(
                error_code=ErrorCode.ROS_CALLBACK_FAILED,
                message=f"{message_type} handler failed: {str(e)}",
                details={"received_data": data, "exception": str(e)},
                device_id=self.device_id,
            )

        if isinstance(callback_result, str):
            return callback_result

        response_data = {"status": "accepted"}
        if isinstance(callback_result, dict):
            response_data.update(callback_result)

        return SuccessResponse.create(
            response_type=f"{message_type}_ack",
            data=response_data,
            device_id=self.device_id,
        )
    
    async def _handle_status_query(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """处理状态查询"""
        del data
        if self.on_status_query:
            try:
                status = await self._invoke_callback(self.on_status_query, context)
                if status:
                    return json.dumps(
                        self._augment_status_snapshot(status, context),
                        ensure_ascii=False,
                    )
            except Exception as e:
                print(f"[WebSocketHandler] 状态查询失败: {e}")

        return self._create_status_response(context)
    
    async def _handle_register(self, data: Dict[str, Any]) -> Optional[str]:
        """处理设备注册"""
        device_name = data.get("name", self.device_id)
        
        response = {
            "type": "register_ack",
            "status": "success",
            "device_id": self.device_id,
            "device_name": device_name,
            "supported_commands": self._get_supported_commands(),
            "timestamp": int(time.time())
        }
        
        self._debug("ws_handler", f"设备已注册: {device_name}")
        
        return json.dumps(response, ensure_ascii=False)
    
    async def _handle_broadcast(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """处理广播消息"""
        content = data.get("content", {})
        
        self._debug("ws_handler", f"收到广播: {content}")
        
        # 如果广播内容包含舵机命令
        servo_cmd = self.message_handler.parse_servo_control(content)
        if servo_cmd and self.on_servo_command:
            try:
                await self._invoke_callback_with_context(
                    self.on_servo_command,
                    servo_cmd,
                    context,
                )
            except Exception as e:
                print(f"[WebSocketHandler] 广播舵机命令处理失败: {e}")
        
        return None
    
    async def _handle_private(
        self,
        data: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """处理私有消息"""
        content = data.get("content", data)
        
        self._debug("ws_handler", "收到私有消息")
        
        # 尝试解析为舵机命令
        servo_cmd = self.message_handler.parse_servo_control(content)
        if servo_cmd and self.on_servo_command:
            try:
                await self._invoke_callback_with_context(
                    self.on_servo_command,
                    servo_cmd,
                    context,
                )
            except Exception as e:
                print(f"[WebSocketHandler] 私有消息舵机命令处理失败: {e}")
            
            response = {
                "type": "private_ack",
                "status": "processed",
                "device_id": self.device_id,
                "timestamp": int(time.time())
            }
            return json.dumps(response, ensure_ascii=False)
        
        return None
    
    def _create_status_response(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """创建状态响应 - 使用标准格式"""
        response = self.get_status_snapshot(context)
        return json.dumps(response, ensure_ascii=False)

    def get_status_snapshot(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """获取当前状态快照。"""
        response = {
            "character_name": "robot",
            "bus_servos": self.servo_state.get("bus_servos", {}),
            "pwm_servos": self.servo_state.get("pwm_servos", {}),
            "time": time.strftime("%Y-%m-%d-%H:%M:%S"),
            "current_status": self._build_current_status(),
            "execution_state": dict(self.execution_state),
            "result_code": 200,
            "timestamp": int(time.time())
        }
        return self._augment_status_snapshot(response, context)
    
    def _get_supported_commands(self) -> Dict[str, Any]:
        """获取支持的命令列表"""
        return {
            "servo_control": [
                "{b: -1, c: servo_id, p: angle_-90_90, s: speed}",  # 总线舵机
                "{b: 0, c: channel_0_15, p: pwm_value}",  # PCA 舵机
                "{servo_type: 'bus', servo_id: 1, position: 90, speed: 100}",
                "{servo_type: 'pca', servo_id: 0, position: 90}",
                "{character_name: 'robot', web_servo: {is_bus_servo: true, servo_id: 1, position: 90, speed: 100}}"
            ],
            "teleop_claim": ["request teleop control lease"],
            "teleop_release": ["release teleop control lease"],
            "heartbeat": ["keep connection alive"],
            "status_query": ["request device status"]
        }
    
    def update_servo_state(self, servo_id: int, servo_type: str, position: int):
        """
        更新舵机状态
        
        Args:
            servo_id: 舵机 ID
            servo_type: 舵机类型 ("bus" 或 "pca")
            position: 当前位置
        """
        if servo_type == "bus":
            if "bus_servos" not in self.servo_state:
                self.servo_state["bus_servos"] = {}
            self.servo_state["bus_servos"][f"id_{servo_id}"] = position
        elif servo_type == "pca":
            if "pwm_servos" not in self.servo_state:
                self.servo_state["pwm_servos"] = {}
            self.servo_state["pwm_servos"][f"id_{servo_id}"] = position

    def update_execution_state(self, execution_state: Dict[str, Any]):
        """更新执行层状态快照。"""
        if not isinstance(execution_state, dict):
            return
        self.execution_state = dict(execution_state)

    def get_requester_teleop_status(
        self,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """根据当前 execution_state 生成连接级 teleop 控制权视图。"""
        requester_id = self._extract_requester_id(context)
        lease_id = self._extract_lease_id(context)
        holder_id = str(self.execution_state.get("teleop_holder_id") or "")
        current_lease_id = str(self.execution_state.get("teleop_lease_id") or "")
        teleop_active = bool(self.execution_state.get("teleop_active"))
        holder_matches = bool(requester_id) and holder_id == requester_id
        lease_matches = bool(lease_id) and current_lease_id == lease_id
        control_confirmed = bool(
            holder_matches
            and teleop_active
            and self.execution_state.get("active_source") == "teleop"
            and (not lease_id or lease_matches)
        )
        return {
            "requester_id": requester_id,
            "teleop_lease_id": current_lease_id,
            "known_holder_matches": holder_matches,
            "known_lease_matches": lease_matches,
            "known_teleop_active": teleop_active,
            "control_confirmed": control_confirmed,
            "confirmation_source": "execution_state",
        }

    @staticmethod
    def _get_explicit_message_type(data: Dict[str, Any]) -> str:
        """提取用于扩展回调分发的显式消息类型。"""
        if not isinstance(data, dict):
            return ""
        for key in ("type", "Type", "TYPE"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return ""

    @staticmethod
    def _is_builtin_message_type(message_type: str) -> bool:
        """判断显式类型是否属于不可被扩展回调覆盖的内建消息。"""
        try:
            return MessageType(message_type) is not MessageType.UNKNOWN
        except ValueError:
            return False

    async def _invoke_callback(
        self,
        callback: Callable,
        payload: Optional[Dict[str, Any]] = None,
    ):
        payload = dict(payload or {})
        if len(inspect.signature(callback).parameters) == 0:
            return await callback()
        return await callback(payload)

    async def _invoke_callback_with_context(
        self,
        callback: Callable,
        payload: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        payload = dict(payload or {})
        context = dict(context or {})
        param_count = len(inspect.signature(callback).parameters)
        if param_count == 0:
            return await callback()
        if param_count == 1:
            return await callback(payload)
        return await callback(payload, context)

    @staticmethod
    def _default_teleop_ack_payload(
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        requester_id = WebSocketHandler._extract_requester_id(context)

        return {
            'status': 'requested',
            'requester_id': requester_id,
            'teleop_lease_id': '',
            'execution_state': {},
            'known_holder_matches': False,
            'known_lease_matches': False,
            'known_teleop_active': False,
        }

    def _augment_status_snapshot(
        self,
        snapshot: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        response = dict(snapshot)
        response.update(self.get_requester_teleop_status(context))
        return response

    @staticmethod
    def _extract_requester_id(
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not isinstance(context, dict):
            return ""
        return str(context.get("requester_id") or "").strip()

    @staticmethod
    def _extract_lease_id(
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        if not isinstance(context, dict):
            return ""
        return str(context.get("lease_id") or "").strip()

    def _build_current_status(self) -> Dict[str, Any]:
        """根据 execution_state 构造当前状态摘要。"""
        movement_active = bool(
            self.execution_state.get("teleop_active")
            or self.execution_state.get("motion_active")
        )
        listening = self.execution_state.get("active_source") == "teleop"
        action = str(self.execution_state.get("mode") or "idle")
        led_state = "red" if self.execution_state.get("estop_active") else (
            "green" if movement_active else "off"
        )
        return {
            "movement_active": movement_active,
            "listening": listening,
            "action": action,
            "led_state": led_state,
        }
    
    def update_system_state(self, **kwargs):
        """
        更新系统状态
        
        Args:
            cpu_temp: CPU 温度
            free_memory: 空闲内存
            uptime: 运行时间
        """
        self.system_state.update(kwargs)
    
    def get_uptime(self) -> float:
        """获取从最后一次心跳后经过的时间"""
        return time.time() - self.last_heartbeat
