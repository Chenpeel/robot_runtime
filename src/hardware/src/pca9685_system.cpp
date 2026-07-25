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

std::string parameter_or_default(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name, const std::string & default_value)
{
  const auto value = parameters.find(name);
  return value == parameters.end() ? default_value : value->second;
}

std::int64_t parse_integer(const std::string & value, const std::string & name)
{
  std::size_t parsed = 0;
  std::int64_t result = 0;
  try {
    result = std::stoll(value, &parsed, 0);
  } catch (const std::exception &) {
    throw std::invalid_argument(name + " 必须是整数");
  }
  if (parsed != value.size()) {
    throw std::invalid_argument(name + " 必须是整数");
  }
  return result;
}

double parse_number(const std::string & value, const std::string & name)
{
  std::size_t parsed = 0;
  double result = 0.0;
  try {
    result = std::stod(value, &parsed);
  } catch (const std::exception &) {
    throw std::invalid_argument(name + " 必须是有限数值");
  }
  if (parsed != value.size() || !std::isfinite(result)) {
    throw std::invalid_argument(name + " 必须是有限数值");
  }
  return result;
}

bool parse_boolean(const std::string & value, const std::string & name)
{
  if (value == "true" || value == "1") {
    return true;
  }
  if (value == "false" || value == "0") {
    return false;
  }
  throw std::invalid_argument(name + " 必须为 true 或 false");
}

const std::string & required_joint_parameter(
  const hardware_interface::ComponentInfo & joint, const std::string & name)
{
  const auto value = joint.parameters.find(name);
  if (value == joint.parameters.end() || value->second.empty()) {
    throw std::invalid_argument("joint " + joint.name + " 缺少参数 " + name);
  }
  return value->second;
}

}  // namespace

