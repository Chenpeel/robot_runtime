# 当前模块职责快照

## 1. 文档定位

本文记录截至 2026-03-19 的仓库当前事实，用于补充说明现有模块到底已经承担了
什么职责。

它与长期规划文档的关系如下：

- `docs/module_responsibilities.md`
  - 保留为长期目标职责文档。
- 本文
  - 只描述当前代码里已经存在的模块、节点和边界现状。

因此，本文不替代长期规划，也不把未来模块写成已落地事实。


## 2. 当前模块总览

当前仓库大体可以分成六个职责域：

- 遥控与调试入口
  - `websocket_bridge`
- 执行器驱动
  - `servo_hardware`
- 传感器接入
  - `sensor_hardware` 代码模块，尚未独立成 ROS 包
- 控制原型
  - `parallel_3dof_controller`
- 仿真桥接
  - `sim_servo_bridge_cpp`
  - `websocket_bridge/isaac_bridge_node`
- 接口、工具与描述资源
  - `servo_msgs`
  - `record_load_action`
  - `robot_description`
  - `mjc_viewer`


## 3. 当前模块职责

### 3.1 `websocket_bridge`

- 状态
  - 已实现，且处于明显的过渡态。
- 当前承接位置
  - 目录：`src/websocket`
  - ROS 包名：`websocket_bridge`
- 当前主要职责
  - 提供 WebSocket 服务端接入。
  - 解析 WebSocket JSON 消息并下发舵机命令。
  - 订阅 `/servo/state` 并向 WebSocket 客户端广播状态。
  - 订阅 `/sensor/imu` 并向 WebSocket 客户端广播传感器数据。
  - 承接心跳、状态查询和调试日志聚合。
  - 通过 `record_load_action` 触发 BVH 动作播放。
  - 包内还直接提供 `isaac_bridge_node`。
  - 包内 `full_system.launch.py` 还承担整机主 launch 编排。
- 当前主要输入
  - WebSocket 客户端消息
  - `/servo/state`
  - `/sensor/imu`
- 当前主要输出
  - `/servo/command`
  - WebSocket 状态广播
  - WebSocket IMU 广播
- 当前非职责
  - 不应该长期承担执行仲裁。
  - 不应该长期承担仿真责任域的主入口。
  - 不应该长期承载 demo/BVH 与系统级 launch 编排。
- 当前问题
  - 遥控、调试、状态桥接、BVH、仿真桥和系统编排混在同一个包内。
  - 直接依赖驱动级 `/servo/command`，没有经过独立执行边界。
- 与长期规划的关系
  - 长期上更接近 `teleoperation_bridge` 的前身。
  - 仿真相关部分应逐步拆到 `simulation_bridge` 责任域。
  - demo/BVH 应降级为可选能力，而不是主运行链路中心。

### 3.2 `servo_hardware`

- 状态
  - 已实现，核心驱动链路已在使用中，但包边界仍是过渡态。
- 当前承接位置
  - 目录：`src/hardware`
  - ROS 包名：`servo_hardware`
- 当前主要职责
  - 提供总线舵机驱动。
  - 提供 PCA 舵机驱动。
  - 提供协议路由、协议探测和协议注册能力。
  - 承接驱动级服务，例如总线指令和角度读取。
- 当前主要输入
  - `/servo/command`
  - 读写服务请求
- 当前主要输出
  - `/servo/state`
  - 驱动诊断与协议错误信息
- 当前非职责
  - 不负责任务语义理解。
  - 不负责执行仲裁。
  - 不负责轨迹规划。
- 当前问题
  - 包内同时导出了 `sensor_hardware` 里的 IMU 节点。
  - “执行器驱动”和“传感器驱动”在 ROS 包层面仍未分开。
- 与长期规划的关系
  - 长期应只保留执行器和协议相关能力。
  - 传感器节点应迁出为独立 `sensor_hardware` 包。

### 3.3 `sensor_hardware`

- 状态
  - 代码已存在，但尚未成为独立 ROS 包。
- 当前承接位置
  - 代码目录：`src/hardware/sensor_hardware`
  - 当前通过 `servo_hardware` 的 `setup.py` 导出入口点。
