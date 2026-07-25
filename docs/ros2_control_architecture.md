# ROS 2 Control 目标分层架构

## 1. 文档定位

本文冻结机器人运行时转向 ROS 2 Control 后的目标分层、责任、权限和接口边界。
它是 `docs/plan.md` 与 `docs/module_responsibilities.md` 在 ROS 2 Control 方向上的
专项长期设计，不代表对应实现已经完成。

文档优先级如下：

1. `docs/plan.md` 与 `docs/module_responsibilities.md` 定义全局架构红线。
2. 本文细化 ROS 2 Control 专项目标架构。
3. `docs/ros2_control_migration_plan.md` 定义到达目标架构的阶段和门禁。
4. 当前事实、近期任务和编码细则必须由后续专项文档记录，不能写回长期目标。

本文不授权立即切换真机驱动，不授权删除旧 Python 驱动，也不把
`src/hardware` 当前可构建状态等同于正式主链已经接入。


## 2. 设计目标

目标架构必须同时满足：

- 上层任务、场景和运动学不依赖舵机 ID、串口协议或 pulse/tick 编码。
- `execution_manager` 继续持有 task、teleop、motion 的唯一准入和安全权限。
- ROS 2 Control controller 独占 joint command interfaces，负责轨迹执行或实时
  内环控制。
- hardware plugin 只负责生命周期、设备标定、协议和有界 I/O。
- 真实硬件、mock hardware 和 simulation 使用同一 joint-space 控制合同。
- legacy 与 ROS 2 Control backend 在任何进程图中只能选择一个物理设备 owner。
- 取消、保护停止、急停、恢复和完成确认具有可验证且不夸大的语义。
- 配置只有一个权威来源，运动学、URDF、controller 和硬件标定不重复解释同一
  物理量。

本阶段不追求：

- 把全部业务逻辑改写成 ros2_control controller plugin。
- 把运动学放入 hardware `read()` 或 `write()`。
- 为了使用 ROS 2 Control 直接废弃现有 task Action、scene gate 或执行仲裁。
- 在协议、限位和停止语义未验收前把新 backend 设为默认真机入口。


## 3. 核心架构决策

### 3.1 运动学默认位于上层控制域

当前并联 3-DOF 运动学默认由 `motion_control` 承接。现有
`parallel_3dof_controller` 是迁移前的实现载体，长期应将其纯运动学模型收敛为
与 ROS、驱动和设备协议无关的库。

该层输入：

- task/motion goal 中的目标姿态。
- 机构几何参数和工作空间约束。
- 可选的结构化场景与当前 joint state。

该层输出：

- 明确的 URDF joint names。
- 弧度制 joint positions。
- 单调递增的 `time_from_start`。
- 可验证的轨迹、约束和失败原因。

该层不得输出或持有：

- 舵机 ID。
- LX/ZL/PCA 协议类型。
- pulse、PWM tick 或协议帧。
- 串口/I2C 设备路径。
- hardware plugin 生命周期句柄。

当前 solver 中 `theta -> 500..2500us` 的映射属于待移除的驱动耦合。目标 solver
应输出与 URDF joint coordinate 一致的弧度值；物理方向、零偏和 raw 范围由硬件
标定层唯一持有。

### 3.2 ros2_control controller 承担轨迹执行和实时内环

第一阶段使用标准 `JointTrajectoryController`：

- 校验 joint names、关节范围和时间序列。
- 对轨迹点进行插值。
- 独占目标关节的 `position` command interfaces。
- 基于 joint state 生成标准 feedback/result/cancel 语义。

只有同时满足以下条件，才允许把一小段运动学内环下沉到自定义
`ControllerInterface` 或 `ChainableControllerInterface`：

1. 目标功能必须在每个 controller update 周期使用最新反馈重新求解。
2. Jazzy/目标环境 profiling 证明上层 ROS 调度不能满足频率或抖动指标。
3. 求解核已是 C++、定长、预分配、无阻塞 I/O、无运行期日志和无异常控制流。
4. Python/离线参考实现与实时实现的网格、边界和失败输入差分通过。
5. 上层 task、scene、lease、取消和错误映射仍留在非实时层。
6. controller 只接收已经通过 `execution_manager` 授权的引用，不形成第二正式
   入口。

