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
- `execution_manager` 已建立最小执行边界，teleop 与 motion 已不再都直接碰驱动层。
- `sensor_hardware` 已独立成 ROS 包。
- teleop 控制权链已落地显式 claim / keepalive / release。
- teleop `MotionCommand` 已收紧为显式 requester / lease 约束。
- `parallel_3dof_controller` 已更明确地以 `duration_ms` /
  `value_encoding` 表达 `MotionCommand` 语义；求解器输出当前也已补充
  `duration_ms`，控制器优先消费该字段，`speed` 仅保留为兼容镜像。
- `websocket_bridge` 当前也已开始把 `servo_control` 输入标准化为
  `value_encoding` / `duration_ms` 优先的 motion 语义；bus 目标值会在桥接
  前归一到 pulse us，`speed` 仅保留为兼容镜像。
- `execution_manager` 当前也已继续收紧 `MotionCommand` consumer 侧时长解
  析：显式 `duration_ms` 仍是主语义，旧 `speed` 只在正值时作为兼容回退。
- `execution_manager` 当前也已把内部仲裁器从命令载荷细节中进一步解耦；
  `CommandArbitrator` 现在只按来源、时间与 teleop 身份做仲裁，不再要求一
  层伪 `CommandFrame` 中间快照。
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

**Phase C-Next：继续收紧 `MotionCommand` 的中性执行语义**

原因：

- BVH/demo 已完成 opt-in 断依赖，sim 域 package-level surface 也已基本收
  口，这两块不再是当前主推进阻塞项。
- `MotionCommand.duration_ms` / `value_encoding` 已成为 producer 与 consumer
  的主语义，但旧 `speed` 回退和 servo 风格字段仍存在于公共接口及多个生产
  者中。
- 当前更适合沿既有中性 setpoint 适配层做小步收紧，而不是立即改包名、移动
  目录或继续深挖 demo 内部实现。


## 5. 下一阶段建议范围

下一阶段建议范围控制在：

- 审计 `MotionCommand` 的所有 producer / consumer，只选择一个可独立验证
  的旧字段依赖继续收紧；不在同一阶段同时改消息定义和所有调用方。
- 继续稳定 `duration_ms`、`value_encoding` 的主语义优先级，优先消除内部
  对旧 `speed` 回退的实际依赖，再评估公共字段删除。
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
  也会优先采用这组显式语义继续下发。
- `execution_manager/command_adapter.py` 当前也已把 consumer 侧时长回退收紧
  为“先读正值 `duration_ms`，再读正值旧 `speed`”，无效旧字段不再被提升为
  内部执行时长。
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

建议优先修改的文件：

- `src/execution_manager/execution_manager/command_adapter.py`
- `src/execution_manager/test/test_command_adapter.py`
- `src/parallel_3dof_controller/parallel_3dof_controller/controller_node.py`
- `src/websocket/websocket_bridge/bridge_node.py`
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
