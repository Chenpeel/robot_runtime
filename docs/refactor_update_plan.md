> **基于 `docs/plan.md` 的全局重构进度：55%**
>
> `[███████████░░░░░░░░░]`
>
> 阶段快照：Phase 0 `100%` / Phase 1 `25%` / Phase 2 `100%` /
> Phase 3 `75%` / Phase 4 `100%` / Phase 5 `0%` / Phase 6 `0%`
>
> 评估日期：2026-07-20。Phase 0–6 等权，单阶段只取
> `0% / 25% / 50% / 75% / 100%` 五档；算术平均后取最近的 `5%`。
> 当前原始均值为 `57.1%`。该比例衡量长期蓝本落地程度，不代表发布就绪度、
> 测试覆盖率或外部迁移完成度。

# 重构更新计划

## 1. 文档定位

本文是截至 2026-07-20 的重构更新计划，用来连接“当前仓库事实”和“长期规
划目标”。

它与现有文档的关系如下：

- `docs/plan.md`
  - 保留为长期目标规划文档，描述理想架构和最终边界。
- `docs/module_responsibilities.md`
  - 保留为长期目标职责文档，描述目标模块的正式分工。
- `docs/current_module_responsibilities.md`
  - 记录当前代码中已经存在的模块事实。
- 本文
  - 基于当前事实，给出近期可执行的重构顺序、范围和验收标准。

因此，本文不是去推翻长期规划，而是补上一层“从现在怎么走到那里”的执行计
划。


## 2. 当前基线

当前仓库最重要的现实约束有六点：

1. `websocket_bridge` 目前是混合职责包。
   - 它仍同时承担 WebSocket 接入、人工遥控、状态回传与 IMU 上行；
     核心另提供默认为空的通用扩展装配机制。
   - BVH 已收口到 `record_load_action` 的显式 opt-in 扩展，不再属于
     默认 `websocket_bridge` 核心。
2. `motion_msgs` 已经落地最小接口，但字段语义仍保留明显的过渡态。
3. `robot_bringup` 已经独立承接整机主 launch，并开始按硬件、遥控、仿真拆
   分启动入口。
4. `sensor_hardware` 已经独立成 ROS 包，主 launch 也已切到新包。
5. `simulation_bridge` 已经独立承接 Isaac 仿真桥，但 `sim_joint_bridge_cpp`
   仍是单独的 C++ 仿真桥，仿真域还没有完全收口。
6. `task_api_msgs`、`task_service_bridge` 与 `/task/execute` 已落地，当前
   `parallel_3dof_controller` 作为 motion owner，经 `execution_manager`
   接到驱动边界；包名和多任务类型仍未最终收口。

这意味着当前阶段的关键不是补齐所有远期模块，而是先把已有链路的边界理顺。


## 3. 本轮重构目标

本轮更新计划只追求四个结果：

1. 把“当前事实”和“长期目标”从文档层彻底拆开，避免误导后续开发。
2. 把当前运行链路中的 teleop、控制、驱动、仿真边界重新梳理清楚。
3. 继续收敛 `execution_manager` 与 `sensor_hardware` 落地后的遗留问题。
4. 在不破坏现有 `colcon build` 和主 launch 的前提下推进重构。

本轮不追求：

- 一次性引入所有远期模块。
- 为了命名统一而先做大规模目录迁移。
- 在没有性能证据的情况下做 Python 到 C++ 的大规模重写。


## 4. 推荐执行顺序

### Phase A：补充现状文档

目标：

- 增加与长期规划并行存在的“当前事实”文档。

动作：

1. 新增当前模块职责快照文档。
2. 新增基于当前事实的更新计划文档。
3. 明确新旧文档各自职责，避免后续再把未来模块写成现状。

完成标准：

- 新人只读文档，也能分清“现在有什么”和“未来要变成什么”。

### Phase B：先拆边界，不先改包名

目标：

- 在保持现有包名和构建方式不变的前提下，先把边界和接线说清楚、理顺。

当前状态：

- `robot_bringup` 包已创建，并承接整机主入口 `full_system.launch.py`。
- 整机入口已拆为 hardware、teleop、task、simulation 四个子 launch 再组合。
- 场景化 launch 当前也已开始复用 `robot_bringup.launch_utils` 统一解析总线协议
  缓存默认路径，不再在子场景入口里硬编码旧的 `websocket` 源码树绝对路径。
- `websocket_bridge` 不再默认承接系统级编排。
- `websocket_bridge` 核心已收口为默认不加载任何 capability 的通用
  WebSocket/teleop 节点，BVH 只由 `record_load_action` 的 demo launch 显式装配。
- `robot_bringup` 已增加 `docs/plan.md` Phase 2 仓库级完成合同，通过结构化
  AST、XML 与 JSON 检查固定四项拆包结果：WebSocket 与 simulation 包级分
  离、IMU 只由独立 `sensor_hardware` 导出、BVH 只由可选 demo 反向装配，
  以及 `full_system` 实际返回 hardware / teleop / task / simulation 四个子域
  include。Phase 2 聚合合同 5 项、BVH 预处理回归 6 项、既有相关边界 27 项，
  共 38 项直接证据通过，已形成可重复的 source-level 验收。
