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


#include "robot_hardware/yb_imu_sensor.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <cstring>
#include <iterator>
#include <limits>
#include <set>
#include <stdexcept>
#include <thread>
#include <unordered_map>
#include <utility>

#include "pluginlib/class_list_macros.hpp"
#include "rclcpp/logging.hpp"

namespace robot_hardware
{
namespace
{

constexpr std::uint8_t kFrameHead1 = 0x7E;
constexpr std::uint8_t kFrameHead2 = 0x23;
constexpr std::uint8_t kRawAccelRegister = 0x04;
constexpr std::uint8_t kRawGyroRegister = 0x0A;
constexpr std::uint8_t kRawMagRegister = 0x10;
constexpr std::uint8_t kQuaternionRegister = 0x16;
constexpr std::uint8_t kBarometerRegister = 0x32;
constexpr std::uint8_t kAlgoTypeRegister = 0x61;
constexpr std::uint8_t kCalibrateImuRegister = 0x70;
constexpr std::uint8_t kSerialRawReport = 0x04;
constexpr std::uint8_t kSerialQuaternionReport = 0x16;
constexpr std::uint8_t kSerialBarometerReport = 0x32;
constexpr double kStandardGravity = 9.80665;
constexpr double kPi = 3.14159265358979323846;
constexpr auto kSerialReadTimeout = std::chrono::milliseconds(25);

enum StateIndex : std::size_t
{
  kOrientationX = 0,
  kOrientationY,
  kOrientationZ,
  kOrientationW,
  kAngularVelocityX,
  kAngularVelocityY,
  kAngularVelocityZ,
  kLinearAccelerationX,
  kLinearAccelerationY,
  kLinearAccelerationZ,
  kMagneticFieldX,
  kMagneticFieldY,
  kMagneticFieldZ,
  kTemperature,
  kPressure,
  kHeight,
};

const std::unordered_map<std::string, std::size_t> kInterfaceIndices{
  {"orientation.x", kOrientationX},
  {"orientation.y", kOrientationY},
  {"orientation.z", kOrientationZ},
  {"orientation.w", kOrientationW},
  {"angular_velocity.x", kAngularVelocityX},
  {"angular_velocity.y", kAngularVelocityY},
  {"angular_velocity.z", kAngularVelocityZ},
  {"linear_acceleration.x", kLinearAccelerationX},
  {"linear_acceleration.y", kLinearAccelerationY},
  {"linear_acceleration.z", kLinearAccelerationZ},
  {"magnetic_field.x", kMagneticFieldX},
  {"magnetic_field.y", kMagneticFieldY},
  {"magnetic_field.z", kMagneticFieldZ},
  {"temperature", kTemperature},
  {"pressure", kPressure},
  {"height", kHeight},
};

const std::set<std::string> kRequiredInterfaces{
  "orientation.x",
  "orientation.y",
  "orientation.z",
  "orientation.w",
  "angular_velocity.x",
  "angular_velocity.y",
  "angular_velocity.z",
  "linear_acceleration.x",
  "linear_acceleration.y",
  "linear_acceleration.z",
};

const std::string & require_parameter(
  const std::unordered_map<std::string, std::string> & parameters,
  const std::string & name)
{
  const auto iterator = parameters.find(name);
  if (iterator == parameters.end() || iterator->second.empty()) {
    throw std::invalid_argument("missing hardware parameter: " + name);
  }
  return iterator->second;
}

std::int64_t parse_integer(const std::string & text, const std::string & name)
{
  std::size_t parsed = 0;
  const std::int64_t value = std::stoll(text, &parsed, 0);
  if (parsed != text.size()) {
    throw std::invalid_argument("invalid integer hardware parameter: " + name);
  }
  return value;
}

bool parse_boolean(const std::string & text, const std::string & name)
{
  if (text == "true" || text == "1") {
    return true;
  }
  if (text == "false" || text == "0") {
    return false;
  }
  throw std::invalid_argument("invalid boolean hardware parameter: " + name);
}

std::int16_t decode_i16_le(const std::uint8_t * data)
{
  const std::uint16_t bits = static_cast<std::uint16_t>(data[0]) |
    (static_cast<std::uint16_t>(data[1]) << 8U);
  std::int16_t value = 0;
  std::memcpy(&value, &bits, sizeof(value));
  return value;
}

float decode_f32_le(const std::uint8_t * data)
{
  const std::uint32_t bits = static_cast<std::uint32_t>(data[0]) |
    (static_cast<std::uint32_t>(data[1]) << 8U) |
    (static_cast<std::uint32_t>(data[2]) << 16U) |
    (static_cast<std::uint32_t>(data[3]) << 24U);
  float value = 0.0F;
  std::memcpy(&value, &bits, sizeof(value));
  return value;
}

bool normalize_quaternion(
  double w, double x, double y, double z, std::array<double, 4> & normalized)
{
  if (!std::isfinite(w) || !std::isfinite(x) || !std::isfinite(y) ||
    !std::isfinite(z))
  {
    return false;
  }
  const double norm = std::hypot(std::hypot(w, x), std::hypot(y, z));
  if (!std::isfinite(norm) || norm <= std::numeric_limits<double>::epsilon()) {
    return false;
  }
  normalized = {x / norm, y / norm, z / norm, w / norm};
  return true;
}

bool all_finite(const std::vector<double> & values)
{
  return std::all_of(
    values.begin(), values.end(), [](double value) {
      return std::isfinite(value);
    });
}

}  // namespace

hardware_interface::CallbackReturn YbImuSensor::on_init(
  const hardware_interface::HardwareInfo & info)
{
  if (hardware_interface::SensorInterface::on_init(info) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }

  try {
    if (info_.sensors.size() != 1U) {
      throw std::invalid_argument("YbImuSensor requires exactly one sensor component");
    }
    const auto & sensor = info_.sensors.front();
    if (!sensor.command_interfaces.empty()) {
      throw std::invalid_argument("YbImuSensor does not expose command interfaces");
    }

    std::set<std::string> declared;
    exported_interfaces_.clear();
    for (const auto & interface : sensor.state_interfaces) {
      const auto index = kInterfaceIndices.find(interface.name);
      if (index == kInterfaceIndices.end()) {
        throw std::invalid_argument("unsupported IMU state interface: " + interface.name);
      }
      if (!declared.insert(interface.name).second) {
        throw std::invalid_argument("duplicate IMU state interface: " + interface.name);
      }
      exported_interfaces_.emplace_back(interface.name, index->second);
    }
    for (const auto & required : kRequiredInterfaces) {
      if (declared.count(required) != 1U) {
        throw std::invalid_argument("missing required IMU state interface: " + required);
      }
    }

    sensor_name_ = sensor.name;
    magnetic_field_declared_ = declared.count("magnetic_field.x") != 0U ||
      declared.count("magnetic_field.y") != 0U ||
      declared.count("magnetic_field.z") != 0U;
    barometer_declared_ = declared.count("temperature") != 0U ||
      declared.count("pressure") != 0U || declared.count("height") != 0U;

    const auto & parameters = info_.hardware_parameters;
    const std::string & transport = require_parameter(parameters, "transport");
    if (transport == "i2c") {
      transport_ = Transport::kI2c;
    } else if (transport == "serial") {
      transport_ = Transport::kSerial;
    } else {
      throw std::invalid_argument("transport must be either 'i2c' or 'serial'");
    }
    device_ = require_parameter(parameters, "device");

    if (transport_ == Transport::kI2c) {
      const std::int64_t address = parse_integer(
        require_parameter(parameters, "address"), "address");
      if (address < 0x03 || address > 0x77) {
        throw std::invalid_argument("I2C address must be in [0x03, 0x77]");
      }
      address_ = static_cast<std::uint8_t>(address);
    } else {
      const std::int64_t baud_rate = parse_integer(
        require_parameter(parameters, "baud_rate"), "baud_rate");
      if (baud_rate <= 0 || baud_rate > std::numeric_limits<int>::max()) {
        throw std::invalid_argument("baud_rate is out of range");
      }
      baud_rate_ = static_cast<int>(baud_rate);
    }

    algo_type_ = static_cast<int>(parse_integer(
        require_parameter(parameters, "algo_type"), "algo_type"));
    if (algo_type_ != 6 && algo_type_ != 9) {
      throw std::invalid_argument("algo_type must be 6 or 9");
    }
    calibrate_on_start_ = parse_boolean(
      require_parameter(parameters, "calibrate_on_start"), "calibrate_on_start");

    const auto timeout = parameters.find("calibration_timeout_ms");
    if (timeout != parameters.end()) {
      const std::int64_t milliseconds = parse_integer(
        timeout->second, "calibration_timeout_ms");
      if (milliseconds <= 0 || milliseconds > 30000) {
        throw std::invalid_argument("calibration_timeout_ms must be in [1, 30000]");
      }
      calibration_timeout_ = std::chrono::milliseconds(milliseconds);
    }

    reset_runtime_state();
    return hardware_interface::CallbackReturn::SUCCESS;
  } catch (const std::exception & error) {
    RCLCPP_ERROR(
      rclcpp::get_logger("YbImuSensor"), "IMU initialization rejected: %s", error.what());
    exported_interfaces_.clear();
    mark_states_nan();
    return hardware_interface::CallbackReturn::ERROR;
  }
}

std::vector<hardware_interface::StateInterface> YbImuSensor::export_state_interfaces()
{
  std::vector<hardware_interface::StateInterface> interfaces;
  interfaces.reserve(exported_interfaces_.size());
  for (const auto & interface : exported_interfaces_) {
    interfaces.emplace_back(sensor_name_, interface.first, &states_[interface.second]);
  }
  return interfaces;
}

hardware_interface::CallbackReturn YbImuSensor::on_configure(
  const rclcpp_lifecycle::State & previous_state)
{
  if (hardware_interface::SensorInterface::on_configure(previous_state) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }

  reset_runtime_state();
  try {
    if (transport_ == Transport::kI2c) {
      configure_i2c();
    } else {
      configure_serial();
    }
    configured_ = true;
    return hardware_interface::CallbackReturn::SUCCESS;
  } catch (const std::exception & error) {
    i2c_device_.close();
    serial_port_.close();
    configured_ = false;
    RCLCPP_ERROR(
      rclcpp::get_logger("YbImuSensor"), "failed to configure IMU: %s", error.what());
    return hardware_interface::CallbackReturn::ERROR;
  }
}

hardware_interface::CallbackReturn YbImuSensor::on_activate(
  const rclcpp_lifecycle::State & previous_state)
{
  if (hardware_interface::SensorInterface::on_activate(previous_state) !=
    hardware_interface::CallbackReturn::SUCCESS)
  {
    return hardware_interface::CallbackReturn::ERROR;
  }
  const bool open = transport_ == Transport::kI2c ? i2c_device_.is_open() :
    serial_port_.is_open();
  if (!configured_ || !open) {
    mark_states_nan();
    return hardware_interface::CallbackReturn::ERROR;
  }
  mark_states_nan();
  serial_rx_buffer_.clear();
  serial_states_.fill(std::numeric_limits<double>::quiet_NaN());
  have_serial_raw_ = false;
  have_serial_quaternion_ = false;
  active_ = true;
  return hardware_interface::CallbackReturn::SUCCESS;
}

hardware_interface::CallbackReturn YbImuSensor::on_deactivate(
  const rclcpp_lifecycle::State & previous_state)
{
  active_ = false;
  mark_states_nan();
  have_serial_raw_ = false;
  have_serial_quaternion_ = false;
  return hardware_interface::SensorInterface::on_deactivate(previous_state);
}

hardware_interface::CallbackReturn YbImuSensor::on_cleanup(
  const rclcpp_lifecycle::State & previous_state)
{
  active_ = false;
  configured_ = false;
  i2c_device_.close();
  serial_port_.close();
  reset_runtime_state();
  return hardware_interface::SensorInterface::on_cleanup(previous_state);
}

hardware_interface::return_type YbImuSensor::read(
  const rclcpp::Time & /*time*/, const rclcpp::Duration & /*period*/)
{
  const bool open = transport_ == Transport::kI2c ? i2c_device_.is_open() :
    serial_port_.is_open();
  if (!active_ || !open) {
    mark_states_nan();
    return hardware_interface::return_type::ERROR;
  }

  try {
    return transport_ == Transport::kI2c ? read_i2c() : read_serial();
  } catch (const std::exception & error) {
    mark_states_nan();
    serial_states_.fill(std::numeric_limits<double>::quiet_NaN());
    have_serial_raw_ = false;
    have_serial_quaternion_ = false;
    RCLCPP_ERROR(
      rclcpp::get_logger("YbImuSensor"), "failed to read IMU: %s", error.what());
    return hardware_interface::return_type::ERROR;
  }
}

void YbImuSensor::mark_states_nan() noexcept
{
  states_.fill(std::numeric_limits<double>::quiet_NaN());
}

void YbImuSensor::reset_runtime_state() noexcept
{
  mark_states_nan();
  serial_states_.fill(std::numeric_limits<double>::quiet_NaN());
  serial_rx_buffer_.clear();
  have_serial_raw_ = false;
  have_serial_quaternion_ = false;
  active_ = false;
}

void YbImuSensor::configure_i2c()
{
  i2c_device_.open(device_, address_);
  i2c_device_.write_byte(kAlgoTypeRegister, static_cast<std::uint8_t>(algo_type_));
  if (calibrate_on_start_) {
    calibrate_i2c();
  }
}

void YbImuSensor::configure_serial()
{
  serial_port_.open(device_, baud_rate_);
  write_serial_command(
    kAlgoTypeRegister, {static_cast<std::uint8_t>(algo_type_), 0x5F});
  if (calibrate_on_start_) {
    calibrate_serial();
  }
}

void YbImuSensor::calibrate_i2c()
{
  i2c_device_.write_byte(kCalibrateImuRegister, 0x01);
  const auto deadline = std::chrono::steady_clock::now() + calibration_timeout_;
  while (std::chrono::steady_clock::now() < deadline) {
    const auto status = i2c_device_.read_block(kCalibrateImuRegister, 1);
    if (status.front() != 0U) {
      return;
    }
    const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
      deadline - std::chrono::steady_clock::now());
    if (remaining > std::chrono::milliseconds::zero()) {
      std::this_thread::sleep_for(std::min(remaining, std::chrono::milliseconds(50)));
    }
  }
  throw std::runtime_error("IMU calibration timed out");
}

