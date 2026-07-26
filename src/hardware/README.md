# robot_hardware

`robot_hardware` 将舵机与 YbImu 作为 ROS 2 Control 硬件组件加载。包内不订阅
业务命令话题；资源声明、控制器独占和生命周期由 `controller_manager` 负责。

## 插件

- `robot_hardware/BusServoSystem`：一个实例独占一个串口，可管理多个 LX/ZL
  舵机；导出弧度制 `position` command/state。`raw_min`/`raw_max` 使用协议原始
  单位，LX 的常用受控区间为 `125..875`，ZL 为 `833..2167`。
- `robot_hardware/Pca9685System`：一个实例独占一块 PCA9685；导出弧度制
  `position` command/state。PCA9685 无编码器，state 是最后一次成功写入的估计值。
- `robot_hardware/YbImuSensor`：通过 I2C 或串口读取 YbImu，导出标准 IMU
  orientation、angular velocity、linear acceleration 接口。加速度已由 g 转为 m/s²。

总线协议必须在每个 joint 上显式配置为 `lx` 或 `zl`。自动探测、文件读写和长
时间等待不会进入实时更新循环。`feedback_per_cycle` 控制每次 `read()` 最多轮询的
舵机数，将单周期阻塞限制为该值乘 `read_timeout_ms`。

## 配置原则

所有硬件数值只存在于 `<ros2_control>` 参数中：串口、ID、协议、方向、零偏、
raw 限位与弧度限位不得再由不同 JSON 文件重复定义。完整字段示例见
`urdf/example_robot.urdf.xacro`。

PCA9685 的 `position` state 是开环估计，不代表真实关节反馈。对需要闭环安全保证的
关节必须增加编码器或改用能够返回真实位置的执行器。

## 运行

```bash
ros2 launch robot_hardware ros2_control.launch.py \
  description_file:=/path/to/robot.urdf.xacro
```

同一个串口或 I2C 设备不能同时由旧 Python 驱动与本包插件打开。切换到此启动方式
前，应停止 `bus_port_driver`、`pca_servo_driver` 和 `imu_*_driver`。

维护类指令（修改 ID、恢复出厂、校准）不属于实时 command interface，应该在硬件
inactive 且独占设备时由单独 commissioning 工具执行。
