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


#include "robot_hardware/position_actuator_system.hpp"

#include <algorithm>
#include <cmath>
#include <limits>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>

#include "hardware_interface/types/hardware_interface_type_values.hpp"
#include "rclcpp/logging.hpp"

namespace robot_hardware
{

// ======== 默认虚函数实现 ========

void PositionActuatorSystem::parse_hardware_params(
  const std::unordered_map<std::string, std::string> & /*parameters*/)
{
  // 默认无全局参数
}

PositionActuatorSystem::JointConfig PositionActuatorSystem::parse_joint_config(
  const hardware_interface::ComponentInfo & joint)
{
  JointConfig config;

  // 从 command interface 的 min/max 读取位置范围
  config.calibration.position_min = std::stod(
    param_utils::required_parameter(
      {{"min", joint.command_interfaces.front().min}}, "min"));
  config.calibration.position_max = std::stod(
    param_utils::required_parameter(
      {{"max", joint.command_interfaces.front().max}}, "max"));

  // 可选参数
  config.calibration.offset = param_utils::parameter_or<double>(
    joint.parameters, "offset_rad", 0.0);
  config.calibration.direction = param_utils::parameter_or<double>(
    joint.parameters, "direction", 1.0);

  validate_calibration(config.calibration);
  return config;
}

void PositionActuatorSystem::on_activate_success()
{
  // 默认无操作
}

// ======== 私有辅助 ========

void PositionActuatorSystem::validate_joint_declarations()
{
  if (info_.joints.empty()) {
    throw std::invalid_argument(
            "PositionActuatorSystem requires at least one joint");
  }

  for (const auto & joint : info_.joints) {
    param_utils::validate_position_interfaces(joint);
  }
}

// ======== SystemInterface 实现 ========

hardware_interface::CallbackReturn PositionActuatorSystem::on_init(
  const hardware_interface::HardwareInfo & info)
{
  if (hardware_interface::SystemInterface::on_init(info) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }

  try {
    validate_joint_declarations();

    // 1. 解析全局参数（子类钩子）
    parse_hardware_params(info_.hardware_parameters);

    // 2. 解析每个关节的配置（子类钩子，可返回派生类型）
    joint_configs_.clear();
    joint_configs_.reserve(info_.joints.size());
    for (const auto & joint : info_.joints) {
      auto config = parse_joint_config(joint);
      validate_calibration(config.calibration);
      joint_configs_.push_back(std::move(config));
    }

    // 3. 初始化命令和状态数组
    commands_.assign(info_.joints.size(),
      std::numeric_limits<double>::quiet_NaN());
    states_.assign(info_.joints.size(),
      std::numeric_limits<double>::quiet_NaN());

  } catch (const std::exception & error) {
    RCLCPP_ERROR(
      rclcpp::get_logger("PositionActuatorSystem"),
      "initialization rejected: %s", error.what());
    joint_configs_.clear();
    commands_.clear();
    states_.clear();
    return hardware_interface::CallbackReturn::ERROR;
  }

  return hardware_interface::CallbackReturn::SUCCESS;
}

std::vector<hardware_interface::StateInterface>
PositionActuatorSystem::export_state_interfaces()
{
  std::vector<hardware_interface::StateInterface> interfaces;
  interfaces.reserve(info_.joints.size());
  for (std::size_t index = 0; index < info_.joints.size(); ++index) {
    interfaces.emplace_back(
      info_.joints[index].name,
      hardware_interface::HW_IF_POSITION,
      &states_[index]);
  }
  return interfaces;
}

std::vector<hardware_interface::CommandInterface>
PositionActuatorSystem::export_command_interfaces()
{
  std::vector<hardware_interface::CommandInterface> interfaces;
  interfaces.reserve(info_.joints.size());
  for (std::size_t index = 0; index < info_.joints.size(); ++index) {
    interfaces.emplace_back(
      info_.joints[index].name,
      hardware_interface::HW_IF_POSITION,
      &commands_[index]);
  }
  return interfaces;
}

hardware_interface::CallbackReturn PositionActuatorSystem::on_configure(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  if (!do_configure()) {
    return hardware_interface::CallbackReturn::ERROR;
  }
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn PositionActuatorSystem::on_activate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  // 激活时将 states_ 初始化为 commands_（兜底），子类可在
  // on_activate_success() 中用真实读数覆盖。
  for (std::size_t index = 0; index < info_.joints.size(); ++index) {
    if (!std::isfinite(states_[index])) {
      states_[index] = commands_[index];
    }
    if (!std::isfinite(states_[index])) {
      states_[index] = 0.5 * (
        joint_configs_[index].calibration.position_min +
        joint_configs_[index].calibration.position_max);
    }
  }

  on_activate_success();
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn PositionActuatorSystem::on_deactivate(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  for (std::size_t index = 0; index < info_.joints.size(); ++index) {
    do_stop_single(index);
  }
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn PositionActuatorSystem::on_cleanup(
  const rclcpp_lifecycle::State & /*previous_state*/)
{
  if (!do_cleanup()) {
    return hardware_interface::CallbackReturn::ERROR;
  }
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::return_type PositionActuatorSystem::read(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  for (std::size_t index = 0; index < info_.joints.size(); ++index) {
    const auto result = do_read_single(index);
    if (!result) {
      return hardware_interface::return_type::ERROR;
    }
    states_[index] = *result;
  }
  return hardware_interface::return_type::OK;
}

hardware_interface::return_type PositionActuatorSystem::write(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  for (std::size_t index = 0; index < info_.joints.size(); ++index) {
    if (!std::isfinite(commands_[index])) {
      RCLCPP_ERROR(
        rclcpp::get_logger("PositionActuatorSystem"),
        "rejecting non-finite position command at joint index %zu", index);
      return hardware_interface::return_type::ERROR;
    }
    if (!do_write_single(index, commands_[index])) {
      return hardware_interface::return_type::ERROR;
    }
  }
  return hardware_interface::return_type::OK;
}

}  // namespace robot_hardware
