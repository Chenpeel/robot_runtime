# 当前模块职责快照

## 1. 文档定位

本文记录截至 2026-03-23 的仓库当前事实，用于补充说明现有模块到底已经承担了
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
  - `sim_servo_bridge_cpp`
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
  - 已开始收回 simulation 域内部的 driver-facing 接线细节，避免整机层继续
    把 `/servo/command` / `/servo/state` 当成仿真入口的公共参数面。
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
  - 在将 teleop 命令下发到执行层前，先基于最新 `execution_state` 做一层
    holder / lease 预校验；若当前连接缺少 requester / lease 或尚未确认控制
    权，会直接返回错误回包。
  - 在 WebSocket 连接断开时，按同一 session id 尝试自动释放 teleop holder。
  - 将 `teleop_claim_ack` / `teleop_release_ack` 收紧为“请求已转发”语义，
    并附带当前已知执行状态快照，不再把 ack 当成控制权已经生效。
  - 在 `status_query` 回包与 `execution_state` 状态广播里提供连接级
    requester 视角的 teleop 控制权确认字段，便于客户端将当前连接与执行层
    holder / lease 状态对齐。
  - 通过 `record_load_action` 触发 BVH 动作播放时，已开始默认将 demo/BVH
    生成的 `MotionCommand` 输出到 motion 执行入口，而不再复用 teleop 命令入
    口。
  - 解析 WebSocket JSON 消息并下发舵机命令。
  - 订阅 `/servo/state` 并向 WebSocket 客户端广播状态。
  - 订阅 `/execution/state` 并向 WebSocket 客户端暴露执行层状态与
    teleop 控制权反馈。
  - 订阅 `/sensor/imu` 并向 WebSocket 客户端广播传感器数据。
  - 承接心跳续租、状态查询和调试日志聚合。
  - 通过 `record_load_action` 触发 BVH 动作播放。
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
  - 通过参数 `bvh_command_topic` 默认输出
    `motion_msgs/MotionCommand` 到
    `/execution/motion/command`
  - WebSocket 状态广播
  - WebSocket 执行状态广播与状态查询回包
  - WebSocket IMU 广播
- 当前非职责
  - 不应该长期承担执行仲裁。
  - 不应该长期承担仿真责任域的主入口。
  - 不应该长期承载 demo/BVH 与系统级 launch 编排。
- 当前问题
  - 遥控、调试、状态桥接和 BVH 仍混在同一个包内。
  - demo/BVH 虽已不再复用 teleop 执行入口，但能力本身仍挂在
    `websocket_bridge` 包内，尚未真正从 teleop 主链路边界里抽离。
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
  - 节点默认输出虽然已经切到执行边界，并已改用 `motion_msgs`。当前也已开始
    双写 `duration_ms` 与 `value_encoding`，但外部消息仍保留
    `servo_type`、`servo_id`、`position`、`speed` 这类过渡定义。
- 与长期规划的关系
  - 长期上更接近 `teleoperation_bridge` 的前身。
  - 整机主 launch 已迁到 `robot_bringup`。
  - Isaac 仿真桥已经拆到 `simulation_bridge`，后续还需继续收口 demo/BVH
    等非核心能力。
  - demo/BVH 应降级为可选能力，而不是主运行链路中心。

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
  - 仍需继续核对其它 launch 和文档引用是否全部切到新包。
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
    `value_encoding` 作为主语义，并将 `speed` 保留为兼容镜像字段。
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
  - 优先读取 `MotionCommand.duration_ms` 与 `value_encoding`，在过渡期回退
    兼容旧字段语义。
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
    先补上一层中性 setpoint 适配，且 producer 也开始双写更明确的时长与编
    码字段，但外部命令字段仍带有明显的 servo 风格命名。
- 与长期规划的关系
  - 已补出控制层与驱动层之间的最小正式边界。
  - 当前执行层状态已经开始被 `websocket_bridge` 消费，但后续还需要继续演进
    到更稳定的内部消息接口和更完整的仲裁规则。

### 3.7 `simulation_bridge`