即使采用自定义 controller，机构级运动学核也不进入 hardware plugin。

### 3.3 hardware interface 不承担运动学

`robot_hardware` 的 `BusServoSystem`、`Pca9685System` 和 `YbImuSensor` 只负责：

- 导出标准 command/state interfaces。
- lifecycle configure/activate/deactivate/cleanup。
- joint radian 与设备 raw 值之间的标定换算。
- 串口、I2C、协议编码、协议解析和错误传播。
- deactivate/error 路径上的硬件安全动作。

hardware plugin 禁止：

- 解析 task、motion、teleop 或场景语义。
- 订阅 `MotionCommand`、`JointTrajectory` 或 `/servo/command`。
- 执行 RPY 到多个 joint 的并联机构求解。
- 判断 requester、lease、优先级或任务结果。
- 将开环命令回显描述为真实位置反馈。

原因是 hardware interface 必须能被不同机器人、controller、mock 和 simulation
复用，其 `read()/write()` 还必须保持可预测的时序边界。

### 3.4 execution_manager 是唯一执行授权面

`execution_manager` 继续作为非实时执行策略层，负责：

- task、teleop、motion 来源隔离。
- requester/lease 校验。
- 优先级、超时、停止中的新命令阻断和 estop 锁存。
- 选择唯一执行 backend。
- 将已准入的 joint trajectory 交给指定 ROS 2 Control controller。
- 将 controller feedback/result/cancel 和硬件状态映射回稳定执行状态。

生产运行图中，只有 `execution_manager` 的 ROS 2 Control adapter 可以调用正式
`FollowJointTrajectory` Action。motion owner、teleop、demo 和外部节点不得绕过
该边界直接发布 trajectory topic 或直接调用 controller Action。

### 3.5 两种硬件 backend 必须互斥

迁移期间允许存在：

- `legacy`：`MotionCommand -> ServoCommand -> servo_hardware`。
- `ros2_control`：joint trajectory -> controller -> command interface ->
  `robot_hardware`。
- `mock`：同一 ROS 2 Control controller 合同连接 mock hardware。

但每个运行实例只能选择一个单值 backend。旧 Python driver 与
`controller_manager` 不得同时打开同一串口或 I2C 设备，也不得同时成为同一关节
的命令 owner。


## 4. 目标运行链路

### 4.1 正式任务链

```text
ExecuteTask
    -> task_service_bridge
    -> ExecuteMotion
    -> motion_control
       - scene admission
       - task identity
       - IK / trajectory generation
    -> execution_manager trajectory gateway
       - source / requester / lease
       - priority / timeout / estop
    -> FollowJointTrajectory
    -> resource-group trajectory controller
    -> joint position command interfaces
    -> robot_hardware
       - rad <-> raw calibration
       - serial / I2C protocol
    -> physical actuator
```

### 4.2 反馈链

```text
physical actuator
    -> robot_hardware read()
    -> joint position state interfaces
    -> controller state / joint_state_broadcaster
    -> execution_manager feedback adapter
    -> motion_control result / feedback
    -> task_service_bridge
```

只有真实、有效且足够新的 joint state 才能形成 `target_reached` 或
`stop_confirmed`。PCA9685 的 command echo 只能标为 estimated，不得参与物理完成
确认。

### 4.3 遥控链

遥控输入仍先经过 teleoperation bridge 和 execution admission。允许的上层遥控
合同可以是短时 joint trajectory、速度引用或专用实时 controller reference，
但不得直写 hardware command interface。


## 5. 分层职责与权限

### 5.1 task_service_bridge

拥有：

- 唯一外部 `/task/execute` 入口。
- task/motion Action 的身份和结果转发。

可以：

- 调用正式 `/motion/execute`。
- 传播 cancel 和结构化反馈。

禁止：

- 调用 `FollowJointTrajectory`。
- 访问 controller manager 或 hardware interface。
- 生成 joint/raw 命令。

