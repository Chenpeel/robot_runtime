# 重构更新计划

## 1. 文档定位

本文是截至 2026-03-23 的重构更新计划，用来连接“当前仓库事实”和“长期规
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
   - 它仍同时承担 WebSocket 接入、人工遥控、状态回传、IMU 上行与 BVH 播
     放等多类职责。
2. `motion_msgs` 已经落地最小接口，但字段语义仍保留明显的过渡态。
3. `robot_bringup` 已经独立承接整机主 launch，并开始按硬件、遥控、仿真拆
   分启动入口。
4. `sensor_hardware` 已经独立成 ROS 包，主 launch 也已切到新包。
5. `simulation_bridge` 已经独立承接 Isaac 仿真桥，但 `sim_joint_bridge_cpp`
   仍是单独的 C++ 仿真桥，仿真域还没有完全收口。
6. `execution_manager` 已经落地最小可运行实现，并切到 `motion_msgs`，但
   还没有 `task_service_bridge`、`task_api_msgs` 等更正式的上层入口。

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
- 整机入口已拆为 hardware、teleop、simulation 三个子 launch 再组合。
- 场景化 launch 当前也已开始复用 `robot_bringup.launch_utils` 统一解析总线协议
  缓存默认路径，不再在子场景入口里硬编码旧的 `websocket` 源码树绝对路径。
- `websocket_bridge` 不再默认承接系统级编排。

动作：

1. 将 `websocket_bridge` 内部职责拆成四类看待：
   - teleop 入口
   - 状态与传感器上行桥
   - demo/BVH 能力
   - 仿真桥与 launch 编排
2. 约束后续新增功能：
   - 不再继续把仿真和 demo 逻辑往 `bridge_node` 里堆。
   - 不再继续把系统级编排逻辑默认放进 `websocket_bridge`。
3. 让文档和 launch 组织先反映出边界，而不是所有东西都以
   `websocket_bridge` 为中心。

完成标准：

- 现有系统仍能启动。
- 文档和 launch 结构已经能反映出 teleop、simulation、hardware 的职责差
  异。

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
  `CommandArbitrator` 现在只按来源、时间与 teleop 身份做仲裁，不再要求
  一层伪 `CommandFrame` 中间快照，而是由节点在 setpoint 适配后直接送入仲
  裁，再把被接受的请求转回驱动层命令。
- `MotionCommand` 已开始增量补充 `duration_ms` 与 `value_encoding`，
  `execution_manager` 已优先读取新字段，`websocket_bridge` 与
  `parallel_3dof_controller` 也已开始双写；其中
  `parallel_3dof_controller` 已先在 producer 内部显式以
  `duration_ms` / `value_encoding` 作为主语义，并将 `speed` 保留为兼容镜
  像字段。
- `websocket_bridge` 内部的 demo/BVH 回放链路也已开始默认改走
  `/execution/motion/command`，不再复用 teleop 命令入口，降低 demo 能力与
  teleop 控制权约束的耦合。
- BVH 配置所有权当前也已完全收回 `record_load_action`，运行时不再继续把
  `websocket_bridge` 当成 `bvh_action_map.json` 的兜底来源，继续减少 demo
  能力对 teleop 包边界的历史耦合。
- BVH 的运行说明当前也已继续收回 `record_load_action/README.md`；
  `websocket/config/README.md` 只保留指向说明，继续减少 demo 文档职责留在
  `websocket_bridge` 包内。
- 当执行层当前处于 teleop 活跃态时，新的 BVH 播放请求当前也会被桥接层直
  接拒绝；若 teleop 在播放过程中变为活跃态，当前 BVH 播放也会立即停止，
  继续减少 demo 路径对 teleop 主链路的运行时干扰。
- `websocket_bridge` 已开始消费 `motion_msgs/ExecutionState`，并将执行层状
  态上行到 WebSocket 状态查询/广播链路。

动作：

1. 继续稳定最小执行请求与执行反馈接口，尤其是刚补上的 teleop 控制权反馈语
   义。
2. 继续收紧 `motion_msgs` 的字段语义，减少过渡式 servo 风格字段长期保留；
   当前已先在 `execution_manager` 内部补上中性适配层，并已为消息增量补充更
   明确的时长和编码语义。下一步重点转为继续扩大 producer/consumer 对新字
   段的优先级，逐步弱化旧字段的歧义。
3. 继续稳定 teleop 显式 claim / release / keepalive 接口与上层调用约束，
   明确哪些行为是正式入口，哪些仍是过渡态；当前虽已有连接级 holder 语义，
   但仍缺更正式的 lease token、抢占策略、跨入口约束，以及更正式的客户端
   侧控制权确认流程。当前虽已在 register / status_query / execution_state
   广播中显式暴露 requester 视角，并已补上第一版 lease token。当前
   teleop `MotionCommand` 已不再接受空 requester，且在已有活跃 lease 时
   也不再接受空 lease；现阶段的兼容回退主要还留在 `TeleopControl`
   keepalive / release 对空 lease 的 holder 语义过渡上。与此同时，桥接层当
   前仍只是基于快照做本地预校验，还不是执行层主导的正式准入协议，后续仍缺
   更正式的抢占策略和跨入口统一约束。
4. 在 `execution_manager` 中继续补齐更完整的控制状态机、急停和超时保护。

完成标准：

- 至少一条控制链不再直接发布 `/servo/command`。
- 至少一条 teleop 链路经过执行层。
- 驱动层只负责驱动，不负责控制权判断。

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
3. 在需要时引入 `motion_msgs`，替代上层模块对 `servo_msgs` 的长期直接依
   赖。
4. 更远期再评估 `task_service_bridge`、`task_api_msgs`、`speech_interface`、
   `vision_perception` 的落地顺序。

完成标准：

- 包名与实际职责一致。
- 上层模块不再长期直接依赖驱动级消息。


## 5. 当前建议优先级

如果只按投入产出比排序，建议顺序如下：

1. 文档分层
   - 先补事实文档，停止让规划文档承载当前状态。
2. 执行边界
   - 这是控制层和桥接层解耦的前提。
3. `websocket_bridge` 降职责
   - 当前 sim 收口已基本完成，下一步更值得继续压缩 teleop/debug/demo 的混
     合包边界。
4. 正式命名收敛
   - 只有在前面四步稳定后才值得做。


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
`robot_bringup`，仿真域本轮也已基本完成 package-level 收口；下一步更应围
绕 `websocket_bridge` 降职责与执行边界继续推进，最后再做正式命名和远期模
块落地。
