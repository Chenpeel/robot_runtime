# 当前模块职责快照

## 1. 文档定位

本文记录截至 2026-07-17 的仓库当前事实，用于补充说明现有模块到底已经承担了
什么职责。

它与长期规划文档的关系如下：

- `docs/module_responsibilities.md`
  - 保留为长期目标职责文档。
- 本文
  - 只描述当前代码里已经存在的模块、节点和边界现状。

因此，本文不替代长期规划，也不把未来模块写成已落地事实。


## 2. 当前模块总览

当前仓库大体可以分成八个职责域：

- 系统集成与场景化启动
  - `robot_bringup`

- 遥控与调试入口
  - `websocket_bridge`
- 执行协调与安全仲裁
  - `execution_manager`
- 执行器驱动
  - `servo_hardware`
- 传感器接入
  - `sensor_hardware`，已独立成 ROS 包
- 控制原型
  - `parallel_3dof_controller`
- 仿真桥接
  - `simulation_bridge`
  - `sim_joint_bridge_cpp`
- 接口、工具与描述资源
  - `motion_msgs`
  - `servo_msgs`
  - `record_load_action`
  - `robot_description`
  - `mjc_viewer`


## 3. 当前模块职责

### 3.1 `robot_bringup`

- 状态
  - 已实现，处于第一版独立编排层状态。
- 当前承接位置
  - ROS 包目录：`src/robot_bringup`
  - ROS 包名：`robot_bringup`
- 当前主要职责
  - 承接整机主入口 `full_system.launch.py`。
  - 将整机编排拆为 hardware、teleop、simulation 三个子 launch。
  - 组合 `execution_manager`、`websocket_bridge`、`servo_hardware`、
    `sensor_hardware` 与 `simulation_bridge` 等运行链路。
  - 已开始在 `full_system`、`parallel_3dof_multi_system` 等场景入口复用
    `launch_utils` 统一解析总线协议缓存默认路径，避免场景 launch 硬编码旧的
    `websocket` 源码树绝对路径。
  - 已开始收回 simulation 域内部的 driver-facing 接线细节，避免整机层继续
    把 `/servo/command` / `/servo/state` 当成仿真入口的公共参数面。
  - 当前持有 `docs/plan.md` Phase 2 仓库级完成合同，以结构化源码检查统一验
    收 WebSocket/simulation 包级分离、sensor 独立所有权、BVH 默认 opt-in
    和 full-system 三分域组合，防止已拆出的职责重新混回默认主链。
- 当前主要输入
  - 启动参数
  - 各职责域包的 launch 与配置引用
- 当前主要输出
  - 面向整机运行场景的 launch 入口
  - 面向硬件、遥控、仿真的分域 launch 组合
- 当前非职责
  - 不承接 WebSocket 消息解析。
  - 不承接执行仲裁本体。
  - 不承接驱动协议实现。
- 当前问题
  - 仍是新引入的编排层，后续还需要继续把更多场景化 launch 从功能包边界
    收口过来。
- 与长期规划的关系
  - 已把系统级编排从 `websocket_bridge` 中拆出。
  - 是后续继续按硬件、遥控、仿真职责域组织入口的当前承接点。

### 3.2 `websocket_bridge`

- 状态
  - 已实现，且处于明显的过渡态。
- 当前承接位置
  - 目录：`src/websocket`
  - ROS 包名：`websocket_bridge`
- 当前主要职责
  - 提供 WebSocket 服务端接入。
  - 在客户端 `register` 时显式回传当前连接的 `requester_id` / `clientId`。
  - 通过显式 `teleop_claim` / `teleop_release` 接口申请与释放 teleop 控制权。
  - 将 WebSocket 连接级 session id 作为 teleop requester 向执行层下发。
  - 在 teleop 控制权确认后缓存当前连接对应的 `teleop_lease_id`，并在
    keepalive / release 时优先继续透传。
  - 在 `servo_control` 等 teleop 命令链路中，开始把当前连接的
    `requester_id` / `lease_id` 一并透传到 `MotionCommand`，作为当前 teleop
    执行命令的显式身份字段。
  - `servo_control` 输入当前也已开始被标准化为 `MotionCommand` 风格字段：
    显式补 `value_encoding` / `duration_ms`，并在 bus 输入为角度时先归一到
    pulse us 后再下发。
  - WebSocket payload 与规范化 ack 仍保留兼容 `speed`；默认 teleop
    `MotionCommand` producer 只写入 `duration_ms`，不再镜像已弃用的公共
    `speed` 字段；两者属于不同协议层合同。
  - 在将 teleop 命令下发到执行层前，先基于最新 `execution_state` 做一层
    holder / lease 预校验；若当前连接缺少 requester / lease 或尚未确认控制
    权，会直接返回错误回包。
  - 在 WebSocket 连接断开时，按同一 session id 尝试自动释放 teleop holder。
  - 将 `teleop_claim_ack` / `teleop_release_ack` 收紧为“请求已转发”语义，
    并附带当前已知执行状态快照，不再把 ack 当成控制权已经生效。
  - 在 `status_query` 回包与 `execution_state` 状态广播里提供连接级
    requester 视角的 teleop 控制权确认字段，便于客户端将当前连接与执行层
    holder / lease 状态对齐。
  - 解析 WebSocket JSON 消息，将 teleop 输入转换为
    `motion_msgs/TeleopControl` 和 `motion_msgs/MotionCommand` 后发往执行层。
  - 订阅 `/servo/state` 并向 WebSocket 客户端广播状态。
  - 订阅 `/execution/state` 并向 WebSocket 客户端暴露执行层状态与
    teleop 控制权反馈。
  - 订阅 `/sensor/imu` 并向 WebSocket 客户端广播传感器数据。
  - 承接心跳续租、状态查询和调试日志聚合。
  - 通过通用字符串参数 `extension_factories` 按 `module:callable` 规格动态
    装配可选扩展；默认值为空，默认运行时不加载任何扩展。
  - 核心节点只面向扩展调用通用的 `register_message_handlers`、
    `on_execution_state` 和 `close` 生命周期钩子，不再内建 BVH 协议知识。
  - `websocket_bridge/package.xml` 已移除对 `record_load_action` 的依赖；
    核心代码也不再持有 BVH topic、publisher、消息注册、teleop 联锁或
    错误映射。
  - 默认 `teleop.launch.py`、`full_system.launch.py` 和 WebSocket core schema
    均不启用或广告 BVH 能力。
