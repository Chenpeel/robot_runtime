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


#include "robot_hardware/bus_servo_system.hpp"

#include <algorithm>
#include <cmath>
#include <exception>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <unordered_set>
#include <utility>

#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "rclcpp/logging.hpp"

namespace robot_hardware
{
namespace
{

const auto kLogger = rclcpp::get_logger("robot_hardware.bus_servo_system");

}  // namespace

// ======== PositionActuatorSystem 虚函数实现 ========

void BusServoSystem::parse_hardware_params(
  const std::unordered_map<std::string, std::string> & parameters)
{
  using param_utils::parameter_or;
  using param_utils::required_parameter;

  port_ = required_parameter(parameters, "port");
  baud_rate_ = parameter_or<int>(parameters, "baud_rate", 115200);
  move_duration_ms_ = static_cast<std::uint16_t>(std::clamp(
      parameter_or<int>(parameters, "move_duration_ms", 100), 0, 30000));
  read_timeout_ = std::chrono::milliseconds(
    std::clamp(
      parameter_or<int>(parameters, "read_timeout_ms", 20), 1, 1000));
  feedback_per_cycle_ = static_cast<std::size_t>(std::max(
      1, parameter_or<int>(parameters, "feedback_per_cycle", 1)));
  max_consecutive_errors_ = static_cast<unsigned int>(std::max(
      1, parameter_or<int>(parameters, "max_consecutive_errors", 5)));
  read_position_ = parameter_or<bool>(parameters, "read_position", true);
  release_torque_on_deactivate_ = parameter_or<bool>(
    parameters, "release_torque_on_deactivate", false);
}

PositionActuatorSystem::JointConfig BusServoSystem::parse_joint_config(
  const hardware_interface::ComponentInfo & joint)
{
  using param_utils::parameter_or;
  using param_utils::required_parameter;

  // 先让基类填充标定信息
  auto config = PositionActuatorSystem::parse_joint_config(joint);

  // 解析舵机专属字段
  Servo servo;
  const int id = std::stoi(required_parameter(joint.parameters, "servo_id"));
  if (id < 0 || id > 253) {
    throw std::invalid_argument("servo_id must be in [0, 253]");
  }
  servo.id = static_cast<std::uint16_t>(id);

  // 检查重复 ID
  for (const auto & existing : servos_) {
    if (existing.id == servo.id) {
      throw std::invalid_argument(
              "duplicate servo_id: " + std::to_string(servo.id));
    }
  }

  servo.protocol = parse_bus_protocol(required_parameter(joint.parameters, "protocol"));

  // 设置默认 raw 范围（基于协议）
  const double default_raw_min = servo.protocol == BusProtocol::kLx ? 125.0 : 833.0;
  const double default_raw_max = servo.protocol == BusProtocol::kLx ? 875.0 : 2167.0;
  config.calibration.raw_min = parameter_or<double>(
    joint.parameters, "raw_min", default_raw_min);
  config.calibration.raw_max = parameter_or<double>(
    joint.parameters, "raw_max", default_raw_max);

  servo.calibration = config.calibration;
  servos_.push_back(std::move(servo));

  return config;
}

bool BusServoSystem::do_configure()
{
  serial_.open(port_, baud_rate_);
  return true;
}

bool BusServoSystem::do_cleanup()
{
  serial_.close();
  return true;
}

std::optional<double> BusServoSystem::do_read_single(std::size_t index)
{
  if (!read_servo(index, true)) {
    return std::nullopt;
  }
  return servos_[index].state;
}

bool BusServoSystem::do_write_single(std::size_t index, double position)
{
  auto & servo = servos_.at(index);
  if (!std::isfinite(position)) {
    RCLCPP_ERROR(kLogger, "rejecting non-finite command for servo_id=%u", servo.id);
    return false;
  }
  const auto raw = static_cast<std::uint16_t>(std::lround(
      position_to_raw(position, servo.calibration)));
  serial_.write_all(encode_move(servo.protocol, servo.id, raw, move_duration_ms_));
  servo.last_command = position;
  if (!read_position_) {
    servo.state = position;
  }
  return true;
}

void BusServoSystem::do_stop_single(std::size_t index)
{
  const auto & servo = servos_.at(index);
  if (!serial_.is_open()) {
    return;
  }
  serial_.write_all(encode_stop(servo.protocol, servo.id));
  if (release_torque_on_deactivate_) {
    serial_.write_all(encode_torque_release(servo.protocol, servo.id));
  }
}

// ======== 覆盖的生命周期与读写（舵机特有逻辑） ========

hardware_interface::CallbackReturn BusServoSystem::on_activate(
  const rclcpp_lifecycle::State & previous_state)
{
  // 先让基类完成 states_ 的兜底初始化
  if (PositionActuatorSystem::on_activate(previous_state) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }

  // 读取初始位置
  for (std::size_t index = 0; index < servos_.size(); ++index) {
    if (read_position_ && !read_servo(index, true)) {
      do_cleanup();
      return hardware_interface::CallbackReturn::ERROR;
    }
    if (!std::isfinite(servos_[index].state)) {
      servos_[index].state = 0.5 * (
        servos_[index].calibration.position_min +
        servos_[index].calibration.position_max);
    }
    servos_[index].command = servos_[index].state;
    servos_[index].last_command = servos_[index].state;
    // 同步到基类的 states_ / commands_
    states_[index] = servos_[index].state;
    commands_[index] = servos_[index].command;
  }
  next_feedback_index_ = 0;
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn BusServoSystem::on_deactivate(
  const rclcpp_lifecycle::State & previous_state)
{
  if (!serial_.is_open()) {
    return hardware_interface::CallbackReturn::SUCCESS;
  }
  for (std::size_t index = 0; index < servos_.size(); ++index) {
    try {
      do_stop_single(index);
    } catch (const std::exception & error) {
      RCLCPP_ERROR(
        kLogger, "stop servo %u failed (continuing): %s",
        servos_[index].id, error.what());
    }
  }
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::return_type BusServoSystem::read(
  const rclcpp::Time &, const rclcpp::Duration &)
{
  if (!serial_.is_open()) {
    return hardware_interface::return_type::ERROR;
  }
  if (!read_position_) {
    for (auto & servo : servos_) {
      servo.state = servo.last_command;
      // 同步到基类数组
      const auto offset = static_cast<std::size_t>(&servo - servos_.data());
      if (offset < states_.size()) {
        states_[offset] = servo.state;
      }
    }
    return hardware_interface::return_type::OK;
  }

  const std::size_t count = std::min(feedback_per_cycle_, servos_.size());
  for (std::size_t offset = 0; offset < count; ++offset) {
    const std::size_t index = (next_feedback_index_ + offset) % servos_.size();
    if (!read_servo(index, true) &&
      servos_[index].consecutive_errors >= max_consecutive_errors_)
    {
      return hardware_interface::return_type::ERROR;
    }
    states_[index] = servos_[index].state;
  }
  next_feedback_index_ = (next_feedback_index_ + count) % servos_.size();
  return hardware_interface::return_type::OK;
}

hardware_interface::return_type BusServoSystem::write(
  const rclcpp::Time &, const rclcpp::Duration &)
{
  if (!serial_.is_open()) {
    return hardware_interface::return_type::ERROR;
  }
  try {
    for (std::size_t index = 0; index < servos_.size(); ++index) {
      auto & servo = servos_[index];
      const double cmd = commands_[index];
      servo.command = cmd;

      if (!std::isfinite(cmd)) {
        RCLCPP_ERROR(kLogger, "rejecting non-finite position command: servo_id=%u", servo.id);
        return hardware_interface::return_type::ERROR;
      }
      if (std::isfinite(servo.last_command) &&
        std::abs(cmd - servo.last_command) <= 1e-9)
      {
        continue;
      }
      const auto raw = static_cast<std::uint16_t>(std::lround(
          position_to_raw(cmd, servo.calibration)));
      serial_.write_all(encode_move(servo.protocol, servo.id, raw, move_duration_ms_));
      servo.last_command = cmd;
      if (!read_position_) {
        servo.state = cmd;
        states_[index] = cmd;
      }
    }
  } catch (const std::exception & error) {
    RCLCPP_ERROR(kLogger, "write bus servo failed: %s", error.what());
    return hardware_interface::return_type::ERROR;
  }
  return hardware_interface::return_type::OK;
}

// ======== 辅助函数 ========

bool BusServoSystem::read_servo(std::size_t index, bool report_error)
{
  auto & servo = servos_.at(index);
  try {
    const auto response = serial_.exchange(
      encode_position_read(servo.protocol, servo.id), read_timeout_);
    const auto raw = decode_position(servo.protocol, response, servo.id);
    if (!raw) {
      throw std::runtime_error("position response missing or invalid");
    }
    servo.state = raw_to_position(static_cast<double>(*raw), servo.calibration);
    servo.consecutive_errors = 0;
    return true;
  } catch (const std::exception & error) {
    ++servo.consecutive_errors;
    if (report_error) {
      RCLCPP_WARN(
        kLogger, "read servo %u failed (%u/%u): %s", servo.id,
        servo.consecutive_errors, max_consecutive_errors_, error.what());
    }
    return false;
  }
}

}  // namespace robot_hardware

PLUGINLIB_EXPORT_CLASS(
  robot_hardware::BusServoSystem, hardware_interface::SystemInterface)