### 5.2 motion_control

拥有：

- motion ActionServer。
- 场景准入、机构约束、IK、轨迹生成和任务级完成策略。
- pose/channel 到 URDF joint name 的机构映射。

可以：

- 读取 joint state、controller feedback 和结构化 scene。
- 向 execution gateway 提交带身份和 lease 的 trajectory 请求。

禁止：

- 访问设备协议、raw 值或硬件端口。
- claim ros2_control command interface。
- 直接调用正式 JTC Action。

### 5.3 execution_manager 与 ros2_control adapter

拥有：

- 来源、lease、优先级、stop/estop 和 backend 选择。
- 生产环境中唯一 JTC ActionClient 权限。
- controller cancel、hold/deactivate 和恢复编排。

可以：

- 将已准入的 trajectory 转发到指定资源组 controller。
- 读取 controller state、joint state 和 hardware/controller 生命周期状态。
- 请求 controller/hardware 生命周期切换。

禁止：

- 执行机构 IK 或轨迹规划。
- 解释设备 raw 编码。
- 直接绕过 controller 写串口/I2C。

### 5.4 controller_manager 与 controller

拥有：

- command interface 资源 claim。
- 实时 update loop。
- 轨迹校验、插值、关节限制和 controller feedback。

可以：

- 在明确资源组内控制 joint interfaces。
- 在满足实时门禁后加载专用并联机构内环 controller。

禁止：

- 自行解释 task/trace/session/lease。
- 成为外部正式任务入口。
- 读取硬件配置文件中的业务策略。

### 5.5 robot_hardware

拥有：

- 设备文件、协议、ID、channel、raw limits、零偏和物理方向。
- hardware lifecycle 和 I/O 错误。
- rad/raw 变换。

可以：

- 将有效 command interface 写入设备。
- 将真实设备反馈转换为 state interface。
- 在 deactivate/error 时执行协议级停止或失能。

禁止：

- 生成轨迹或运动学目标。
- 接收业务 topic/action。
- 将估计 state 冒充真实反馈。

### 5.6 robot_bringup

拥有：

- 单值 `hardware_backend` 选择。
- controller、broadcaster、execution adapter 和 hardware 的装配顺序。
- 防止 legacy/ros2_control 双 owner 的启动门禁。

禁止：

- 内联设备标定和运动学常量。
- 通过同时启动两套 backend 提供所谓回退。

### 5.7 commissioning 工具

拥有：

- 舵机 ID、协议确认、零点、方向、raw 范围和真实设备验收。

约束：

- 只能在 hardware inactive 且独占设备时运行。
- 不进入实时控制循环。
- 产出可审计配置，不在运行时自动猜测协议或永久修改配置。


## 6. 接口与单位合同

### 6.1 任务与姿态层

- 姿态公共输入沿用明确单位，例如当前 Action 的 `roll_deg/pitch_deg/yaw_deg`。
- motion_control 内部尽早转换为 SI/radian。
- task identity 不进入 ros2_control command interface。

### 6.2 motion 到 execution

计划新增内部 trajectory wrapper Action。它至少承载：

- task/trace/session/requester/lease 身份。
- controller resource group。
- `trajectory_msgs/JointTrajectory`。
- timeout、完成和取消所需的稳定字段。

来源不能由不可信 payload 自行声明，应由 task/teleop/motion 的独立 endpoint 或
受控调用路径确定。

### 6.3 execution 到 controller

- 正式执行使用 `control_msgs/action/FollowJointTrajectory`。
- 不使用 fire-and-forget trajectory topic 作为正式任务入口。
- `joint_names` 必须与目标 resource group 完全一致。
- position 使用 radian，时间使用单调递增的 `time_from_start`。

### 6.4 controller 到 hardware

- 第一阶段仅使用 `position` command/state interface，单位 radian。
- command interface 是 controller_manager 内部资源，不是 ROS topic。
- protocol duration、串口帧和 raw position 不得向上泄漏。

### 6.5 hardware 内部