- 当前主要输入
  - WebSocket 客户端消息
  - `/servo/state`
  - `/execution/state`
  - `/sensor/imu`
- 当前主要输出
  - 通过参数 `teleop_control_topic` 默认输出
    `motion_msgs/TeleopControl` 到
    `/execution/teleop/control`
  - 通过参数 `command_topic` 默认输出
    `motion_msgs/MotionCommand` 到
    `/execution/teleop/command`
  - WebSocket 状态广播
  - WebSocket 执行状态广播与状态查询回包
  - WebSocket IMU 广播
- 当前非职责
  - 不应该长期承担执行仲裁。
  - 不应该长期承担仿真责任域的主入口。
  - 不应该长期承载 demo/BVH 与系统级 launch 编排。
- 当前问题
  - 遥控、调试、状态桥接和 IMU 上行仍混在同一个包内。
  - 显式 `teleop_claim` / `teleop_release` 链路虽然已经落地，并且执行状态里
    已补上最小控制权反馈、连接级 holder 语义和第一版 `teleop_lease_id`，
    但当前还没有更正式的抢占策略和上层接口约束。
  - 当前 ack 语义虽然已经和执行层状态分离，但上层客户端仍需要继续从
    `execution_state` 角度完成更正式的控制权确认与超时处理。
  - 当前 requester 视角的确认语义虽然已覆盖 register / status_query /
    `execution_state` 广播，但它仍属于 WebSocket 出站层派生逻辑，还不是更
    正式的跨入口统一约束。当前 teleop `MotionCommand` 虽已收紧为必须带
    requester，并在已有活跃 lease 时必须带 lease，但 keepalive / release
    对空 lease 仍保留过渡兼容。
  - 当前 teleop 命令预校验依赖 `websocket_bridge` 持有的最新
    `execution_state` 快照，仍存在桥接层快照与执行层真实状态之间的短窗口。
  - 节点默认输出虽然已经切到执行边界，并已改用 `motion_msgs`，且默认 teleop
    producer 已只写入 `duration_ms` / `value_encoding` 这组显式语义；但
    WebSocket payload 仍保留兼容 `speed`；公共消息层仍保留
    `servo_type`、`servo_id`、`position` 等过渡定义，另有已弃用、仅在迁移
    窗口内保留且仓库内禁止读写的 `speed` 字段。
- 与长期规划的关系
  - 长期上更接近 `teleoperation_bridge` 的前身。
  - 整机主 launch 已迁到 `robot_bringup`。
  - Isaac 仿真桥已拆到 `simulation_bridge`。
  - demo/BVH 已收口为 `record_load_action` 所有的显式可选扩展，
    不再属于默认 teleop 核心。

### 3.3 `servo_hardware`

- 状态
  - 已实现，核心驱动链路已在使用中，但包边界仍是过渡态。
- 当前承接位置
  - 目录：`src/hardware`
  - ROS 包名：`servo_hardware`
- 当前主要职责
  - 提供总线舵机驱动。
  - 提供 PCA 舵机驱动。
  - 提供协议路由、协议探测和协议注册能力。
  - 承接驱动级服务，例如总线指令和角度读取。
- 当前主要输入
  - `/servo/command`
  - 读写服务请求
- 当前主要输出
  - `/servo/state`
  - 驱动诊断与协议错误信息
- 当前非职责
  - 不负责任务语义理解。
  - 不负责执行仲裁。
  - 不负责轨迹规划。
- 当前问题
  - 仍需等待上层控制和 teleop 链路继续收敛到 `execution_manager`，减少
    对驱动级接口的直接假设。
