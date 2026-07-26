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


#ifndef ROBOT_HARDWARE__BUS_SERVO_PROTOCOL_HPP_
#define ROBOT_HARDWARE__BUS_SERVO_PROTOCOL_HPP_

#include <cstdint>
#include <optional>
#include <string>
#include <vector>

namespace robot_hardware
{

enum class BusProtocol {kLx, kZl};

BusProtocol parse_bus_protocol(const std::string & value);
std::vector<std::uint8_t> encode_move(
  BusProtocol protocol, std::uint16_t servo_id, std::uint16_t position,
  std::uint16_t duration_ms);
std::vector<std::uint8_t> encode_stop(BusProtocol protocol, std::uint16_t servo_id);
std::vector<std::uint8_t> encode_torque_release(
  BusProtocol protocol, std::uint16_t servo_id);
std::vector<std::uint8_t> encode_position_read(
  BusProtocol protocol, std::uint16_t servo_id);
std::optional<std::int32_t> decode_position(
  BusProtocol protocol, const std::vector<std::uint8_t> & data,
  std::uint16_t expected_servo_id);

}  // namespace robot_hardware

#endif  // ROBOT_HARDWARE__BUS_SERVO_PROTOCOL_HPP_
