# WebSocket Bridge

WebSocket通信桥接包，用于ROS 2与WebSocket客户端之间的双向通信。

## 功能特性

- ✅ **双向通信**: Web/树莓派 ↔ WebSocket ↔ ROS 2
- ✅ **多客户端支持**: 维护多个WebSocket连接
- ✅ **协议转换**: JSON消息 ↔ ROS 2结构化数据
- ✅ **舵机控制**: 支持总线舵机和PCA舵机
- ✅ **状态同步**: 实时广播机器人状态
- ✅ **心跳机制**: 自动检测连接状态，并在 teleop 已申请时续租控制权
- ✅ **错误处理**: 统一的错误码和异常处理
- ✅ **日志系统**: 结构化日志记录

## 快速开始

### 1. 安装依赖

```bash
pip install websockets
```

### 2. 集成到ROS 2节点

```python
from websocket_bridge import WebSocketBridgeServer

class YourNode(Node):
    def __init__(self):
        super().__init__('your_node')

        # 创建WebSocket服务器
        self.ws_server = WebSocketBridgeServer(
            host='0.0.0.0',
            port=9105,
            device_id='robot_01'
        )

        # 注册舵机控制回调
        self.ws_server.set_servo_command_callback(self.handle_servo_command)
        self.ws_server.set_teleop_claim_callback(self.handle_teleop_claim)
        self.ws_server.set_teleop_release_callback(self.handle_teleop_release)

        # 启动WebSocket服务器
        asyncio.create_task(self.ws_server.start())

    async def handle_servo_command(self, servo_cmd: dict):
        """处理舵机控制命令"""
        servo_type = servo_cmd['servo_type']  # 'bus' 或 'pca'
        servo_id = servo_cmd['servo_id']
        position = servo_cmd['position']
        # 发布到ROS 2话题...

    async def handle_teleop_claim(self):
        """处理 teleop 控制权申请"""

    async def handle_teleop_release(self):
        """处理 teleop 控制权释放"""
```

### 3. 独立运行（测试）

```bash
cd src/websocket
python -m websocket_bridge.ws_server --host 0.0.0.0 --port 9105 --debug
```

### 4. 默认执行链路

`bridge_node` 会将 WebSocket teleop 控制权请求发布到参数
`teleop_control_topic` 指定的话题，消息类型为
`motion_msgs/TeleopControl`，默认值为 `/execution/teleop/control`。

舵机控制请求仍通过参数 `command_topic` 发布到
`motion_msgs/MotionCommand`，默认值为 `/execution/teleop/command`。

完整系统默认链路如下：

```text
WebSocket -> bridge_node -> TeleopControl -> /execution/teleop/control
          -> bridge_node -> MotionCommand -> /execution/teleop/command
          -> execution_manager -> ServoCommand -> /servo/command
```

如需联调时临时直连驱动层，可显式覆盖为 `/servo/command`。

当前 teleop 链路约束如下：

- 客户端完成 `register` 后，`connected` 回包会显式返回当前连接的
  `requester_id`（并提供同值 `clientId`），便于后续和执行层 holder 对比。
- 客户端先发送 `teleop_claim`，由 `bridge_node` 发布
  `motion_msgs/TeleopControl(action=\"claim\")`。
- `bridge_node` 会使用当前 WebSocket 连接的 session id 填充
  `TeleopControl.requester_id`，作为当前 teleop holder 的最小标识。
- 控制权生效后，heartbeat 会被桥接为 `keepalive`，用于续租 teleop 控制权。
- 客户端结束遥控时发送 `teleop_release`，由 `bridge_node` 发布
  `motion_msgs/TeleopControl(action=\"release\")`。
- 当 WebSocket 连接断开时，`ws_server` 也会按同一 session id 尝试自动释放
  当前 teleop holder。
- `teleop_claim_ack` / `teleop_release_ack` 当前只表示“请求已转发到执行层”，
  会附带当前已知的 `execution_state` 快照；控制权是否真正生效，仍以随后到达
  的 `execution_state` 广播为准。
- `status_query` 响应，以及 `status_update.data.type == "execution_state"` 的
  广播 payload，都会补充连接级 `requester_id`、`known_holder_matches`、
  `known_teleop_active`、`control_confirmed`，用于把当前连接和执行层 holder
  语义对齐。
- 舵机控制命令仍走 `MotionCommand`，但最终是否执行由
  `execution_manager` 仲裁。
- 当前 `bridge_node` 发布 `MotionCommand` 时会同时写入：
  - 兼容字段：`position`、`speed`
  - 增量语义字段：`value_encoding`、`duration_ms`

状态查询与状态广播现在也会携带执行层反馈：

```text
/execution/state (ExecutionState)
  -> bridge_node -> WebSocket status_query/status_update
```

当前 `execution_state` 中除了 `mode` / `active_source` 之外，还会携带
teleop 控制权的最小反馈信息，例如：

