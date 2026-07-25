# 重构推进说明

## 1. 文档角色

当前重构过程中，文档按四层使用：

1. 长期蓝本
   - `docs/plan.md`
   - `docs/module_responsibilities.md`
2. ROS 2 Control 专项长期设计
   - `docs/ros2_control_architecture.md`
   - `docs/ros2_control_migration_plan.md`
3. 当前事实与阶段进度
   - `docs/refactor_update_plan.md`
   - `docs/current_module_responsibilities.md`
4. 本文
   - 用来约束日常推进方式、判断优先级，并明确下一阶段应该先做什么。

约束：

- `docs/plan.md` 和 `docs/module_responsibilities.md` 是全局蓝本，不在日常推进中直接修改。
- 任何实现和提交，都要先回到这两份蓝本文档看“目标边界是什么”。
- 当前实际落地情况，只写入 `docs/refactor_update_plan.md` 和
  `docs/current_module_responsibilities.md`。
- ROS 2 Control 的目标分层、权限和迁移阶段只写入两份专项长期设计文档；
  未经当前事实、近期计划和编码规则审查，不进入运行代码实现。


## 2. 推进规则

每一轮推进都按下面顺序执行：

1. 先对照长期蓝本判断目标边界。
2. 再对照当前事实文档确认仓库真实状态。
3. 默认只选择一个可以独立验证、可以单独提交的小阶段；用户明确要求跨阶段进
   度时，每个切片仍必须分别形成实现与验收闭环。
4. 实现完成后，同步更新：
   - `docs/refactor_update_plan.md`
   - `docs/current_module_responsibilities.md`
5. 运行与该阶段直接相关的定向测试或构建。
6. 采用简短英文 commit message 做小阶段提交。

额外要求：

- 每次更新仓库内任一文档时（包括 `docs/` 与各包 README），都必须重新对照
  `docs/plan.md` 评估全局重构进度，并同步更新
  `docs/refactor_update_plan.md` 最上方的百分比进度条、阶段快照和评估日期；
  即使百分比不变，也必须确认当前证据仍然有效。
- 全局进度以 `docs/plan.md` 明确定义的 Phase 0–6 为固定分母，各阶段等权；
  单阶段只允许使用 `0% / 25% / 50% / 75% / 100%` 五档，算术平均后取最近
  的 `5%`，避免使用无法由完成标准支撑的伪精确数字。
- 进度评估必须以已落地实现、自动化验证、构建或场景验收证据为依据。单纯修
  改说明文字不增加进度；未运行的 build / launch、未确认的仓外依赖和未通过
  的 breaking-change 门禁不得计为完成。
- 证据失效、验收回退或长期范围扩大时，进度允许下降，不能只增不减；如果
  `docs/plan.md` 增删正式 Phase，必须说明重新设定分母的原因并重新计算全部
  阶段，不能继续沿用旧百分比。
- `docs/refactor_update_plan.md` 自身的 Phase A–F 只用于近期执行排序，不得替
  代 `docs/plan.md` Phase 0–6 作为全局进度分母。
- 不为了“形式统一”一次性迁移全部职责域。
- 不把过渡兼容代码写成长期架构事实。
- 不把 demo、调试、仿真临时链路重新混回正式主链路。
- 某一块重构完成且旧目录、旧副本、旧入口已经无引用时，应及时删除，不长
  期保留“等以后再清理”的废弃目录；目录级清理应作为对应重构阶段的收尾动
  作，而不是无限后延。

### ROS 2 Control 专项工作流

转向 ROS 2 Control 时，必须按下列顺序推进：

1. 先在 `ros2_control_architecture.md` 冻结分层、职责、权限、接口、
   安全与实时性红线。
2. 再在 `ros2_control_migration_plan.md` 冻结总体阶段、依赖、验收和回滚。
3. 然后建立当前事实、近期更新计划和编码规则三份专项实施文档。
4. 仅在上述文档通过审查后，选择一个可独立验证的小切片实现。

专项文档只描述其归属层：长期设计不写成当前实现，当前事实不提前宣称目标
架构已接线，近期计划不替代全局 Phase 0–6 计分。


## 3. 当前阶段判断

截至 2026-07-24，当前重构已经完成的关键基础包括：

- `robot_bringup` 已承接整机主入口，并拆出 hardware / teleop / task /
  simulation / context 五个子域；context 域通过 `enable_context` 显式启用，
  speech 与 perception owner 也可在独立 launch 中分别启停。
- `robot_bringup` 场景化 launch 当前也已开始复用 `launch_utils` 统一解析总线
  协议缓存默认路径，不再在子场景入口里硬编码旧的 `websocket` 源码树绝对路径。
- `robot_bringup` 当前已增加 `docs/plan.md` Phase 2 仓库级完成合同，以 AST、
  XML 和 JSON 结构化验证 WebSocket/simulation 包级分离、独立
  `sensor_hardware` 所有权、BVH 默认 opt-in 依赖方向，以及
  `full_system` 对 hardware / teleop / task / simulation 四个子 launch 的真实
  组合；这是 Phase 2 原始拆包验收基线。当前 source contract 已随 Phase 5
  继续固定 context 为第五个 include，但不把新增上下文能力倒计为 Phase 2
  完成证据；
  Phase 2 聚合合同 5 项、BVH 预处理回归 6 项、既有相关边界 27 项，共
  38 项直接证据通过。
- Phase 2 收尾同时修复了三个仓库级用户入口残留：`preprocess_bvh.py` 不再
  指向 WebSocket 的旧 BVH 配置，会相对配置文件目录解析 `bvh_dir`，并已对齐
  正式播放器的嵌套 target、`joint_alias`、踝关节轴映射、舵机限位和正反向
  语义；随仓 5 个动作均可离线生成 250 帧，生成结果与正式静态转换器逐帧
  一致。根 README 不再启动已删除的 `isaac_bridge_node`；
  `sim_bridge_co_test.sh` 不再向 full-system 传递已删除的实现级开关，只使用
  `enable_simulation`。
- 基于上述实现与自动化证据，`docs/plan.md` Phase 2 已从 `75%` 调整为
  `100%`：全局原始进度由 `39.3%` 提升到 `42.9%`，按最近 `5%` 展示由
  `40%` 提升到 `45%`，实际推进约 `3.6` 个百分点。该完成状态只覆盖 Phase 2
  拆包目标，不代表 Phase 1 的 colcon/launch 验收、WebSocket 剩余职责拆分或
  `sim_joint_bridge_cpp` 最终合并已经完成。