- raw 编码只在 hardware plugin 和 commissioning 配置中存在。
- `position_to_raw` 与 `raw_to_position` 必须互为可测试的标定变换。
- protocol-specific limits 必须在写设备前再次防御性限幅。


## 7. Controller 资源拓扑

当前单个 14-joint `JointTrajectoryController` 不作为正式踝部控制的推荐终态。
建议拆分为互不重叠的资源组：

```text
right_ankle_trajectory_controller
    right_ankle_cube_joint
    right_ankle_axle_joint
    right_foot_joint

left_ankle_trajectory_controller
    left_ankle_cube_joint
    left_ankle_axle_joint
    left_foot_joint

body_trajectory_controller(s)
    remaining non-overlapping joints
```

每个 controller 默认要求完整 joint goal，不依赖 14-joint controller 的 partial
goal 隐式保持语义。若未来需要全身同步轨迹，应新增明确的全身 controller 场景，
并保证不会与局部 controller 同时 claim 重叠资源。

motion_control 的 `theta_a/theta_b/theta_c` 到三个 URDF joint 的对应关系只是候选，
必须通过机构定义和真机 commissioning 冻结，不能从现有舵机 ID 顺序直接推断。


## 8. 安全与生命周期

### 8.1 状态模型

```text
UNCONFIGURED
    -> INACTIVE
    -> ACTIVE
    -> STOPPING
    -> INACTIVE

ACTIVE / STOPPING
    -> FAULTED_OR_ESTOP
    -> explicit recovery
    -> INACTIVE
```

恢复后不得自动重放旧 trajectory、旧 lease 或旧 command。

### 8.2 取消

普通 cancel 至少包含：

1. execution manager 接受 cancel 并阻断同一资源的新目标。
2. 取消 active `FollowJointTrajectory` goal。
3. controller 停止推进目标或进入经验证的 hold 策略。
4. 使用新的真实 joint samples 确认稳定。
5. 清理 lease 和 active goal。

Action cancel ACK 不等于物理停止。

### 8.3 保护停止与急停

保护停止/estop 至少包含：

1. 锁存 execution admission。
2. 取消 controller goal。
3. 通过专用安全 adapter 切换/deactivate controller 或 hardware component。
4. hardware deactivate/error 路径对所有设备执行 best-effort stop/full-off。
5. 聚合 controller/hardware 状态和真实反馈。
6. 只有满足物理证据的 backend 才能设置 `stop_confirmed=true`。

当前 Bus `stop_all()` 没有逐设备上行 ACK，PCA state 又是命令回显，因此生命周期
调用成功本身不能宣称物理停止已确认。

### 8.4 恢复

- release 必须是显式操作。
- 恢复前重新读取当前位置并将 controller command 初始化为当前 state。
- 任一设备仍 faulted、stale 或 unavailable 时不得恢复新任务。
- controller/hardware 全部确认 active 后才重新开放 admission。


## 9. 实时性边界

### 9.1 非实时层

task bridge、motion Action、scene admission、execution policy、controller manager
service 调用都属于非实时层，可以使用 Action/Service、日志和动态对象，但必须有
超时和取消边界。

### 9.2 controller update

controller `update()` 必须：

- 有界执行。
- 不阻塞文件、网络、串口或 Service。
- 不做动态参数加载。
- 避免堆分配、异常和无界容器增长。
- 只读取预先 claim 的 state/reference，写预先 claim 的 command。

### 9.3 hardware read/write

hardware `read()/write()` 只做设备 I/O、标定和错误传播。所有超时必须纳入控制
周期预算。

当前 `update_rate=50Hz` 对应 `20ms` 周期，而四个 Bus hardware component 各自
一次 read 最长可等待 `20ms`。若在同一更新线程串行阻塞，最坏时间会超过周期，
所以正式接入前必须通过 tracing 决定：

- 收紧单次 timeout/feedback budget；或
- 使用 ros2_control 支持的异步硬件执行模型；或
- 按设备总线拆分 controller manager 进程与更新频率；或
- 采用经验证的非阻塞 I/O 缓存。

不能在没有测量的情况下只提高 update rate。


## 10. 配置所有权

