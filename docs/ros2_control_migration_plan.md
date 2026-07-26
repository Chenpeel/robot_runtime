# ROS 2 Control 总体迁移计划

## 1. 文档定位

本文定义从现有 `MotionCommand -> ServoCommand -> Python driver` 链路迁移到
ROS 2 Control 的总体阶段、依赖、验收和回滚策略。

目标边界以 `docs/ros2_control_architecture.md` 为准。本文只定义实施顺序，不
把阶段动作写成当前已完成事实，也不替代后续的现状、近期更新计划和编码规则。

专项文档按以下顺序建立：

1. 已建立：`docs/ros2_control_architecture.md`
   - 长期分层、职责、权限、接口、安全和实时性红线。
2. 已建立：本文
   - 总体迁移阶段、依赖、验收和回滚。
3. 下一轮建立：`docs/ros2_control_current_state.md`
   - 只记录仓库当前实现和已验证证据。
4. 下一轮建立：`docs/ros2_control_update_plan.md`
   - 从当前事实到下一门禁的近期小切片。
5. 下一轮建立：`docs/ros2_control_coding_rules.md`
   - C++、实时循环、plugin、controller、配置和测试编码规则。
6. 此后才按近期计划逐阶段实现。


## 2. 当前迁移起点

当前仓库同时存在两套未接通的驱动路径。

### 2.1 现有正式路径

```text
task / teleop / motion
    -> parallel_3dof_controller or bridge
    -> MotionCommand (servo ID + raw target)
    -> execution_manager
    -> ServoCommand
    -> servo_hardware Python driver
    -> serial / I2C
```

该路径已经具备 task/teleop/motion 仲裁、lease、停止、estop、反馈和 Action/DDS
回归，但公共命令仍带驱动风格字段。

### 2.2 新增独立 ROS 2 Control 路径

```text
JointTrajectoryController
    -> joint position command interfaces (rad)
    -> robot_hardware C++ plugins
    -> serial / I2C
```

当前 `robot_hardware` 已提供 BusServoSystem、Pca9685System 和 YbImuSensor，独立
launch 会启动 controller_manager、broadcaster 和单个 14-joint JTC。但该路径尚
未接入 `robot_bringup`、`execution_manager` 或正式 task/motion Action。

### 2.3 已知阻塞

- 仓库当前有 20 个 ROS 包，`robot_hardware` 是新增独立包。
- `robot_bringup/hardware.launch.py` 仍启动 legacy Python drivers。
- 两套 backend 不能同时打开同一物理设备。
- `jiyuan_hardware.yaml` 的 protocol 仍为 `unconfigured`。
- 单个 JTC claim 全部 14 个 joint，不适合当前三关节踝部 goal。
- solver 仍将 theta 转为 pulse，并持有 servo ID 顺序。
- execution_manager 尚无 trajectory gateway 或 ROS 2 Control safety adapter。
- Bus feedback 时序、PCA estimated state、stop ACK 和真机恢复语义尚未闭环。
- ros2_control limits、主 URDF limits 与 solver workspace 尚未形成统一合同。

这些事实只用于定义迁移起点，不构成 ROS 2 Control 主链完成证据。


## 3. 迁移策略

采用“加法建立、mock 验证、单值切换、最后清理”的策略：

1. 先冻结 joint、单位、limits、资源和安全合同。
2. 保持 legacy backend 为默认，建立完全隔离的 ROS 2 Control mock 路径。
3. 先验证 hardware/controller，再接 execution gateway。
4. motion owner 最后从 raw `MotionCommand` 切到 joint trajectory。
5. bringup 使用单值 backend 选择，不进行双写或影子真机命令。
6. 经过仿真和真机 canary 后再改变默认值。
7. legacy 删除是单独阶段，不能和首次 ROS 2 Control 接入混在同一提交。

每一阶段必须：

- 有明确输入和输出合同。
- 有自动化测试或可重复构建/launch/场景证据。
- 有失败时的稳定状态。
- 有不依赖回滚代码的运行级回退方式。
- 同步当前事实和专项更新计划。


## 4. 总体依赖图