- Phase 2 调分当轮的 source-level 定向回归按 `robot_bringup` 15 项、
  `record_load_action` 58 项、simulation/WebSocket 定向合同 15 项分组，共
  88 项通过。前述 38 项是独立归档的 Phase 2 直接证据集，与 88 项定向回归
  中的 32 项重叠；两组分别用于调分审计与较宽回归，不能相加。当轮宿主环境
  未提供 `colcon`、`ros2` 与 Docker Compose，因此没有把 ROS 构建、安装后
  entry point、launch 启动或容器联测计入 Phase 2 完成证据。
- Phase 1 的物理目录迁移当前覆盖全部 20 个 ROS 包：既有公共接口位于
  `src/interfaces/`，控制、执行、桥接、bringup、语音、感知、描述与工具包
  分别位于 `src/control/`、`src/execution/`、`src/bridges/`、
  `src/bringup/`、`src/speech/`、`src/perception/`、`src/description/` 和
  `src/tools/`；新增 `robot_hardware` 位于独立的 `src/hardware/` ROS 2
  Control 硬件域。ROS 包名、接口定义与公共业务语义均未随物理路径改变。
- 全仓目录合同固定全部 20 个包的当前职责域位置、manifest 包名不变、包名唯一
  且发现集合完整；新增合同项明确 `robot_hardware` 属于独立 `hardware` 域。
  初始化脚本、Docker Compose、BVH 工具、配置 fallback、仓库级源码合同和事实
  文档中的物理路径已同步更新，ROS 包名、Python import、entry point、Topic、
  Service、Action 与公共业务语义保持不变。
- 本轮在新的 `/private/tmp/robot-runtime-phase1-all-20260724` 隔离工作区，以
  `src` 为唯一 base path 完成全部 20 个 ROS 包的 clean build，用时约
  `5min42s`；build / install / log 均使用新目录，未复用上一轮 install。source
  本轮 install 后，`robot_bringup` 的 `full_system.launch.py`、`task.launch.py`、
  `context.launch.py`，以及 `mjc_viewer/mjc_viewer.launch.py`、
  `robot_description/display.launch.py`、
  `record_load_action/bvh_websocket_demo.launch.py` 共 6 个安装后 launch 的
  `--show-args` 均解析成功。该结果补齐了此前 16 包主运行闭包未覆盖
  `record_load_action`、`robot_description` 和 `mjc_viewer` 的证据缺口；它不
  等于 `robot_hardware` 已接入正式运行链。
- 定向回归通过：motion 接口 25 项、bringup 35 项、controller 41 项、speech
  16 项、perception 14 项、simulation 3 项、execution 32 项、task bridge 28
  项、驱动安全 11 项和 BVH 路径/转换 6 项；task bridge 包含三类真实
  Action/DDS smoke。因此 Phase 1 的 `100%` 现由全 20 包构建、安装后 6 个
  launch 解析和既有 DDS / 定向回归共同支撑。该完成状态只覆盖
  `docs/plan.md` 固定的目录重组、构建和 launch 标准，不代表历史 ROS 包名已
  全部重命名，也不替代 Phase 3 schema、目标 Jazzy 或硬件发布验收。
- `execution_manager` 已建立最小执行边界，teleop 与 motion 已不再都直接碰驱动层。
- `sensor_hardware` 已独立成 ROS 包。
- teleop 控制权链已落地显式 claim / keepalive / release。
- teleop `MotionCommand` 已收紧为显式 requester / lease 约束。
- `parallel_3dof_controller` 已更明确地以 `duration_ms` /
  `value_encoding` 表达 `MotionCommand` 语义；求解器输出当前只保留
  `duration_ms` 时长字段，控制器只读取该显式时长并发布，不再回退或镜像旧
  `speed` 字段；公共字段已进入弃用迁移窗口，该包内旧词表仅保留在
  `speed` / `default_speed` 参数名中。
- `websocket_bridge` 当前也已开始把 `servo_control` 输入标准化为
  `value_encoding` / `duration_ms` 优先的 motion 语义；bus 目标值会在桥接
  前归一到 pulse us。WebSocket payload 与规范化 ack 仍保留兼容 `speed`，但
  默认 teleop producer 发布 `MotionCommand` 时已不再写入该镜像；这组外部
  协议字段与已弃用的 ROS 公共消息字段是两个独立合同。
- `execution_manager` 当前也已继续收紧 `MotionCommand` consumer 侧时长解
  析：内部 setpoint 时长只来自显式正值 `duration_ms`，不再从旧
  `speed` 回退推导；adapter 测试也不再伪造该旧字段输入。
- `execution_manager` 当前也已把内部仲裁器从命令载荷细节中进一步解耦；
  `CommandArbitrator` 现在只按来源、时间以及 task/teleop 身份与 lease 做仲
  裁，不再要求一层伪 `CommandFrame` 中间快照。
- `motion_msgs` 当前已新增中性执行器反馈 `ActuatorState`，使用
  `actuator_type` / `actuator_id` / `position_raw` / `value_encoding`，并提
  供 `status` / `reason` / `recoverable` 和原始 `driver_error_code`。执行层
  会订阅驱动级 `/servo/state`，经独立 `feedback_adapter` 转换后向上发布
  `/execution/actuator_state`。
- `websocket_bridge` 已改为只消费 `motion_msgs/ActuatorState`，不再导入
  `ServoState`、不再直订阅 `/servo/state`，`package.xml` 也已移除
  `servo_msgs`；既有 WebSocket `servo_type` / `servo_id` / `position` /
  `angle` / `pulse` 状态字段保持兼容。至此现有上层 producer/bridge 的运行
  依赖均收口到 `motion_msgs`，`servo_msgs` 只留在执行、驱动和 simulation
  兼容边界。
- Phase 3 新增 6 项仓库级双向边界合同、6 项反馈适配测试和 1 项 WebSocket
  payload 兼容测试，均已通过。本次 Phase 3 验收在一次性 ROS 2 Humble
  容器完成核心 5 包（`motion_msgs`、`servo_msgs`、`execution_manager`、
  `parallel_3dof_controller`、`websocket_bridge`）与 `robot_bringup` 完整依
  赖闭包 10 包隔离构建；`colcon test-result` 汇总 36 项零失败，其中包括
  34 个 Python 用例和 2 个 `ament_cmake_pytest` / CTest 注册项。此外，
  `ros2 interface show`、launch 参数解析、
  teleop/full-system `--show-args`、8 秒 teleop 启动冒烟和真实
  `ServoState → ActuatorState`、`MotionCommand → ServoCommand` pub/sub
  验收。该证据证明当前接口在 Humble 可生成和运行；仓库目标 Jazzy 的发布前
  回归仍需在对应镜像或目标环境补充，不能由本次跨发行版结构验收替代。