void YbImuSensor::calibrate_serial()
{
  write_serial_command(kCalibrateImuRegister, {0x01, 0x5F});

  // 旧串口协议不提供可靠的完成应答；以小段有界等待代替一次 7 秒长休眠。
  const auto deadline = std::chrono::steady_clock::now() + calibration_timeout_;
  while (std::chrono::steady_clock::now() < deadline) {
    const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
      deadline - std::chrono::steady_clock::now());
    const auto wait = std::min(remaining, std::chrono::milliseconds(50));
    const auto bytes = serial_port_.read_some(256, wait);
    serial_rx_buffer_.insert(serial_rx_buffer_.end(), bytes.begin(), bytes.end());
    SerialUpdates ignored;
    parse_serial_buffer(ignored);
  }
}

hardware_interface::return_type YbImuSensor::read_i2c()
{
  std::array<double, kStateCount> next;
  next.fill(std::numeric_limits<double>::quiet_NaN());

  const auto acceleration = i2c_device_.read_block(kRawAccelRegister, 6);
  const auto gyroscope = i2c_device_.read_block(kRawGyroRegister, 6);
  const auto quaternion = i2c_device_.read_block(kQuaternionRegister, 16);

  const double acceleration_scale = (16.0 / 32767.0) * kStandardGravity;
  next[kLinearAccelerationX] = decode_i16_le(acceleration.data()) * acceleration_scale;
  next[kLinearAccelerationY] = decode_i16_le(acceleration.data() + 2) * acceleration_scale;
  next[kLinearAccelerationZ] = decode_i16_le(acceleration.data() + 4) * acceleration_scale;

  const double gyroscope_scale = (2000.0 / 32767.0) * (kPi / 180.0);
  next[kAngularVelocityX] = decode_i16_le(gyroscope.data()) * gyroscope_scale;
  next[kAngularVelocityY] = decode_i16_le(gyroscope.data() + 2) * gyroscope_scale;
  next[kAngularVelocityZ] = decode_i16_le(gyroscope.data() + 4) * gyroscope_scale;

  std::array<double, 4> normalized{};
  if (!normalize_quaternion(
      decode_f32_le(quaternion.data()), decode_f32_le(quaternion.data() + 4),
      decode_f32_le(quaternion.data() + 8), decode_f32_le(quaternion.data() + 12),
      normalized))
  {
    mark_states_nan();
    return hardware_interface::return_type::ERROR;
  }
  next[kOrientationX] = normalized[0];
  next[kOrientationY] = normalized[1];
  next[kOrientationZ] = normalized[2];
  next[kOrientationW] = normalized[3];

  if (magnetic_field_declared_) {
    const auto magnetic_field = i2c_device_.read_block(kRawMagRegister, 6);
    constexpr double magnetic_scale = 800.0e-6 / 32767.0;
    next[kMagneticFieldX] = decode_i16_le(magnetic_field.data()) * magnetic_scale;
    next[kMagneticFieldY] = decode_i16_le(magnetic_field.data() + 2) * magnetic_scale;
    next[kMagneticFieldZ] = decode_i16_le(magnetic_field.data() + 4) * magnetic_scale;
  }

  if (barometer_declared_) {
    const auto barometer = i2c_device_.read_block(kBarometerRegister, 16);
    next[kHeight] = decode_f32_le(barometer.data());
    next[kTemperature] = decode_f32_le(barometer.data() + 4);
    next[kPressure] = decode_f32_le(barometer.data() + 8);
  }

  std::vector<double> declared_values;
  declared_values.reserve(exported_interfaces_.size());
  for (const auto & interface : exported_interfaces_) {
    declared_values.push_back(next[interface.second]);
  }
  if (!all_finite(declared_values)) {
    mark_states_nan();
    return hardware_interface::return_type::ERROR;
  }
  states_ = next;
  return hardware_interface::return_type::OK;
}

