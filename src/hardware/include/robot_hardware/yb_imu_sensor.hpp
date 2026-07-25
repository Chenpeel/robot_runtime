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


#ifndef ROBOT_HARDWARE__YB_IMU_SENSOR_HPP_
#define ROBOT_HARDWARE__YB_IMU_SENSOR_HPP_

#include <array>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <string>
#include <utility>
#include <vector>

#include "hardware_interface/sensor_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/duration.hpp"
#include "rclcpp/time.hpp"
#include "rclcpp_lifecycle/state.hpp"

#include "robot_hardware/i2c_device.hpp"
#include "robot_hardware/serial_port.hpp"

namespace robot_hardware
{

class YbImuSensor final : public hardware_interface::SensorInterface
{
public:
  hardware_interface::CallbackReturn on_init(
    const hardware_interface::HardwareInfo & info) override;

  std::vector<hardware_interface::StateInterface> export_state_interfaces() override;

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

private:
  enum class Transport
  {
    kI2c,
    kSerial,
  };

  struct SerialUpdates
  {
    bool raw{false};
    bool quaternion{false};
    bool barometer{false};
    bool invalid{false};
  };

  static constexpr std::size_t kStateCount = 16;

  void mark_states_nan() noexcept;
  void reset_runtime_state() noexcept;
  void configure_i2c();
  void configure_serial();
  void calibrate_i2c();
  void calibrate_serial();
  hardware_interface::return_type read_i2c();
  hardware_interface::return_type read_serial();

  void write_serial_command(
    std::uint8_t function, const std::vector<std::uint8_t> & payload);
  SerialUpdates receive_serial_updates(std::chrono::milliseconds timeout);
  void parse_serial_buffer(SerialUpdates & updates);
  void parse_serial_frame(
    const std::vector<std::uint8_t> & frame, SerialUpdates & updates);

  Transport transport_{Transport::kI2c};
  std::string device_;
  std::uint8_t address_{0x23};
  int baud_rate_{115200};
  int algo_type_{9};
  bool calibrate_on_start_{false};
  std::chrono::milliseconds calibration_timeout_{7000};

  std::string sensor_name_;
  std::array<double, kStateCount> states_{};
  std::array<double, kStateCount> serial_states_{};
  std::vector<std::pair<std::string, std::size_t>> exported_interfaces_;
  bool magnetic_field_declared_{false};
  bool barometer_declared_{false};

  I2cDevice i2c_device_;
  SerialPort serial_port_;
  std::vector<std::uint8_t> serial_rx_buffer_;
  bool have_serial_raw_{false};
  bool have_serial_quaternion_{false};
  bool configured_{false};
  bool active_{false};
};

}  // namespace robot_hardware

#endif  // ROBOT_HARDWARE__YB_IMU_SENSOR_HPP_