- 基于上述双向执行边界与 ROS 验收，`docs/plan.md` Phase 3 已从 `50%` 提升
  到 `75%`：全局原始进度由 `42.9%` 提升到 `46.4%`，实际推进约 `3.6` 个百
  分点。按最近 `5%` 展示仍为 `45%`，因此顶部进度条保持 9/20 格，不能误写
  为 `50%`。Phase 3 尚未达到 `100%`，因为 `MotionCommand` 最终中性 schema
  与 breaking 切换门禁仍未完成；`speech_msgs`、`perception_msgs` 后续随真实
  owner 落地，不改变该最终命令 schema 阻塞。
- `motion_msgs` 当前新增内部 task admission 接口
  `TaskExecutionControl` / `TaskExecutionState`。前者用
  `task_id` / `trace_id` / `session_id` 和 execution lease 表达
  start / keepalive / finish / cancel；后者发布 active、剩余租约、
  `status` / `reason` / `recoverable`、控制/命令计数，以及最近一条 task
  `MotionCommand` 的 requester、接受结果和稳定 reason。finish、cancel、
  timeout、estop 终态会立即清空 lease，但保留最近一次成功准入的完整
  task/trace/session 身份，便于上层关联终态。两个新类型没有修改既有
  `MotionCommand` / `ExecutionState` 字段布局，也不是外部 `task_api_msgs`。
- `execution_manager` 当前通过 `/execution/task/control`、
  `/execution/task/command`、`/execution/task/state` 建立第一版正式 task 内
  部准入边界，并增加 `task_active` / `active_source=task`。task 活跃时只接
  受 requester 等于当前 `task_id` 且 lease 匹配的 task topic 命令；新的
  teleop claim、普通 motion 和 requester 为空的 BVH/demo 均会被执行层拒
  绝。正式 task start 会撤销普通 teleop lease 与被抢占的旧 motion 活跃窗
  口；finish/cancel/timeout 会撤销 task 准入；estop 会同时清理 task 与
  teleop lease，解除后仍保留 `blocked/estop` 终态，不能让旧 lease 自动恢
  复。执行层还会保留最近 256 个终态身份 tombstone，拒绝延迟 start 重放；
  该保护只存在于当前进程内，节点重启后的持久幂等仍由未来外部任务入口承接。
- BVH 可选扩展会在 `task_active` 时先本地阻断并返回稳定
  `bvh_blocked_by_active_task`，但执行层仍保留最终裁决。WebSocket 核心只从
  既有 `ExecutionState.mode/active_source` 派生 task 活跃状态，不发布
  `TaskExecutionControl`，也没有新增 WebSocket 正式任务请求。
- Phase 4A 新增 12 项 task 仲裁单元测试、7 项仓库级入口边界合同、1 项 BVH
  task 联锁和 2 项 WebSocket task 状态回归，共 22 项 source-level 直接证
  据；另有 1 项由 pytest/colcon 自动发现的真实 ROS pub/sub smoke。ARM64
  ROS 2 Humble 容器在禁网、仓库只读、`/tmp` 隔离条件下完成
  `robot_bringup` 10 包依赖闭包及额外 `record_load_action` 构建，共 11 包；
  `motion_msgs` / `execution_manager` / `robot_bringup` 的
  `colcon test-result` 汇总 72 项零失败，其中 69 个 Python/pytest 用例、3
  个 `ament_cmake_pytest` / CTest 注册项。两条新消息的
  `ros2 interface show` 和 execution/teleop/full-system launch 参数解析均
  通过。
- 自动 ROS smoke 使用同一进程内两个真实 ROS 节点和 DDS pub/sub，确认错误
  task lease 会进入 `TaskExecutionState.last_command_reason`，task 窗口会拒
  绝普通 motion 与 teleop，匹配 lease 的 task 命令会生成
  `ServoCommand`；finish/cancel/timeout/estop 分别形成可关联终态，解除
  estop 后仍保留 blocked 结果，延迟 start 被拒绝为
  `task_control_replay`，finish 后普通 motion 恢复。该场景未启动真实硬件，
  也不是 `/task/execute` Action 测试。
- 更宽的 `websocket_bridge` 包级 colcon 基线仍有 2 个既有
  flake8/pep257 失败（同时为 132 passed、30 skipped），因此没有混入本轮
  72 项零失败集合；本轮直接受影响的 WebSocket task 映射与状态查询定向回
  归均已通过。上述 Humble ARM64 证据仍不能替代目标 Jazzy 发布回归。
- Phase 4A 调分当时，基于上述 task-aware execution admission、跨入口优先级
  与 ROS 验收，
  `docs/plan.md` Phase 4 已从 `25%` 提升到 `50%`。全局原始进度由 `46.4%`
  提升到 `50.0%`，实际推进约 `3.6` 个百分点；按最近 `5%` 展示由 `45%`
  提升到 `50%`，顶部进度条相应调整为 10/20 格。Phase 4 尚未达到
  `75% / 100%`，因为 `task_api_msgs`、`task_service_bridge`、
  `/task/execute`、motion goal/result 与真实任务取消/完成反馈仍未落地；当
  前 `cancel` 只撤销后续命令准入，不等同于驱动级在途停止。
- Phase 4B 已落地 `task_api_msgs/ExecuteTask`、
  `motion_msgs/ExecuteMotion`、实际位置读取和停止请求接口；
  `task_service_bridge` 是唯一 `/task/execute` ActionServer，只映射到
  `/motion/execute`，不依赖驱动消息，也不会把 goal accepted 冒充完成。
- 当前 `parallel_3dof_controller` 作为 motion owner，完整执行 task lease
  start/keepalive/finish/cancel，携带 lease 进入 `/execution/task/command`，
  并只以 execution_manager 转发的驱动级实际位置新采样判断完成。三执行器必
  须连续三个样本进入目标容差；取消必须经过 stop 请求、连续稳定位置确认、
  task cancel 和终态 lease 清理后才返回结果。
- `execution_manager` 新增受完整 task/trace/session/lease 保护的
  `/execution/read_actuator_position` 与 `/execution/stop_actuators`，独占
  motion-level 到 driver-level 适配；stop service 只报告命令写出，
  `stop_confirmed` 仍由 motion owner 的后续采样确认。
