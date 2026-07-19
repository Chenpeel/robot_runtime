# 重构推进说明

## 1. 文档角色

当前重构过程中，文档按三层使用：

1. 长期蓝本
   - `docs/plan.md`
   - `docs/module_responsibilities.md`
2. 当前事实与阶段进度
   - `docs/refactor_update_plan.md`
   - `docs/current_module_responsibilities.md`
3. 本文
   - 用来约束日常推进方式、判断优先级，并明确下一阶段应该先做什么。

约束：

- `docs/plan.md` 和 `docs/module_responsibilities.md` 是全局蓝本，不在日常推进中直接修改。
- 任何实现和提交，都要先回到这两份蓝本文档看“目标边界是什么”。
- 当前实际落地情况，只写入 `docs/refactor_update_plan.md` 和
  `docs/current_module_responsibilities.md`。


## 2. 推进规则

每一轮推进都按下面顺序执行：

1. 先对照长期蓝本判断目标边界。
2. 再对照当前事实文档确认仓库真实状态。
3. 只选择一个可以独立验证、可以单独提交的小阶段。
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
- 不为了“形式统一”先做大规模目录迁移。
- 不把过渡兼容代码写成长期架构事实。
- 不把 demo、调试、仿真临时链路重新混回正式主链路。
- 某一块重构完成且旧目录、旧副本、旧入口已经无引用时，应及时删除，不长
  期保留“等以后再清理”的废弃目录；目录级清理应作为对应重构阶段的收尾动
  作，而不是无限后延。


## 3. 当前阶段判断

截至 2026-07-17，当前重构已经完成的关键基础包括：

- `robot_bringup` 已承接整机主入口，并拆出 hardware / teleop / simulation 三个子域。
- `robot_bringup` 场景化 launch 当前也已开始复用 `launch_utils` 统一解析总线
  协议缓存默认路径，不再在子场景入口里硬编码旧的 `websocket` 源码树绝对路径。
- `robot_bringup` 当前已增加 `docs/plan.md` Phase 2 仓库级完成合同，以 AST、
  XML 和 JSON 结构化验证 WebSocket/simulation 包级分离、独立
  `sensor_hardware` 所有权、BVH 默认 opt-in 依赖方向，以及
  `full_system` 对 hardware / teleop / simulation 三个子 launch 的真实组合；
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
  与 breaking 切换门禁仍未完成，其他未来接口包也尚未随真实模块落地。
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
- 基于上述 task-aware execution admission、跨入口优先级与 ROS 验收，
  `docs/plan.md` Phase 4 已从 `25%` 提升到 `50%`。全局原始进度由 `46.4%`
  提升到 `50.0%`，实际推进约 `3.6` 个百分点；按最近 `5%` 展示由 `45%`
  提升到 `50%`，顶部进度条相应调整为 10/20 格。Phase 4 尚未达到
  `75% / 100%`，因为 `task_api_msgs`、`task_service_bridge`、
  `/task/execute`、motion goal/result 与真实任务取消/完成反馈仍未落地；当
  前 `cancel` 只撤销后续命令准入，不等同于驱动级在途停止。
- BVH/demo capability 的动作输出已改走 `/execution/motion/command`，不再复
  用 teleop 命令入口。
- BVH 配置所有权当前也已完全收回 `record_load_action`，运行时不再继续把
  `websocket_bridge` 当成 `bvh_action_map.json` 的兜底来源。
- BVH 的运行说明当前也已继续收回 `record_load_action/README.md`；
  `websocket/config/README.md` 只保留指向说明。
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
- `record_load_action/bvh_websocket_demo.launch.py` 是当前显式 opt-in 入口；
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

**Phase 4-Next：冻结真实任务 goal / result / cancel 与停止语义**

原因：

- 正式 task 的内部身份、lease、优先级和 task topic 准入已经落地，但当前还
  没有能表达 motion goal、执行反馈、完成结果和真实取消的接口。
- `TaskExecutionControl` 是执行准入租约，不是外部任务 Action；其 `cancel`
  只阻止后续 task 命令，不能把已经发到驱动的命令伪装为已停止。
- 现在直接创建 `task_service_bridge` 并发布 `MotionCommand` 会绕过长期蓝本中
  的 `motion_control`；收到请求立即返回 success 又会把“已接收”伪装成“已
  完成”。这两条路径都不应进入当前事实。
- 下一步应先冻结 motion_control-facing 的 goal/feedback/result/cancel 与停
  止确认语义，再由真实 owner 实现 `/task/execute`；`MotionCommand` 最终
  schema 和 breaking 门禁仍保留为并行设计约束，但在仓外事实缺失时不直接
  修改公共布局。


## 5. 下一阶段建议范围

下一阶段建议范围控制在：