- 与长期规划的关系
  - 长期应只保留执行器和协议相关能力。
  - 传感器节点已迁出为独立 `sensor_hardware` 包。

### 3.4 `sensor_hardware`

- 状态
  - 已拆分为独立 ROS 包。
- 当前承接位置
  - ROS 包目录：`src/sensor_hardware`
  - Python 包目录：`src/sensor_hardware/sensor_hardware`
- 当前主要职责
  - 提供 IMU 的 I2C 驱动节点。
  - 提供 IMU 的串口驱动节点。
  - 发布 `/sensor/imu` 传感器数据。
- 当前主要输入
  - I2C 设备读取
  - 串口设备读取
- 当前主要输出
  - `/sensor/imu`
  - 传感器诊断日志
- 当前非职责
  - 不负责控制决策。
  - 不负责视觉感知。
  - 不负责执行器协议。
- 当前问题
  - Phase 2 合同已固定独立 package、entry point、旧源码清理和 bringup 装
    配事实；后续仍需在具备 ROS 环境时补充独立 build/install/start 验收。
- 与长期规划的关系
  - 已达到“独立 `sensor_hardware` ROS 包”的阶段目标。

### 3.5 `parallel_3dof_controller`

- 状态
  - 已实现，但属于控制原型和过渡方案。
- 当前承接位置
  - 目录：`src/parallel_3dof_controller`
  - ROS 包名：`parallel_3dof_controller`
- 当前主要职责
  - 订阅脚踝 RPY 姿态命令。
  - 进行 3-DOF 并联机构运动学求解。
  - 将姿态结果转换为 `motion_msgs/MotionCommand`。
  - 在输出 `MotionCommand` 时已开始显式以 `duration_ms` 与
    `value_encoding` 作为主语义，不再镜像写入已弃用的 `speed` 字段。
  - 求解器输出当前只保留 `duration_ms` 时长字段，控制器也只消费该字段；旧
    词表仅保留在 `rpy_to_servo_commands(..., speed=...)` 与
    `default_speed` 参数名中，不再进入内部命令 dict 或 `MotionCommand`。
  - 发布 theta 反馈用于调试。
- 当前主要输入
  - `~/ankle_rpy`
- 当前主要输出
  - 通过参数 `command_topic` 默认输出
    `motion_msgs/MotionCommand` 到
    `/execution/motion/command`
  - `~/ankle_theta`
- 当前非职责
  - 不负责执行仲裁。
  - 不负责任务级调度。
  - 不负责驱动协议本身。
- 当前问题
  - 已不再直接依赖 `servo_msgs`。当前 `MotionCommand` 也已开始补充更明确的
    时长与编码语义，controller 内部也已先按新语义表达；但外部接口仍保留驱动
    风格字段作为过渡接口。
- 与长期规划的关系
  - 长期更接近 `motion_control` 的前身。
  - 当前已先输出到执行边界，后续还需继续把过渡消息演进为更稳定的控制语
    义接口。

### 3.6 `execution_manager`

- 状态
  - 已落地最小可运行实现，处于第一版过渡态。
- 当前承接位置
  - 目录：`src/execution_manager`
  - ROS 包名：`execution_manager`
- 当前主要职责
  - 接收 `motion_msgs/TeleopControl`，处理 teleop 控制权的申请、续租与释放。
  - 接收 teleop 与 motion 两路 `motion_msgs/MotionCommand` 执行请求。
  - 维护最小控制状态机：`idle`、`motion_active`、`teleop_active`、
    `estop`。
  - 只在 teleop 已显式获得控制权时接受 teleop 命令。
  - 在 teleop 控制权活跃窗口内阻止 motion 直接下发。
  - 按 `requester_id` 维护当前 teleop holder，并限制 keepalive / release
    只能由当前 holder 发起。
  - 为当前活跃控制权生成第一版 `teleop_lease_id`，并在 keepalive /
    release 时优先按 lease 校验，空 lease 仍兼容回退到 holder 语义。
  - teleop `MotionCommand` 当前必须携带 `requester_id`；当当前
    `teleop_lease_id` 非空时也必须携带匹配的 `lease_id`，并按 holder /
    lease 校验命令归属，减少“只要 teleop_active 就可发命令”的歧义。
  - 在执行层内部先将 `motion_msgs/MotionCommand` 适配为更中性的内部
    setpoint 语义，再继续仲裁并转发到驱动层。
  - 当前仲裁器也已进一步从命令载荷细节中解耦，只按来源、时间与 teleop
    身份做仲裁，不再要求一层伪 `CommandFrame` 中间快照。
  - 优先读取 `MotionCommand.value_encoding`，缺失时按 actuator type 补过渡
    默认编码；`duration_ms` 是 `MotionCommand` 唯一执行时长输入，公共
    `speed` 字段已弃用且执行层禁止读取。
  - 将被接受的命令转换为 `servo_msgs/ServoCommand` 并转发到
    `/servo/command`。
  - 发布 `motion_msgs/ExecutionState` 到 `/execution/state`，其中包含最小
    teleop 控制权反馈，例如剩余租约时间、最近一次控制动作结果、控制动作计
    数、当前 holder 标识与当前 lease 标识。