hardware_interface::return_type YbImuSensor::read_serial()
{
  const SerialUpdates updates = receive_serial_updates(kSerialReadTimeout);
  if (updates.invalid) {
    mark_states_nan();
    serial_states_.fill(std::numeric_limits<double>::quiet_NaN());
    have_serial_raw_ = false;
    have_serial_quaternion_ = false;
    return hardware_interface::return_type::ERROR;
  }
  if (!updates.raw && !updates.quaternion && !updates.barometer) {
    mark_states_nan();
    have_serial_raw_ = false;
    have_serial_quaternion_ = false;
    return hardware_interface::return_type::ERROR;
  }
  if (!have_serial_raw_ || !have_serial_quaternion_) {
    mark_states_nan();
    return hardware_interface::return_type::ERROR;
  }

  for (const auto & interface : exported_interfaces_) {
    if (!std::isfinite(serial_states_[interface.second])) {
      // 自定义报告可能低频到达；在首次收到前显式报告无效数据。
      mark_states_nan();
      return hardware_interface::return_type::ERROR;
    }
  }
  states_ = serial_states_;
  return hardware_interface::return_type::OK;
}

void YbImuSensor::write_serial_command(
  std::uint8_t function, const std::vector<std::uint8_t> & payload)
{
  std::vector<std::uint8_t> frame{kFrameHead1, kFrameHead2, 0U, function};
  frame.insert(frame.end(), payload.begin(), payload.end());
  if (frame.size() + 1U > std::numeric_limits<std::uint8_t>::max()) {
    throw std::invalid_argument("serial command is too large");
  }
  frame[2] = static_cast<std::uint8_t>(frame.size() + 1U);
  std::uint8_t checksum = 0;
  for (const std::uint8_t value : frame) {
    checksum = static_cast<std::uint8_t>(checksum + value);
  }
  frame.push_back(checksum);
  serial_port_.write_all(frame);
}