hardware_interface::CallbackReturn Pca9685System::on_init(
  const hardware_interface::HardwareInfo & info)
{
  if (hardware_interface::SystemInterface::on_init(info) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }

  try {
    if (info_.joints.empty()) {
      throw std::invalid_argument("至少需要配置一个 joint");
    }

    i2c_device_ = parameter_or_default(info_.hardware_parameters, "i2c_device", "/dev/i2c-1");
    if (i2c_device_.empty()) {
      throw std::invalid_argument("i2c_device 不能为空");
    }

    const auto address = parse_integer(
      parameter_or_default(info_.hardware_parameters, "address", "64"), "address");
    if (address < 0 || address > 0x7F) {
      throw std::invalid_argument("address 必须在 0..127 范围内");
    }
    address_ = static_cast<std::uint8_t>(address);

    frequency_hz_ = parse_number(
      parameter_or_default(info_.hardware_parameters, "frequency", "50"), "frequency");
    if (frequency_hz_ <= 0.0) {
      throw std::invalid_argument("frequency 必须大于 0");
    }
    const auto prescale = std::llround(
      kOscillatorFrequency / (kPwmResolution * frequency_hz_) - 1.0);
    if (prescale < 3 || prescale > 255) {
      throw std::invalid_argument("frequency 超出 PCA9685 可配置范围");
    }

    const auto min_pwm = parse_integer(
      parameter_or_default(info_.hardware_parameters, "min_pwm", "110"), "min_pwm");
    const auto max_pwm = parse_integer(
      parameter_or_default(info_.hardware_parameters, "max_pwm", "520"), "max_pwm");
    if (min_pwm < 0 || max_pwm > 4095 || min_pwm >= max_pwm) {
      throw std::invalid_argument("PWM 范围必须满足 0 <= min_pwm < max_pwm <= 4095");
    }
    min_pwm_ = static_cast<std::uint16_t>(min_pwm);
    max_pwm_ = static_cast<std::uint16_t>(max_pwm);
    deactivate_full_off_ = parse_boolean(
      parameter_or_default(info_.hardware_parameters, "deactivate_full_off", "true"),
      "deactivate_full_off");

    std::array<bool, 16> used_channels{};
    joints_.clear();
    joints_.reserve(info_.joints.size());

    for (const auto & joint : info_.joints) {
      if (joint.command_interfaces.size() != 1 ||
        joint.command_interfaces.front().name != hardware_interface::HW_IF_POSITION)
      {
        throw std::invalid_argument(
                "joint " + joint.name + " 必须且只能声明一个 position command interface");
      }
      if (joint.state_interfaces.size() != 1 ||
        joint.state_interfaces.front().name != hardware_interface::HW_IF_POSITION)
      {
        throw std::invalid_argument(
                "joint " + joint.name + " 必须且只能声明一个 position state interface");
      }

      const auto channel = parse_integer(required_joint_parameter(joint, "channel"), "channel");
      if (channel < 0 || channel > 15) {
        throw std::invalid_argument(
                "joint " + joint.name + " 的 channel 必须在 0..15 范围内");
      }
      if (used_channels[static_cast<std::size_t>(channel)]) {
        throw std::invalid_argument("PCA9685 channel 不允许重复: " + std::to_string(channel));
      }
      used_channels[static_cast<std::size_t>(channel)] = true;

      const auto & command_interface = joint.command_interfaces.front();
      if (command_interface.min.empty() || command_interface.max.empty()) {
        throw std::invalid_argument(
                "joint " + joint.name + " 的 position command interface 必须声明 min 和 max");
      }

      JointConfiguration configuration;
      configuration.channel = static_cast<std::uint8_t>(channel);
      configuration.calibration.position_min = parse_number(
        command_interface.min, joint.name + ".position.min");
      configuration.calibration.position_max = parse_number(
        command_interface.max, joint.name + ".position.max");
      configuration.calibration.raw_min = static_cast<double>(min_pwm_);
      configuration.calibration.raw_max = static_cast<double>(max_pwm_);
      configuration.calibration.offset = 0.0;

      const auto offset = joint.parameters.find("offset_raw");
      if (offset != joint.parameters.end()) {
        configuration.offset_raw = parse_number(offset->second, joint.name + ".offset_raw");
      }
      const auto direction = joint.parameters.find("direction");
      if (direction != joint.parameters.end()) {
        configuration.calibration.direction = parse_number(
          direction->second, joint.name + ".direction");
      }
      validate_calibration(configuration.calibration);
      joints_.push_back(configuration);
    }

    command_positions_.resize(joints_.size());
    state_positions_.resize(joints_.size());
    last_pwm_.assign(joints_.size(), -1);
    for (std::size_t index = 0; index < joints_.size(); ++index) {
      const auto initial_position = std::clamp(
        0.0, joints_[index].calibration.position_min, joints_[index].calibration.position_max);
      command_positions_[index] = initial_position;
      state_positions_[index] = initial_position;
    }
  } catch (const std::exception & error) {
    RCLCPP_ERROR(kLogger, "PCA9685 配置无效: %s", error.what());
    return hardware_interface::CallbackReturn::ERROR;
  }

  return hardware_interface::CallbackReturn::SUCCESS;
}

std::vector<hardware_interface::StateInterface> Pca9685System::export_state_interfaces()
{
  std::vector<hardware_interface::StateInterface> interfaces;
  interfaces.reserve(info_.joints.size());
  for (std::size_t index = 0; index < info_.joints.size(); ++index) {
    interfaces.emplace_back(
      info_.joints[index].name, hardware_interface::HW_IF_POSITION, &state_positions_[index]);
  }
  return interfaces;
}

std::vector<hardware_interface::CommandInterface> Pca9685System::export_command_interfaces()
{
  std::vector<hardware_interface::CommandInterface> interfaces;
  interfaces.reserve(info_.joints.size());
  for (std::size_t index = 0; index < info_.joints.size(); ++index) {
    interfaces.emplace_back(
      info_.joints[index].name, hardware_interface::HW_IF_POSITION, &command_positions_[index]);
  }
  return interfaces;
}