- 当前主要输入
  - `/execution/teleop/control`
  - `/execution/teleop/command`
  - `/execution/motion/command`
  - `/execution/estop`
- 当前主要输出
  - `/servo/command`
  - `/execution/state`
- 当前非职责
  - 不做任务语义理解。
  - 不做轨迹生成。
  - 不做驱动协议实现。
- 当前问题
  - `motion_msgs/TeleopControl` 目前仍只是最小 claim / keepalive /
    release 接口。虽然 `ExecutionState` 已补上最小控制权反馈、holder 标
    识与第一版 lease 标识，但还没有更正式的持有者抢占规则和多入口约束。
  - teleop `MotionCommand` 虽已收紧为必须带 requester / lease（在已有活
    跃 lease 时），但这套约束仍主要落在当前 teleop 入口与执行层组合上，尚
    未演进成更正式的跨入口统一准入协议；另外 keepalive / release 对空
    lease 仍保留过渡兼容。
  - 当前 `motion_msgs` 已经落地最小接口。虽然 `execution_manager` 内部已
    先补上一层中性 setpoint 适配，并已移除 consumer 侧旧 `speed` 时长回退，
    仓库内置 `MotionCommand` producer 也已停止写入该镜像，公共字段已标记弃
    用并建立源码门禁；但删除它属于 breaking ROS interface change，仍需先
    确认仓外 consumer、旧 rosbag、目标 schema 与全量同步切换条件。其余公共
    命令字段也仍带有明显的 servo 风格命名。
- 与长期规划的关系
  - 已补出控制层与驱动层之间的最小正式边界。
  - 当前执行层状态已经开始被 `websocket_bridge` 消费，但后续还需要继续演进
    到更稳定的内部消息接口和更完整的仲裁规则。

### 3.7 `simulation_bridge`

- 状态
  - 已落地第一版 Python 仿真桥实现；本轮 launch contract 与默认参数归属
    已基本收口完成，当前主要剩余最终包边界合并与必要维护。
- 当前承接位置
  - 目录：`src/simulation_bridge`
  - ROS 包名：`simulation_bridge`
- 当前主要职责
  - 承接 Isaac 仿真侧与当前舵机链路之间的消息互转。
  - 将 `/sim/servo_command` 转换为驱动级 `/servo/command`。
  - 将 `/servo/state` 转换为 `/sim/servo_state`。
- 当前主要输入
  - `/sim/servo_command`
  - `/servo/state`
- 当前主要输出
  - `/servo/command`
  - `/sim/servo_state`
- 当前非职责
  - 不负责 teleop 主入口。
  - 不负责执行仲裁。
  - 不负责控制算法。