- Phase 2 收尾也已清除用户入口中的旧边界引用：BVH 预处理脚本默认配置与相
  对资源目录均从 `record_load_action` 解析，并与正式播放器的嵌套 target、
  `joint_alias`、轴映射、舵机限位和正反向语义保持一致；随仓 5 个动作均可生
  成 250 帧，且输出与正式静态转换器逐帧一致。根 README 改用当前
  `sim_servo_bridge_node`，仿真联测脚本只传递 `enable_simulation` 域级开关。
- Phase 2 调分当轮的 source-level 定向回归按 `robot_bringup` 15 项、
  `record_load_action` 58 项、simulation/WebSocket 定向合同 15 项分组，共
  88 项通过。前述 38 项是独立归档的 Phase 2 直接证据集，与 88 项定向回归
  中的 32 项重叠；两组分别用于调分审计与较宽回归，不能相加。当轮宿主环境
  没有 `colcon`、`ros2` 与 Docker Compose，未把 ROS 构建、安装后 entry
  point、launch 启动或容器联测计入 Phase 2 完成证据，这些仍受 Phase 1 和
  后续运行验收约束。

动作：

1. 将 `websocket_bridge` 核心职责拆成三类看待：
   - teleop 入口
   - 状态与传感器上行桥
   - 通用可选扩展的加载与生命周期钩子
2. 约束后续新增功能：
   - 不再继续把仿真和 demo 逻辑往 `bridge_node` 里堆。
   - 不再继续把系统级编排逻辑默认放进 `websocket_bridge`。
3. demo/BVH 等具体 capability 必须由各自所有者包实现，并通过独立场景
   launch 显式 opt-in，不得成为默认 teleop/full-system 依赖。
4. 让文档和 launch 组织先反映出边界，而不是所有东西都以
   `websocket_bridge` 为中心。

完成标准：

- 现有系统仍能启动。
- 文档和 launch 结构已经能反映出 teleop、simulation、hardware 的职责差
  异。
- 默认 teleop/full-system 可以在不启用 BVH 的情况下运行，BVH 仅由显式
  demo launch 装配。

### Phase C：引入执行边界

目标：

- 新建最小可用的 `execution_manager`，把控制层和驱动层之间补上一道正式边
  界。

当前状态：

- `execution_manager` 包已创建并接入 `robot_bringup` 的
  `full_system.launch.py`。
- `motion_msgs` 包已创建，提供最小 `MotionCommand` 与 `ExecutionState`
  接口。
- `motion_msgs` 已继续补充最小 `TeleopControl`，用于 teleop 显式申请、
  续租和释放控制权。
- `websocket_bridge` 节点默认通过参数 `command_topic` 输出
  `motion_msgs/MotionCommand` 到
  `/execution/teleop/command`。
- `websocket_bridge` 节点默认通过参数 `teleop_control_topic` 输出
  `motion_msgs/TeleopControl` 到
  `/execution/teleop/control`，并把心跳接成 teleop keepalive。
- `websocket_bridge` 已通过 `teleop_claim` / `teleop_release` 这组显式
  WebSocket 消息接入 teleop 控制权链，不再把“发命令即抢占”当成当前事实。
- `parallel_3dof_controller` 节点默认通过参数 `command_topic` 输出
  `motion_msgs/MotionCommand` 到
  `/execution/motion/command`。
- `execution_manager` 已改为接收 `motion_msgs/MotionCommand`，发布
  `motion_msgs/ExecutionState`，仅对驱动层输出 `servo_msgs/ServoCommand`。
- `motion_msgs` 已新增中性执行器反馈 `ActuatorState`，使用
  `actuator_type` / `actuator_id` / `position_raw` / `value_encoding`，并提
  供 `status` / `reason` / `recoverable` 和原始 `driver_error_code`。
- `execution_manager` 已补齐反馈适配方向：订阅驱动级 `/servo/state`，经纯
  逻辑 `feedback_adapter` 转换后只向上发布 `/execution/actuator_state`。
  `websocket_bridge` 只消费该 `motion_msgs/ActuatorState`，并已移除
  `servo_msgs` manifest 依赖、运行时导入和 `/servo/state` 直订阅；既有
  WebSocket 状态字段保持兼容。
- Phase 3 仓库级合同已固定上层包只依赖 `motion_msgs`、驱动接口依赖白名单、
  `execution_manager` 双向适配所有权和 bringup 反馈接线。新增反馈适配、边
  界和 WebSocket payload 兼容测试共 13 项通过。
- 本次 Phase 3 验收已在仓库只读挂载的一次性 ROS 2 Humble 容器完成：核心
  5 包（`motion_msgs`、`servo_msgs`、`execution_manager`、
  `parallel_3dof_controller`、`websocket_bridge`）与 `robot_bringup` 完整依
  赖闭包 10 包分别构建通过；`motion_msgs` 与 `execution_manager` 的
  `colcon test-result` 汇总 36 项零失败，其中包括 34 个 Python 用例和 2 个
  `ament_cmake_pytest` / CTest 注册项；`ros2 interface show`、
  execution launch 参数解析、teleop/full-system `--show-args` 与 8 秒 teleop
  启动冒烟均通过。真实 pub/sub 也确认了 `ServoState → ActuatorState` 与
  `MotionCommand.duration_ms → ServoCommand.speed` 双向适配。该证据证明当前
  接口在 Humble 可生成和运行；仓库目标 Jazzy 的发布前回归仍需在对应镜像或
  目标环境补充，不能由本次跨发行版结构验收替代。