- `TaskExecutionState` 当前也会为最近一次控制请求报告完整
  task/trace/session 身份；motion owner 只有在已收到 execution task state
  且 task-control DDS 订阅已发现后才接受 goal。multi-instance 控制器固定关
  闭正式 ActionServer，`/motion/execute` 仍只有一个 owner。
- execution manager 为每个已接受的 stop 建立单调 operation token；token 未
  完成时拒绝所有新执行命令和 task start，避免调用方超时后的旧 stop 干扰新
  任务。estop 会直接对已接受命令或驱动状态中见过的 bus ID 写出协议 stop；
  stop 未完整写出或驱动服务超过 manager 级超时会锁存
  `driver_stop_failed` / `driver_stop_timeout`、保持 estop 和 stop token，不能
  通过迟到响应或普通 estop release 自动恢复。
- stop 批处理当前按执行器 best-effort：单个 ID 的协议读取或 stop 写出超时只
  记入聚合故障，不会跳过其余 ID。`execution_manager` 同时以 transient-local
  的 `/servo/driver_safety` 发布权威 `DriverSafetyState`；协议 router 与端口驱
  动均在 stop 写出前建立本地 fence，急停期间拒绝新 move，解除后仍拒绝时间戳
  早于 fence 的迟到 topic/service move。正常 release 必须经
  `/servo/set_driver_safety` 聚合全部有效 port driver 的应用 ACK；ACK 返回前
  持续保留 stop token 与 estop，release 失败或超时会保持二者并锁存故障；故
  障锁存时普通 estop release 不会发布驱动级 release。
- `src/bringup/robot_bringup/launch/task.launch.py` 当前组合 execution manager、motion owner
  和 task bridge，`full_system` 会关闭 teleop 子栈内的重复 execution owner。
  Phase 4B/C 在 ARM64 ROS 2 Humble 的禁网、只读、`/tmp` 隔离容器完成 12 包
  闭包构建；八个目标包的功能 xUnit 汇总 158 项零失败，另有未被包注册器发现
  的 `parallel_3dof_controller` 定向测试 26 项通过。`DriverSafetyState`、
  `SetDriverSafety`、带命令时间戳的 `ExecuteBusCommand` 及既有 task/motion 接
  口均完成生成，task、hardware、full-system launch 参数解析及独立
  Action/DDS smoke 均通过。smoke 的 fake driver 会渐进逼近目标，
  成功链产生 11 条 feedback、连续三个目标样本后完成；取消链实际收到三个协
  议 stop，并以连续四个冻结位置样本确认停止。扩展场景还确认延迟 stop 期间
  新 task 无命令逸出且完成后恢复、estop 对三个执行器直接 stop、三条 stop 前
  迟到 move 与 active 期间新 move 均被驱动 fence 拒绝、全部端口 release ACK
  后恢复，
  以及首个执行器 stop 超时后其余两个 ID 仍收到协议 stop，最终继续锁存故障并
  阻断新 task。完整 smoke 用时 `8.5329s`。`servo_hardware` 功能测试为 31 项
  通过；包级历史 flake8/pep257 基线未计入零失败集合。该证据不是物理硬件验
  收，Humble 也不替代目标 Jazzy 发布回归。
- 对照 `docs/plan.md` 的原始 Phase 4 完成标准，唯一正式桥、统一执行边界、差
  异化默认优先级及上述安全闭环均已有实现和自动化证据，因此 Phase 4 从 `75%`
  提升到 `100%`。全局原始进度由 `53.6%` 提升到 `57.1%`，实际推进约 `3.6`
  个百分点；按最近 `5%` 展示仍为 `55%`，顶部进度条保持 11/20 格。当前只支
  持 `ankle_pose`、正式 `motion_control` 包边界、motion owner 可消费的完整
  scene/task context、部署 ACL、跨进程持久幂等、目标硬件和 Jazzy 回归仍是
  发布加固或后续演进事项，但不再扩张为 Phase 4 蓝本完成门禁。
- Phase 5 已落地两个非空上下文垂直切片。`speech_msgs/SpeechIntent` 与
  `speech_interface` 将严格校验后的边缘 JSON 意图发布到 `/speech/intent`，
  并只通过唯一 `/task/execute` Action 发起当前真实 `ankle_pose` 任务；低置
  信、非法字段、Action 拒绝和最终结果均会发布稳定的
  `status/reason/recoverable`。`perception_msgs/DetectedObject` /
  `SceneState` 与 `vision_perception` 将检测 JSON 校验后发布到
  `/perception/scene_state`，重复对象 ID、未知字段、非有限坐标、越界置信
  度和负尺寸会形成结构化拒绝状态。
- `task_api_msgs` 已新增 `TaskContextSignal`；`task_service_bridge` 会订阅结
  构化 speech intent 与 scene state，并统一发布 `/task/context_signal`。该
  context adapter 不发布 `MotionCommand`、`ServoCommand` 或
  `TaskExecutionControl`，也不改变 `/task/execute -> /motion/execute` 的唯一
  正式 Action 链。`src/bringup/robot_bringup/launch/context.launch.py` 提供独立装配，
  `full_system` 已把 context 作为第五个可选运行域。
- Phase 5 隔离验收在禁网、源码只读的 ARM64 ROS 2 Humble 容器完成 16 包依
  赖闭包构建；八个直接相关包共 `119` 项测试零失败。`SpeechIntent`、
  `SceneState`、`TaskContextSignal` 完成接口生成，context/task/full-system
  launch 参数解析通过。独立真实 Action/DDS smoke 用时 `0.5387s`，覆盖语音
  意图到 fake motion 成功结果、感知场景到 task context，以及低置信语音与
  重复对象 ID 的拒绝链。
- 该 Humble 证据覆盖核心垂直切片。随后补齐了拒绝链身份保留、感知 `float32`
  范围和 JSON 资源上限，以及 `enable_context=false` 同时关闭 task bridge
  上下文订阅/发布的边界；本轮已在同一类禁网、源码只读 ARM64 Humble 容器重新
  构建 16 包，并对 `parallel_3dof_controller`、`task_service_bridge`、
  `robot_bringup` 汇总 59 项测试零失败。
