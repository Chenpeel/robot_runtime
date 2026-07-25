# 硬件抽象层设计方案

## 1. 背景与动机

当前 `robot_hardware` 包中，`BusServoSystem`、`Pca9685System` 和 `YbImuSensor` 
三个硬件驱动都直接继承 ROS 2 `hardware_interface` 基类（`SystemInterface` / 
`SensorInterface`）。三者存在大量重复模式：

- 参数解析逻辑（`required_parameter`、`parameter_or`、`parse_integer`、`parse_boolean` 等）
- 生命周期管理模板代码
- 位置标定（`PositionCalibration`）的使用方式
- 错误处理与日志模式

随着硬件替换（如换用不同型号舵机、不同 PWM 控制器、不同 IMU），如果每个新驱动
都复制这些模式，将导致维护成本急剧上升、代码质量下降。

**核心目标**：引入抽象基类层，使硬件驱动通过派生实现，而非复制粘贴。

---

## 2. 现有代码分析

### 2.1 当前类层次

```
hardware_interface::SystemInterface
├── BusServoSystem   (总线舵机, 串口)
└── Pca9685System    (PCA9685 PWM, I2C)

hardware_interface::SensorInterface
└── YbImuSensor      (IMU 传感器, I2C/串口)
```

### 2.2 两个 SystemInterface 子类的共同点

| 特性 | BusServoSystem | Pca9685System |
|------|---------------|---------------|
| 接口类型 | position 命令 + position 状态 | position 命令 + position 状态 |
| 标定 | `PositionCalibration` | `PositionCalibration` |
| 传输层 | `SerialPort` | `I2cDevice` |
| 反馈 | 真实读取 | 回显命令（开环） |
| 停止行为 | 发送停止/释放扭矩 | 设置 PWM full-off |

### 2.3 重复代码清单

1. **参数解析辅助函数**：`required_parameter`、`parameter_or<T>`、`parse_integer`、`parse_boolean`、`parse_number` —— 每个 `.cpp` 文件匿名命名空间各有一份
2. **关节接口校验**：`validate_position_interfaces` 逻辑在两处几乎相同
3. **`export_state_interfaces` / `export_command_interfaces`**：基于 `info_.joints` 的标准模式
4. **`on_init` 中的循环模式**：遍历 `info.joints`，解析标定参数，调用 `validate_calibration`
5. **生命周期骨架**：`on_configure` → 打开设备，`on_cleanup` → 关闭设备，`on_activate` → 初始化状态

### 2.4 YbImuSensor 的特殊性

`YbImuSensor` 继承 `SensorInterface`（非 `SystemInterface`），接口模型不同（纯状态导出，无命令），不适合与位置执行器共用同一个抽象基类。当前暂不纳入本次重构范围，后续可单独抽取 `SensorBase`。

---

## 3. 目标架构

```
hardware_interface::SystemInterface
└── PositionActuatorSystem          [NEW] 抽象基类
    ├── BusServoSystem              [REFACTOR]
    └── Pca9685System               [REFACTOR]

hardware_interface::SensorInterface
└── YbImuSensor                     [UNCHANGED]

robot_hardware::param_utils         [NEW] 公共参数解析工具（头文件）
```

### 3.1 PositionActuatorSystem 抽象基类

负责所有"位置命令 → 位置状态"型执行器的公共逻辑：

- 关节配置结构体与标定信息的统一管理
- `export_state_interfaces()` / `export_command_interfaces()` 的标准实现
- `on_init()` 的公共流程（参数解析、关节校验、标定构建）
- `read()` / `write()` 中公共的前置检查

子类只需实现：

| 纯虚函数 | 职责 |
|---------|------|
| `do_configure()` | 打开具体传输层（串口/I2C/...） |
| `do_cleanup()` | 关闭具体传输层 |
| `do_read_single(index)` | 读取单个关节的真实位置 |
| `do_write_single(index)` | 向单个关节发送位置命令 |
| `do_stop_single(index)` | 停止/释放单个关节（deactivate 时调用） |

### 3.2 公共参数解析工具 (param_utils.hpp)

将三个 `.cpp` 文件中重复的匿名命名空间辅助函数提取到公共头文件：