- `motion_msgs` 已新增独立的内部任务执行准入接口
  `TaskExecutionControl` / `TaskExecutionState`，不修改既有
  `MotionCommand` / `ExecutionState` 字段布局，也不把它们冒充为外部
  `task_api_msgs`。控制接口携带 `task_id` / `trace_id` / `session_id`，由
  `execution_manager` 生成并校验 task lease；状态接口提供
  `status` / `reason` / `recoverable`、剩余租约、控制/命令计数和最近 task
  命令的独立准入结果。finish/cancel/timeout/estop 会立即撤销 lease，但保留
  最近一次成功准入的完整 task/trace/session 身份供终态关联。
- `execution_manager` 已增加 `/execution/task/control`、
  `/execution/task/command`、`/execution/task/state` 三条内部链路与
  `task_active` 模式。仲裁顺序当前固定为 estop、正式 task、普通 teleop、
  普通 motion/demo：task 活跃时只接受 requester 等于当前 `task_id` 且 lease
  匹配的 task topic 命令；普通 motion、空 requester 的 BVH/demo 和新的
  teleop claim 均被拒绝。正式 task start 会清理普通 teleop lease 与被抢占
  的旧 motion 活跃窗口；finish、cancel、timeout 和 estop 会撤销 task 准
  入，estop 同时清理已有 teleop/task lease，解除后仍保留 blocked 终态且必
  须重新申请。最近 256 个终态身份会形成进程内 tombstone，延迟 start 重放
  会被拒绝为 `task_control_replay`。
- BVH 可选扩展现在会在 `task_active` 时本地阻断并返回稳定的
  `bvh_blocked_by_active_task`，执行层仍保留最终裁决；WebSocket 核心只从既
  有 `ExecutionState.mode/active_source` 派生 task 活跃状态，不生产 task
  control/command，也没有新增正式任务 WebSocket 协议。
- Phase 4A 新增 12 项 task 仲裁单元测试和 7 项仓库级入口边界合同；BVH task
  联锁增加 1 项、WebSocket task 状态回归增加 2 项，共 22 项 source-level
  直接证据；另有 1 项由 pytest/colcon 自动发现的真实 ROS pub/sub smoke。
  ARM64 ROS 2 Humble 隔离环境已完成 `robot_bringup` 10 包依赖闭包及额外
  `record_load_action` 构建，共 11 包；`motion_msgs`、`execution_manager`、
  `robot_bringup` 的 `colcon test-result` 汇总 72 项零失败（69 个
  Python/pytest 用例和 3 个 `ament_cmake_pytest` / CTest 注册项），接口生成
  与三层 launch 参数解析通过。
- 自动 ROS smoke 通过真实 DDS/pub-sub 确认：错误 task lease 的独立拒绝反馈
  可见；普通 motion 与 teleop 在 task 窗口被拒；匹配 task lease 的命令产生
  `ServoCommand`；finish/cancel/timeout/estop 终态保留完整任务身份；解除
  estop 后 blocked 终态仍可见；延迟 start 重放被拒；finish 后普通 motion
  恢复。该场景不包含真实硬件或外部 `/task/execute` Action。
- 更宽的 `websocket_bridge` 包级 colcon 仍受既有 flake8/pep257 基线约束，
  结果为 132 passed、30 skipped、2 failed，未计入本轮 72 项零失败集合；本
  轮直接受影响的 WebSocket 定向回归已通过。Humble 结果不替代仓库目标
  Jazzy 的发布前回归。
- Phase 4B 已新增正式 `task_api_msgs/ExecuteTask` 和
  `motion_msgs/ExecuteMotion` Action，以及受 task lease 保护的实际位置读取
  与停止请求服务。`task_service_bridge` 是唯一 `/task/execute` server，只
  将结构化 goal 映射到 `/motion/execute`，不依赖 `servo_msgs`，也不直接发
  布 `MotionCommand` 或 `ServoCommand`。
- 当前 `parallel_3dof_controller` 作为 motion owner：申请 task lease 后才向
  `/execution/task/command` 发布三执行器目标；完成必须来自
  `execution_manager` 转发的驱动级实际位置新采样并连续三次进入容差。取消
  会先请求协议级 stop，再用独立停止阈值连续采样确认位置稳定，最后撤销 task
  lease 并等待可关联终态；stop 写出与物理停止确认始终分离。
- `execution_manager` 当前独占 motion-level 到 driver-level 的读取与停止适
  配，校验完整 task/trace/session/lease；LX 使用 `move_stop`，ZL 使用
  `stop_motion`。`robot_bringup/task.launch.py` 组合 execution、motion owner
  和 task bridge，`full_system` 只保留一个 execution manager owner。
- `TaskExecutionState` 对最近控制请求补齐 task/trace/session 完整身份；motion
  owner 只在收到 execution task state 且 DDS 控制订阅已发现后接受 goal。
  multi-instance controller 强制关闭正式 ActionServer，避免形成第二个
  `/motion/execute` owner。
- stop 当前使用单调 operation token；driver 调用未完成时统一阻断 task、
  teleop 与普通 motion 新命令和 task start。estop 会直接停止已知 bus ID；
  driver stop 失败或超时会锁存 `driver_stop_failed` /
  `driver_stop_timeout`、estop 与 token，迟到响应和普通 release 都不能静默恢
  复准入。