hardware_interface::CallbackReturn Pca9685System::on_configure(
  const rclcpp_lifecycle::State &)
{
  try {
    device_.open(i2c_device_, address_);
    initialize_controller();
    std::fill(last_pwm_.begin(), last_pwm_.end(), -1);
  } catch (const std::exception & error) {
    device_.close();
    RCLCPP_ERROR(
      kLogger, "无法配置 PCA9685 (%s, 0x%02X): %s", i2c_device_.c_str(),
      static_cast<unsigned int>(address_), error.what());
    return hardware_interface::CallbackReturn::ERROR;
  }

  RCLCPP_INFO(
    kLogger, "PCA9685 已配置: device=%s address=0x%02X frequency=%.3fHz",
    i2c_device_.c_str(), static_cast<unsigned int>(address_), frequency_hz_);
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn Pca9685System::on_cleanup(
  const rclcpp_lifecycle::State &)
{
  device_.close();
  std::fill(last_pwm_.begin(), last_pwm_.end(), -1);
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn Pca9685System::on_activate(
  const rclcpp_lifecycle::State &)
{
  if (!device_.is_open()) {
    RCLCPP_ERROR(kLogger, "PCA9685 尚未配置，无法激活");
    return hardware_interface::CallbackReturn::ERROR;
  }
  command_positions_ = state_positions_;
  std::fill(last_pwm_.begin(), last_pwm_.end(), -1);
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn Pca9685System::on_deactivate(
  const rclcpp_lifecycle::State &)
{
  if (!deactivate_full_off_ || !device_.is_open()) {
    return hardware_interface::CallbackReturn::SUCCESS;
  }

  try {
    for (const auto & joint : joints_) {
      set_channel_full_off(joint.channel);
    }
    std::fill(last_pwm_.begin(), last_pwm_.end(), -1);
  } catch (const std::exception & error) {
    RCLCPP_ERROR(kLogger, "PCA9685 停机 full-off 失败: %s", error.what());
    return hardware_interface::CallbackReturn::ERROR;
  }
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::return_type Pca9685System::read(
  const rclcpp::Time &, const rclcpp::Duration &)
{
  state_positions_ = command_positions_;
  return hardware_interface::return_type::OK;
}

hardware_interface::return_type Pca9685System::write(
  const rclcpp::Time &, const rclcpp::Duration &)
{
  if (!device_.is_open()) {
    RCLCPP_ERROR(kLogger, "PCA9685 设备未打开，无法写入命令");
    return hardware_interface::return_type::ERROR;
  }

  try {
    std::vector<std::uint16_t> pwm_values;
    pwm_values.reserve(joints_.size());
    for (std::size_t index = 0; index < joints_.size(); ++index) {
      const double converted = position_to_raw(
        command_positions_[index], joints_[index].calibration);
      const double adjusted = std::clamp(
        converted + joints_[index].offset_raw,
        static_cast<double>(min_pwm_), static_cast<double>(max_pwm_));
      pwm_values.push_back(static_cast<std::uint16_t>(std::lround(adjusted)));
    }

    for (std::size_t index = 0; index < joints_.size(); ++index) {
      if (last_pwm_[index] == static_cast<int>(pwm_values[index])) {
        continue;
      }
      write_channel(joints_[index].channel, pwm_values[index]);
      last_pwm_[index] = pwm_values[index];
    }
  } catch (const std::exception & error) {
    RCLCPP_ERROR(kLogger, "PCA9685 写入失败: %s", error.what());
    return hardware_interface::return_type::ERROR;
  }
  return hardware_interface::return_type::OK;
}

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

void Pca9685System::set_channel_full_off(std::uint8_t channel)
{
  const auto base_register = static_cast<std::uint8_t>(kFirstLed + 4U * channel);
  device_.write_block(base_register, {0x00, 0x00, 0x00, kFullOff});
}

}  // namespace robot_hardware

PLUGINLIB_EXPORT_CLASS(robot_hardware::Pca9685System, hardware_interface::SystemInterface)