YbImuSensor::SerialUpdates YbImuSensor::receive_serial_updates(
  std::chrono::milliseconds timeout)
{
  SerialUpdates updates;
  const auto deadline = std::chrono::steady_clock::now() + timeout;
  while (std::chrono::steady_clock::now() < deadline) {
    const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
      deadline - std::chrono::steady_clock::now());
    auto bytes = serial_port_.read_some(512, std::max(remaining, std::chrono::milliseconds(1)));
    if (bytes.empty()) {
      break;
    }
    serial_rx_buffer_.insert(serial_rx_buffer_.end(), bytes.begin(), bytes.end());
    parse_serial_buffer(updates);
    if (updates.invalid || (updates.raw && updates.quaternion)) {
      break;
    }
  }
  return updates;
}

void YbImuSensor::parse_serial_buffer(SerialUpdates & updates)
{
  while (true) {
    auto header = serial_rx_buffer_.end();
    for (auto iterator = serial_rx_buffer_.begin(); iterator != serial_rx_buffer_.end();
      ++iterator)
    {
      if (*iterator == kFrameHead1 && std::next(iterator) != serial_rx_buffer_.end() &&
        *std::next(iterator) == kFrameHead2)
      {
        header = iterator;
        break;
      }
    }

    if (header == serial_rx_buffer_.end()) {
      const bool keep_head = !serial_rx_buffer_.empty() &&
        serial_rx_buffer_.back() == kFrameHead1;
      serial_rx_buffer_.clear();
      if (keep_head) {
        serial_rx_buffer_.push_back(kFrameHead1);
      }
      return;
    }
    serial_rx_buffer_.erase(serial_rx_buffer_.begin(), header);
    if (serial_rx_buffer_.size() < 3U) {
      return;
    }

    const std::size_t frame_size = serial_rx_buffer_[2];
    if (frame_size < 5U || frame_size > 64U) {
      serial_rx_buffer_.erase(serial_rx_buffer_.begin());
      updates.invalid = true;
      continue;
    }
    if (serial_rx_buffer_.size() < frame_size) {
      return;
    }

    std::vector<std::uint8_t> frame(
      serial_rx_buffer_.begin(), serial_rx_buffer_.begin() + frame_size);
    std::uint8_t checksum = 0;
    for (std::size_t index = 0; index + 1U < frame.size(); ++index) {
      checksum = static_cast<std::uint8_t>(checksum + frame[index]);
    }
    if (checksum != frame.back()) {
      serial_rx_buffer_.erase(serial_rx_buffer_.begin());
      updates.invalid = true;
      continue;
    }

    parse_serial_frame(frame, updates);
    serial_rx_buffer_.erase(
      serial_rx_buffer_.begin(), serial_rx_buffer_.begin() + frame_size);
  }
}