- stop 批处理当前按执行器 best-effort：单个 ID 的协议读取或 stop 写出超时只
  标记聚合故障，仍继续尝试其余 ID。`execution_manager` 通过 transient-local
  `/servo/driver_safety` 发布权威 `DriverSafetyState`；router 与 port driver
  在协议 stop 前建立本地 fence，active 期间拒绝 move，release 后也拒绝时间戳
  早于 fence 的迟到 topic/service move。正常 release 通过
  `/servo/set_driver_safety` 聚合全部有效 port driver 的 ACK；ACK 返回前保持
  stop token 与 estop，release 失败或超时继续锁存故障。
- Phase 4B/C 在禁网、仓库只读、`/tmp` 隔离的 ARM64 ROS 2 Humble 容器完成
  12 包依赖闭包构建；八个目标包的功能 xUnit 汇总 158 项零失败，另有
  `parallel_3dof_controller` 定向测试 26 项通过。四个 task/motion
  Action/Service、`DriverSafetyState`、`SetDriverSafety` 和带命令时间戳的
  `ExecuteBusCommand` 均完成接口生成，task/hardware/full-system launch 参数
  解析通过。独立 Action/DDS smoke 在同一真实 ROS 图中启动五个
  节点，确认成功链 11 条 feedback、目标外不会提前完成、连续三个目标样本后
  成功、并发任务拒绝和 task 窗口仲裁；取消链确认三个协议 stop 实际写出、
  连续四个冻结位置样本后 `stop_confirmed=true`，且 task lease 最终清空。新增
  smoke 还确认延迟 stop 期间新 task 被 `task_stop_pending` 阻断且无命令逸出、
  stop 完成后恢复，estop 对三个执行器直接 stop，三条迟到 move 和 active 期
  间新 move 均被拒绝、全部端口 release ACK 后恢复，以及首个 stop 超时后其余
  两个 ID
  仍收到协议 stop，最终故障锁存且新 task 持续阻断。完整 smoke 用时约
  `8.5329s`。`servo_hardware` 包级历史 flake8/pep257 基线未计入零失败集合。
  fake driver 不是物理硬件，Humble 结果也不替代目标 Jazzy 发布回归。
- `execution_manager` 已开始通过独立控制话题处理 teleop claim / release /
  keepalive，并拒绝未持有 teleop 控制权的 teleop 命令。
- `ExecutionState` 已开始提供第一版 teleop 控制权反馈，包括剩余租约时间、
  最近一次控制动作结果与控制动作计数。
- WebSocket teleop 链路已开始透传连接级 `requester_id`，执行层也已开始维
  护最小 `teleop_holder_id` 语义，用于约束 claim / keepalive / release。
- `motion_msgs/TeleopControl` 与 `ExecutionState` 已开始增量补充
  `lease_id` / `teleop_lease_id`，执行层会为活跃 teleop 控制权生成第一版
  lease，并在 keepalive / release 时优先按 lease 校验。
- teleop 链路上的 `MotionCommand` 已开始增量补充 `requester_id` /
  `lease_id`，`execution_manager` 也已将 teleop 执行命令收紧为必须携带
  `requester_id`，并在当前 `teleop_lease_id` 非空时必须携带匹配的
  `lease_id`。
- `websocket_bridge` 已开始在命令下发前基于最新 `execution_state` 做本地
  holder / lease 预校验；若当前连接缺少 requester / lease 或尚未确认控制
  权，会直接返回错误，减少“先发命令再等执行层拒绝”的往返。
- `ws_server` 已开始在连接断开时按同一 `requester_id` 尝试自动释放 teleop
  holder，减少旧租约拖到超时窗口后才清空的问题。
- `teleop_claim_ack` / `teleop_release_ack` 已开始只表达“请求已转发到执行
  层”，并附带当前已知 `execution_state` 快照，不再把 ack 本身当成控制权
  已生效的最终确认。
- `ws_server` 已开始在 `connected` 回包显式暴露当前连接的
  `requester_id` / `clientId`。
- `status_query` 已开始补充连接级 requester 视角的 teleop 控制确认字段，
  例如 `known_holder_matches`、`known_lease_matches`、
  `known_teleop_active` 与 `control_confirmed`，用于把当前连接与执行层
  holder / lease 语义对齐。
- `execution_state` 对应的 WebSocket `status_update` 广播也已开始按连接补充同
  一组 requester 视角字段，减少客户端必须主动轮询 `status_query` 才能确认
  控制权的耦合。
- `execution_manager` 内部已开始把 `MotionCommand` 先适配为更中性的内部
  setpoint 语义，再继续仲裁并转发到驱动层。
- `execution_manager` 当前也已进一步把仲裁器从命令载荷细节中解耦；
  `CommandArbitrator` 现在只按来源、时间以及 task/teleop 身份与 lease 做仲
  裁，不再要求一层伪 `CommandFrame` 中间快照，而是由节点在 setpoint 适配
  后直接送入仲裁，再把被接受的请求转回驱动层命令。
- `MotionCommand` 已开始增量补充 `duration_ms` 与 `value_encoding`，
  `execution_manager` 已优先读取新字段；默认 WebSocket teleop producer、
  `parallel_3dof_controller` 与可选 BVH producer 也已停止写入旧 `speed`
  镜像。其中 `parallel_3dof_controller` 已先在
  producer 内部显式以 `duration_ms` / `value_encoding` 作为主语义；求解器
  输出当前只保留 `duration_ms` 时长字段，控制器只接受该显式时长，并在发布
  `MotionCommand` 时只写入这组显式字段，不再回退或镜像旧 `speed`。该包内
  旧词表仅保留在 `speed` / `default_speed` 参数名中。