- 当前 motion owner 已新增可选 `SceneAdmissionGate`。context 启用时它直接订
  阅完整 `/perception/scene_state`，仅保护正式 `/motion/execute` task 路径：
  Action 已接受后、申请 task lease 前首次 fail-closed 检查 `status=ok`、场景接
  收年龄、非空 observation ID、完整 session 和 observation replay；不可变快照
  同时保留 frame 与完整对象集合，并以 `SceneGeometryPolicy` 校验 frame、对象
  ID 唯一性、`target_group` 对应的唯一目标标签、置信度、正尺寸和 AABB 安全包
  络。取得 lease 后、首条 task `MotionCommand` 前再持锁复用同一身份与几何策
  略，并原子提交整批三执行器命令，场景更新不能插入该批命令。
- 缺失、rejected、空 observation、stale、session mismatch 及不安全几何在
  lease 前返回稳定、可恢复 Result，且不产生 task control、task motion 或 servo
  命令；若场景在 lease 等待中失效，则同 task/trace/session 的
  `start -> cancel` 会释放已取得的非空 lease，仍无 task motion 或 servo 命令。
  本机 ROS 2 Humble Action/DDS smoke 用时 `3.0229s`，fresh 场景由真实
  controller、execution manager 与 fake driver 完成三个执行器目标。遗留
  `~/ankle_rpy` 调试输入不属于这条正式 task 场景准入边界。
- 本轮在本机 macOS ARM64 ROS 2 Humble 环境以 `/private/tmp` 独立 build/install
  目录完成 16 包依赖闭包构建，并 source 该 install 重跑真实 scene smoke。该
  环境需显式固定 micromamba Python 3.12/NumPy、启用 CMP0148 兼容策略，并把
  ROS 前缀的 `libatomic` 加入 module/shared/executable linker 搜索路径；这是
  本机 CMake 4.3 自动选择 Homebrew Python 3.14 和 ROS 前缀链接设置造成的环境
  适配，不是接口源码变更或发布就绪结论。
- 本轮全新 16 包 clean build 后 source 新 install，scene admission 的真实
  owner Action/DDS smoke 2 项约 `4.23s` 通过；task bridge 全套 28 项在
  `9.752s` 内通过。测试覆盖 frame、对象身份、目标选择、置信度、非有限几何、
  尺寸和安全包络拒绝，lease-race 保持同身份 `start -> cancel` 并释放非空
  lease，fresh 安全场景仍完成三个执行器目标。
- 基于两个结构化接口包、两个 producer owner、task bridge consumer、独立
  bringup，以及当前 motion owner 对 `DetectedObject` frame、标签、置信度与
  AABB 的实际消费，`docs/plan.md` Phase 5 从 `75%` 提升到 `100%`。lease 前
  与 lease 后原子准入复用同一几何策略，已满足固定蓝本完成标准。真实 ASR/TTS、
  相机硬件/检测模型、更多任务规划、目标 Jazzy、部署 ACL 和真实硬件停止验收
  仍是发布加固或后续能力，不再扩张为 Phase 5 固定蓝本分母门禁。
- 为落实 Phase 6 的“按 profiling 结果”前置条件，新增
  `scripts/profile_runtime_hotpaths.py`，以 PID 隔离的真实 rclpy/DDS 顺序闭环
  测量 execution manager、当前 motion owner 和 simulation bridge。ARM64
  Humble 16 包 clean build 后三条路径各采集 200 个计量样本和 20 个 warmup，
  均零超时：execution p50/p95/p99 为 16.55/43.75/57.16ms，motion 为
  24.06/50.12/70.13ms，simulation 为 13.99/33.03/45.51ms；详细环境、统计
  口径、尾延迟与 CPU 限制记录在 `docs/runtime_profiling_baseline.md`。
- 本轮先修正 profiling 基线：`parallel_3dof_params.yaml` 改用 ROS wildcard
  节点选择器，避免 launch 将节点重命名为 `parallel_3dof_controller` 后几何
  参数失效；solver 测试的默认舵机 ID 期望也已与正式配置统一为右侧 `9–11`、
  左侧 `12–14`。脚本新增显式 `--motion-l0/l1/l2` 参数和 solver 分段计时，
  本机 Humble 五轮、每轮 200 样本和 20 warmup 均零超时；motion 端到端五轮
  平均 p50/p95/p99 为 `1.51/2.56/3.93ms`，solver 分段为
  `0.260/0.564/0.896ms`，p50 占端到端约 `17.2%`。这只收紧热点证据，不改变
  Phase 6 `25%`。
- 基于三域实际运行基线和热点排序，Phase 6 从 `0%` 提升到 `25%`；尚未有
  同接口 C++ 后端、launch 单值切换、Python/C++ 对比或硬件/仿真回归，不能计
  为 `50%`。Phase 5 与 Phase 6 各提升一档后，全局原始进度由 `64.3%` 提升到
  `71.4%`，实际推进约 `7.1` 个百分点；按最近 `5%` 展示由 `65%` 提升到
  `70%`，顶部进度条更新为 14/20 格。本轮推进超过用户要求的 `4` 个百分点。
- 本轮 Phase 1 与 Phase 5 各提升一档，阶段快照为
  `100 / 50 / 100 / 75 / 100 / 100 / 25`。阶段总和 `550`，除以 7 后全局
  原始进度由 `71.4%` 提升到 `78.6%`，实际推进约 `7.1` 个百分点；按最近
  `5%` 展示为 `80%`，进度条为 16/20 格，超过至少推进 `4` 个百分点的要求。
- 本次继续完成 Phase 1 剩余两档，阶段快照为
  `100 / 100 / 100 / 75 / 100 / 100 / 25`。阶段总和 `600`，除以 7 后全局
  原始进度由 `78.6%` 提升到 `85.7%`，实际推进约 `7.1` 个百分点；按最近
  `5%` 展示为 `85%`，进度条为 17/20 格，超过至少推进 `4` 个百分点的要求。
- 此前补齐的 Phase 1 19 包 clean build 与 6 个安装后 launch 解析证据，现已由
  2026-07-24 的 20 包 clean build 复核；两次工作均只确认既有 `100%` 档位仍然
  有效，不重复计分。当前阶段总和仍为 `600`，原始均值仍为 `85.7%`，按最近
  `5%` 展示仍为 `85%`。
- 本轮全局复核后，只有 Phase 3 和 Phase 6 尚未封顶；单阶段提升一档只增加
  `25 / 7 = 3.57` 个原始百分点，严格满足“至少推进 4%”必须同时完成
  Phase 3 `75% -> 100%` 与 Phase 6 `25% -> 50%`。Phase 3 仍需项目所有者冻结
  最终中性 schema、canonical topic、旧 subscriber 兼容和版本策略；Phase 6
  仍需目标 Jazzy、同接口 C++ 后端、Python/C++ 差分、launch 单值切换以及仿真
  和物理硬件回归。上述门禁未形成证据前，不能通过重复计分或修改分母虚增进度。
