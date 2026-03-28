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


## 3. 当前阶段判断

截至 2026-03-24，当前重构已经完成的关键基础包括：

- `robot_bringup` 已承接整机主入口，并拆出 hardware / teleop / simulation 三个子域。
- `execution_manager` 已建立最小执行边界，teleop 与 motion 已不再都直接碰驱动层。
- `sensor_hardware` 已独立成 ROS 包。
- teleop 控制权链已落地显式 claim / keepalive / release。
- teleop `MotionCommand` 已收紧为显式 requester / lease 约束。
- `parallel_3dof_controller` 已更明确地以 `duration_ms` /
  `value_encoding` 表达 `MotionCommand` 语义。
- BVH/demo 回放已默认改走 `/execution/motion/command`，不再复用 teleop 命令入口。

这意味着：

- 当前不应再回头修改长期蓝本。
- 当前重点不再是“是否需要 execution 边界”，而是继续把剩余混杂责任域逐个收口。


## 4. 当前优先级

下一优先级定义为：

**Phase E-1：统一仿真域入口与 contract**

原因：

- 从全局蓝本看，仿真链路应当形成独立责任域：
  `motion_control / execution_manager <-> simulation_bridge <-> simulator`
- 从当前事实看，`simulation_bridge` 与 `sim_servo_bridge_cpp` 仍然是分裂状态。
- 当前整机编排虽然已经通过 `robot_bringup` 统一 include 仿真 launch，但仿真域内部仍保留两套 bridge 实现细节和参数语义。
- 与继续深挖 teleop requester / lease 细节相比，仿真域收口更符合当前阶段的全局推进顺序，也更不容易和刚完成的执行边界收紧重复。


## 5. 下一阶段建议范围

Phase E-1 的建议范围控制在：

- 统一 `simulation_bridge` 与 `sim_servo_bridge_cpp` 的 launch contract。
- 统一仿真域暴露给 `robot_bringup` 的参数名、默认 topic 和开关语义。
- 明确哪些能力属于 Python Isaac bridge，哪些能力暂时仍由 C++ bridge 承接。
- 继续让 `robot_bringup` 只感知“simulation 责任域入口”，而不是感知仿真域内部两套实现的细碎差异。

当前进度补充：

- `simulation_bridge/simulation.launch.py` 已进一步把包级 enable 开关从
  `enable_isaac_bridge`、`enable_sim_cpp_bridge` 收口为
  `enable_sim_servo_bridge`、`enable_sim_joint_bridge`。
- `bridge_stack.launch.py` 现在负责把这组 capability-based 开关映射到
  Isaac 子 launch 与 C++ 子 launch 的内部实现级 enable 参数。
- `sim_publish_rate_hz` 也已进一步从 `simulation_bridge/simulation.launch.py`
  下沉到 `sim_cpp_bridge.launch.py`，不再作为 package-level public
  surface 暴露。
- `isaac_bridge.launch.py` 与 `isaac_bridge_node.py` 现在也已把
  simulator-facing topic 参数从 `isaac_*` 收口为 `sim_servo_*`，继续朝
  simulation 域统一词表推进。
- `sim_servo_bridge_cpp` 现在也已移除 `servo_cmd_topic`、
  `joint_cmd_topic`、`joint_state_fb_topic`、`publish_rate_hz` 这组旧参数
  兼容分支，只保留当前 simulation 词表。
- 后续仍应继续统一仿真域 message contract 与包边界，而不是重新把实现细
  节上抬到 `robot_bringup`。

建议优先修改的文件：

- `src/simulation_bridge/launch/simulation.launch.py`
- `src/simulation_bridge/launch/bridge_stack.launch.py`
- `src/robot_bringup/launch/simulation.launch.py`
- `src/robot_bringup/launch/full_system.launch.py`
- `src/simulation_bridge/simulation_bridge/isaac_bridge_node.py`
- `src/sim_servo_bridge_cpp/src/sim_servo_bridge_node.cpp`
- `src/sim_servo_bridge_cpp/config/default_params.yaml`

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
