# 当前模块职责快照

## 1. 文档定位

本文记录截至 2026-07-20 的仓库当前事实，用于补充说明现有模块到底已经承担了
什么职责。

它与长期规划文档的关系如下：

- `docs/module_responsibilities.md`
  - 保留为长期目标职责文档。
- 本文
  - 只描述当前代码里已经存在的模块、节点和边界现状。

因此，本文不替代长期规划，也不把未来模块写成已落地事实。


## 2. 当前模块总览

当前仓库大体可以分成九个职责域：

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
- 正式任务入口
  - `task_service_bridge`
  - `task_api_msgs`
- 控制原型与当前 motion owner
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
  - 将整机编排拆为 hardware、teleop、task、simulation 四个子 launch。
  - 组合 `execution_manager`、`websocket_bridge`、`servo_hardware`、
    `sensor_hardware` 与 `simulation_bridge` 等运行链路。
  - 已开始在 `full_system`、`parallel_3dof_multi_system` 等场景入口复用
    `launch_utils` 统一解析总线协议缓存默认路径，避免场景 launch 硬编码旧的
    `websocket` 源码树绝对路径。
  - 已开始收回 simulation 域内部的 driver-facing 接线细节，避免整机层继续
    把 `/servo/command` / `/servo/state` 当成仿真入口的公共参数面。
  - 当前持有 `docs/plan.md` Phase 2 仓库级完成合同，以结构化源码检查统一验
    收 WebSocket/simulation 包级分离、sensor 独立所有权、BVH 默认 opt-in
    和 full-system 四分域组合，防止已拆出的职责重新混回默认主链。
  - `teleop.launch.py` 与 `full_system.launch.py` 已公开统一的
    `execution_actuator_state_topic`，将执行层反馈同时接到
    `execution_manager` 与 `websocket_bridge`，不再让上层桥接直接订阅驱动
    状态话题。
  - `task.launch.py` 组合唯一 task bridge、当前 motion owner 与共享
    execution manager；`full_system` 会关闭 teleop 子栈内的重复 execution
    owner，并统一透传 `/task/execute`、`/motion/execute`、task lease 话题与
    motion-level 读取/停止服务。
- 当前主要输入
  - 启动参数
  - 各职责域包的 launch 与配置引用
- 当前主要输出
  - 面向整机运行场景的 launch 入口
  - 面向硬件、遥控、任务、仿真的分域 launch 组合
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
  - 订阅 `motion_msgs/ActuatorState` 的 `/execution/actuator_state`，将执行
    层适配后的执行器状态转换为兼容的 WebSocket 状态字段；核心包已移除
    `servo_msgs` manifest 依赖和运行时导入。
  - 订阅 `/execution/state` 并向 WebSocket 客户端暴露执行层状态与
    teleop 控制权反馈；当 `mode=task_active` 或 `active_source=task` 时，只派
    生 task 活跃展示状态，并在 bridge fallback 与常规 status query 两条摘要
    路径中一致标记 `movement_active=true`，不生产 task control/command。
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
  - `/execution/actuator_state`
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
  - 不作为正式任务入口，不发布 `TaskExecutionControl`，也不提供
    `/task/execute`。
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
    `execution_state` 广播，但它仍属于 WebSocket 出站层派生逻辑；task / teleop
    / motion 的最终跨入口准入已经收回 `execution_manager`。teleop
    `MotionCommand` 已收紧为必须带 requester，并在已有活跃 lease 时必须带
    lease，但 keepalive / release 对空 lease 仍保留过渡兼容。
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
  - router 与每个 port driver 均维护驱动安全 latch/fence：协议 stop 先建立
    fence，再写出硬件命令；active 期间拒绝 topic/service move，release 后继
    续拒绝时间戳早于 fence 的迟到命令。
  - 订阅 transient-local `/servo/driver_safety` 权威状态，并通过
    `/servo/set_driver_safety` 聚合所有有效 port driver 的应用确认；router 只
    在全部端口 ACK 后解除自身 latch。
- 当前主要输入
  - `/servo/command`
  - `/servo/driver_safety`
  - 读写服务请求
- 当前主要输出
  - `/servo/state`
  - 驱动诊断与协议错误信息