- 当前主要职责
  - 提供 IMU 的 I2C 驱动节点。
  - 提供 IMU 的串口驱动节点。
  - 发布 `/sensor/imu` 传感器数据。
- 当前主要输入
  - I2C 设备读取
  - 串口设备读取
- 当前主要输出
  - `/sensor/imu`
  - 传感器诊断日志
- 当前非职责
  - 不负责控制决策。
  - 不负责视觉感知。
  - 不负责执行器协议。
- 当前问题
  - 没有独立 `package.xml`、`setup.py` 和安装边界。
  - 仍然依附在 `servo_hardware` 包里发布和启动。
- 与长期规划的关系
  - 长期应升级为独立 `sensor_hardware` ROS 包。

### 3.4 `parallel_3dof_controller`

- 状态
  - 已实现，但属于控制原型和过渡方案。
- 当前承接位置
  - 目录：`src/parallel_3dof_controller`
  - ROS 包名：`parallel_3dof_controller`
- 当前主要职责
  - 订阅脚踝 RPY 姿态命令。
  - 进行 3-DOF 并联机构运动学求解。
  - 将姿态结果直接转换为 `ServoCommand`。
  - 发布 theta 反馈用于调试。
- 当前主要输入
  - `~/ankle_rpy`
- 当前主要输出
  - `~/servo/command`，launch 中会 remap 到 `/servo/command`
  - `~/ankle_theta`
- 当前非职责
  - 不负责执行仲裁。
  - 不负责任务级调度。
  - 不负责驱动协议本身。
- 当前问题
  - 当前直接依赖 `servo_msgs`。
  - 当前直接面向驱动级命令输出，没有独立执行边界。
- 与长期规划的关系
  - 长期更接近 `motion_control` 的前身。
  - 后续应改成先输出到执行边界，而不是直接发布 `ServoCommand`。

### 3.5 `sim_servo_bridge_cpp`

- 状态
  - 已实现，可选启用，处于过渡态。
- 当前承接位置
  - 目录：`src/sim_servo_bridge_cpp`
  - ROS 包名：`sim_servo_bridge_cpp`
- 当前主要职责
  - 将 `/sim/joint_cmd` 转换为 `/servo/command`。
  - 将 `/servo/state` 转换为 `/sim/joint_state_fb`。
  - 在仿真关节表示和当前舵机表示之间做驱动级桥接。
- 当前主要输入
  - `/sim/joint_cmd`
  - `/servo/state`
- 当前主要输出
  - `/servo/command`
  - `/sim/joint_state_fb`
- 当前非职责
  - 不负责高层控制规划。
  - 不负责人工遥控入口。
  - 不负责执行仲裁。
- 当前问题
  - 仍然直接耦合驱动级接口。
  - 当前通过 `websocket_bridge` 的主 launch 启停，仿真边界不独立。
- 与长期规划的关系
  - 长期应被纳入统一的 `simulation_bridge` 责任域。

### 3.6 `servo_msgs`

- 状态
  - 已实现，且是当前相对稳定的驱动级接口边界。
- 当前承接位置
  - 目录：`src/servo_msgs`
  - ROS 包名：`servo_msgs`
- 当前主要职责
  - 提供舵机命令、状态和相关服务定义。
  - 作为当前硬件链路的正式接口。
- 当前主要输入输出
  - 被 `servo_hardware`、`parallel_3dof_controller`、`websocket_bridge`、
    `sim_servo_bridge_cpp` 等包共同使用。
- 当前非职责
  - 不表达任务语义。
  - 不表达运动学层命令。
  - 不表达外部任务服务接口。
- 当前问题
  - 上层控制和桥接模块当前对它的直接依赖范围过大。
- 与长期规划的关系
  - 长期应继续保留为驱动级边界。
  - 上层模块应逐步减少对它的长期直接依赖。

### 3.7 `record_load_action`

- 状态
  - 已实现，但更适合作为工具/演示包。
- 当前承接位置
  - 目录：`src/record_load_action`
  - ROS 包名：`record_load_action`
- 当前主要职责
  - 承载 BVH 资源配置。
  - 提供 BVH 动作播放与静态转换工具。