- `execution_manager` 当前也已移除 consumer 侧旧 `speed` 时长回退：内部
  setpoint 时长只来自显式正值 `duration_ms`，旧 `MotionCommand.speed` 不
  再被提升为内部执行时长。
- 公共 `MotionCommand.speed` 当前已标记为弃用，仅在接口迁移窗口内保留；
  `motion_msgs` 已增加 no-read / no-write 源码合同并注册为 60 秒测试，同时
  保护 WebSocket、BVH 与 `ServoCommand.speed` 这三类独立合同。
- 字段删除会改变 ROS 类型描述、生成代码与序列化布局。当前已新增专项迁移说
  明，记录仓外 consumer、旧 rosbag、目标 schema、版本策略、clean rebuild
  和同步重启门禁；这些外部条件确认前不直接修改 `.msg` 布局。
- `websocket_bridge` 当前也已开始把 `servo_control` 输入标准化为
  `MotionCommand` 风格字段：显式补 `value_encoding` / `duration_ms`，并把
  bus 目标值在桥接前归一到 pulse us；WebSocket payload 与规范化 ack 仍保留
  兼容 `speed`，但默认 teleop `MotionCommand` producer 已不再写入该镜像。
- `websocket_bridge` 核心已将可选 capability 收口到通用字符串参数
  `extension_factories`；它按 `module:callable` 动态装配扩展，默认值为空。
- 核心节点现在只调用扩展的 `register_message_handlers`、
  `on_execution_state` 和 `close` 钩子；它不再声明 BVH topic，不再创建
  BVH publisher，也不再承担 `bvh_play` 注册、teleop 联锁或 BVH 错误映射。
- `websocket_bridge/package.xml` 已移除 `record_load_action` 依赖，核心
  Python 模块也已移除具体 BVH 导入。
- 通用 `MessageHandler` 已移除 `BVH_PLAY` 枚举与 `parse_bvh_action`；
  `WebSocketHandler` 只按已注册的显式 `type` 分发扩展。
- `record_load_action` 已提供 `BvhWebSocketExtension` 和
  `create_extension`；该扩展独立持有 `/execution/motion/command` publisher，
  并承担 `bvh_play` 注册、accepted ack、错误映射、execution state 联锁以及
  `BvhWebSocketPlaybackAdapter` / `BvhPlaybackRuntime` 关闭生命周期。
- `BvhWebSocketExtension` 当前也已只把回调提供的执行时长写入显式
  `duration_ms`，不再镜像旧 `MotionCommand.speed`；请求级 `speed_ms` 合同与
  播放器内部 timing 行为保持不变。
- `record_load_action/launch/bvh_websocket_demo.launch.py` 作为显式 opt-in 入口
  include `robot_bringup/teleop.launch.py`，传入
  `record_load_action.bvh_websocket_extension:create_extension`，并将 motion 入口
  固定为 `/execution/motion/command`。
- 默认 `teleop.launch.py`、`full_system.launch.py` 和 WebSocket core schema
  均不启用或广告 BVH；显式请求示例已迁入
  `record_load_action/config/bvh_play_request.json`。
- `bvh_action_map.json` 和默认路径解析仍由 `record_load_action` 唯一所有；
  `robot_bringup` 与 `websocket_bridge` 仍不公开 `bvh_action_file` 参数。
- BVH 对外合同保持不变：只保留显式 `bvh_play` 与直接字段；旧的泛化
  消息类型别名 `action`、`action.bvh` 嵌套 payload、顶层 `bvh` 别名、
  直发舵机或 private 触发路径仍不存在。
- `/execution/motion/command` topic、播放 timing 透传、teleop 活跃时的播放
  阻断、accepted `bvh_play_ack`、`TELEOP_CONTROL_REJECTED` 和
  `ROS_CALLBACK_FAILED` 错误类别保持不变。
- `BvhPlaybackRuntime` 仍负责播放/blocked/close 串行化；
  `BvhActionPlayer` 仍为每代 worker 使用独立 `Event`，并以 bool
  `play()` / `stop()` 报告结果，上一代未退出时不创建替代线程。
- player 明确返回 `False` 时仍通过 `ROS_CALLBACK_FAILED` 显式失败；
  blocked 停止未完成时仍可重试，节点 shutdown 则通过通用扩展 `close`
  策略完成有限次数的清理重试。
- `websocket_bridge` 已开始消费 `motion_msgs/ExecutionState`，并将执行层状
  态上行到 WebSocket 状态查询/广播链路。

动作：

1. 继续稳定最小执行请求与执行反馈接口，尤其是刚补上的 teleop 控制权反馈语
   义。
2. 继续收紧 `motion_msgs` 的字段语义，减少过渡式 servo 风格字段长期保留；
   当前已先在 `execution_manager` 内部补上中性适配层，并已为消息增量补充更
   明确的时长和编码语义；consumer 侧旧 `speed` 时长回退与仓库内置 producer
   镜像均已移除，公共字段也已进入带源码门禁的弃用迁移窗口。下一步先冻结
   `servo_type`、`servo_id`、`position` 等剩余字段的目标 schema，并完成仓外
   依赖与 breaking 切换确认，再决定一次性公共接口变更范围。
3. 继续稳定 teleop 显式 claim / release / keepalive 接口与上层调用约束，
   明确哪些行为是正式入口，哪些仍是过渡态。当前 register / status_query /
   execution_state 已暴露 requester 视角，task/teleop/motion 的最终准入也已
   统一到执行层；现阶段兼容回退主要留在 `TeleopControl` keepalive/release
   对空 lease 的 holder 语义上，高优先级人工 takeover 仍未定义。
