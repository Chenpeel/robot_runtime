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
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>

#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "pluginlib/class_list_macros.hpp"
#include "rclcpp/logging.hpp"

namespace robot_hardware
{
namespace
{

const auto kLogger = rclcpp::get_logger("robot_hardware.bus_servo_system");

std::string required_parameter(
  const std::unordered_map<std::string, std::string> & parameters, const std::string & name)
{
  const auto iterator = parameters.find(name);
  if (iterator == parameters.end() || iterator->second.empty()) {
    throw std::invalid_argument("missing parameter: " + name);
  }
  return iterator->second;
}

template<typename Value>
Value parameter_or(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name, Value fallback);

template<>
int parameter_or(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name, int fallback)
{
  const auto iterator = parameters.find(name);
  return iterator == parameters.end() ? fallback : std::stoi(iterator->second);
}

template<>
double parameter_or(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name, double fallback)
{
  const auto iterator = parameters.find(name);
  return iterator == parameters.end() ? fallback : std::stod(iterator->second);
}

template<>
bool parameter_or(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name, bool fallback)
{
  const auto iterator = parameters.find(name);
  if (iterator == parameters.end()) {
    return fallback;
  }
  if (iterator->second == "true" || iterator->second == "1") {
    return true;
  }
  if (iterator->second == "false" || iterator->second == "0") {
    return false;
  }
  throw std::invalid_argument("parameter " + name + " must be boolean");
}

void validate_position_interfaces(const hardware_interface::ComponentInfo & joint)
{
  if (joint.command_interfaces.size() != 1 || joint.state_interfaces.size() != 1 ||
    joint.command_interfaces.front().name != hardware_interface::HW_IF_POSITION ||
    joint.state_interfaces.front().name != hardware_interface::HW_IF_POSITION)
  {
    throw std::invalid_argument(
            "joint " + joint.name + " must expose one position command and state interface");
  }
}

}  // namespace

hardware_interface::CallbackReturn BusServoSystem::on_init(
  const hardware_interface::HardwareInfo & info)
{
  if (hardware_interface::SystemInterface::on_init(info) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }
  try {
    port_ = required_parameter(info.hardware_parameters, "port");
    baud_rate_ = parameter_or<int>(info.hardware_parameters, "baud_rate", 115200);
    move_duration_ms_ = static_cast<std::uint16_t>(std::clamp(
        parameter_or<int>(info.hardware_parameters, "move_duration_ms", 100), 0, 30000));
    read_timeout_ = std::chrono::milliseconds(
      std::clamp(
        parameter_or<int>(info.hardware_parameters, "read_timeout_ms", 20), 1, 1000));
    feedback_per_cycle_ = static_cast<std::size_t>(std::max(
        1, parameter_or<int>(info.hardware_parameters, "feedback_per_cycle", 1)));
    max_consecutive_errors_ = static_cast<unsigned int>(std::max(
        1, parameter_or<int>(info.hardware_parameters, "max_consecutive_errors", 5)));
    read_position_ = parameter_or<bool>(info.hardware_parameters, "read_position", true);
    release_torque_on_deactivate_ = parameter_or<bool>(
      info.hardware_parameters, "release_torque_on_deactivate", false);

    std::unordered_set<std::uint16_t> ids;
    servos_.clear();
    servos_.reserve(info.joints.size());
    if (info.joints.empty()) {
      throw std::invalid_argument("BusServoSystem requires at least one joint");
    }
    for (const auto & joint : info.joints) {
      validate_position_interfaces(joint);
      Servo servo;
      const int id = std::stoi(required_parameter(joint.parameters, "servo_id"));
      if (id < 0 || id > 253 || !ids.insert(static_cast<std::uint16_t>(id)).second) {
        throw std::invalid_argument("servo_id must be unique and in [0, 253]");
      }
      servo.id = static_cast<std::uint16_t>(id);
      servo.protocol = parse_bus_protocol(required_parameter(joint.parameters, "protocol"));
      servo.calibration.position_min = std::stod(
        required_parameter(
          {{"min", joint.command_interfaces.front().min}}, "min"));
      servo.calibration.position_max = std::stod(
        required_parameter(
          {{"max", joint.command_interfaces.front().max}}, "max"));
      const double default_raw_min = servo.protocol == BusProtocol::kLx ? 125.0 : 833.0;
      const double default_raw_max = servo.protocol == BusProtocol::kLx ? 875.0 : 2167.0;
      servo.calibration.raw_min = parameter_or<double>(
        joint.parameters, "raw_min", default_raw_min);
      servo.calibration.raw_max = parameter_or<double>(
        joint.parameters, "raw_max", default_raw_max);
      servo.calibration.offset = parameter_or<double>(joint.parameters, "offset_rad", 0.0);
      servo.calibration.direction = parameter_or<double>(joint.parameters, "direction", 1.0);
      validate_calibration(servo.calibration);
      servos_.push_back(servo);
    }
  } catch (const std::exception & error) {
    RCLCPP_ERROR(kLogger, "总线舵机配置无效: %s", error.what());
    return hardware_interface::CallbackReturn::ERROR;
  }
  return hardware_interface::CallbackReturn::SUCCESS;
}

std::vector<hardware_interface::StateInterface> BusServoSystem::export_state_interfaces()
{
  std::vector<hardware_interface::StateInterface> interfaces;
  interfaces.reserve(servos_.size());
  for (std::size_t index = 0; index < servos_.size(); ++index) {
    interfaces.emplace_back(
      info_.joints[index].name, hardware_interface::HW_IF_POSITION, &servos_[index].state);
  }
  return interfaces;
}

std::vector<hardware_interface::CommandInterface> BusServoSystem::export_command_interfaces()
{
  std::vector<hardware_interface::CommandInterface> interfaces;
  interfaces.reserve(servos_.size());
  for (std::size_t index = 0; index < servos_.size(); ++index) {
    interfaces.emplace_back(
      info_.joints[index].name, hardware_interface::HW_IF_POSITION, &servos_[index].command);
  }
  return interfaces;
}

hardware_interface::CallbackReturn BusServoSystem::on_configure(
  const rclcpp_lifecycle::State &)
{
  try {
    serial_.open(port_, baud_rate_);
  } catch (const std::exception & error) {
    RCLCPP_ERROR(kLogger, "无法打开串口 %s: %s", port_.c_str(), error.what());
    return hardware_interface::CallbackReturn::ERROR;
  }
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn BusServoSystem::on_activate(
  const rclcpp_lifecycle::State &)
{
  for (std::size_t index = 0; index < servos_.size(); ++index) {
    if (read_position_ && !read_servo(index, true)) {
      stop_all();
      return hardware_interface::CallbackReturn::ERROR;
    }
    if (!std::isfinite(servos_[index].state)) {
      servos_[index].state = 0.5 * (
        servos_[index].calibration.position_min +
        servos_[index].calibration.position_max);
    }
    servos_[index].command = servos_[index].state;
    servos_[index].last_command = servos_[index].state;
  }
  next_feedback_index_ = 0;
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn BusServoSystem::on_deactivate(
  const rclcpp_lifecycle::State &)
{
  stop_all();
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn BusServoSystem::on_cleanup(
  const rclcpp_lifecycle::State &)
{
  serial_.close();
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
    for (auto & servo : servos_) {
      if (!std::isfinite(servo.command)) {
        RCLCPP_ERROR(kLogger, "拒绝非有限位置命令: servo_id=%u", servo.id);
        return hardware_interface::return_type::ERROR;
      }
      if (std::isfinite(servo.last_command) &&
        std::abs(servo.command - servo.last_command) <= 1e-9)
      {
        continue;
      }
      const auto raw = static_cast<std::uint16_t>(std::lround(
          position_to_raw(
            servo.command, servo.calibration)));
      serial_.write_all(encode_move(servo.protocol, servo.id, raw, move_duration_ms_));
      servo.last_command = servo.command;
      if (!read_position_) {
        servo.state = servo.command;
      }
    }
  } catch (const std::exception & error) {
    RCLCPP_ERROR(kLogger, "写入总线舵机失败: %s", error.what());
    stop_all();
    return hardware_interface::return_type::ERROR;
  }
  return hardware_interface::return_type::OK;
}

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
        kLogger, "读取舵机 %u 失败 (%u/%u): %s", servo.id,
        servo.consecutive_errors, max_consecutive_errors_, error.what());
    }
    return false;
  }
}

void BusServoSystem::stop_all() noexcept
{
  if (!serial_.is_open()) {
    return;
  }
  for (const auto & servo : servos_) {
    try {
      serial_.write_all(encode_stop(servo.protocol, servo.id));
      if (release_torque_on_deactivate_) {
        serial_.write_all(encode_torque_release(servo.protocol, servo.id));
      }
    } catch (const std::exception & error) {
      RCLCPP_ERROR(
        kLogger, "停止舵机 %u 失败（继续停止其余设备）: %s", servo.id, error.what());
    }
  }
}

}  // namespace robot_hardware

PLUGINLIB_EXPORT_CLASS(
  robot_hardware::BusServoSystem, hardware_interface::SystemInterface)