```cpp
namespace robot_hardware::param_utils {
  // 类型化参数读取
  std::string required_param(map, name);
  template<T> T param_or(map, name, fallback);
  std::int64_t parse_integer(text, name);
  double parse_number(text, name);
  bool parse_boolean(text, name);
  
  // 关节校验
  void validate_position_interfaces(joint);
}
```

---

## 4. 详细设计

### 4.1 PositionActuatorSystem 类定义

```cpp
class PositionActuatorSystem : public hardware_interface::SystemInterface
{
public:
  // 关节配置（子类可见）
  struct JointConfig {
    PositionCalibration calibration;
  };

  // --- SystemInterface 实现 ---
  hardware_interface::CallbackReturn on_init(const HardwareInfo & info) final;
  std::vector<StateInterface> export_state_interfaces() final;
  std::vector<CommandInterface> export_command_interfaces() final;
  hardware_interface::CallbackReturn on_configure(const State &) final;
  hardware_interface::CallbackReturn on_cleanup(const State &) final;
  hardware_interface::return_type read(const Time &, const Duration &) final;
  hardware_interface::return_type write(const Time &, const Duration &) final;

protected:
  // --- 子类必须实现 ---
  virtual bool do_configure() = 0;
  virtual bool do_cleanup() = 0;
  virtual std::optional<double> do_read_single(std::size_t index) = 0;
  virtual bool do_write_single(std::size_t index, double position) = 0;
  virtual void do_stop_single(std::size_t index) = 0;

  // --- 子类可访问的数据 ---
  std::vector<JointConfig> joint_configs_;
  std::vector<double> commands_;
  std::vector<double> states_;
  const hardware_interface::HardwareInfo & hw_info() const;
};
```

### 4.2 on_init 流程（Template Method 模式）

```
on_init(info)
  1. 调用 SystemInterface::on_init(info)
  2. 验证关节非空、接口合规
  3. 调用子类钩子 parse_hardware_params(info.hardware_parameters)  — 可选
  4. 遍历 joints，调用子类钩子 parse_joint_config(joint) → JointConfig
  5. 校验标定 validate_calibration
  6. 初始化 commands_ 和 states_
```

### 4.3 BusServoSystem 改造

改造后只保留舵机特有的：
- `Servo` 内部结构体（id, protocol, consecutive_errors 等）
- 串口管理
- 协议编解码调用
- 循环反馈读（feedback_per_cycle_）逻辑
- `on_activate` 中读取初始位置的特殊流程

移交给基类的：
- `export_state_interfaces / export_command_interfaces`
- `on_configure / on_cleanup` 骨架
- 参数解析辅助函数
- 关节校验

### 4.4 Pca9685System 改造

改造后只保留 PCA9685 特有的：
- I2C 寄存器操作
- PWM 频率配置
- `read()` 中回显命令（开环特性）
- `initialize_controller()` 寄存器初始化

移交给基类的：
- 同上

---

## 5. 文件变更清单

| 操作 | 文件 |
|------|------|
| **新建** | `include/robot_hardware/position_actuator_system.hpp` |
| **新建** | `include/robot_hardware/param_utils.hpp` |
| **新建** | `src/position_actuator_system.cpp` |
| **修改** | `include/robot_hardware/bus_servo_system.hpp` — 改继承 |
| **修改** | `src/bus_servo_system.cpp` — 移除公共代码，实现纯虚函数 |
| **修改** | `include/robot_hardware/pca9685_system.hpp` — 改继承 |
| **修改** | `src/pca9685_system.cpp` — 移除公共代码，实现纯虚函数 |
| **修改** | `CMakeLists.txt` — 添加新源文件 |

---

## 6. 风险评估

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| 抽象层引入性能开销 | 虚函数调用 | 虚函数只在生命周期切换时调用，控制循环中只有 `read`/`write`，开销可忽略 |
| 破坏现有配置兼容性 | 启动失败 | `on_init` 参数解析逻辑不变，配置文件无需修改 |
| 子类行为回归 | 舵机/IMU异常 | 现有单元测试覆盖 `test_bus_servo_protocol`、`test_conversion`，重构后全量运行 |

---

## 7. 后续扩展

- 若新增舵机型号（如未来 X 系列），只需实现 `PositionActuatorSystem` 的 5 个纯虚函数
- 若新增传感器型号，可参照此模式抽取 `SensorBase`
- `param_utils` 后续可被 `sensor_hardware` 包复用