- 当前问题
  - 当前只收口了 Python Isaac 桥，`sim_joint_bridge_cpp` 仍是独立 C++ 包。
  - 整机编排虽已迁到 `robot_bringup`，但仿真域仍是跨
    `simulation_bridge` 与 `sim_joint_bridge_cpp` 组合。
  - 仿真域内部虽然已开始统一 launch contract，并已将 driver-facing 参数与
    一部分 simulator-facing 参数收口到 simulation 词表，但 Python / C++
    两条桥接链路的 topic 与参数语义仍未完全收成一套更高层的 simulation
    接口。
  - 当前 `simulation_bridge/simulation.launch.py` 也已不再继续暴露
    `sim_joint_cmd_topic`、`sim_joint_state_fb_topic` 这组 simulation 域
    topic 参数；这些 simulator-facing 细节现已进一步下沉到
    `sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参数，并已有
    source-level contract 测试固定这层更小的 package-level public
    surface。
  - 当前 `simulation_bridge/simulation.launch.py` 也已不再继续暴露
    `isaac_command_topic`、`isaac_state_topic`、
    `isaac_enforce_limits` 这组 Python Isaac bridge 细节参数，以及
    `isaac_bridge_debug`、`sim_cpp_bridge_debug` 这组 bridge-specific
    debug 开关；bridge-specific 默认值、simulator-facing topic 与频率现已
    进一步收回各子链路的包内 YAML 与节点默认参数，子 launch 只负责装配并
    加载所属配置。
  - 当前 `sim_servo_bridge.launch.py` 与 `sim_servo_bridge_node.py` 也已把
    simulator-facing 的 topic 参数名从 `isaac_command_topic`、
    `isaac_state_topic` 进一步收口为 `sim_servo_command_topic`、
    `sim_servo_state_topic`，用于和 `sim_joint_*` 这组 simulation 域词表
    保持同一命名方向。
  - 当前 `sim_servo_bridge_node.py` 也已改为依赖
    `sim_servo_bridge_utils.py`；对应工具模块与测试文件不再继续保留
    `isaac_bridge_*` 这组旧模块名。
  - 当前 `sim_servo_bridge.launch.py` 也已不再继续声明 bridge-specific 的调
    试 / 限幅 launch 参数；这组默认值此前已从 `isaac_bridge_debug`、
    `isaac_enforce_limits` 收口到 `debug`、`enforce_position_limits`，现
    在统一由 `simulation_bridge/config/default_params.yaml` 与节点默认参数
    持有。
  - 当前 `simulation_bridge` 的包元数据描述与运行说明也已改用
    simulation / sim_servo 词表，不再把 Python servo 子链路入口继续表述
    为 Isaac 专名节点。
  - Phase 2 的 WebSocket/simulation 包级分离已经通过仓库级完成合同；当前
    剩余的 `sim_joint_bridge_cpp` 最终包合并与统一消息合同属于后续仿真域
    收口，不能由 Phase 2 完成状态替代。
  - 当前 `sim_joint_bridge.launch.py` 也已不再继续声明 bridge-specific 的调
    试 launch 参数；对应默认值现在统一由
    `sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参数持有。
  - 当前 `sim_joint_bridge_cpp` 也已把 joint 子链路的可执行名、节点名与默
    认参数根节点从 `sim_servo_bridge_*` 收口为 `sim_joint_bridge_*`，避
    免继续和 Python servo 子链路复用同一节点身份。
  - 当前 `sim_joint_bridge_cpp` 也已把内部成员命名进一步对齐到
    `sim_joint_*` 参数词表，减少源码内部仍用泛化 `joint_*` /
    `publish_rate_*` 变量名带来的语义漂移。
  - 当前 C++ 子链路也已把目录从 `src/sim_servo_bridge_cpp` 迁到
    `src/sim_joint_bridge_cpp`，旧目录壳已清理；此后目录名、ROS 包名与节点
    身份已回到同一套 `sim_joint_*` 词表。
  - 当前 `sim_joint_bridge.launch.py` 也已显式加载
    `sim_joint_bridge_cpp/config/default_params.yaml`，把 C++ 子链路的默认参
    数所有权收回到包内配置，而不是继续散落在 launch 内联默认值里。
  - 当前 `sim_joint_bridge.launch.py` 也已不再继续内联
    `servo_command_topic`、`servo_state_topic` 这组 driver-facing 固定接
    线，改为统一由 `sim_joint_bridge_cpp/config/default_params.yaml` 持有
    默认值。
  - 当前 `sim_joint_bridge.launch.py` 也已不再重复声明
    `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`、
    `sim_publish_rate_hz` 这组 simulator-facing 默认值，进一步把默认值所
    有权收回到 `sim_joint_bridge_cpp/config/default_params.yaml` 与节点默
    认参数。
  - 当前 `sim_joint_bridge_cpp` 也已把 `servo_type` 参数收紧为收发两侧共
    用的同一语义：既控制下发 `ServoCommand.servo_type`，也控制回读
    `ServoState` 的过滤条件；非法值会回退到 `bus`。
  - 当前 `sim_joint_bridge_cpp` 也已把内部 `speed` 参数收口为
    `default_speed`，并在非法值时回退到 `100`，与 Python
    `sim_servo_bridge_node.py` 的默认速度语义保持同一方向。
  - 当前 `sim_servo_bridge.launch.py` 也已显式加载
    `simulation_bridge/config/default_params.yaml`，把 Python servo 子链路的
    默认参数所有权收回到包内配置，而不是继续散落在 launch 内联常量与节点
    默认值里。
  - 当前 `sim_servo_bridge.launch.py` 也已不再重复声明
    `sim_servo_command_topic`、`sim_servo_state_topic` 这组
    simulator-facing 默认值，进一步把默认值所有权收回到
    `simulation_bridge/config/default_params.yaml` 与节点默认参数。
  - 当前 `simulation_bridge/simulation.launch.py` 也已不再继续暴露
    `sim_publish_rate_hz` 这类偏 `sim_cpp_bridge` 实现细节的调优参数；该参
    数现已只保留在 `sim_joint_bridge_cpp/config/default_params.yaml` 与节点默
    认参数。
  - 当前 `simulation_bridge/simulation.launch.py` 自己也已不再暴露
    `servo_command_topic`、`servo_state_topic` 这组 driver-facing launch
    参数，而是将其收回为 simulation 域内部固定接线；`robot_bringup`
    也不再感知这两个内部常量。
  - 当前 `robot_bringup` 也已不再继续暴露
    `isaac_command_topic`、`isaac_state_topic`、
    `isaac_enforce_limits` 这组 Python Isaac bridge 细节参数；这些配置已
    收回到 `simulation_bridge` 包内参数文件与节点默认参数；其中 Python
    servo 子链路内部当前已进一步统一为 `enforce_position_limits`。
  - 当前 `robot_bringup` 也已不再继续暴露
    `isaac_bridge_debug`、`sim_cpp_bridge_debug` 这组 bridge-specific
    debug 参数；这些调试开关也已收回到 `simulation_bridge` 与
    `sim_joint_bridge_cpp` 包内参数文件与节点默认参数，其中 Python servo
    子链路内部当前已进一步统一为 `debug`，C++ joint 子链路内部当前也已统
    一为 `debug`。
  - 当前 `robot_bringup` 也已不再继续暴露
    `enable_isaac_bridge`、`enable_sim_cpp_bridge` 这组内部 bridge 实现级启
    停开关，而是改为只保留一个 `enable_simulation` 域级开关。
  - 当前 `simulation_bridge/simulation.launch.py` 也已进一步不再以
    `enable_isaac_bridge`、`enable_sim_cpp_bridge` 这组实现名开关作为包级
    public surface，而是进一步回到单一 domain entry；原先过渡存在的
    `enable_sim_servo_bridge`、`enable_sim_joint_bridge` 这组内部
    capability-based 开关当前也已从 package-level public launch 退场，
    `simulation.launch.py` 直接编排 `sim_servo_bridge.launch.py` 与
    `sim_joint_bridge.launch.py` 两条内部子链路。
  - 当前 `robot_bringup/full_system.launch.py` 也已不再继续暴露
    `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`、
    `sim_publish_rate_hz` 这组 simulation 域细节参数；这些参数现已收回到
    `robot_bringup/simulation.launch.py` 这个 simulation 域入口中。
  - 当前 `robot_bringup/simulation.launch.py` 也已不再继续暴露
    `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`、
    `sim_publish_rate_hz` 这组 simulation 域细节参数；其中
    `sim_joint_cmd_topic`、`sim_joint_state_fb_topic` 与
    `sim_publish_rate_hz` 当前都已进一步下沉到
    `sim_joint_bridge.launch.py` 这个内部子链路边界。
  - 当前 `simulation_bridge` 包内也已补出 `simulation.launch.py` 作为包级
    public 入口；当前由 `robot_bringup/simulation.launch.py` 只 include
    这个包级 public 入口，而 `simulation.launch.py` 已直接编排
    `sim_servo_bridge.launch.py` 与 `sim_joint_bridge.launch.py` 两个子 launch，
    用于明确 Python 与 C++ 两条桥接链路的内部职责边界。
  - 对应的 sim source-level contract 测试当前也已减重为以当前 public
    contract 为主，只保留少量关键旧词表回归断言。
  - 当前虽然已有独立 launch，且 bringup 已开始不再暴露 driver-facing 的
    内部接线参数，但整机默认链路仍需由 `robot_bringup` include 调起。