4. 继续扩展当前只支持 `ankle_pose` 的正式任务类型，并收口 task context、
   部署级唯一入口、持久幂等、多驱动 stop、物理硬件和 Jazzy 发布回归。

完成标准：

- 至少一条控制链不再直接发布 `/servo/command`。
- 至少一条 teleop 链路经过执行层。
- 驱动层只负责驱动，不负责控制权判断。

基于当前命令与反馈双向边界、仓库级依赖合同和 ROS 构建/pub-sub/launch 验
收，`docs/plan.md` Phase 3 从 `50%` 提升到 `75%`。Phase 3 尚未达到
`100%`：`MotionCommand` 最终中性 schema 与 breaking 切换门禁仍未完成，
`speech_msgs`、`perception_msgs` 也尚未随真实模块落地；本轮新增的
`task_api_msgs` 不改变 Phase 3 的最终命令 schema 阻塞。

基于唯一正式任务桥、task/teleop 共用执行边界且默认优先级不同、实际位置完成
反馈、best-effort stop、驱动安全 fence、系统接线和 ROS Action/DDS 验收，
`docs/plan.md` Phase 4 从 `75%` 提升到 `100%`。全局原始均值由 `53.6%` 提升
到 `57.1%`，实际增加约 `3.6` 个百分点；按最近 `5%` 展示仍为 `55%`，因此顶
部进度条保持 11/20 格。当前只支持 `ankle_pose`、正式 `motion_control` 包边
界、task context、部署访问控制、跨进程持久幂等、目标硬件与 Jazzy 回归仍是
发布加固或后续演进事项，不再扩张为 Phase 4 蓝本完成门禁。

### Phase D：拆分 `sensor_hardware`

目标：

- 将已经存在的 `sensor_hardware` 代码从“包内子模块”提升为独立 ROS 包。

当前状态：

- 独立包已创建，主 launch 已切到新包。
- 旧的 `src/hardware/sensor_hardware` 副本已清理。
- 后续重点从“拆出来”转为“补测试与继续核对引用”。

动作：

1. 继续核对 launch、依赖和构建清单是否全部切到新包。
2. 补充必要测试，确保独立包单独构建和启动稳定。

完成标准：

- `servo_hardware` 只承载执行器与协议能力。
- `sensor_hardware` 可以单独构建、安装和启动。

### Phase E：收口仿真域

目标：

- 将 Isaac 桥与 `sim_joint_bridge_cpp` 这类逻辑从 teleop 包边界中抽离出来。

当前状态：

- `simulation_bridge` 包已创建，并承接了 Isaac 仿真桥。
- `robot_bringup/full_system.launch.py` 已切到 include
  `simulation_bridge` 自己的仿真 launch。
- `sim_joint_bridge_cpp` 仍是独立 C++ 包，仿真域仍未完全收口到统一包边界；
  但当前目录迁移也已完成，代码现位于 `src/sim_joint_bridge_cpp`。
- 仿真域对外 launch contract 已开始收紧最基础的 driver-facing 参数命名，
  例如 C++ 仿真桥当前已以 `servo_command_topic` 作为正式对外主参数名，
  不再继续保留旧 `servo_cmd_topic` 兼容。
- `robot_bringup/simulation.launch.py` 也已开始把 driver-facing 的
  `/servo/command` / `/servo/state` 接线收回为 simulation 域内部固定值，
  不再继续把这两个参数暴露为 bringup 的 public surface。
- C++ 仿真桥对 simulator-facing 的 public 参数名也已开始向
  `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`、
  `sim_publish_rate_hz` 这组 simulation 域词表收口，且当前已不再继续保留
  旧 `joint_cmd_topic`、`joint_state_fb_topic`、`publish_rate_hz`
  兼容分支。
- `simulation_bridge/simulation.launch.py` 当前也已不再继续暴露
  `sim_joint_cmd_topic`、`sim_joint_state_fb_topic` 这组 simulation 域
  topic 参数；这些 simulator-facing 细节现已进一步下沉到
  `sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参数，并已有
  source-level contract 测试固定这层更小的 package-level public surface。
- `simulation_bridge/simulation.launch.py` 当前也已不再继续暴露
  `isaac_command_topic`、`isaac_state_topic`、
  `isaac_enforce_limits` 这组 Python Isaac bridge 细节参数，以及
  `isaac_bridge_debug`、`sim_cpp_bridge_debug` 这组 bridge-specific
  debug 开关；其中 bridge-specific 的调试/限幅开关现已进一步下沉到
  `sim_servo_bridge.launch.py` 与 `sim_joint_bridge.launch.py` 两个子 launch
  中，而 simulator-facing 默认 topic / 频率则进一步收回到包内默认参数与
  节点默认参数。
- `sim_servo_bridge.launch.py` 与 `sim_servo_bridge_node.py` 当前也已把
  simulator-facing 的 topic 参数名从 `isaac_command_topic`、
  `isaac_state_topic` 进一步收口为 `sim_servo_command_topic`、
  `sim_servo_state_topic`，用于和 `sim_joint_*` 这组 simulation 域词表保
  持同一命名方向。
- `sim_servo_bridge_node.py` 当前也已改为依赖
  `sim_servo_bridge_utils.py`；对应工具模块与测试文件不再继续保留
  `isaac_bridge_*` 这组旧模块名。
- `sim_servo_bridge.launch.py` 当前也已不再继续声明 bridge-specific 的调试
  / 限幅 launch 参数；这组默认值此前已从 `isaac_bridge_debug`、
  `isaac_enforce_limits` 收口到 `debug`、`enforce_position_limits`，现在
  统一由 `simulation_bridge/config/default_params.yaml` 与节点默认参数持有。
- `simulation_bridge` 的包元数据描述与运行说明当前也已改用
  simulation / sim_servo 词表，不再把 Python servo 子链路入口继续表述
  为 Isaac 专名节点。
- `sim_joint_bridge.launch.py` 当前也已不再继续声明 bridge-specific 的调试
  launch 参数；对应默认值现在统一由
  `sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参数持有。