- BVH/demo capability 的动作输出已改走 `/execution/motion/command`，不再复
  用 teleop 命令入口。
- BVH 配置所有权当前也已完全收回 `record_load_action`，运行时不再继续把
  `websocket_bridge` 当成 `bvh_action_map.json` 的兜底来源。
- BVH 的运行说明当前也已继续收回
  `src/tools/record_load_action/README.md`；
  `src/bridges/teleoperation_bridge/config/README.md` 只保留指向说明。
- `robot_bringup` 与 `websocket_bridge` 当前也已不再继续把
  `bvh_action_file` 作为 public launch/参数入口上抬；默认解析路径完全收
  回 `record_load_action`。
- BVH 触发入口当前也已收紧为显式 `bvh_play` 消息；旧的泛化 `action` 别
  名，以及经由直发舵机/private 路径隐式转 BVH 的历史入口都已清掉。
- `bvh_play` payload 当前也已继续收紧为显式直接字段；旧的 `action.bvh`
  嵌套 payload 与顶层 `bvh` 历史别名都已不再继续作为当前事实保留。
- `record_load_action` 当前也已提供传输层无关的
  `bvh_request.normalize_bvh_play_request`，统一承接显式直接字段的规范化与
  基础结构校验；`bvh_player` 只保留兼容导入出口。
- `record_load_action` 当前也已提供 `BvhWebSocketPlaybackAdapter`，由它承
  接 `bvh_play` 请求规范化、accepted ack payload 生成、WebSocket-facing
  runtime 装配，以及播放、阻断与关闭操作的原子串行化。
- 通用 `MessageHandler` 当前也已移除 `BVH_PLAY` 枚举和
  `parse_bvh_action`；`WebSocketHandler` 会优先按已注册的未知显式 `type`
  分发扩展，不再内建 BVH 协议知识。
- `websocket_bridge` 核心当前只提供通用 `extension_factories` 动态装配面，
  默认不加载任何扩展；其源码与包清单均不再直接依赖
  `record_load_action`，也不再持有 BVH topic、publisher、注册、错误映射或
  execution-state 联锁。
- `record_load_action` 当前已提供 `BvhWebSocketExtension`，由它持有
  `/execution/motion/command` publisher、注册显式 `bvh_play`、映射既有 ack
  与错误类别，并将 execution state 原子提交到播放门禁。
- `BvhWebSocketExtension` 当前也已只把回调提供的执行时长写入显式
  `duration_ms`，不再镜像旧 `MotionCommand.speed`；请求级 `speed_ms` 合同与
  播放器内部 timing 行为保持不变。
- `MotionCommand.speed` 当前已明确标记为弃用，仅在公共消息迁移窗口内保
  留；仓库级源码门禁会同时禁止内置 producer / consumer 重新读写该字段，并
  保护 WebSocket、BVH 和驱动层的不同 `speed` 合同。
- `docs/motion_command_speed_migration.md` 已记录删除字段前的仓外依赖、旧
  rosbag、目标 schema、版本策略、clean rebuild 与同步重启门禁。当前未取得
  这些外部事实，因此本轮不修改 ROS 公共消息布局。
- `src/tools/record_load_action/launch/bvh_websocket_demo.launch.py` 是当前显式 opt-in 入口；
  默认 `robot_bringup` teleop/full-system 与默认 WebSocket schema 均不再装
  配或广告 BVH。
- `BvhPlaybackRuntime` 继续创建并持有 `BvhActionPlayer`；进入 blocked 时先
  阻断新播放再停止当前播放，节点关闭时进入 closed/blocked 终态。显式停止
  在 blocked/closed 状态下仍可执行，停止或关闭失败仍可按既有策略重试。
- blocked 状态下若停止尚未完成，后续同状态 `set_blocked(True)` 会继续重
  试；adapter 自身的原子门禁保证播放请求只能在 execution-state 阻断提交完
  成后进入，并为拒绝保留同一状态快照。核心扩展宿主对 close 最多额外重试
  一次，然后继续清理其余 WebSocket 资源。
- `BvhActionPlayer` 当前为每代 worker 使用独立 `Event`，并以 bool
  `play()` / `stop()` 报告操作结果；只有确认上一代退出后才会启动下一代，
  超时后仍存活的 worker 会保留句柄并拒绝替代线程。
- `/execution/motion/command` topic、播放 timing 字段透传和 teleop 联锁语义
  保持不变；但当 player 明确返回 `False` 时，现在会通过既有
  `ROS_CALLBACK_FAILED` 类别显式失败，而不是沿用旧 player 未暴露该结果时
  的隐式成功路径，这是本轮的安全性收紧。
- 仿真域 package-level launch contract、默认参数归属与 bringup public
  surface 在本轮也已基本收口完成；当前剩余更多是最终包边界合并与必要维
  护，而不再是主推进阻塞项。
- 对应的 sim source-level contract 测试当前也已减重为以当前 public
  contract 为主，只保留少量关键旧词表回归断言。

这意味着：

- 当前不应再回头修改长期蓝本。
- 当前重点不再是“是否需要 execution 边界”，而是继续把剩余混杂责任域逐个收口。


## 4. 当前优先级

下一优先级定义为：

**结构化上下文后端加固与正式任务演进**

原因：

- speech/perception 的结构化接口、producer、task context adapter 与 bringup
  已落地，但当前 JSON 只代表边缘 backend 合同，不代表真实 ASR/TTS、相机或
  检测模型已经完成。
- 正式 task/motion Action、反馈、取消和 stop 确认已经落地，context 启用时
  `SceneState` 已进入 motion owner 的身份、新鲜度和对象级几何准入；当前只
  实现 `ankle_pose`，尚无轨迹规划或多任务场景决策。
- 三域 DDS profiling 已有第一版热点排序，但 execution tail latency 的单次
  异常、Python/DDS/NumPy 成本归因和目标 Jazzy/硬件数据尚未完成，不能据此直
  接启动 C++ 重写。
- `parallel_3dof_controller` 当前是经过验证的 motion owner，且已位于
  `src/control/parallel_3dof_controller`；但 ROS 包名尚未收口成正式
  `motion_control`，后续命名迁移必须保持现有 Action 合同不变。
- task bridge 的进程内单目标策略与 execution tombstone 已能覆盖当前运行时，
  但部署级唯一入口、ROS ACL 和跨节点重启的持久幂等仍未完成。
