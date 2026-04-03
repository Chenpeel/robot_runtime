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

截至 2026-03-24，当前重构已经完成的关键基础包括：

- `robot_bringup` 已承接整机主入口，并拆出 hardware / teleop / simulation 三个子域。
- `robot_bringup` 场景化 launch 当前也已开始复用 `launch_utils` 统一解析总线
  协议缓存默认路径，不再在子场景入口里硬编码旧的 `websocket` 源码树绝对路径。
- `execution_manager` 已建立最小执行边界，teleop 与 motion 已不再都直接碰驱动层。
- `sensor_hardware` 已独立成 ROS 包。
- teleop 控制权链已落地显式 claim / keepalive / release。
- teleop `MotionCommand` 已收紧为显式 requester / lease 约束。
- `parallel_3dof_controller` 已更明确地以 `duration_ms` /
  `value_encoding` 表达 `MotionCommand` 语义。
- `execution_manager` 当前也已把内部仲裁器从命令载荷细节中进一步解耦；
  `CommandArbitrator` 现在只按来源、时间与 teleop 身份做仲裁，不再要求一
  层伪 `CommandFrame` 中间快照。
- BVH/demo 回放已默认改走 `/execution/motion/command`，不再复用 teleop 命令入口。
- BVH 配置所有权当前也已完全收回 `record_load_action`，运行时不再继续把
  `websocket_bridge` 当成 `bvh_action_map.json` 的兜底来源。
- BVH 的运行说明当前也已继续收回 `record_load_action/README.md`；
  `websocket/config/README.md` 只保留指向说明。
- `robot_bringup` 与 `websocket_bridge` 当前也已不再继续把
  `bvh_action_file` 作为 public launch/参数入口上抬；默认解析路径完全收
  回 `record_load_action`。
- BVH 触发入口当前也已收紧为显式 `bvh_play` 消息；旧的泛化 `action` 别
  名，以及经由直发舵机/private 路径隐式转 BVH 的历史入口都已清掉。
- 当执行层当前处于 teleop 活跃态时，新的 BVH 播放请求当前也会被桥接层直
  接拒绝；若 teleop 在播放过程中变为活跃态，当前 BVH 播放也会立即停止。
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

**Phase B/C-Next：继续收缩 `websocket_bridge` 的混合职责**

原因：

- 从全局蓝本看，`websocket_bridge` 不应长期同时承担 teleop、debug、状
  态桥接与 demo/BVH 混合职责。
- 从当前事实看，sim 域本轮已经完成主要收口，继续深挖仿真内部细节的投入
  产出比已经下降。
- `execution_manager`、BVH 配置归属与 bringup 编排都已进一步收紧，当前
  已具备继续压缩 `websocket_bridge` 历史耦合的条件。


## 5. 下一阶段建议范围

下一阶段建议范围控制在：

- 继续从 `websocket_bridge` 收回 demo/BVH 的触发、配置与说明职责，避免它
  继续作为 teleop 主链路之外能力的历史挂载点。
- 继续稳定 `motion_msgs/MotionCommand` 在 producer / consumer 两侧对
  `duration_ms`、`value_encoding` 的主语义优先级，减少过渡式驱动字段长
  期占据外部接口中心。
- 仿真域后续只保留必要维护，不再把内部实现细节重新上抬到
  `robot_bringup` 或 package-level public surface。

当前进度补充：

- `simulation_bridge/simulation.launch.py` 已进一步把包级 enable 开关从
  `enable_isaac_bridge`、`enable_sim_cpp_bridge` 收口为
  `enable_sim_servo_bridge`、`enable_sim_joint_bridge`。
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

- `src/websocket/websocket_bridge/bridge_node.py`
- `src/websocket/websocket_bridge/ws_server.py`
- `src/record_load_action/record_load_action/bvh_player.py`
- `src/record_load_action/README.md`
- `src/websocket/config/README.md`
- `src/websocket/test/test_bridge_node_teleop_guard.py`

实施后必须同步更新：

- `docs/refactor_update_plan.md`
- `docs/current_module_responsibilities.md`


## 6. 当前不优先做的事

现阶段暂不优先：

- 再做一轮 teleop requester / lease 语义深挖
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