- `sim_joint_bridge_cpp` 当前也已把 joint 子链路的可执行名、节点名与默认参
  数根节点从 `sim_servo_bridge_*` 收口为 `sim_joint_bridge_*`，避免继续和
  Python servo 子链路复用同一节点身份。
- `sim_joint_bridge_cpp` 当前也已把内部成员命名进一步对齐到
  `sim_joint_*` 参数词表，减少源码内部仍用泛化 `joint_*` / `publish_rate_*`
  变量名带来的语义漂移。
- C++ 子链路当前也已把目录从 `src/sim_servo_bridge_cpp` 迁到
  `src/sim_joint_bridge_cpp`，旧目录壳已清理；此后目录名、ROS 包名与节点身
  份已回到同一套 `sim_joint_*` 词表。
- `sim_joint_bridge.launch.py` 当前也已显式加载
  `sim_joint_bridge_cpp/config/default_params.yaml`，把 C++ 子链路的默认参数
  所有权收回到包内配置，而不是继续散落在 launch 内联默认值里。
- `sim_joint_bridge.launch.py` 当前也已不再继续内联
  `servo_command_topic`、`servo_state_topic` 这组 driver-facing 固定接线，
  改为统一由 `sim_joint_bridge_cpp/config/default_params.yaml` 持有默认值。
- `sim_joint_bridge.launch.py` 当前也已不再重复声明
  `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`、
  `sim_publish_rate_hz` 这组 simulator-facing 默认值，进一步把默认值所有权
  收回到 `sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参数。
- `sim_joint_bridge_cpp` 当前也已把 `servo_type` 参数收紧为收发两侧共用的同
  一语义：既控制下发 `ServoCommand.servo_type`，也控制回读 `ServoState`
  的过滤条件；非法值会回退到 `bus`。
- `sim_joint_bridge_cpp` 当前也已把内部 `speed` 参数收口为 `default_speed`，
  并在非法值时回退到 `100`，与 Python `sim_servo_bridge_node.py` 的默认速
  度语义保持同一方向。
- `sim_servo_bridge.launch.py` 当前也已显式加载
  `simulation_bridge/config/default_params.yaml`，把 Python servo 子链路的默认
  参数所有权收回到包内配置，而不是继续散落在 launch 内联常量与节点默认值
  里。
- `sim_servo_bridge.launch.py` 当前也已不再重复声明
  `sim_servo_command_topic`、`sim_servo_state_topic` 这组 simulator-facing
  默认值，进一步把默认值所有权收回到
  `simulation_bridge/config/default_params.yaml` 与节点默认参数。
- `simulation_bridge/simulation.launch.py` 当前也已不再继续暴露
  `sim_publish_rate_hz` 这类偏 `sim_cpp_bridge` 实现细节的调优参数；该参数
  现已只保留在 `sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参
  数。
- `simulation_bridge/simulation.launch.py` 也已不再把
  `servo_command_topic`、`servo_state_topic` 作为 public launch 参数暴露，
  而是回收为 simulation 域内部固定 driver 接线；对应地
  `robot_bringup/simulation.launch.py` 也不再感知这两个内部常量。
- `robot_bringup/simulation.launch.py` 与 `full_system.launch.py` 也已不再继
  续暴露 `isaac_command_topic`、`isaac_state_topic`、
  `isaac_enforce_limits` 这组 Python Isaac bridge 细节参数；这些配置现已
  收回到 `simulation_bridge` 包内参数文件与节点默认参数中；其中 Python
  servo 子链路内部当前已进一步统一为 `enforce_position_limits`。
- `robot_bringup/simulation.launch.py` 与 `full_system.launch.py` 也已不再继
  续暴露 `isaac_bridge_debug`、`sim_cpp_bridge_debug` 这组 bridge-
  specific debug 开关；相关调试参数现已只保留在
  `simulation_bridge` 与 `sim_joint_bridge_cpp` 包内参数文件与节点默认参数
  中；其中 Python servo 子链路内部当前已进一步统一为 `debug`，
  C++ joint 子链路内部当前也已统一为 `debug`。
- `robot_bringup/simulation.launch.py` 与 `full_system.launch.py` 也已不再继
  续暴露 `enable_isaac_bridge`、`enable_sim_cpp_bridge` 这组实现级启停开
  关，而是改为只保留一个 `enable_simulation` 域级开关。