- fake driver 已证明控制图和停止状态机，不代表多协议真实硬件已经完成停止验
  收；目标 Jazzy 发布回归也不能由 Humble 结果替代。


## 5. 下一阶段建议范围

下一阶段建议范围控制在：

- 在保持当前结构化消息和稳定拒绝 reason 的前提下接入真实 ASR/NLU、TTS 与
  相机/检测 backend；设备或模型验收必须单独记录，不能复用 JSON smoke 结
  论。
- 在不放宽现有 scene gate 的 session、新鲜度、replay、frame、置信度和 AABB
  门禁前提下，将真实检测 backend 或更高层规划场景接入同一正式
  task/motion/execution 边界；禁止 perception 直接发布执行或驱动命令。
- 在目标 Jazzy、目标硬件或等价仿真环境中重复三域 profiling，并用 tracing 拆
  分 publish、callback、求解、状态发布与 DDS 时间；确认稳定热点前不迁移 C++。
- 在不修改现有 Action 身份与停止字段的前提下增加下一种真实任务类型，并为
  每种类型提供实际 owner、完成反馈和取消清理证据。
- 评估 `parallel_3dof_controller -> motion_control` 的包边界收口，避免为命名
  迁移复制 ActionServer 或引入第二条正式执行路径。
- 增加部署级唯一 `/task/execute` 约束、ROS ACL 与跨进程持久幂等设计；未落
  地前继续明确其不属于当前完成证据。
- 在目标硬件验证 LX/ZL stop、位置冻结和故障恢复，并补充目标 Jazzy clean
  build、launch 与 Action 回归；不能复用 fake driver/Humble 结论。
- `MotionCommand` 最终 schema 继续按
  `docs/motion_command_speed_migration.md` 盘点仓外 publisher/subscriber、旧
  rosbag、生成绑定与部署镜像；门禁全部通过前不删除或重排公共字段。
- `websocket_bridge` 后续只继续处理 teleop / debug / status 的剩余混杂，
  不重新把 BVH capability、配置或样例放回默认核心。
- 仿真域后续只保留必要维护，不再把内部实现细节重新上抬到
  `robot_bringup` 或 package-level public surface。

当前进度补充：

- `speech_interface` 与 `vision_perception` 已分别形成严格 JSON 边缘适配
  器，结构化输出经 `task_service_bridge` 汇入 `/task/context_signal`；
  `robot_bringup` 已以独立 context 域装配两条链路。
- context 链已在 Humble 隔离环境完成接口生成、16 包构建、119 项初始回归与
  重新构建后的 59 项受影响包测试。本机 source 独立 install 后也完成 16 包
  clean build。`SceneAdmissionGate` 通过真实 controller 的 Action/DDS smoke
  证明身份、新鲜度、frame、目标对象、置信度、尺寸和 AABB 拒绝均无
  control/motion/servo 命令逸出；lease 等待竞态会 start/cancel 并释放 lease
  但无 motion/servo 命令，fresh 安全场景可完成。这些证据不替代真实设备、目标
  Jazzy 或部署环境验收。
- 校准后的受影响回归已通过：`parallel_3dof_controller` 为 `108 passed`、
  `25` 个 subtests、`1 skipped`，`robot_bringup` 为 `36 passed`、`65` 个
  subtests；真实 profiling 冒烟为 3 条路径各 `5/5`、零超时。DDS 复测仍只
  能作为 Humble 基线，不能替代目标 Jazzy 或物理硬件验收。controller 的
  `setup.py` 同时补齐 pytest test extra，修复 `colcon test` 只运行空 unittest
  suite 的注册缺陷；重建后包级测试发现 109 个 item，`colcon test-result`
  汇总 134 项、零错误、零失败、1 项跳过。
- `scripts/profile_runtime_hotpaths.py` 已完成 execution/motion/simulation 三
  域 600 个真实 DDS 计量样本的初始基线；它只支持热点排序和 Phase 6 的 25%
  证据，尚不支持 C++ 迁移结论。
- `src/bridges/simulation_bridge/launch/simulation.launch.py` 已进一步把包级 enable 开关从
  `enable_isaac_bridge`、`enable_sim_cpp_bridge` 收口为
  `enable_sim_servo_bridge`、`enable_sim_joint_bridge`。
- `src/bridges/teleoperation_bridge/websocket_bridge/message_handler.py` 当前也已开始把 `servo_control`
  解析结果标准化为 `MotionCommand` 风格字段：显式补 `value_encoding`、
  `duration_ms`，并在 bus 输入为角度时先换算到 pulse us；`bridge_node.py`
  也会只采用这组显式时长语义继续下发，不再镜像旧 `MotionCommand.speed`。
- `src/execution/execution_manager/execution_manager/command_adapter.py` 当前也已移除 consumer 侧旧
  `speed` 时长回退，只把正值 `duration_ms` 提升为内部执行时长；测试 fixture
  也已清除旧公共字段，改为覆盖缺失、非法和非正 `duration_ms`。
- `motion_msgs` 当前已把公共 `MotionCommand.speed` 标记为弃用，并注册标准
  库源码合同测试，禁止三个内置 producer 写入或 execution adapter 读取该字
  段；根 README 的失效 CLI 示例也已改走显式 `duration_ms` motion 入口。
- `bvh_play` 请求规范化、ack、错误映射、motion publisher、执行联锁与播放
  生命周期当前均已收回 `record_load_action` 的可选 capability；
  `bridge_node` 只保留通用扩展工厂、状态通知与关闭钩子。
- 默认 teleop/full-system 不启用 BVH；需要演示链路时由
  `src/tools/record_load_action/launch/bvh_websocket_demo.launch.py` 显式装配，并继续走
  `/execution/motion/command` 与 `execution_manager`。
- `src/bridges/simulation_bridge/launch/simulation.launch.py` 当前也已进一步不再把
  `enable_sim_servo_bridge`、`enable_sim_joint_bridge` 这组内部 capability
  开关保留为 package-level public surface，而是回到纯 assembly 入口，直接
  编排 `sim_servo_bridge.launch.py` 与 `sim_joint_bridge.launch.py` 两条内部子
  链路。