- 当前非职责
  - 不负责任务语义理解。
  - 不负责执行仲裁。
  - 不判断 task/teleop 来源或默认优先级；这里只执行最终驱动安全门禁。
  - 不负责轨迹规划。
- 当前问题
  - fake driver 与纯逻辑测试已覆盖多 ID best-effort stop、迟到 move fence 和
    release ACK；真实 LX/ZL 硬件、多端口故障与恢复流程仍需目标环境验收。
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
    配事实；12 包 ROS 闭包已覆盖 build/install，后续仍需补充独立节点启动与
    目标硬件场景验收。
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
  - 作为当前 `/motion/execute` 唯一 ActionServer，接收结构化
    `ankle_pose` goal，并贯穿 task/trace/session 身份。
  - 只有在收到 execution task state 且 task-control DDS 订阅已发现后才接受
    正式 goal；multi-instance launch 会强制关闭其 ActionServer，避免同名
    motion owner。
  - 为正式 goal 申请、续租和释放 task lease，携带 task lease 向
    `/execution/task/command` 发布三执行器目标。
  - 通过 `/execution/read_actuator_position` 读取驱动实际位置，要求三执行
    器连续三个新样本进入容差后才返回成功，不把 accepted 或目标回显当完成。
  - cancel/timeout/driver error 会请求 `/execution/stop_actuators`；取消只有
    在 stop 写出、连续稳定位置采样、task cancel 和终态 lease 清理后才返回，
    `stop_command_sent` 与 `stop_confirmed` 独立报告。
  - 将姿态结果转换为 `motion_msgs/MotionCommand`。
  - 在输出 `MotionCommand` 时已开始显式以 `duration_ms` 与
    `value_encoding` 作为主语义，不再镜像写入已弃用的 `speed` 字段。
  - 求解器输出当前只保留 `duration_ms` 时长字段，控制器也只消费该字段；旧
    词表仅保留在 `rpy_to_servo_commands(..., speed=...)` 与
    `default_speed` 参数名中，不再进入内部命令 dict 或 `MotionCommand`。
  - 发布 theta 反馈用于调试。
- 当前主要输入
  - `~/ankle_rpy`
  - `/motion/execute`
  - `/execution/task/state`
  - `/execution/read_actuator_position`
  - `/execution/stop_actuators`
- 当前主要输出
  - 通过参数 `command_topic` 默认输出
    `motion_msgs/MotionCommand` 到
    `/execution/motion/command`
  - `/execution/task/control`
  - `/execution/task/command`
  - `~/ankle_theta`
- 当前非职责
  - 不负责执行仲裁。
  - 不负责外部任务协议适配。
  - 不负责驱动协议本身。