- `teleop_holder_id`
- `teleop_control_remaining_sec`
- `last_teleop_control_action`
- `last_teleop_control_accepted`
- `last_teleop_control_reason`

当该状态通过 WebSocket `status_update` 广播给客户端时，如果
`data.type == "execution_state"`，还会额外补当前连接视角的：

- `requester_id`
- `known_holder_matches`
- `known_teleop_active`
- `control_confirmed`

### 5. Isaac-ROS 仿真桥接

用于 Isaac 仿真侧与 ROS 舵机链路直连：

```bash
# 仅启动桥接节点
ros2 run simulation_bridge isaac_bridge_node

# 在完整系统中启用（默认已启用）
ros2 launch robot_bringup full_system.launch.py enable_isaac_bridge:=true
```

默认话题映射：

- `/sim/servo_command` -> `/servo/command`
- `/servo/state` -> `/sim/servo_state`

## 消息格式

### Web → ROS（舵机控制）

teleop 控制权:

```json
{
  "type": "teleop_claim"
}
```

```json
{
  "type": "teleop_release"
}
```

heartbeat:

```json
{
  "type": "heartbeat"
}
```

说明：

- heartbeat 始终保留连接保活语义。
- 当 teleop 控制权已经通过 `teleop_claim` 生效后，`bridge_node` 会将
  heartbeat 额外桥接成 `TeleopControl(action="keepalive")`，用于续租。

简写格式:
```json
{
  "b": -1,      // -1=总线舵机, 0=PCA舵机
  "c": 1,       // 舵机ID
  "p": 1500,    // 位置（总线舵机为微秒值，PCA为tick值）
  "s": 100      // 速度（可选）
}
```

完整格式:
```json
{
  "servo_type": "bus",
  "servo_id": 1,
  "position": 90,
  "speed": 100
}
```

### ROS → Web（状态响应）

其中 `execution_state` 字段来自 `motion_msgs/ExecutionState`：

```json
{
  "character_name": "robot",
  "requester_id": "client-a",
  "known_holder_matches": true,
  "known_teleop_active": true,
  "control_confirmed": true,
  "confirmation_source": "execution_state",
  "servo_states": {
    "bus_servos": [{"servo_id": 1, "angle": 90, "status": "ok"}],
    "pwm_servos": [{"servo_id": 0, "angle": 120, "status": "ok"}]
  },
  "system_state": {
    "movement_active": false,
    "action": "idle"
  },
  "execution_state": {
    "mode": "idle",
    "active_source": null,
    "teleop_holder_id": "",
    "estop_active": false,
    "teleop_active": false,
    "motion_active": false,
    "teleop_control_remaining_sec": 0.0,
    "last_teleop_control_action": "",
    "last_teleop_control_accepted": false,
    "last_teleop_control_reason": "",
    "teleop_control_accepted_count": 0,
    "teleop_control_rejected_count": 0
  },
  "timestamp": 1234567890,
  "result_code": 200
}
```

## API文档

### WebSocketBridgeServer

主要方法:

- `set_servo_command_callback(callback)` - 注册舵机命令回调
- `set_heartbeat_callback(callback)` - 注册心跳回调
- `set_teleop_claim_callback(callback)` - 注册 teleop 控制权申请回调
- `set_teleop_release_callback(callback)` - 注册 teleop 控制权释放回调
- `broadcast_status(status_dict)` - 广播状态到所有客户端
- `start()` - 启动WebSocket服务器
- `stop()` - 停止服务器

### WebSocketHandler

消息处理器，负责解析和路由WebSocket消息。

### MessageHandler

消息解析器，支持多种舵机控制协议格式。

### ErrorCode

错误码枚举:

- `200` - 成功
- `4001` - 无效消息格式
- `4002` - 无效舵机命令
- `5001` - 舵机命令执行失败
- `6001` - 连接超时

## 配置

配置文件位于 `config/` 目录:

- `std_web2ros_stream.json` - Web→ROS数据流格式定义
- `std_ros2web_stream.json` - ROS→Web数据流格式定义

## 测试

运行单元测试:

```bash
cd src/websocket
pytest test/ -v
```

运行特定测试:

```bash
pytest test/test_message_handler.py -v
pytest test/test_websocket_handler.py -v
pytest test/test_stream_schemas.py -v
```

## 日志配置

```python
from websocket_bridge.logger import set_log_level
import logging

# 设置日志级别为DEBUG
set_log_level('websocket_bridge.message_handler', logging.DEBUG)
```

## 项目结构

```
websocket_bridge/
├── __init__.py                  # 包导出
├── message_handler.py           # 消息解析和路由
├── websocket_handler.py         # WebSocket处理器
├── ws_server.py                 # WebSocket服务器
├── stream_schemas.py            # JSON格式验证
├── error_codes.py               # 错误码定义
└── logger.py                    # 日志配置
```

## 许可证

MIT License

## 维护者

chenpeel (chenpeel@foxmail.com)