```text
R0 文档与决策冻结
    -> R1 机械模型和标定合同
        -> R2 hardware plugin 验证 -----------+
        -> R3 controller 资源拓扑与 mock -----+-> R4 execution gateway
                                               -> R5 motion joint trajectory
R2 + R3 + R4 + R5
    -> R6 bringup 单值 backend 集成
        -> R7 安全、反馈和恢复闭环
            -> R8 仿真与真机 canary
                -> R9 默认切换与 legacy 清理
```

R2 与 R3 可以在 R1 完成后并行。R4 的接口设计可与 R2/R3 并行，但正式接线必须
等待 controller endpoint 和安全语义稳定。R6 之前禁止把新 backend 纳入默认
full-system。


## 5. 阶段 R0：文档与决策冻结

### 目标

建立可审查的目标架构和迁移边界，防止先写 adapter 再争论责任归属。

### 动作

1. 审查 `ros2_control_architecture.md` 和本文。
2. 冻结专项文档层级和优先级。
3. 明确当前轮只产生规划，不增加 `docs/plan.md` Phase 完成度。
4. 建立下一轮现状、近期计划和编码规则文档。

### 完成门禁

- 运动学默认放置位置、execution 唯一权限和 hardware 禁止事项得到确认。
- legacy/ros2_control 单值互斥原则得到确认。
- 所有后续阶段都有验收与回滚边界。

### 回滚

纯文档阶段不改变运行图；发现设计问题时修订文档，不引入兼容代码。


## 6. 阶段 R1：机械模型与标定合同

### 目标

让 motion、URDF、controller 和 hardware 对同一 joint 的名称、方向、单位和限位
只有一种解释。

### 动作

1. 冻结左右踝 solver channel 到 URDF joint name 的映射。
2. 对每个 joint 确认 axis、零点、正方向、radian limits、servo ID、protocol、
   raw limits 和端口。
3. 统一主 URDF limits 与 `<ros2_control>` command limits。
4. 区分机构 workspace limit、controller trajectory limit 和 hardware physical
   limit，并建立相容性检查。
5. 将 protocol 从 `unconfigured` 改为经真机 commissioning 证明的值。
6. 证明 hardware rad/raw round-trip 与真实零点/方向一致。
7. 冻结 PCA state 为 estimated、Bus state 的 freshness 定义。

### 交付物

- joint mapping 清单。
- 单一硬件配置 schema。
- limits/protocol 结构化验证工具或测试。
- commissioning 记录和失败设备清单。

### 完成门禁

- 不再从 servo ID 顺序推断 joint 语义。
- solver 不再需要 raw calibration 才能解释输出。
- 未配置协议或冲突 limits 会在 configure/build contract 中失败。
- 所有硬件配置变更可追溯。

### 回滚

legacy 配置保持可运行；R1 不改变默认 backend。


## 7. 阶段 R2：Hardware Plugin 验证

### 目标

证明 `robot_hardware` 是可加载、可停止、时序有界的 ROS 2 Control 设备边界，
而不仅是协议函数可以编译。

### 动作

1. 为 Bus/PCA/IMU 提供可注入 transport 或 fake transport。
2. 测试 plugin lifecycle、interface export、非法配置和重复资源。
3. 测试 activate 时 command 初始化为当前 state，避免激活跳变。
4. 测试 read/write 的 NaN、timeout、连续错误、断线和恢复行为。
5. 测试 deactivate/error 的 Bus stop_all 和 PCA full-off。
6. 为 stop failure、state validity 和 freshness 建立可上报状态。
7. 对四条 Bus hardware component 进行 read/write tracing。
8. 在 50Hz、目标 update rate 和故障注入下核对周期预算。
9. 决定同步 I/O、异步 hardware、非阻塞缓存或多 controller-manager 进程方案。

### 完成门禁

- pluginlib 可以从安装空间加载全部正式插件。
- xacro 展开和 HardwareInfo 解析有自动化合同。
- 单周期最坏 I/O 有实测上界且不超过选定预算。
- hardware ERROR 能使 controller/execution 进入稳定阻断状态。
- fake transport 下不需要访问真实 `/dev` 设备。

### 回滚

所有验证使用独立 launch 或 mock，默认 legacy bringup 不变。


## 8. 阶段 R3：Controller 资源拓扑与 Mock 闭环

### 目标