- 与长期规划的关系
  - 已开始形成 `simulation_bridge` 正式责任域。
  - 后续需要继续把 C++ 仿真桥与实现本体一起最终收口，但这部分当前已不再
    是本轮主推进面。

### 3.8 `sim_joint_bridge_cpp`

- 状态
  - 已实现，可选启用，处于过渡态。
- 当前承接位置
  - 目录：`src/sim_joint_bridge_cpp`
  - ROS 包名：`sim_joint_bridge_cpp`
- 当前主要职责
  - 将 `/sim/joint_cmd` 转换为 `/servo/command`。
  - 将 `/servo/state` 转换为 `/sim/joint_state_fb`。
  - 在仿真关节表示和当前舵机表示之间做驱动级桥接。
- 当前主要输入
  - `/sim/joint_cmd`
  - `/servo/state`
- 当前主要输出
  - `/servo/command`
  - `/sim/joint_state_fb`
- 当前非职责
  - 不负责高层控制规划。
  - 不负责人工遥控入口。
  - 不负责执行仲裁。
- 当前问题
  - 仍然直接耦合驱动级接口。
  - 当前只保留 `servo_command_topic`、`servo_state_topic` 与
    `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`、
    `sim_publish_rate_hz` 这套当前参数词表，旧参数兼容分支已移除。
    simulator-facing 与 driver-facing 默认值均由
    `sim_joint_bridge_cpp/config/default_params.yaml` 和节点默认参数持有，
    `simulation_bridge` 的 package-level launch 不再显式暴露这些细节；但
    仿真域的其它参数与消息 contract 仍未完全统一。
  - 当前虽仍由 `robot_bringup` 的整机链路间接触发，但其节点装配与启停已
    先收口到 `simulation_bridge/simulation.launch.py` 与其内部子 launch
    编排中，仍未完全完成的是包边界与实现本体的最终合并，而不再是
    launch 入口归属本身。
  - 当前 joint 子链路的运行身份也已开始向 capability 词表收口，子 launch
    已改为启动 `sim_joint_bridge_node` / `sim_joint_bridge`，不再继续复
    用 Python servo 子链路的节点身份。
- 与长期规划的关系
  - 长期应被纳入统一的 `simulation_bridge` 责任域。

### 3.9 `servo_msgs`

- 状态
  - 已实现，且是当前相对稳定的驱动级接口边界。
- 当前承接位置
  - 目录：`src/servo_msgs`
  - ROS 包名：`servo_msgs`
- 当前主要职责
  - 提供舵机命令、状态和相关服务定义。
  - 作为当前硬件链路的正式接口。