- 明确 task goal 由 `motion_control` 接收何种结构化目标，以及如何把
  `task_id` / `trace_id` / `session_id` 贯穿到 feedback 和 result。
- 冻结任务取消与执行层停止的区别：准入 lease 撤销、运动控制取消、驱动在途
  停止和最终 stopped 确认必须是可区分的状态，不能复用一个布尔值。
- 在存在真实 motion owner 和可回传完成结果前，不创建空
  `task_service_bridge`、假 `/task/execute` 或直接面向执行器的外部任务字段。
- `MotionCommand` 最终 schema 继续按
  `docs/motion_command_speed_migration.md` 盘点仓外 publisher/subscriber、旧
  rosbag、生成绑定与部署镜像；门禁全部通过前不删除或重排公共字段。
- `websocket_bridge` 后续只继续处理 teleop / debug / status 的剩余混杂，
  不重新把 BVH capability、配置或样例放回默认核心。
- 仿真域后续只保留必要维护，不再把内部实现细节重新上抬到
  `robot_bringup` 或 package-level public surface。

当前进度补充：

- `simulation_bridge/simulation.launch.py` 已进一步把包级 enable 开关从
  `enable_isaac_bridge`、`enable_sim_cpp_bridge` 收口为
  `enable_sim_servo_bridge`、`enable_sim_joint_bridge`。
- `websocket_bridge/message_handler.py` 当前也已开始把 `servo_control`
  解析结果标准化为 `MotionCommand` 风格字段：显式补 `value_encoding`、
  `duration_ms`，并在 bus 输入为角度时先换算到 pulse us；`bridge_node.py`
  也会只采用这组显式时长语义继续下发，不再镜像旧 `MotionCommand.speed`。
- `execution_manager/command_adapter.py` 当前也已移除 consumer 侧旧
  `speed` 时长回退，只把正值 `duration_ms` 提升为内部执行时长；测试 fixture
  也已清除旧公共字段，改为覆盖缺失、非法和非正 `duration_ms`。
- `motion_msgs` 当前已把公共 `MotionCommand.speed` 标记为弃用，并注册标准
  库源码合同测试，禁止三个内置 producer 写入或 execution adapter 读取该字
  段；根 README 的失效 CLI 示例也已改走显式 `duration_ms` motion 入口。
- `bvh_play` 请求规范化、ack、错误映射、motion publisher、执行联锁与播放
  生命周期当前均已收回 `record_load_action` 的可选 capability；
  `bridge_node` 只保留通用扩展工厂、状态通知与关闭钩子。
- 默认 teleop/full-system 不启用 BVH；需要演示链路时由
  `record_load_action/bvh_websocket_demo.launch.py` 显式装配，并继续走
  `/execution/motion/command` 与 `execution_manager`。
- `simulation_bridge/simulation.launch.py` 当前也已进一步不再把
  `enable_sim_servo_bridge`、`enable_sim_joint_bridge` 这组内部 capability
  开关保留为 package-level public surface，而是回到纯 assembly 入口，直接
  编排 `sim_servo_bridge.launch.py` 与 `sim_joint_bridge.launch.py` 两条内部子
  链路。
- `sim_publish_rate_hz` 也已进一步从 `simulation_bridge/simulation.launch.py`
  下沉到 `sim_joint_bridge_cpp/config/default_params.yaml` 与节点默认参数，不再
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
- `sim_joint_bridge_cpp` 现在也已移除 `servo_cmd_topic`、
  `joint_cmd_topic`、`joint_state_fb_topic`、`publish_rate_hz` 这组旧参数
  兼容分支，只保留当前 simulation 词表。
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
- `simulation_bridge/simulation.launch.py` 现在也已不再暴露
  `sim_joint_cmd_topic`、`sim_joint_state_fb_topic`，package-level public
  surface 已进一步收紧为单一 domain entry。
- `bridge_stack.launch.py` 当前也已移除，`simulation.launch.py` 直接 include
  `sim_servo_bridge.launch.py` 与 `sim_joint_bridge.launch.py` 两个子链路。
- sim 相关 source-level contract 测试当前也已减重为以当前 public
  surface 为主，只保留少量关键旧词表回归断言。
- 后续仍应继续统一仿真域 message contract 与包边界，但这部分当前已不再
  是主推进面，而是后续阶段的维护与最终合并事项。

下一阶段建议优先审计的文件：

- `src/motion_msgs/msg/MotionCommand.msg`
- `docs/motion_command_speed_migration.md`
- `src/execution_manager/execution_manager/command_adapter.py`
- `src/websocket/websocket_bridge/bridge_node.py`
- `src/parallel_3dof_controller/parallel_3dof_controller/controller_node.py`
- `src/record_load_action/record_load_action/bvh_websocket_extension.py`

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
