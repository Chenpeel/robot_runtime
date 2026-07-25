// Copyright 2026 chenpeel
//
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
//
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
//
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
// THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.


#ifndef ROBOT_HARDWARE__POSITION_ACTUATOR_SYSTEM_HPP_
#define ROBOT_HARDWARE__POSITION_ACTUATOR_SYSTEM_HPP_

#include <cstddef>
#include <optional>
#include <string>
#include <vector>

#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/duration.hpp"
#include "rclcpp/time.hpp"
#include "rclcpp_lifecycle/state.hpp"

#include "robot_hardware/conversion.hpp"
#include "robot_hardware/param_utils.hpp"

namespace robot_hardware
{

/**
 * @brief 位置执行器的抽象基类。
 *
 * 封装所有 position-command / position-state 型硬件驱动共用的参数解析、
 * 接口导出、生命周期骨架和读写调度逻辑。
 *
 * 子类只需要实现五个纯虚函数即可得到一个功能完整的 ROS 2
 * SystemInterface 硬件插件：
 *
 * - do_configure()       打开传输层（串口 / I2C / ...）
 * - do_cleanup()         关闭传输层
 * - do_read_single()     读取单个关节的物理位置
 * - do_write_single()    向单个关节写入位置命令
 * - do_stop_single()     停止/释放单个关节
 *
 * 子类也可以覆盖以下虚函数来定制初始化流程：
 *
 * - parse_hardware_params()   解析全局硬件参数
 * - parse_joint_config()      解析单个关节的专属配置
 * - on_activate_success()    激活成功后的后置处理
 */
class PositionActuatorSystem : public hardware_interface::SystemInterface
{
public:
  /**
   * @brief 关节配置，子类可扩展。
   */
  struct JointConfig
  {
    PositionCalibration calibration;
  };

  // --- SystemInterface 实现（子类可按需覆盖） ---

  hardware_interface::CallbackReturn on_init(
    const hardware_interface::HardwareInfo & info) override;

  std::vector<hardware_interface::StateInterface> export_state_interfaces() override;

  std::vector<hardware_interface::CommandInterface> export_command_interfaces() override;

  hardware_interface::CallbackReturn on_configure(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_activate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_deactivate(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::CallbackReturn on_cleanup(
    const rclcpp_lifecycle::State & previous_state) override;

  hardware_interface::return_type read(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

  hardware_interface::return_type write(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

protected:
  // ======== 子类必须实现的纯虚函数 ========

  /**
   * @brief 打开硬件传输层。
   * @return true 成功，false 失败。
   */
  virtual bool do_configure() = 0;

  /**
   * @brief 关闭硬件传输层。
   * @return true 成功，false 失败。
   */
  virtual bool do_cleanup() = 0;

  /**
   * @brief 读取单个关节的物理位置。
   * @return 位置值（弧度），或 nullopt 表示读取失败。
   */
  virtual std::optional<double> do_read_single(std::size_t index) = 0;

  /**
   * @brief 向单个关节写入位置命令。
   * @param index 关节索引。
   * @param position 目标位置（弧度）。
   * @return true 成功，false 失败。
   */
  virtual bool do_write_single(std::size_t index, double position) = 0;

  /**
   * @brief 停止/释放单个关节（deactivate 时调用）。
   */
  virtual void do_stop_single(std::size_t index) = 0;

  // ======== 子类可选覆盖的虚函数 ========

  /**
   * @brief 解析全局硬件参数（在 on_init 中遍历关节之前调用）。
   *
   * 默认实现为空。子类可在此解析 transport、baud_rate 等全局参数。
   *
   * @param parameters info.hardware_parameters
   * @throws std::invalid_argument 参数非法时抛出。
   */
  virtual void parse_hardware_params(
    const std::unordered_map<std::string, std::string> & parameters);

  /**
   * @brief 解析单个关节的专属配置。
   *
   * 默认实现从 joint 的 min/max 和 parameters 中读取标定字段，
   * 返回填充好的 JointConfig。
   *
   * 子类可覆盖以返回包含扩展字段的派生配置对象。
   *
   * @param joint 关节组件信息。
   * @return 关节配置（子类可返回派生类型）。
   * @throws std::invalid_argument 参数非法时抛出。
   */
  virtual JointConfig parse_joint_config(
    const hardware_interface::ComponentInfo & joint);

  /**
   * @brief 激活成功后的回调（在 on_activate 末尾调用）。
   *
   * 默认实现为空。子类可在此完成首次位置读取、状态同步等。
   */
  virtual void on_activate_success();

  // ======== 子类可访问的数据 ========

  /// 关节配置列表（on_init 完成后填充）。
  std::vector<JointConfig> joint_configs_;

  /// 命令值数组（由 export_command_interfaces 暴露给 controller_manager）。
  std::vector<double> commands_;

  /// 状态值数组（由 export_state_interfaces 暴露给 controller_manager）。
  std::vector<double> states_;

  /// 硬件信息引用（便捷访问）。
  const hardware_interface::HardwareInfo & hw_info() const { return info_; }

private:
  void validate_joint_declarations();
};

}  // namespace robot_hardware

#endif  // ROBOT_HARDWARE__POSITION_ACTUATOR_SYSTEM_HPP_