- `sim_publish_rate_hz` 也已进一步从
  `src/bridges/simulation_bridge/launch/simulation.launch.py` 下沉到
  `src/bridges/sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参数，不再
  作为 package-level public surface 暴露；`sim_joint_bridge.launch.py`
  当前也不再重复声明这组默认值。
- `sim_servo_bridge.launch.py` 与 `sim_servo_bridge_node.py` 现在也已把
  simulator-facing topic 参数从 `isaac_*` 收口为 `sim_servo_*`，继续朝
  simulation 域统一词表推进。
- `sim_servo_bridge_node.py` 当前也已改为依赖
  `sim_servo_bridge_utils.py`；对应工具模块与测试文件不再继续保留
  `isaac_bridge_*` 命名。
- `sim_servo_bridge.launch.py` 当前也已不再继续声明 bridge-specific 的调试
  / 限幅 launch 参数；这组默认值此前已从 `isaac_bridge_debug`、
  `isaac_enforce_limits` 收口到 `debug`、`enforce_position_limits`，现在
  统一由 `src/bridges/simulation_bridge/config/default_params.yaml` 与节点默认参数持有。
- `simulation_bridge` 的包元数据描述与运行说明当前也已改用
  simulation / sim_servo 词表，不再把 Python servo 子链路入口继续表述
  为 Isaac 专名节点。
- `sim_joint_bridge.launch.py` 当前也已不再继续声明 bridge-specific 的调试
  launch 参数；对应默认值现在统一由
  `src/bridges/sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参数持有。
- `sim_joint_bridge_cpp` 当前也已把 joint 子链路的可执行名、节点名与默认参
  数根节点从 `sim_servo_bridge_*` 收口为 `sim_joint_bridge_*`，避免继续和
  Python servo 子链路复用同一节点身份。
- `sim_joint_bridge_cpp` 当前也已把内部成员命名进一步对齐到
  `sim_joint_*` 参数词表，减少源码内部仍用泛化 `joint_*` / `publish_rate_*`
  变量名带来的语义漂移。
- `sim_joint_bridge_cpp` 现在也已移除 `servo_cmd_topic`、
  `joint_cmd_topic`、`joint_state_fb_topic`、`publish_rate_hz` 这组旧参数
  兼容分支，只保留当前 simulation 词表。
- C++ 子链路此前已从旧的 `sim_servo_bridge_cpp` 根级目录迁到
  `src/bridges/sim_joint_bridge_cpp`；此后目录名、ROS 包名与节点身
  份已回到同一套 `sim_joint_*` 词表。
- `sim_joint_bridge.launch.py` 当前也已显式加载
  `src/bridges/sim_joint_bridge_cpp/config/default_params.yaml`，把 C++ 子链路的默认参数
  所有权收回到包内配置，而不是继续散落在 launch 内联默认值里。
- `sim_joint_bridge.launch.py` 当前也已不再继续内联
  `servo_command_topic`、`servo_state_topic` 这组 driver-facing 固定接线，
  改为统一由 `src/bridges/sim_joint_bridge_cpp/config/default_params.yaml` 持有默认值。
- `sim_joint_bridge.launch.py` 当前也已不再重复声明
  `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`、
  `sim_publish_rate_hz` 这组 simulator-facing 默认值，进一步把默认值所有权
  收回到 `src/bridges/sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参数。
- `sim_joint_bridge_cpp` 当前也已把 `servo_type` 参数收紧为收发两侧共用的同
  一语义：既控制下发 `ServoCommand.servo_type`，也控制回读 `ServoState`
  的过滤条件；非法值会回退到 `bus`。
- `sim_joint_bridge_cpp` 当前也已把内部 `speed` 参数收口为 `default_speed`，
  并在非法值时回退到 `100`，与 Python `sim_servo_bridge_node.py` 的默认速
  度语义保持同一方向。
- `sim_servo_bridge.launch.py` 当前也已显式加载
  `src/bridges/simulation_bridge/config/default_params.yaml`，把 Python servo 子链路的默认
  参数所有权收回到包内配置，而不是继续散落在 launch 内联常量与节点默认值
  里。
- `sim_servo_bridge.launch.py` 当前也已不再重复声明
  `sim_servo_command_topic`、`sim_servo_state_topic` 这组 simulator-facing
  默认值，进一步把默认值所有权收回到
  `src/bridges/simulation_bridge/config/default_params.yaml` 与节点默认参数。
- `src/bridges/simulation_bridge/launch/simulation.launch.py` 现在也已不再暴露
  `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`，package-level public
  surface 已进一步收紧为单一 domain entry。
- `bridge_stack.launch.py` 当前也已移除，`simulation.launch.py` 直接 include
  `sim_servo_bridge.launch.py` 与 `sim_joint_bridge.launch.py` 两个子链路。
- sim 相关 source-level contract 测试当前也已减重为以当前 public
  surface 为主，只保留少量关键旧词表回归断言。
- 后续仍应继续统一仿真域 message contract 与包边界，但这部分当前已不再
  是主推进面，而是后续阶段的维护与最终合并事项。

下一阶段建议优先审计的文件：

- `src/interfaces/motion_msgs/msg/MotionCommand.msg`
- `docs/motion_command_speed_migration.md`
- `src/execution/execution_manager/execution_manager/command_adapter.py`
- `src/bridges/teleoperation_bridge/websocket_bridge/bridge_node.py`
- `src/control/parallel_3dof_controller/parallel_3dof_controller/controller_node.py`
- `src/control/parallel_3dof_controller/parallel_3dof_controller/scene_admission.py`
- `scripts/profile_runtime_hotpaths.py`
- `docs/runtime_profiling_baseline.md`
- `src/tools/record_load_action/record_load_action/bvh_websocket_extension.py`

实施后必须同步更新：

- `docs/refactor_update_plan.md`
- `docs/current_module_responsibilities.md`


## 6. 当前不优先做的事

现阶段暂不优先：

- 再做一轮 teleop requester / lease 语义深挖
- 立即把 `record_load_action` 的离线工具与 demo 集成拆成多个 ROS 包
- 立即推动 `parallel_3dof_controller -> motion_control` 正式改名
- 立即把所有 `servo_msgs` 依赖一次性替换掉
- 大规模目录迁移
- Python 到 C++ 的大规模重写

这些工作并非不做，而是要放在当前责任域进一步收口之后再做。


## 7. 执行结果要求

每完成一轮推进，至少要满足以下输出：

- 代码改动本身可独立解释。
- 文档能反映“当前事实”而不是“未来想象”。
- 定向测试或定向构建通过。
- 提交粒度足够小，方便回溯和继续推进。

如果下一轮推进内容偏离以上约束，应先回到
`docs/plan.md`、`docs/module_responsibilities.md`、
`docs/refactor_update_plan.md` 和
`docs/current_module_responsibilities.md` 重新校准，再继续实施。