- 当前主要输入输出
  - 被 `servo_hardware`、`execution_manager`、`simulation_bridge`、
    `sim_joint_bridge_cpp` 等包共同使用。
- 当前非职责
  - 不表达任务语义。
  - 不表达运动学层命令。
  - 不表达外部任务服务接口。
- 当前问题
  - 上层控制和桥接模块当前对它的直接依赖范围过大。
- 与长期规划的关系
  - 长期应继续保留为驱动级边界。
  - 上层模块应逐步减少对它的长期直接依赖。

### 3.10 `record_load_action`

- 状态
  - 已实现，当前作为显式 opt-in 的工具/演示包。
- 当前承接位置
  - 目录：`src/record_load_action`
  - ROS 包名：`record_load_action`
- 当前主要职责
  - 承载 BVH 资源配置。
  - 承载 BVH 运行说明与使用约束说明。
  - 提供 BVH 动作播放与静态转换工具。
  - 作为 `bvh_action_map.json` 的唯一配置所有者与默认解析入口。
  - 仓库级 `scripts/preprocess_bvh.py` 当前也默认从本包读取
    `bvh_action_map.json`，并以配置文件父目录为基准解析相对 `bvh_dir`，不
    再依赖 WebSocket 配置目录或 shell 当前工作目录。
  - 该脚本已与正式播放器的嵌套 target、`joint_alias`、轴映射、舵机限位和
    `sign` / `invert` 语义对齐；随仓 5 个动作均可生成 250 帧，且离线结果与
    正式静态转换器逐帧一致。
  - 提供传输层无关的 `bvh_request.normalize_bvh_play_request`，负责显式
    `bvh_play` 直接字段的规范化与基础结构校验。
  - 提供 `BvhWebSocketPlaybackAdapter`，承接 `bvh_play` 请求规范化、accepted
    ack payload 生成和 WebSocket-facing runtime 装配。
  - 提供 `BvhWebSocketExtension` 与 `create_extension`，作为通用
    `extension_factories` 机制的 BVH 具体实现。
  - 该扩展独立持有指向 `/execution/motion/command` 的 `MotionCommand`
    publisher，并承担 `bvh_play` 注册、accepted ack、BVH 错误映射、
    execution state 驱动的 teleop 播放联锁以及 adapter/runtime 关闭生命周期。
  - 该扩展只把回调提供的执行时长写入显式 `duration_ms`，禁止写入迁移窗口
    内保留的已弃用 `MotionCommand.speed`；请求级 `speed_ms` 合同与播放器内
    部 timing 行为保持不变。
  - 提供 `bvh_websocket_demo.launch.py` 作为显式演示入口；它 include
    `robot_bringup/teleop.launch.py`，显式传入
    `record_load_action.bvh_websocket_extension:create_extension`，并将
    motion 输入固定接到 `/execution/motion/command`。
  - 默认 teleop/full-system launch 不启用该扩展，默认 WebSocket schema
    也不广告 BVH；显式直接字段示例位于
    `config/bvh_play_request.json`。
  - 对外 BVH 合同保持不变：只保留显式 `bvh_play` 与直接字段，
    旧的泛化消息类型别名 `action`、`action.bvh` 嵌套 payload、顶层
    `bvh` 别名、直发舵机或 private 触发路径均不恢复。
  - accepted `bvh_play_ack` 形状、timing 字段透传、teleop 拒绝的
    `TELEOP_CONTROL_REJECTED` 和播放失败的 `ROS_CALLBACK_FAILED` 类别保持稳定。
  - 提供 `BvhPlaybackRuntime`，由它创建并持有 `BvhActionPlayer`，串行化播
    放、blocked 状态切换与 close 生命周期。
  - runtime 在进入 blocked 时先关闭新播放入口再停止当前播放；close 会进入
    closed/blocked 终态，停止失败时保留未完成状态供后续重试，显式停止请求
    在 blocked/closed 状态下仍可执行。
  - blocked 状态下若停止尚未完成，同状态 `set_blocked(True)` 会继续尝试停
    止；成功后再收到同状态调用不会重复停止，返回值仍只表示 blocked 状态本
    身是否发生变化。
  - `BvhActionPlayer` 为每代 worker 使用独立 `Event`，`play()` / `stop()`
    以 bool 报告结果；上一代未确认退出时不会创建替代线程。
- 当前主要输入
  - BVH 动作文件
  - 显式 opt-in 后 WebSocket 侧触发的播放请求
  - 由 `websocket_bridge` 通用钩子转发的 execution state
- 当前主要输出
  - 将 BVH 动作对应的 `motion_msgs/MotionCommand` 发布到
    `/execution/motion/command`
  - WebSocket 侧的 accepted ack 或稳定错误类别
- 当前非职责
  - 不负责正式遥控入口。
  - 不负责系统执行仲裁。
- 当前问题
  - 当前已不再渗入默认 teleop/full-system 主链路；后续需继续保持
    扩展显式 opt-in，避免 demo 合同重新回流到通用 bridge 核心。
  - 离线动作资源/转换工具与 WebSocket demo 装配目前仍处于同一个 ROS 包，
    因此仅安装离线工具也会带入 bridge 与 bringup 运行依赖；后续可在边界稳定
    后评估拆出更小的 demo 集成层。