void YbImuSensor::parse_serial_frame(
  const std::vector<std::uint8_t> & frame, SerialUpdates & updates)
{
  const std::uint8_t function = frame[3];
  const std::uint8_t * payload = frame.data() + 4;
  const std::size_t payload_size = frame.size() - 5U;

  if (function == kSerialRawReport) {
    if (payload_size < 18U) {
      updates.invalid = true;
      return;
    }
    const double acceleration_scale = (16.0 / 32767.0) * kStandardGravity;
    const double gyroscope_scale = (2000.0 / 32767.0) * (kPi / 180.0);
    constexpr double magnetic_scale = 800.0e-6 / 32767.0;
    serial_states_[kLinearAccelerationX] = decode_i16_le(payload) * acceleration_scale;
    serial_states_[kLinearAccelerationY] = decode_i16_le(payload + 2) * acceleration_scale;
    serial_states_[kLinearAccelerationZ] = decode_i16_le(payload + 4) * acceleration_scale;
    serial_states_[kAngularVelocityX] = decode_i16_le(payload + 6) * gyroscope_scale;
    serial_states_[kAngularVelocityY] = decode_i16_le(payload + 8) * gyroscope_scale;
    serial_states_[kAngularVelocityZ] = decode_i16_le(payload + 10) * gyroscope_scale;
    serial_states_[kMagneticFieldX] = decode_i16_le(payload + 12) * magnetic_scale;
    serial_states_[kMagneticFieldY] = decode_i16_le(payload + 14) * magnetic_scale;
    serial_states_[kMagneticFieldZ] = decode_i16_le(payload + 16) * magnetic_scale;
    updates.raw = true;
    have_serial_raw_ = true;
    return;
  }

  if (function == kSerialQuaternionReport) {
    if (payload_size < 16U) {
      updates.invalid = true;
      return;
    }
    std::array<double, 4> normalized{};
    if (!normalize_quaternion(
        decode_f32_le(payload), decode_f32_le(payload + 4),
        decode_f32_le(payload + 8), decode_f32_le(payload + 12), normalized))
    {
      updates.invalid = true;
      return;
    }
    serial_states_[kOrientationX] = normalized[0];
    serial_states_[kOrientationY] = normalized[1];
    serial_states_[kOrientationZ] = normalized[2];
    serial_states_[kOrientationW] = normalized[3];
    updates.quaternion = true;
    have_serial_quaternion_ = true;
    return;
  }

  if (function == kSerialBarometerReport) {
    if (!barometer_declared_) {
      return;
    }
    if (payload_size < 12U) {
      updates.invalid = true;
      return;
    }
    const double height = decode_f32_le(payload);
    const double temperature = decode_f32_le(payload + 4);
    const double pressure = decode_f32_le(payload + 8);
    if (!std::isfinite(height) || !std::isfinite(temperature) || !std::isfinite(pressure)) {
      updates.invalid = true;
      return;
    }
    serial_states_[kHeight] = height;
    serial_states_[kTemperature] = temperature;
    serial_states_[kPressure] = pressure;
    updates.barometer = true;
  }
}

}  // namespace robot_hardware

PLUGINLIB_EXPORT_CLASS(robot_hardware::YbImuSensor, hardware_interface::SensorInterface)
