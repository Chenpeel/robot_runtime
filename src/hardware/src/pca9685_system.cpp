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


#include "robot_hardware/pca9685_system.hpp"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <limits>
#include <stdexcept>
#include <string>
#include <thread>
#include <unordered_map>
#include <vector>

#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "rclcpp/rclcpp.hpp"

namespace robot_hardware
{
namespace
{

constexpr std::uint8_t kMode1 = 0x00;
constexpr std::uint8_t kMode2 = 0x01;
constexpr std::uint8_t kFirstLed = 0x06;
constexpr std::uint8_t kPrescale = 0xFE;
constexpr std::uint8_t kMode1Restart = 0x80;
constexpr std::uint8_t kMode1AutoIncrement = 0x20;
constexpr std::uint8_t kMode1Sleep = 0x10;
constexpr std::uint8_t kMode2OutputDrive = 0x04;
constexpr std::uint8_t kFullOff = 0x10;
constexpr double kOscillatorFrequency = 25000000.0;
constexpr double kPwmResolution = 4096.0;

const rclcpp::Logger kLogger = rclcpp::get_logger("robot_hardware.pca9685_system");

}  // namespace

// ======== PositionActuatorSystem 虚函数实现 ========

void Pca9685System::parse_hardware_params(
  const std::unordered_map<std::string, std::string> & parameters)
{
  using param_utils::parameter_or_default;
  using param_utils::parse_boolean;
  using param_utils::parse_integer;
  using param_utils::parse_number;

  i2c_device_ = parameter_or_default(parameters, "i2c_device", "/dev/i2c-1");
  if (i2c_device_.empty()) {
    throw std::invalid_argument("i2c_device cannot be empty");
  }

  const auto address = parse_integer(
    parameter_or_default(parameters, "address", "64"), "address");
  if (address < 0 || address > 0x7F) {
    throw std::invalid_argument("address must be in [0, 127]");
  }
  address_ = static_cast<std::uint8_t>(address);

  frequency_hz_ = parse_number(
    parameter_or_default(parameters, "frequency", "50"), "frequency");
  if (frequency_hz_ <= 0.0) {
    throw std::invalid_argument("frequency must be > 0");
  }
  const auto prescale = std::llround(
    kOscillatorFrequency / (kPwmResolution * frequency_hz_) - 1.0);
  if (prescale < 3 || prescale > 255) {
    throw std::invalid_argument("frequency exceeds PCA9685 prescale range");
  }

  const auto min_pwm = parse_integer(
    parameter_or_default(parameters, "min_pwm", "110"), "min_pwm");
  const auto max_pwm = parse_integer(
    parameter_or_default(parameters, "max_pwm", "520"), "max_pwm");
  if (min_pwm < 0 || max_pwm > 4095 || min_pwm >= max_pwm) {
    throw std::invalid_argument("PWM range must satisfy 0 <= min_pwm < max_pwm <= 4095");
  }
  min_pwm_ = static_cast<std::uint16_t>(min_pwm);
  max_pwm_ = static_cast<std::uint16_t>(max_pwm);
  deactivate_full_off_ = parse_boolean(
    parameter_or_default(parameters, "deactivate_full_off", "true"),
    "deactivate_full_off");
}

PositionActuatorSystem::JointConfig Pca9685System::parse_joint_config(
  const hardware_interface::ComponentInfo & joint)
{
  using param_utils::parse_integer;
  using param_utils::parse_number;

  // 先让基类填充标定信息（position_min/max, offset, direction）
  auto config = PositionActuatorSystem::parse_joint_config(joint);

  // 设置 PCA9685 特有的 raw 范围
  config.calibration.raw_min = static_cast<double>(min_pwm_);
  config.calibration.raw_max = static_cast<double>(max_pwm_);

  // 解析 PCA9685 专属字段，存入并行数组
  const auto channel = parse_integer(
    param_utils::required_parameter(joint.parameters, "channel"), "channel");
  if (channel < 0 || channel > 15) {
    throw std::invalid_argument(
            "joint " + joint.name + " channel must be in [0, 15]");
  }
  // 检查重复 channel
  for (const auto existing : channels_) {
    if (existing == static_cast<std::uint8_t>(channel)) {
      throw std::invalid_argument(
              "duplicate PCA9685 channel: " + std::to_string(channel));
    }
  }
  channels_.push_back(static_cast<std::uint8_t>(channel));

  double offset_raw = 0.0;
  const auto offset = joint.parameters.find("offset_raw");
  if (offset != joint.parameters.end()) {
    offset_raw = parse_number(offset->second, joint.name + ".offset_raw");
  }
  offset_raws_.push_back(offset_raw);

  return config;
}

bool Pca9685System::do_configure()
{
  device_.open(i2c_device_, address_);
  initialize_controller();
  last_pwm_.assign(channels_.size(), -1);
  RCLCPP_INFO(
    kLogger, "PCA9685 configured: device=%s address=0x%02X frequency=%.3fHz",
    i2c_device_.c_str(), static_cast<unsigned int>(address_), frequency_hz_);
  return true;
}

bool Pca9685System::do_cleanup()
{
  device_.close();
  last_pwm_.clear();
  return true;
}

std::optional<double> Pca9685System::do_read_single(std::size_t /*index*/)
{
  // PCA9685 无反馈，由 read() 整体回显
  return 0.0;  // 不会被使用，read() 已覆盖
}

bool Pca9685System::do_write_single(std::size_t index, double position)
{
  const double converted = position_to_raw(position, joint_configs_[index].calibration);
  const double adjusted = std::clamp(
    converted + offset_raws_[index],
    static_cast<double>(min_pwm_), static_cast<double>(max_pwm_));
  const auto pwm = static_cast<std::uint16_t>(std::lround(adjusted));

  if (static_cast<std::size_t>(index) < last_pwm_.size() &&
    last_pwm_[index] == static_cast<int>(pwm))
  {
    return true;  // 无变化，跳过写入
  }
  write_channel(channels_[index], pwm);
  if (static_cast<std::size_t>(index) < last_pwm_.size()) {
    last_pwm_[index] = static_cast<int>(pwm);
  }
  return true;
}

void Pca9685System::do_stop_single(std::size_t index)
{
  if (!deactivate_full_off_ || !device_.is_open()) {
    return;
  }
  const auto base_register = static_cast<std::uint8_t>(kFirstLed + 4U * channels_[index]);
  device_.write_block(base_register, {0x00, 0x00, 0x00, kFullOff});
  if (static_cast<std::size_t>(index) < last_pwm_.size()) {
    last_pwm_[index] = -1;
  }
}

// ======== 覆盖的读写（PCA9685 开环特性） ========

hardware_interface::return_type Pca9685System::read(
  const rclcpp::Time &, const rclcpp::Duration &)
{
  // 开环：状态回显最近命令
  states_ = commands_;
  return hardware_interface::return_type::OK;
}

hardware_interface::return_type Pca9685System::write(
  const rclcpp::Time &, const rclcpp::Duration &)
{
  if (!device_.is_open()) {
    RCLCPP_ERROR(kLogger, "PCA9685 device not open, cannot write commands");
    return hardware_interface::return_type::ERROR;
  }

  try {
    for (std::size_t index = 0; index < joint_configs_.size(); ++index) {
      if (!do_write_single(index, commands_[index])) {
        return hardware_interface::return_type::ERROR;
      }
    }
  } catch (const std::exception & error) {
    RCLCPP_ERROR(kLogger, "PCA9685 write failed: %s", error.what());
    return hardware_interface::return_type::ERROR;
  }
  return hardware_interface::return_type::OK;
}

// ======== PCA9685 寄存器操作 ========

void Pca9685System::initialize_controller()
{
  device_.write_byte(kMode1, 0x00);
  std::this_thread::sleep_for(std::chrono::milliseconds(10));
  device_.write_byte(kMode2, kMode2OutputDrive);

  const auto current_mode = device_.read_block(kMode1, 1).front();
  const auto sleep_mode = static_cast<std::uint8_t>(
    (current_mode & static_cast<std::uint8_t>(~kMode1Restart)) | kMode1Sleep);
  const auto prescale = static_cast<std::uint8_t>(std::llround(
      kOscillatorFrequency / (kPwmResolution * frequency_hz_) - 1.0));

  device_.write_byte(kMode1, sleep_mode);
  device_.write_byte(kPrescale, prescale);
  device_.write_byte(kMode1, current_mode);
  std::this_thread::sleep_for(std::chrono::milliseconds(5));
  device_.write_byte(
    kMode1, static_cast<std::uint8_t>(current_mode | kMode1Restart | kMode1AutoIncrement));
}

void Pca9685System::write_channel(std::uint8_t channel, std::uint16_t pwm)
{
  const auto base_register = static_cast<std::uint8_t>(kFirstLed + 4U * channel);
  device_.write_block(
    base_register,
    {0x00, 0x00, static_cast<std::uint8_t>(pwm & 0xFFU),
      static_cast<std::uint8_t>((pwm >> 8U) & 0x0FU)});
}

}  // namespace robot_hardware

PLUGINLIB_EXPORT_CLASS(
  robot_hardware::Pca9685System, hardware_interface::SystemInterface)

}  // namespace robot_hardware

PLUGINLIB_EXPORT_CLASS(robot_hardware::Pca9685System, hardware_interface::SystemInterface)