- `robot_description`
  - 机械 joint/link、axis、origin 和物理 joint limits 的权威来源。
- motion_control 配置
  - 机构几何、workspace、solver 参数和输出 joint names。
  - 不保存设备 ID、raw limits 或协议。
- ros2_control xacro/hardware 配置
  - hardware component、port、ID/channel、protocol、direction、offset、raw limits。
- controller YAML
  - update rate、resource groups、controller type、trajectory tolerance 和状态频率。
- robot_bringup
  - backend 和场景选择，不复制上述数值。

URDF limits、ros2_control command limits 和 solver workspace 必须通过结构化合同验
证相容。任意一处不能以“更保守”为理由长期静默覆盖另一处。


## 11. 权限模型

生产权限至少满足：

- 外部客户端只能访问 task/teleop 正式入口。
- motion_control 只能访问 execution trajectory gateway 和只读状态。
- 只有 execution manager 可以访问正式 JTC Action 和 controller/hardware lifecycle。
- 只有 active controller 可以 claim joint command interfaces。
- 只有 controller_manager 加载的 hardware plugin 可以打开设备。
- commissioning 工具只能在 controller/hardware inactive 时获得设备独占锁。
- broadcaster、diagnostics 和 perception 只读，不拥有 command interface。
- demo/BVH 不能通过 trajectory topic 绕过 execution admission。

这些规则最终应由 launch 合同、resource claim、ROS 2 security policy 和自动化
测试共同约束，不能只依赖命名约定。


## 12. 验证分层

1. 纯算法
   - IK/FK、workspace、limits、channel-to-joint mapping、Python/C++ 差分。
2. hardware 单元
   - protocol golden frames、rad/raw round-trip、错误、限幅和 lifecycle。
3. controller 单元
   - resource claim、完整 joint goal、插值、cancel、hold 和超时。
4. mock integration
   - execution gateway -> FJT -> controller -> mock hardware -> state feedback。
5. Action/DDS 安全链
   - task/teleop/motion 优先级、lease、cancel、estop、恢复和旧命令阻断。
6. 仿真
   - 两侧踝关节轨迹、状态误差、超时和并发资源冲突。
7. 真机
   - 每条总线的 I/O 预算、真实反馈、协议 stop、断线、恢复和长期稳定性。


## 13. 架构红线

以下行为禁止进入正式架构：

1. 在 hardware `read()/write()` 中执行并联机构 IK/FK。
2. motion_control 继续生成 pulse/tick 或依赖 servo ID。
3. 上层直接调用 JTC 或发布 trajectory topic 绕过 execution manager。
4. legacy 与 ros2_control backend 同时打开物理设备。
5. 单个全身 controller 与局部 controller 同时 claim 重叠 joint。
6. 把 JTC cancel、lifecycle success 或 PCA command echo 当成物理停止确认。
7. 在未确认协议、joint mapping 和 limits 时启动真机 command controller。
8. 将业务身份、lease 或场景逻辑写进 hardware plugin。
9. 将 raw 标定同时保存在 solver、bridge 和 hardware 三处。
10. 为追求语言统一一次性重写已验证的 Action、仲裁和安全状态机。


## 14. 实现前必须冻结的决策

1. `theta_a/b/c` 与左右踝 URDF joint names 的机械对应关系。
2. 每个 joint 的正方向、零点、弧度范围、raw 范围和真实协议。
3. 左右踝 controller 的资源分组及全身 controller 策略。
4. motion -> execution 的 trajectory wrapper Action schema。
5. legacy/ros2_control/mock 的单值 backend 参数和默认值。
6. controller cancel、保护停止、estop、stop-confirmed 和恢复的证据定义。
7. Bus feedback freshness、PCA estimated state 和故障传播合同。
8. controller update rate、hardware read/write timeout 和进程拆分方案。
9. `move_duration_ms` 与 JTC 插值周期的真机跟踪策略。
10. ROS 2 Humble 开发环境与目标 Jazzy 发布环境的兼容验收矩阵。

上述决策未冻结前，只允许补充事实、测试和 mock 验证，不进入默认真机切换。
