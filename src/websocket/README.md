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

舵机控制请求通过参数 `command_topic` 发布到
`motion_msgs/MotionCommand`，默认值为 `/execution/teleop/command`。

完整系统默认链路如下：

```text
WebSocket -> bridge_node -> TeleopControl -> /execution/teleop/control
          -> bridge_node -> MotionCommand (teleop) -> /execution/teleop/command
          -> execution_manager -> ServoCommand -> /servo/command
```

默认核心节点不装配 demo/BVH。可选能力通过通用参数
`extension_factories` 显式加载，未配置时不导入任何扩展包。

当前 teleop 链路约束如下：

- 客户端完成 `register` 后，`connected` 回包会显式返回当前连接的
  `requester_id`（并提供同值 `clientId`），便于后续和执行层 holder 对比。
- 客户端先发送 `teleop_claim`，由 `bridge_node` 发布
  `motion_msgs/TeleopControl(action=\"claim\")`。
- `bridge_node` 会使用当前 WebSocket 连接的 session id 填充
  `TeleopControl.requester_id`，作为当前 teleop holder 的最小标识。
- `execution_manager` 在 claim 生效后会生成 `teleop_lease_id`，并通过
  `ExecutionState` 回传；`ws_server` 会把它缓存到当前连接上下文里。
- 控制权生效后，heartbeat 会被桥接为 `keepalive`，用于续租 teleop 控制权。
- `keepalive` / `release` 当前会优先透传最近一次确认的 `lease_id`；若为空，
  执行层仍会按 `requester_id` 走过渡兼容。
- 客户端结束遥控时发送 `teleop_release`，由 `bridge_node` 发布
  `motion_msgs/TeleopControl(action=\"release\")`。
- 当 WebSocket 连接断开时，`ws_server` 也会按同一 session id 尝试自动释放
  当前 teleop holder。
- `teleop_claim_ack` / `teleop_release_ack` 当前只表示“请求已转发到执行层”，
  会附带当前已知的 `execution_state` 快照；控制权是否真正生效，仍以随后到达
  的 `execution_state` 广播为准。
- `status_query` 响应，以及 `status_update.data.type == "execution_state"` 的
  广播 payload，都会补充连接级 `requester_id`、`teleop_lease_id`、
  `known_holder_matches`、`known_lease_matches`、`known_teleop_active`、
  `control_confirmed`，用于把当前连接和执行层 holder / lease 语义对齐。
- 普通 `servo_control` 映射到 `MotionCommand` 时，会透传当前连接的
  `requester_id` / `lease_id`；当前 teleop `MotionCommand` 已要求
  `requester_id` 必填，且当执行层已确认 `teleop_lease_id` 后 `lease_id`
  也必须匹配。
- `bridge_node` 现在也会基于最新 `execution_state` 先做一层 holder / lease
  预校验；若当前连接尚未确认控制权，或缺少执行层当前要求的 requester /
  lease 身份字段，会直接返回 `TELEOP_CONTROL_REJECTED`，不再先发命令再
  等执行层拒绝。
- 舵机控制命令仍走 `MotionCommand`，但最终是否执行由
  `execution_manager` 仲裁。
- 当前 `bridge_node` 发布 `MotionCommand` 时会同时写入：
  - 兼容字段：`position`、`speed`
  - 增量语义字段：`value_encoding`、`duration_ms`
  - teleop 身份字段：`requester_id`、`lease_id`
- `servo_control` 输入当前也开始被标准化为同一套 motion 语义：
  - bus 输入默认仍可写角度值，但会在桥接前归一为 pulse us
  - 若显式提供 `value_encoding == "bus_pulse_us"`，则会保留原始脉宽值
  - 若同时提供 `duration_ms` 与 `speed`，会优先采用 `duration_ms`
- `bridge_node` 提供通用可选扩展宿主：按逗号分隔的
  `module:callable` 工厂加载扩展，并统一调用扩展的消息注册、执行状态通知和
  关闭钩子。
- 默认 `extension_factories` 为空；核心包可以在未安装
  `record_load_action` 时独立构建、导入和启动。
- 显式配置的扩展若缺包、工厂不可调用、生命周期接口不完整或消息类型冲突，
  节点会在 WebSocket 线程启动前直接失败，不会静默降级为“已启用”。
- 扩展关闭先于 WebSocket 资源清理；首次关闭失败时核心只额外重试一次，最
  终失败不会阻断其余资源清理。
- BVH 的消息、发布、联锁、错误合同和专用 demo launch 已归属
  `record_load_action`，不再是本包默认职责。运行方式见
  `src/record_load_action/README.md`。

状态查询与状态广播现在也会携带执行层反馈：

```text
/execution/state (ExecutionState)
  -> bridge_node -> WebSocket status_query/status_update
```

当前 `execution_state` 中除了 `mode` / `active_source` 之外，还会携带
teleop 控制权的最小反馈信息，例如：

- `teleop_holder_id`
- `teleop_lease_id`
- `teleop_control_remaining_sec`
- `last_teleop_control_action`
- `last_teleop_control_accepted`
- `last_teleop_control_reason`

当该状态通过 WebSocket `status_update` 广播给客户端时，如果
`data.type == "execution_state"`，还会额外补当前连接视角的：

- `requester_id`
- `teleop_lease_id`
- `known_holder_matches`
- `known_lease_matches`
- `known_teleop_active`
- `control_confirmed`

### 5. 可选 BVH demo

默认 `robot_bringup` 不注册 `bvh_play`，默认 WebSocket schema 也不再广告
BVH。需要演示链路时显式运行：

```bash
ros2 launch record_load_action bvh_websocket_demo.launch.py
```

该入口通过通用扩展工厂装配 BVH capability，并继续将动作命令发送到
`/execution/motion/command`，由 `execution_manager` 仲裁。该 launch 只组装
WebSocket 与执行命令链，不会启动硬件或仿真 consumer；需要实际动作时应另行
启动对应链路。该入口会自行启动 WebSocket bridge 与 execution manager，不能
与同端口的 `full_system.launch.py` 重复启动。

### 6. 仿真 servo 桥接

用于仿真侧 servo 话题与 ROS 舵机链路直连：

```bash
# 仅启动桥接节点
ros2 run simulation_bridge sim_servo_bridge_node

# 在完整系统中启用（默认已启用）
ros2 launch robot_bringup full_system.launch.py enable_simulation:=true
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
  "duration_ms": 100
}
```

显式原始脉宽格式:
```json
{
  "servo_type": "bus",
  "servo_id": 1,
  "position": 1500,
  "value_encoding": "bus_pulse_us",
  "duration_ms": 100
}
```

### ROS → Web（状态响应）

其中 `execution_state` 字段来自 `motion_msgs/ExecutionState`：

```json
{
  "character_name": "robot",
  "requester_id": "client-a",
  "teleop_lease_id": "lease-1",
  "known_holder_matches": true,
  "known_lease_matches": true,
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
    "teleop_lease_id": "",
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
- `set_message_callback(msg_type, callback)` - 为特定消息类型注册通用回调
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
