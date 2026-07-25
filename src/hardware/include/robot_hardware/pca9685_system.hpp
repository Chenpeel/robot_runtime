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


#ifndef ROBOT_HARDWARE__PCA9685_SYSTEM_HPP_
#define ROBOT_HARDWARE__PCA9685_SYSTEM_HPP_

#include <cstdint>
#include <string>
#include <vector>

#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/duration.hpp"
#include "rclcpp/time.hpp"
#include "rclcpp_lifecycle/state.hpp"

#include "robot_hardware/conversion.hpp"
#include "robot_hardware/i2c_device.hpp"
#include "robot_hardware/position_actuator_system.hpp"

namespace robot_hardware
{

/**
 * @brief PCA9685 位置控制硬件插件。
 *
 * PCA9685 没有位置反馈能力，因此导出的 position state
 * 是最近命令的估计回显，
 * 不能视为关节的实测位置。
 */
class Pca9685System : public PositionActuatorSystem
{
public:
  hardware_interface::return_type read(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;
  hardware_interface::return_type write(
    const rclcpp::Time & time, const rclcpp::Duration & period) override;

private:
  // --- PositionActuatorSystem 纯虚函数实现 ---
  bool do_configure() override;
  bool do_cleanup() override;
  std::optional<double> do_read_single(std::size_t index) override;
  bool do_write_single(std::size_t index, double position) override;
  void do_stop_single(std::size_t index) override;

  // --- PositionActuatorSystem 可选覆盖 ---
  void parse_hardware_params(
    const std::unordered_map<std::string, std::string> & parameters) override;
  JointConfig parse_joint_config(
    const hardware_interface::ComponentInfo & joint) override;

  void initialize_controller();
  void write_channel(std::uint8_t channel, std::uint16_t pwm);

  I2cDevice device_;
  std::string i2c_device_{"/dev/i2c-1"};
  std::uint8_t address_{64};
  double frequency_hz_{50.0};
  std::uint16_t min_pwm_{110};
  std::uint16_t max_pwm_{520};
  bool deactivate_full_off_{true};

  /// PCA9685 专属字段：每个关节的通道号和 PWM 偏置
  std::vector<std::uint8_t> channels_;
  std::vector<double> offset_raws_;

  std::vector<int> last_pwm_;
};

}  // namespace robot_hardware

#endif  // ROBOT_HARDWARE__PCA9685_SYSTEM_HPP_
