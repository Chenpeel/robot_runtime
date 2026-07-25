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


#ifndef ROBOT_HARDWARE__PARAM_UTILS_HPP_
#define ROBOT_HARDWARE__PARAM_UTILS_HPP_

#include <cmath>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <string>
#include <unordered_map>

#include "hardware_interface/hardware_info.hpp"

namespace robot_hardware
{
namespace param_utils
{

// --- 参数读取 ---

inline const std::string & required_parameter(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name)
{
  const auto iterator = parameters.find(name);
  if (iterator == parameters.end() || iterator->second.empty()) {
    throw std::invalid_argument("missing parameter: " + name);
  }
  return iterator->second;
}

inline std::string parameter_or_default(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name, const std::string & fallback)
{
  const auto iterator = parameters.find(name);
  return iterator == parameters.end() ? fallback : iterator->second;
}

template<typename T>
T parameter_or(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name, T fallback);

template<>
inline int parameter_or(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name, int fallback)
{
  const auto iterator = parameters.find(name);
  return iterator == parameters.end() ? fallback : std::stoi(iterator->second);
}

template<>
inline double parameter_or(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name, double fallback)
{
  const auto iterator = parameters.find(name);
  return iterator == parameters.end() ? fallback : std::stod(iterator->second);
}

template<>
inline bool parameter_or(
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

// --- 数值解析 ---

inline std::int64_t parse_integer(const std::string & value, const std::string & name)
{
  std::size_t parsed = 0;
  std::int64_t result = 0;
  try {
    result = std::stoll(value, &parsed, 0);
  } catch (const std::exception &) {
    throw std::invalid_argument(name + " must be an integer");
  }
  if (parsed != value.size()) {
    throw std::invalid_argument(name + " must be an integer");
  }
  return result;
}

inline double parse_number(const std::string & value, const std::string & name)
{
  std::size_t parsed = 0;
  double result = 0.0;
  try {
    result = std::stod(value, &parsed);
  } catch (const std::exception &) {
    throw std::invalid_argument(name + " must be a finite number");
  }
  if (parsed != value.size() || !std::isfinite(result)) {
    throw std::invalid_argument(name + " must be a finite number");
  }
  return result;
}

inline bool parse_boolean(const std::string & value, const std::string & name)
{
  if (value == "true" || value == "1") {
    return true;
  }
  if (value == "false" || value == "0") {
    return false;
  }
  throw std::invalid_argument(name + " must be true or false");
}

// --- 关节接口校验 ---

inline void validate_position_interfaces(
  const hardware_interface::ComponentInfo & joint)
{
  if (joint.command_interfaces.size() != 1 ||
    joint.state_interfaces.size() != 1 ||
    joint.command_interfaces.front().name != hardware_interface::HW_IF_POSITION ||
    joint.state_interfaces.front().name != hardware_interface::HW_IF_POSITION)
  {
    throw std::invalid_argument(
            "joint " + joint.name +
            " must expose exactly one position command and one position state interface");
  }
}

}  // namespace param_utils
}  // namespace robot_hardware

#endif  // ROBOT_HARDWARE__PARAM_UTILS_HPP_