- 与长期规划的关系
  - 长期应保留为可选工具/演示资源，而不是正式主链路核心。

### 3.11 `robot_description`

- 状态
  - 已实现，职责边界相对清晰。
- 当前承接位置
  - 目录：`src/robot_description`
  - ROS 包名：`robot_description`
- 当前主要职责
  - 承载 URDF、mesh、MJCF、纹理与展示资源。
- 当前主要输入输出
  - 为描述、展示、仿真和标定提供静态资源。
- 当前非职责
  - 不负责控制逻辑。
  - 不负责执行仲裁。
  - 不负责驱动协议。
- 当前问题
  - 当前没有明显职责漂移问题。
- 与长期规划的关系
  - 长期继续作为描述资源域存在即可。

### 3.12 `mjc_viewer`

- 状态
  - 已实现，属于展示与仿真辅助模块。
- 当前承接位置
  - 目录：`src/mjc_viewer`
  - ROS 包名：`mjc_viewer`
- 当前主要职责
  - 提供 MuJoCo 视图与仿真展示辅助能力。
- 当前主要输入输出
  - 依赖模型和状态数据做展示。
- 当前非职责
  - 不负责正式控制链路。
  - 不负责驱动层。
  - 不负责遥控入口。
- 当前问题
  - 当前没有进入正式执行链路，但文档中需要持续强调它属于辅助域。
- 与长期规划的关系
  - 长期应继续留在描述/展示辅助域，不进入执行仲裁主链。


## 4. 当前尚未落地的目标模块

下列名称出现在长期规划文档中，但当前仓库里还没有对应的正式落地包：

- `motion_control`
  - 当前只有原型 `parallel_3dof_controller`，还不能等同于正式
    `motion_control`。
- `teleoperation_bridge`
  - 当前只有混合职责的 `websocket_bridge`，还不能直接等同于正式
    `teleoperation_bridge`。
- `task_service_bridge`
  - 当前不存在独立实现。
- `task_api_msgs`
  - 当前不存在独立消息包。
- `speech_interface`
  - 当前不存在独立实现。
- `vision_perception`
  - 当前不存在独立实现。


## 5. 当前事实到长期规划的映射

为了避免长期规划与当前事实之间断层，现阶段可以按下面的方式理解映射关系：

- `websocket_bridge`
  - 当前事实：teleop/debug/status/IMU 上行的混合包，另提供默认为空的
    通用扩展装配机制
  - 长期去向：以 `teleoperation_bridge` 为主，仿真相关拆到
    `simulation_bridge`
- `record_load_action`
  - 当前事实：独立所有 BVH 配置、播放、WebSocket 扩展和显式 demo launch，
    默认不启用
  - 长期去向：继续作为可选工具/演示资源，不进入正式主链路
- `parallel_3dof_controller`
  - 当前事实：已经输出到执行边界的控制原型
  - 长期去向：演进为 `motion_control`
- `execution_manager`
  - 当前事实：最小执行仲裁层已经落地，统一接 teleop 与 motion 两路命令，
    并开始通过显式 teleop 控制话题处理 claim / keepalive / release
  - 长期去向：演进为正式执行边界，并逐步替换上层对 `servo_msgs` 的直接依
    赖
- `simulation_bridge`
  - 当前事实：Isaac 仿真桥已独立成 Python 包，package-level launch
    contract 与 bringup public surface 本轮已基本收口完成
  - 长期去向：形成统一的仿真责任域
- `servo_hardware`
  - 当前事实：执行器驱动包，IMU 入口已不再由它导出
  - 长期去向：保留执行器与协议能力
- `sensor_hardware`
  - 当前事实：已独立成 ROS 包
  - 长期去向：独立成 `sensor_hardware` ROS 包
- `sim_joint_bridge_cpp`
  - 当前事实：仍是独立 C++ 仿真桥
  - 长期去向：继续向 `simulation_bridge` 责任域收口


## 6. 简短结论

当前仓库已经有可运行的遥控、驱动、传感器、仿真和控制原型，但模块边界仍
处于过渡态。当前已完成多项关键改造：`sensor_hardware` 已独立成包，
`execution_manager` 已补出最小执行边界，`simulation_bridge` 已承接 Isaac
仿真桥且 sim 域 package-level 收口已基本完成，BVH 也已从默认
`websocket_bridge` 核心抽离为 `record_load_action` 所有的显式可选扩展。
但整体上仍需继续面对这些现实问题：`websocket_bridge` 仍混合
teleop/debug/status/IMU 上行职责，`parallel_3dof_controller` 虽已输出
`MotionCommand`，但接口仍保留 servo 风格过渡字段；其中 `speed` 已进入弃
用迁移窗口，尚待外部依赖和 breaking 切换门禁确认。C++ 仿真桥仍待最终包边
界合并。长期规划应继续保留，当前事实则由本文负责单独记录。