- 当前主要输入
  - BVH 动作文件
  - WebSocket 侧触发的播放请求
- 当前主要输出
  - 通过回调向上层发布动作对应的舵机命令
- 当前非职责
  - 不负责正式遥控入口。
  - 不负责系统执行仲裁。
- 当前问题
  - 当前被 `websocket_bridge` 直接依赖，导致 demo 能力渗入主链路。
- 与长期规划的关系
  - 长期应保留为可选工具/演示资源，而不是正式主链路核心。

### 3.8 `robot_description`

- 状态
  - 已实现，职责边界相对清晰。
- 当前承接位置
  - 目录：`src/robot_description`
  - ROS 包名：`robot_description`
- 当前主要职责
  - 承载 URDF、mesh、MJCF、纹理与展示资源。
- 当前主要输入输出
  - 为描述、展示、仿真和标定提供静态资源。
- 当前非职责
  - 不负责控制逻辑。
  - 不负责执行仲裁。
  - 不负责驱动协议。
- 当前问题
  - 当前没有明显职责漂移问题。
- 与长期规划的关系
  - 长期继续作为描述资源域存在即可。

### 3.9 `mjc_viewer`

- 状态
  - 已实现，属于展示与仿真辅助模块。
- 当前承接位置
  - 目录：`src/mjc_viewer`
  - ROS 包名：`mjc_viewer`
- 当前主要职责
  - 提供 MuJoCo 视图与仿真展示辅助能力。
- 当前主要输入输出
  - 依赖模型和状态数据做展示。
- 当前非职责
  - 不负责正式控制链路。
  - 不负责驱动层。
  - 不负责遥控入口。
- 当前问题
  - 当前没有进入正式执行链路，但文档中需要持续强调它属于辅助域。
- 与长期规划的关系
  - 长期应继续留在描述/展示辅助域，不进入执行仲裁主链。


## 4. 当前尚未落地的目标模块

下列名称出现在长期规划文档中，但当前仓库里还没有对应的正式落地包：

- `execution_manager`
  - 当前不存在独立实现。
- `motion_control`
  - 当前只有原型 `parallel_3dof_controller`，还不能等同于正式
    `motion_control`。
- `teleoperation_bridge`
  - 当前只有混合职责的 `websocket_bridge`，还不能直接等同于正式
    `teleoperation_bridge`。
- `simulation_bridge`
  - 当前只有 `isaac_bridge_node` 和 `sim_servo_bridge_cpp` 这类分散实现。
- `motion_msgs`
  - 当前不存在独立消息包。
- `task_service_bridge`
  - 当前不存在独立实现。
- `task_api_msgs`
  - 当前不存在独立消息包。
- `speech_interface`
  - 当前不存在独立实现。
- `vision_perception`
  - 当前不存在独立实现。


## 5. 当前事实到长期规划的映射

为了避免长期规划与当前事实之间断层，现阶段可以按下面的方式理解映射关系：

- `websocket_bridge`
  - 当前事实：teleop/debug/status/demo/sim 的混合包
  - 长期去向：以 `teleoperation_bridge` 为主，仿真相关拆到
    `simulation_bridge`
- `parallel_3dof_controller`
  - 当前事实：直接输出驱动级舵机命令的控制原型
  - 长期去向：演进为 `motion_control`
- `servo_hardware`
  - 当前事实：执行器驱动包，同时挂着传感器入口
  - 长期去向：保留执行器与协议能力
- `sensor_hardware`
  - 当前事实：代码模块已存在，但包未独立
  - 长期去向：独立成 `sensor_hardware` ROS 包
- `sim_servo_bridge_cpp` 与 `isaac_bridge_node`
  - 当前事实：分散的仿真桥实现
  - 长期去向：收口到 `simulation_bridge`


## 6. 简短结论

当前仓库已经有可运行的遥控、驱动、传感器、仿真和控制原型，但模块边界明显
还处于过渡态。最重要的不是把未来名字提前套到现有代码上，而是先承认当前现
实：`websocket_bridge` 过大、`parallel_3dof_controller` 直连驱动、
`sensor_hardware` 还没独立、仿真桥还未收口。长期规划应继续保留，当前事实
则由本文负责单独记录。