- 当前问题
  - 已不再直接依赖 `servo_msgs`，但当前正式 Action 只支持 `ankle_pose`，包
    名和目录也还没有收口成长期蓝本中的 `motion_control`。普通 RPY topic 与
    `MotionCommand` 仍保留驱动风格过渡字段。
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
  - 接收 `motion_msgs/TaskExecutionControl`，处理正式 task 的 start、续租、
    finish 与 cancel 准入动作；控制消息必须携带完整
    `task_id` / `trace_id` / `session_id`，start 成功后由执行层生成 task lease。
  - 分别接收 task、teleop 与普通 motion 三路 `MotionCommand` 执行请求；task
    命令使用独立 `/execution/task/command`，不能借普通 motion topic 绕过准
    入。
  - 维护控制状态机：`idle`、`motion_active`、`teleop_active`、
    `task_active`、`estop`。
  - 当前优先级固定为 estop、正式 task、普通 teleop、普通 motion/demo。
    task 活跃时只接受 requester 等于当前 `task_id` 且 lease 匹配的 task
    topic 命令，新的 teleop claim 与普通 motion 均被拒绝。
  - 正式 task start 会撤销普通 teleop holder/lease，并清理被抢占的旧 motion
    活跃窗口；finish、cancel、timeout 会撤销 task 准入。estop 会同时清空
    task/teleop lease 和普通 motion 活跃时间，解除后旧 lease 不会自动恢
    复，`blocked/estop` task 终态仍会保留。
  - lease 撤销后仍保留最近一次成功准入的 task/trace/session 身份用于关联
    finish/cancel/timeout/estop 终态；最近 256 个终态身份形成进程内
    tombstone，拒绝延迟 start 重放。节点重启后的持久幂等不在当前职责内。
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
  - 当前仲裁器也已进一步从命令载荷细节中解耦，只按来源、时间以及
    task/teleop 身份与 lease 做仲裁，不再要求一层伪 `CommandFrame` 中间快
    照。
  - 优先读取 `MotionCommand.value_encoding`，缺失时按 actuator type 补过渡
    默认编码；`duration_ms` 是 `MotionCommand` 唯一执行时长输入，公共
    `speed` 字段已弃用且执行层禁止读取。
  - 将被接受的命令转换为 `servo_msgs/ServoCommand` 并转发到
    `/servo/command`；输出命令由 execution manager 以本地严格递增时间语义重
    打 stamp，供驱动 fence 区分 stop 前旧命令。
  - 提供受完整 task/trace/session/lease 保护的
    `/execution/read_actuator_position` 与 `/execution/stop_actuators`，作为唯
    一 motion-level 到 driver-level 服务适配 owner。位置读取来自驱动服务；
    stop 会按实际协议映射 LX `move_stop` / ZL `stop_motion`，且服务本身不声
    明物理停止确认。
  - 为已接受的 stop 建立单调 operation token；driver 调用未完成时拒绝所有新
    执行命令和 task start，防止迟到 stop 跨任务生效。单个执行器协议读取或
    stop 写出超时后仍继续尝试其余 ID，最后聚合故障。
  - 通过 `/servo/driver_safety` 发布 transient-local `DriverSafetyState`；正常
    stop/estop release 会调用 `/servo/set_driver_safety`，只有 router 与全部有
    效 port driver ACK 后才清除 operation token 和发布权威 false。release 失
    败或超时会保持 token/estop 并锁存不可恢复故障。
  - estop 会绕过已撤销 task lease，直接对已知 bus 执行器写协议 stop；driver
    stop 失败或超时会锁存 `driver_stop_failed` / `driver_stop_timeout`、estop
    与 token，只能通过节点重启恢复，不能由迟到响应或普通 release 自动解锁。
  - 订阅驱动级 `servo_msgs/ServoState` 的 `/servo/state`，先转换为内部
    `ActuatorFeedback`，再通过 `motion_msgs/ActuatorState` 发布到
    `/execution/actuator_state`；该消息使用 actuator 命名、显式
    `value_encoding` 和 `status` / `reason` / `recoverable` 错误语义。
  - 发布 `motion_msgs/ExecutionState` 到 `/execution/state`，其中包含最小
    teleop 控制权反馈，例如剩余租约时间、最近一次控制动作结果、控制动作计
    数、当前 holder 标识与当前 lease 标识。
  - 发布 `motion_msgs/TaskExecutionState` 到 `/execution/task/state`，提供
    当前 task 身份、lease、剩余时间、`status` / `reason` / `recoverable`、
    最近控制请求的完整 task/trace/session 身份、最近一条 task 命令的
    requester/接受结果/reason，以及控制/命令接受拒绝计数。既有
    `ExecutionState` 仅通过 `mode=task_active` /
    `active_source=task` 表达总状态，未修改字段布局。
- 当前主要输入
  - `/execution/task/control`
  - `/execution/task/command`
  - `/execution/teleop/control`
  - `/execution/teleop/command`
  - `/execution/motion/command`
  - `/execution/estop`
  - `/servo/state`
  - `/servo/read_position`
  - `/servo/execute_command`
  - `/servo/set_driver_safety`
- 当前主要输出
  - `/servo/command`
  - `/servo/driver_safety`
  - `/execution/state`
  - `/execution/task/state`
  - `/execution/actuator_state`
  - `/execution/read_actuator_position`
  - `/execution/stop_actuators`
- 当前非职责
  - 不做任务语义理解。
  - 不做轨迹生成。
  - 不做驱动协议实现。