- `simulation_bridge/simulation.launch.py` 当前也已进一步不再以
  `enable_isaac_bridge`、`enable_sim_cpp_bridge` 这组实现名开关作为包级
  public surface，而是进一步回到单一 domain entry；原先过渡存在的
  `enable_sim_servo_bridge`、`enable_sim_joint_bridge` 这组内部
  capability-based 开关当前也已从 package-level public launch 退场，
  `simulation.launch.py` 直接编排 `sim_servo_bridge.launch.py` 与
  `sim_joint_bridge.launch.py` 两条内部子链路，仿真域 package-level
  contract 进一步缩小。
- `robot_bringup/full_system.launch.py` 也已不再继续暴露
  `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`、
  `sim_publish_rate_hz` 这组 simulation 域细节参数；这些参数现已收回到
  `robot_bringup/simulation.launch.py` 这个 simulation 域入口中。
- `robot_bringup/simulation.launch.py` 也已不再继续暴露
  `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`、
  `sim_publish_rate_hz` 这组 simulation 域细节参数；其中
  `sim_joint_cmd_topic`、`sim_joint_state_fb_topic` 与
  `sim_publish_rate_hz` 当前都已进一步下沉到
  `sim_joint_bridge.launch.py` 这个内部子链路边界。
- `simulation_bridge` 包内当前也已补出 `simulation.launch.py` 作为包级
  public 入口；当前由 `robot_bringup/simulation.launch.py` 只 include 这
  个包级 public 入口，而 `simulation.launch.py` 已直接编排
  `sim_servo_bridge.launch.py` 与 `sim_joint_bridge.launch.py` 两个子 launch，用
  于明确 Python 与 C++ 两条桥接链路的内部职责边界。
- 对应的 sim source-level contract 测试当前也已减重为以当前 public
  contract 为主，只保留少量关键旧词表回归断言，避免继续大面积固化历史过
  渡实现细节。
- `docs/plan.md` Phase 2 所要求的 simulation 包级拆出当前已通过仓库级完成
  合同；`sim_joint_bridge_cpp` 的最终包边界合并与统一消息合同仍属于本
  Phase 的后续仿真域收口，不因 Phase 2 拆包验收完成而提前标记完成。

动作：

1. 明确哪一部分保留 Python，哪一部分保留 C++。
2. 继续把仿真桥接节点、测试和 launch 开关归并到统一的 simulation 责任
   域。
3. 避免后续重新让 `websocket_bridge` 持有仿真主入口和整机仿真编排。

完成标准：

- 仿真链路可以独立启停。
- 仿真桥不再和 teleop 长期混在同一包边界下。

### Phase F：再处理正式命名

目标：

- 在边界稳定之后，再处理包名、接口名和目录收敛。

动作：

1. 评估 `parallel_3dof_controller -> motion_control` 的迁移。
2. 评估 `websocket_bridge -> teleoperation_bridge` 的迁移。
3. 继续收紧已落地的 `motion_msgs` 语义，逐步淘汰上层模块中保留的
   servo 风格过渡字段。
4. 继续扩展已落地的 `task_service_bridge`、`task_api_msgs`，更远期再评估
   `speech_interface`、`vision_perception` 的落地顺序。

完成标准：

- 包名与实际职责一致。
- 上层模块不再长期直接依赖驱动级消息。


## 5. 当前建议优先级

如果只按投入产出比排序，建议顺序如下：

1. `motion_msgs` 语义收紧
   - consumer 侧已不再依赖旧 `speed` 时长回退，仓库内置 producer 也已停止
     写入该镜像；公共字段已进入弃用迁移窗口并有自动化门禁。后续先冻结完整
     目标 schema、确认仓外依赖与切换策略，不在证据不足时直接破坏 ROS 接口。
2. 继续稳定正式任务链
   - `/task/execute -> /motion/execute -> execution_manager -> driver` 已跑通，
     后续重点是多任务类型、正式 `motion_control` 包边界、持久幂等、部署访问
     控制、目标硬件和 Jazzy 回归，不能把 fake driver 验收写成硬件完成。
3. `websocket_bridge` 剩余职责收紧
   - sim 收口与 BVH 可选扩展抽离已基本完成，下一步只继续压缩
     teleop/debug/status/IMU 上行的混合包边界。
4. 正式命名收敛
   - 只有在前面边界稳定后才值得做。


## 6. 需要持续遵守的约束

后续每个阶段都要反复检查以下红线：

1. 不把未实现模块写成已落地事实。
2. 不继续扩张 `websocket_bridge` 的职责。
3. 不把 `/servo/command` 直发当作新架构的长期方案。
4. 不让驱动层承接控制权仲裁。
5. 不在没有 profiling 结果前推动语言重写。
6. 某一块重构完成且旧目录、旧副本、旧入口已经无引用时，要及时删除，不长
   期保留废弃目录等待后续“顺手再清”。


## 7. 简短结论

长期规划文档仍然有效，但当前仓库离那套目标架构还有几步关键过渡工作。
因此更合理的做法不是去覆盖旧规划，而是补充一层“当前事实 + 近期执行顺序”
文档：先把边界整理清楚。当前整机主 launch 已从 `websocket_bridge` 拆到
`robot_bringup`，仿真域本轮也已基本完成 package-level 收口；BVH 已收口为
`record_load_action` 所有的显式 opt-in 扩展，默认 teleop/full-system 与
WebSocket schema 均不再启用或广告该能力。下一步更应围绕执行边界、
`motion_msgs` 最终命令 schema、正式任务链剩余部署/硬件语义和
`websocket_bridge` 剩余 teleop/debug/status/IMU 职责继续收紧，最后再做正
式命名和远期模块落地。
