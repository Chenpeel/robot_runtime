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


#ifndef ROBOT_HARDWARE__BUS_SERVO_SYSTEM_HPP_
#define ROBOT_HARDWARE__BUS_SERVO_SYSTEM_HPP_

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <limits>
#include <string>
#include <unordered_set>
#include <vector>

#include "hardware_interface/system_interface.hpp"
#include "hardware_interface/types/hardware_interface_return_values.hpp"
#include "rclcpp/macros.hpp"
#include "robot_hardware/bus_servo_protocol.hpp"
#include "robot_hardware/conversion.hpp"
#include "robot_hardware/serial_port.hpp"

namespace robot_hardware
{

class BusServoSystem : public hardware_interface::SystemInterface
{
public:
  RCLCPP_SHARED_PTR_DEFINITIONS(BusServoSystem)

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

private:
  struct Servo
  {
    std::uint16_t id{0};
    BusProtocol protocol{BusProtocol::kZl};
    PositionCalibration calibration;
    double state{std::numeric_limits<double>::quiet_NaN()};
    double command{std::numeric_limits<double>::quiet_NaN()};
    double last_command{std::numeric_limits<double>::quiet_NaN()};
    unsigned int consecutive_errors{0};
  };

  bool read_servo(std::size_t index, bool report_error);
  void stop_all() noexcept;

  std::string port_;
  int baud_rate_{115200};
  std::uint16_t move_duration_ms_{100};
  std::chrono::milliseconds read_timeout_{20};
  std::size_t feedback_per_cycle_{1};
  unsigned int max_consecutive_errors_{5};
  bool read_position_{true};
  bool release_torque_on_deactivate_{false};
  std::size_t next_feedback_index_{0};
  std::vector<Servo> servos_;
  SerialPort serial_;
};

}  // namespace robot_hardware

#endif  // ROBOT_HARDWARE__BUS_SERVO_SYSTEM_HPP_