- 当前问题
  - task / teleop / motion 已具备第一版统一准入与优先级合同，正式 task
    Action 也已通过当前 motion owner 接入；但 `TaskExecutionControl` 仍只表
    达内部 lease，物理停止确认由 motion owner 的实际位置采样形成。fake
    driver 多 ID best-effort、迟到 move fence 和 release ACK 已验收；物理多驱
    动 stop、故障锁存后的运维恢复流程、目标硬件和 Jazzy 回归仍未完成。
  - `motion_msgs/TeleopControl` 目前仍只是最小 claim / keepalive /
    release 接口。虽然 `ExecutionState` 已补上 holder 与第一版 lease 标识，
    但高优先级人工 takeover 等更正式策略仍未定义；普通 teleop claim 在
    task 活跃窗口会被拒绝。
  - teleop `MotionCommand` 已收紧为必须带 requester / lease（在已有活跃
    lease 时），task command 也必须从独立 topic 携带匹配 task_id/lease；跨
    入口最终裁决已经统一到执行层。当前过渡兼容主要还留在 TeleopControl
    keepalive / release 对空 lease 的 holder 回退语义。
  - 当前 `motion_msgs` 已经落地最小接口。虽然 `execution_manager` 内部已
    先补上一层中性 setpoint 适配，并已移除 consumer 侧旧 `speed` 时长回退，
    仓库内置 `MotionCommand` producer 也已停止写入该镜像，公共字段已标记弃
    用并建立源码门禁；但删除它属于 breaking ROS interface change，仍需先
    确认仓外 consumer、旧 rosbag、目标 schema 与全量同步切换条件。其余公共
    命令字段也仍带有明显的 servo 风格命名。
- 与长期规划的关系
  - 已补出控制层与驱动层之间的双向最小正式边界：下行命令和上行执行器反
    馈均由 `execution_manager` 负责 motion/driver 接口适配。
  - 当前执行层状态与执行器反馈均已由 `websocket_bridge` 通过
    `motion_msgs` 消费；task-aware admission 已接入第一版正式任务
    goal/result/cancel，后续仍需扩展任务类型、收口 `motion_control` 包边界
    并完成最终中性命令 schema。

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
  - 当前运行依赖已收紧到 `execution_manager`、`servo_hardware` 与两类
    simulation 驱动兼容包；仍需持续防止新的上层包重新依赖该驱动接口。
- 与长期规划的关系
  - 长期应继续保留为驱动级边界。
  - 上层模块应逐步减少对它的长期直接依赖。

### 3.10 `motion_msgs`

- 状态
  - 已实现最小控制与执行接口集合，处于正式语义继续收口阶段。
- 当前承接位置
  - 目录：`src/motion_msgs`
  - ROS 包名：`motion_msgs`
- 当前主要职责
  - 以 `MotionCommand` 承接上层控制和 teleop 执行请求。
  - 以 `TeleopControl` 承接 teleop claim / keepalive / release。
  - 以 `TaskExecutionControl` 承接正式 task 的内部执行租约，以
    `TaskExecutionState` 承接可关联终态的完整身份、状态、错误语义、最近命
    令准入结果和准入计数；这两个类型不代替外部 `task_api_msgs`。
  - 以 `ExecuteMotion` 承接结构化 motion goal/feedback/result/cancel，并用
    `ReadActuatorPosition` / `StopActuators` 隔离 motion owner 与驱动服务。
  - 以 `ExecutionState` 承接仲裁状态、holder、lease、急停与计数反馈。
  - 以 `ActuatorState` 承接执行层向上发布的执行器状态，使用
    `actuator_type` / `actuator_id` / `position_raw` / `value_encoding`，并
    提供 `status` / `reason` / `recoverable` 结构化错误语义。
- 当前非职责
  - 不定义串口、总线协议或驱动服务。
  - 不表达外部任务服务协议。
  - 不负责执行仲裁实现。
- 当前问题
  - `MotionCommand` 仍保留 `servo_type`、`servo_id`、`position` 以及已弃用
    `speed` 等过渡字段；breaking 切换门禁未通过前不会直接删除公共字段。
  - `speech_msgs`、`perception_msgs` 仍需随真实模块按后续阶段落地，不以空
    接口包冒充完成度。
