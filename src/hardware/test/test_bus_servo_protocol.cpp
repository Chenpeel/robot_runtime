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


#include <cstdint>
#include <vector>

#include "gtest/gtest.h"
#include "robot_hardware/bus_servo_protocol.hpp"

namespace robot_hardware
{

TEST(BusServoProtocol, EncodesLxMoveGoldenFrame)
{
  EXPECT_EQ(
    encode_move(BusProtocol::kLx, 1, 500, 100),
    (std::vector<std::uint8_t>{
      0x55, 0x55, 0x01, 0x07, 0x01, 0xF4, 0x01, 0x64, 0x00, 0x9D}));
}

TEST(BusServoProtocol, EncodesZlFrames)
{
  EXPECT_EQ(
    encode_move(BusProtocol::kZl, 35, 1500, 100),
    (std::vector<std::uint8_t>{
      '#', '0', '3', '5', 'P', '1', '5', '0', '0', 'T', '0', '1', '0', '0', '!'}));
  EXPECT_EQ(
    encode_position_read(BusProtocol::kZl, 35),
    (std::vector<std::uint8_t>{'#', '0', '3', '5', 'P', 'R', 'A', 'D', '!'}));
  EXPECT_EQ(
    encode_stop(BusProtocol::kZl, 35),
    (std::vector<std::uint8_t>{'#', '0', '3', '5', 'P', 'D', 'S', 'T', '!'}));
}

TEST(BusServoProtocol, DecodesLxPositionAndRejectsBadChecksum)
{
  std::vector<std::uint8_t> response{
    0x00, 0x55, 0x55, 0x01, 0x05, 0x1C, 0xF4, 0x01, 0xE8};
  EXPECT_EQ(decode_position(BusProtocol::kLx, response, 1), 500);
  response.back() = 0;
  EXPECT_FALSE(decode_position(BusProtocol::kLx, response, 1).has_value());
}

TEST(BusServoProtocol, DecodesOnlyExpectedZlServo)
{
  const std::vector<std::uint8_t> response{
    '#', '0', '3', '4', 'P', '1', '2', '3', '4', '!',
    '#', '0', '3', '5', 'P', '1', '5', '0', '0', '!'};
  EXPECT_EQ(decode_position(BusProtocol::kZl, response, 35), 1500);
  EXPECT_FALSE(decode_position(BusProtocol::kZl, response, 36).has_value());
}

TEST(BusServoProtocol, RejectsUnknownProtocol)
{
  EXPECT_THROW(parse_bus_protocol("auto"), std::invalid_argument);
  EXPECT_EQ(parse_bus_protocol("LX"), BusProtocol::kLx);
}

}  // namespace robot_hardware
