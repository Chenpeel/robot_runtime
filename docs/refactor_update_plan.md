# 重构更新计划

## 1. 文档定位

本文是截至 2026-03-19 的重构更新计划，用来连接“当前仓库事实”和“长期规
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

当前仓库最重要的现实约束有五点：

1. `websocket_bridge` 目前是混合职责包。
   - 它同时承担 WebSocket 接入、人工遥控、状态回传、IMU 上行、BVH 播
     放、Isaac 仿真桥，以及整机主 launch 编排。
2. `parallel_3dof_controller` 目前仍然直接发布 `servo_msgs/ServoCommand`。
3. `servo_hardware` 与 `sensor_hardware` 虽然在代码目录上已分开，但在
   ROS 包层面仍然混在 `src/hardware` 里。
4. `sim_servo_bridge_cpp` 当前是驱动级双向桥，直接接 `/servo/command` 和
   `/servo/state`，还没有独立的高层仿真边界。
5. 当前仓库里还没有正式落地的 `execution_manager`、`motion_msgs`、
   `task_service_bridge`、`task_api_msgs`。

这意味着当前阶段的关键不是补齐所有远期模块，而是先把已有链路的边界理顺。


## 3. 本轮重构目标

本轮更新计划只追求四个结果：

1. 把“当前事实”和“长期目标”从文档层彻底拆开，避免误导后续开发。
2. 把当前运行链路中的 teleop、控制、驱动、仿真边界重新梳理清楚。
3. 为 `execution_manager` 和 `sensor_hardware` 拆包创造落地条件。
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

动作：

1. 定义最小执行请求与执行反馈接口。
2. 优先让 `parallel_3dof_controller` 通过执行边界下发，而不是继续直接发
   `ServoCommand`。
3. 再把 teleop 入口改成通过执行边界申请控制权和下发命令。
4. 在 `execution_manager` 中实现最小控制权状态机、急停和超时保护。

完成标准：

- 至少一条控制链不再直接发布 `/servo/command`。
- 至少一条 teleop 链路经过执行层。
- 驱动层只负责驱动，不负责控制权判断。

### Phase D：拆分 `sensor_hardware`

目标：

- 将已经存在的 `sensor_hardware` 代码从“包内子模块”提升为独立 ROS 包。

动作：

1. 新建独立的 `sensor_hardware/package.xml`、`setup.py` 和入口点。
2. 从 `servo_hardware` 的导出列表中移除 IMU 节点。
3. 更新 launch、依赖和构建清单。

完成标准：

- `servo_hardware` 只承载执行器与协议能力。
- `sensor_hardware` 可以单独构建、安装和启动。

### Phase E：收口仿真域

目标：

- 将 Isaac 桥与 `sim_servo_bridge_cpp` 这类逻辑从 teleop 包边界中抽离出来。

动作：

1. 明确哪一部分保留 Python，哪一部分保留 C++。
2. 把仿真桥接节点及其 launch 开关归并到统一的 simulation 责任域。
3. 避免后续继续由 `websocket_bridge` 持有仿真主入口。

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
3. `sensor_hardware` 拆包
   - 这是硬件边界清晰化的最低成本改造。
4. 仿真收口
   - 这是 `websocket_bridge` 降职责的关键一步。
5. 正式命名收敛
   - 只有在前面四步稳定后才值得做。


## 6. 需要持续遵守的约束

后续每个阶段都要反复检查以下红线：

1. 不把未实现模块写成已落地事实。
2. 不继续扩张 `websocket_bridge` 的职责。
3. 不把 `/servo/command` 直发当作新架构的长期方案。
4. 不让驱动层承接控制权仲裁。
5. 不在没有 profiling 结果前推动语言重写。


## 7. 简短结论

长期规划文档仍然有效，但当前仓库离那套目标架构还有几步关键过渡工作。
因此更合理的做法不是去覆盖旧规划，而是补充一层“当前事实 + 近期执行顺序”
文档：先把边界整理清楚，再补执行层、拆硬件包、收口仿真域，最后再做正式命
名和远期模块落地。