- 与长期规划的关系
  - 已成为当前上层模块与 `execution_manager` 之间的双向接口边界。
  - 最终仍需冻结驱动无关的正式运动请求 schema。

### 3.11 `task_api_msgs`

- 状态
  - 已落地第一版正式任务接口。
- 当前承接位置
  - 目录：`src/task_api_msgs`
  - ROS 包名：`task_api_msgs`
- 当前主要职责
  - 定义 `ExecuteTask` Action，使用结构化 `ankle_pose` goal。
  - 在 goal/feedback/result 中贯穿 task/trace/session 身份。
  - 明确 success、target reached、admission released、stop requested、stop
    command sent 与 stop confirmed 等可区分语义。
- 当前非职责
  - 不表达驱动命令、协议或 execution lease。
  - 不实现任务执行与仲裁。
- 当前问题
  - 当前只冻结了 `ankle_pose`，尚未覆盖长期规划中的多任务、对话和感知上下
    文。

### 3.12 `task_service_bridge`

- 状态
  - 已落地第一版唯一正式任务 Action 入口。
- 当前承接位置
  - 目录：`src/task_service_bridge`
  - ROS 包名：`task_service_bridge`
- 当前主要职责
  - 提供唯一 `/task/execute` ActionServer，并以唯一 `/motion/execute`
    ActionClient 将 task goal 显式映射给当前 motion owner。
  - 逐字段转发 feedback/result，传播 cancel，并始终等待 motion 最终结果；
    goal accepted 不等于 task success。
  - 以线程安全单目标槽位拒绝第二个并发正式任务。
- 当前非职责
  - 不发布 `MotionCommand`、`ServoCommand` 或 `TaskExecutionControl`。
  - 不依赖 `servo_msgs`，不做运动学、执行仲裁或驱动协议适配。
- 当前问题
  - 当前只支持 `ankle_pose` 映射，单目标策略和幂等状态也仅覆盖当前进程；部
    署级唯一入口、ROS ACL 和跨进程持久幂等仍未完成。

### 3.13 `record_load_action`

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
    execution state 驱动的 teleop/task 播放联锁以及 adapter/runtime 关闭生
    命周期；`task_active` 时会返回 `bvh_blocked_by_active_task`，执行层仍保
    留最终拒绝普通 motion 的兜底。
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

### 3.14 `robot_description`

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

### 3.15 `mjc_viewer`

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
  - 当前事实：已经输出到执行边界，并作为 `/motion/execute` 当前唯一 owner
  - 长期去向：演进为 `motion_control`
- `task_service_bridge`
  - 当前事实：唯一 `/task/execute` owner，映射到 `/motion/execute` 并转发生
    命周期结果
  - 长期去向：扩展外部任务协议和 task context，但继续禁止绕过 motion /
    execution 边界
- `task_api_msgs`
  - 当前事实：已定义第一版结构化 `ExecuteTask` Action
  - 长期去向：在真实 owner 落地时增量扩展多任务、对话与感知语义
- `execution_manager`
  - 当前事实：执行仲裁层已统一接 task、teleop 与普通 motion 三路命令；除
    teleop claim/keepalive/release 外，已增加正式 task 身份、lease、优先级、
    状态和超时/estop 清理合同
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
task/teleop/motion 当前也已具备第一版执行准入、lease 与优先级合同；
`task_api_msgs`、`task_service_bridge`、`/task/execute` 和当前
`/motion/execute` owner 已形成一条经过 Action/DDS 验收的正式任务链。执行安
全边界也已增加多 ID best-effort stop、驱动 latch/fence 和 release ACK，
stop 前迟到命令不会在 stop 后重新驱动执行器，ACK 前也不会恢复新任务准入。
仓库仍需继续面对这些现实问题：`websocket_bridge` 仍混合
teleop/debug/status/IMU 上行职责，`parallel_3dof_controller` 虽已输出
`MotionCommand`，但接口仍保留 servo 风格过渡字段；其中 `speed` 已进入弃
用迁移窗口，尚待外部依赖和 breaking 切换门禁确认。C++ 仿真桥仍待最终包边
界合并。长期规划应继续保留，当前事实则由本文负责单独记录。