建立不重叠、适合局部踝部任务的 controller 资源模型。

### 动作

1. 将 14-joint JTC 拆成至少 right ankle、left ankle 和其他 body 资源组。
2. 每个踝部 controller 只 claim 三个明确 joint。
3. 默认拒绝缺失/未知/重复 joint name，不依赖 partial goal。
4. 配置 trajectory/state publish rate、goal tolerance、stopped tolerance 和超时。
5. 使用 mock hardware 验证 FJT goal/feedback/result/cancel。
6. 验证 controller 切换、重叠资源拒绝和 inactive 状态不接受命令。
7. 评估标准 JTC 是否满足当前 50Hz pose trajectory；没有证据时不创建自定义
   controller。

### 完成门禁

- 左右踝三关节 goal 均可在 mock hardware 完成。
- 局部 controller 不 claim 对侧或其他 body joint。
- 重叠 controller 不能同时 active。
- cancel 后 command/state 行为符合已冻结 hold/stop 合同。
- 所有测试受 60 秒超时约束。

### 回滚

controller 配置仅用于 mock/独立 launch；legacy backend 不加载这些 controller。


## 9. 阶段 R4：Execution Trajectory Gateway

### 目标

在不丢失现有 lease、优先级和 estop 语义的情况下，让 execution manager 成为
唯一 ROS 2 Control controller 调用方。

### 动作

1. 在 `motion_msgs` 设计内部 trajectory wrapper Action。
2. 为 task、teleop、motion 使用不可伪造的独立来源入口。
3. wrapper 携带 identity、lease、resource group、JointTrajectory 和 timeout。
4. execution manager 准入后调用对应 FJT Action。
5. 映射 goal accepted、feedback、result、cancel 和 controller unavailable。
6. backend 参数只允许 `legacy|ros2_control|mock`。
7. 同一进程只创建选中 backend 的 publisher/client，禁止双投递。
8. 增加 ROS 2 Control safety adapter，负责 controller cancel、hold/deactivate 和
   hardware lifecycle 编排。
9. 旧 MotionCommand/ServoCommand 路径仅保留为 legacy adapter。

### 完成门禁

- 外部节点不能绕过 execution manager 驱动正式 controller。
- task/teleop/motion 优先级在 mock ROS 2 Control 路径保持不变。
- backend 切换不会同时创建两套物理 owner。
- controller unavailable/rejected/aborted/cancelled 都形成稳定 reason。
- stop pending 时新 trajectory 不会逸出。

### 回滚

默认仍为 `legacy`；切回 legacy 只改变单值启动参数，不运行数据回放或双写。


## 10. 阶段 R5：Motion Owner 输出 Joint Trajectory

### 目标

让 motion_control 完全脱离 servo/raw 语义，并保持现有 task Action 与 scene gate。

### 动作

1. 将纯机构求解与 ROS Action/scene/lease 编排分离。
2. solver 输出 joint radians，不再输出 pulse 或 servo IDs。
3. 使用 R1 冻结的 joint mapping 生成完整三关节 JointTrajectory。
4. 将 `duration_ms` 转换为单调 `time_from_start`，不传给 hardware interface。
5. 向 execution trajectory gateway 提交 goal。
6. 使用 controller/joint feedback 生成 progress、target_reached 和 failure。
7. cancel/timeout 改走 execution gateway，不直接调用 legacy driver stop/read 服务。
8. legacy 模式通过独立 adapter 将 joint target 映射到旧 MotionCommand；该 adapter
   不成为长期 motion_control 事实。

### 完成门禁

- motion_control 源码和 manifest 不依赖 `servo_msgs`、protocol、raw 或 device。
- pose 网格、workspace 边界和左右踝映射测试通过。
- 新旧 backend 在共同可表达范围内产生等价物理目标。
- scene rejection、lease race、cancel 和 timeout 不产生 controller command 逸出。
- 正式 `/motion/execute` 仍只有一个 owner。

### 回滚

保留独立 legacy adapter 和原接口发布版本；不要在同一个实现中静默回退。


## 11. 阶段 R6：Bringup 单值 Backend 集成

### 目标

将 ROS 2 Control 纳入系统级装配，同时保持 legacy 可回退且绝不双 owner。

### 动作