- 状态
  - 已落地第一版 Python 仿真桥实现，处于收口中的过渡态。
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
  - 当前只收口了 Python Isaac 桥，`sim_servo_bridge_cpp` 仍是独立 C++ 包。
  - 整机编排虽已迁到 `robot_bringup`，但仿真域仍是跨
    `simulation_bridge` 与 `sim_servo_bridge_cpp` 组合。
  - 仿真域内部虽然已开始统一 launch contract，但 Python / C++ 两条桥接链
    路的 topic 与参数语义仍未完全收成一套更高层的 simulation 接口。
  - 当前虽然已有独立 launch，且 bringup 已开始不再暴露 driver-facing 的
    内部接线参数，但整机默认链路仍需由 `robot_bringup` include 调起。
- 与长期规划的关系
  - 已开始形成 `simulation_bridge` 正式责任域。
  - 后续需要继续把 C++ 仿真桥与 launch 组织一起收口。

### 3.8 `sim_servo_bridge_cpp`

- 状态
  - 已实现，可选启用，处于过渡态。
- 当前承接位置
  - 目录：`src/sim_servo_bridge_cpp`
  - ROS 包名：`sim_servo_bridge_cpp`
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
  - 当前虽已开始以 `servo_command_topic` 作为对外主参数名，并对旧
    `servo_cmd_topic` 保留兼容，但仿真域的其它参数与消息 contract 仍未完全
    统一。
  - 当前通过 `robot_bringup` 的整机 launch 启停，仍未完全收口到统一的
    `simulation_bridge` 包边界。
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
    `sim_servo_bridge_cpp` 等包共同使用。
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
  - 已实现，但更适合作为工具/演示包。
- 当前承接位置
  - 目录：`src/record_load_action`
  - ROS 包名：`record_load_action`
- 当前主要职责
  - 承载 BVH 资源配置。
  - 提供 BVH 动作播放与静态转换工具。
- 当前主要输入
  - BVH 动作文件
  - WebSocket 侧触发的播放请求
- 当前主要输出
  - 通过回调向上层发布动作对应的舵机命令
- 当前非职责
  - 不负责正式遥控入口。
  - 不负责系统执行仲裁。
- 当前问题
  - 当前被 `websocket_bridge` 直接依赖，导致 demo 能力渗入主链路。
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
  - 当前事实：teleop/debug/status/demo 的混合包
  - 长期去向：以 `teleoperation_bridge` 为主，仿真相关拆到
    `simulation_bridge`
- `parallel_3dof_controller`
  - 当前事实：已经输出到执行边界的控制原型
  - 长期去向：演进为 `motion_control`
- `execution_manager`
  - 当前事实：最小执行仲裁层已经落地，统一接 teleop 与 motion 两路命令，
    并开始通过显式 teleop 控制话题处理 claim / keepalive / release
  - 长期去向：演进为正式执行边界，并逐步替换上层对 `servo_msgs` 的直接依
    赖
- `simulation_bridge`
  - 当前事实：Isaac 仿真桥已独立成 Python 包，但 C++ 仿真桥和整机编排仍
    未完全收口
  - 长期去向：形成统一的仿真责任域
- `servo_hardware`
  - 当前事实：执行器驱动包，IMU 入口已不再由它导出
  - 长期去向：保留执行器与协议能力
- `sensor_hardware`
  - 当前事实：已独立成 ROS 包
  - 长期去向：独立成 `sensor_hardware` ROS 包
- `sim_servo_bridge_cpp`
  - 当前事实：仍是独立 C++ 仿真桥
  - 长期去向：继续向 `simulation_bridge` 责任域收口


## 6. 简短结论

当前仓库已经有可运行的遥控、驱动、传感器、仿真和控制原型，但模块边界明显
还处于过渡态。当前已经完成了两步关键改造：`sensor_hardware` 已独立成包，
`execution_manager` 也已补出最小执行边界，`simulation_bridge` 已开始承
接 Isaac 仿真桥。但整体上仍然需要继续面对这些现实问题：`websocket_bridge`
仍偏大、`parallel_3dof_controller` 仍直接构造驱动级命令、C++ 仿真桥与整
机编排还未完全收口。长期规划应继续保留，当前事实则由本文负责单独记录。