1. `robot_bringup` 增加单值 `hardware_backend`。
2. `legacy` include 旧 Python hardware launch。
3. `ros2_control` include controller_manager、hardware 和 execution adapter。
4. `mock` include 同 controller 配置和 mock hardware。
5. 为非法 backend、重复 device owner 和 controller spawn failure 建立 launch 门禁。
6. 定义 robot_state_publisher 的唯一 owner，避免重复节点。
7. 按 hardware -> broadcaster -> controller -> execution gateway -> motion/task 顺序
   启动并等待就绪。
8. 停止时按 admission close -> goal cancel -> controller deactivate -> hardware
   deactivate 顺序清理。

### 完成门禁

- full-system 三种 backend 的安装后 launch 可解析。
- `mock` 可运行完整 task/context Action/DDS 场景。
- legacy 和 ros2_control launch 不能同时打开物理设备。
- controller/hardware 未 ready 时 task goal 被稳定拒绝。

### 回滚

保持 `hardware_backend:=legacy` 为默认，直到 R8 真机门禁完成。


## 12. 阶段 R7：安全、反馈与恢复闭环

### 目标

使 ROS 2 Control backend 达到现有执行链同等级别的停止、故障和恢复语义。

### 动作

1. 区分 cancel、hold、protective stop、estop 和 hardware fault。
2. 取消 FJT goal 后等待 controller 状态和新的真实 joint samples。
3. estop 路径 deactivate controller/hardware 并保持 execution latch。
4. 聚合每个 Bus/PCA/hardware component 的停止和 fault 状态。
5. 对 stale state、estimated state、NaN 和 read ERROR 建立稳定 reason。
6. PCA 无真实反馈时禁止 `target_reached` 与物理 `stop_confirmed`。
7. release 前重新读取当前位置、初始化 command 并验证全部资源 inactive/healthy。
8. 恢复后拒绝旧 goal、旧 lease 和迟到 controller feedback。
9. 故障注入覆盖任一总线超时但其余总线仍执行安全动作。

### 完成门禁

- task cancel、timeout、estop、driver fault 和 recovery 全部有 Action/DDS 证据。
- stop_requested、command_sent 和 stop_confirmed 不被合并。
- 没有真实反馈的设备永远不会产生虚假的完成确认。
- release 失败保持 admission closed。

### 回滚

任一安全场景失败时禁止真机默认切换；legacy backend 保持可选。


## 13. 阶段 R8：仿真与真机 Canary

### 目标

证明新链路在目标 Jazzy、仿真和物理硬件中均满足功能、安全和时序要求。

### 动作

1. Jazzy clean build、package test、installed launch 和 plugin load。
2. mock 与 simulation 运行正式 task、teleop、scene gate、cancel、timeout、estop。
3. 单侧踝、低速、小范围真机 canary。
4. 按总线逐步扩大 joint 数量和轨迹范围。
5. 验证 protocol、limits、方向、零点和实际 joint feedback。
6. 测量 controller update、hardware read/write、FJT feedback 和 task end-to-end。
7. 验证串口断开、坏帧、设备离线、PCA 开环和 IMU 故障。
8. 长时间运行中确认无双 owner、无资源泄漏和无旧 goal 重放。

### 完成门禁

- Jazzy、仿真和物理硬件分别通过，不相互替代。
- 控制周期、p95/p99、超时和 feedback freshness 达标。
- 所有安全失败都进入可诊断且默认阻断状态。
- canary 具备明确停机和回退流程。

### 回滚

真机异常立即 estop/deactivate，恢复 `hardware_backend:=legacy` 前必须确认新
controller_manager 和 hardware component 已完全退出并释放设备。


## 14. 阶段 R9：默认切换与 Legacy 清理

### 目标

在新链路完整验收后，将 ROS 2 Control 设为正式默认并清除不再需要的双重实现。

### 动作

1. 将生产默认 backend 从 legacy 改为 ros2_control。
2. 保留一个明确发布周期的 legacy 回退窗口。
3. 盘点外部 MotionCommand/ServoCommand publisher、录包、脚本和部署镜像。
4. 完成版本策略和 breaking-change 门禁。
5. 删除旧 Python device owner、重复配置、失效 launch 和 compatibility adapter。
6. 更新根 README、部署说明、事实职责和运行手册。
7. 再次执行全仓 clean build、测试、launch、mock、simulation 和真机回归。

### 完成门禁

- 正式运行图只有 ROS 2 Control 物理 owner。
- 上层无 `servo_msgs` 或 raw device 依赖。
- legacy 删除不影响外部已确认合同或有明确 major-version 迁移说明。
- 回退方案变为版本回退，而不是长期保留第二套运行时。


## 15. 测试与证据矩阵

### 文档与结构

- 文档链接、职责和红线结构化检查。
- package/launch/config/URDF 所有权检查。
- backend 单值和设备独占源码合同。

### 算法

- IK/FK golden corpus。
- joint mapping、limits、非法姿态和随机网格。
- Python/C++ 差分和数值容差。

### Controller

- controller load/configure/activate/deactivate。
- resource claim 和冲突拒绝。
- FJT goal/feedback/result/cancel。
- trajectory 时间、joint names、limits 和 tolerance。

### Hardware

- plugin load 和 HardwareInfo。
- protocol encode/decode。
- rad/raw round-trip。
- fake transport timeout、坏帧、断线和 stop failure。
- read/write 最坏周期和长期运行。

### 系统

- task/teleop/motion 仲裁。
- scene admission 和 lease race。
- cancel、timeout、estop、release 和 replay 拒绝。
- legacy/ros2_control/mock 三种 backend 的唯一 owner。
- Jazzy、simulation 和 physical hardware 独立回归。

单元测试和后台测试均设置最大 60 秒超时。长时间硬件 soak 必须作为显式场景运行，
不能混入无界单元测试。


## 16. 主要风险与控制措施

### 16.1 双 owner

风险：旧 Python driver 与 robot_hardware 同时打开设备。

控制：单值 backend、launch 合同、设备锁、进程图验收和停机顺序。

### 16.2 关节语义错误

风险：theta channel、URDF joint、方向或零点映射错误导致真机反向运动。

控制：R1 commissioning、低速单关节 canary、限幅和可审计 mapping。

### 16.3 控制周期超时

风险：多个串口 read timeout 串行累加，controller update 超期。

控制：tracing、预算、异步/非阻塞 I/O 或进程拆分，不通过提高频率掩盖问题。

### 16.4 虚假反馈

风险：PCA command echo 或 stale Bus state 被当成实际位置。

控制：validity/freshness/estimated 合同，禁止用于 target/stop confirmed。

### 16.5 安全语义回退

风险：把 FJT cancel 或 lifecycle success 当成物理停止。

控制：多阶段停止证据、真实状态采样、hardware status 聚合和 release 门禁。

### 16.6 公共接口震荡

风险：ROS 2 Control 接入与 MotionCommand breaking change 同时发生。

控制：新增 trajectory wrapper，legacy adapter 独立，breaking 删除留到 R9。


## 17. 进度计分边界

创建本文和架构文档只完成设计冻结，不增加 `docs/plan.md` Phase 0-6 进度。

后续实现只能按已有固定 Phase 计分：

- 接口和 execution 边界证据归入 Phase 3。
- 正式入口、优先级和安全执行闭环归入 Phase 4 的持续加固，但 Phase 4 已封顶时
  不重复计分。
- profiling 驱动的 C++ controller/hardware 性能迁移归入 Phase 6。
- 目录、构建和 launch 证据用于确认 Phase 1 仍有效，不重复计分。

不得为 ROS 2 Control 专项临时增加分母、把文档设计计为实现，或将 legacy 与新
backend 的重复功能分别计分。


## 18. 下一轮文档任务

下一轮只建立专项实施文档，不立即切换运行代码：

1. `ros2_control_current_state.md`
   - 精确列出当前 20 包、插件、interfaces、launch、配置、测试和未接线事实。
2. `ros2_control_update_plan.md`
   - 从 R1 中选择首个可独立验收的小切片，列出文件、测试和回滚。
3. `ros2_control_coding_rules.md`
   - 固定 realtime-safe C++、plugin lifecycle、配置解析、错误、日志、测试和
     launch 编码规则。

三份文档通过审查后，再从 R1 的 joint mapping/limits/protocol 合同开始实现。
