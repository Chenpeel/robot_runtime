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


#include "robot_hardware/bus_servo_protocol.hpp"

#include <algorithm>
#include <cctype>
#include <cstdio>
#include <stdexcept>

namespace robot_hardware
{
namespace
{

std::vector<std::uint8_t> lx_packet(
  std::uint16_t servo_id, std::uint8_t command,
  const std::vector<std::uint8_t> & parameters)
{
  const auto id = static_cast<std::uint8_t>(std::min<std::uint16_t>(servo_id, 253));
  const auto length = static_cast<std::uint8_t>(parameters.size() + 3);
  std::vector<std::uint8_t> packet{0x55, 0x55, id, length, command};
  packet.insert(packet.end(), parameters.begin(), parameters.end());
  unsigned int sum = id + length + command;
  for (const auto value : parameters) {
    sum += value;
  }
  packet.push_back(static_cast<std::uint8_t>(~sum));
  return packet;
}

std::vector<std::uint8_t> zl_packet(std::uint16_t servo_id, const std::string & body)
{
  char id[4]{};
  std::snprintf(id, sizeof(id), "%03u", std::min<std::uint16_t>(servo_id, 999));
  const std::string frame = "#" + std::string(id) + body + "!";
  return {frame.begin(), frame.end()};
}

std::optional<std::int32_t> decode_lx_position(
  const std::vector<std::uint8_t> & data, std::uint16_t expected_servo_id)
{
  for (std::size_t index = 0; index + 7 < data.size(); ++index) {
    if (data[index] != 0x55 || data[index + 1] != 0x55) {
      continue;
    }
    const auto id = data[index + 2];
    const auto length = data[index + 3];
    if (length < 5) {
      continue;
    }
    const std::size_t packet_size = static_cast<std::size_t>(length) + 3;
    if (index + packet_size > data.size() || id != expected_servo_id ||
      data[index + 4] != 0x1C)
    {
      continue;
    }
    unsigned int sum = 0;
    for (std::size_t cursor = index + 2; cursor < index + packet_size - 1; ++cursor) {
      sum += data[cursor];
    }
    if (static_cast<std::uint8_t>(~sum) != data[index + packet_size - 1]) {
      continue;
    }
    const std::uint16_t raw = static_cast<std::uint16_t>(data[index + 5]) |
      (static_cast<std::uint16_t>(data[index + 6]) << 8U);
    return raw >= 0x8000U ? static_cast<std::int32_t>(raw) - 0x10000 : raw;
  }
  return std::nullopt;
}

std::optional<std::int32_t> decode_zl_position(
  const std::vector<std::uint8_t> & data, std::uint16_t expected_servo_id)
{
  const std::string text(data.begin(), data.end());
  char prefix[6]{};
  std::snprintf(
    prefix, sizeof(prefix), "#%03uP", std::min<std::uint16_t>(expected_servo_id, 999));
  std::size_t cursor = text.find(prefix);
  while (cursor != std::string::npos) {
    cursor += 5;
    const std::size_t end = text.find('!', cursor);
    if (end == std::string::npos) {
      return std::nullopt;
    }
    const std::string value = text.substr(cursor, end - cursor);
    if (!value.empty() && std::all_of(
        value.begin() + (value.front() == '-' ? 1 : 0), value.end(),
        [](unsigned char character) {return std::isdigit(character) != 0;}))
    {
      try {
        return static_cast<std::int32_t>(std::stol(value));
      } catch (const std::exception &) {
        return std::nullopt;
      }
    }
    cursor = text.find(prefix, end + 1);
  }
  return std::nullopt;
}

}  // namespace

BusProtocol parse_bus_protocol(const std::string & value)
{
  std::string normalized = value;
  std::transform(
    normalized.begin(), normalized.end(), normalized.begin(),
    [](unsigned char character) {return static_cast<char>(std::tolower(character));});
  if (normalized == "lx") {
    return BusProtocol::kLx;
  }
  if (normalized == "zl") {
    return BusProtocol::kZl;
  }
  throw std::invalid_argument("protocol must be 'lx' or 'zl'");
}

std::vector<std::uint8_t> encode_move(
  BusProtocol protocol, std::uint16_t servo_id, std::uint16_t position,
  std::uint16_t duration_ms)
{
  if (protocol == BusProtocol::kLx) {
    position = std::min<std::uint16_t>(position, 1000);
    duration_ms = std::min<std::uint16_t>(duration_ms, 30000);
    return lx_packet(
      servo_id, 0x01,
      {static_cast<std::uint8_t>(position), static_cast<std::uint8_t>(position >> 8U),
        static_cast<std::uint8_t>(duration_ms),
        static_cast<std::uint8_t>(duration_ms >> 8U)});
  }
  position = std::min<std::uint16_t>(position, 9999);
  duration_ms = std::min<std::uint16_t>(duration_ms, 9999);
  char body[16]{};
  std::snprintf(body, sizeof(body), "P%04uT%04u", position, duration_ms);
  return zl_packet(servo_id, body);
}

std::vector<std::uint8_t> encode_stop(BusProtocol protocol, std::uint16_t servo_id)
{
  return protocol == BusProtocol::kLx ? lx_packet(servo_id, 0x0C, {}) :
         zl_packet(servo_id, "PDST");
}

std::vector<std::uint8_t> encode_torque_release(
  BusProtocol protocol, std::uint16_t servo_id)
{
  return protocol == BusProtocol::kLx ? lx_packet(servo_id, 0x1F, {0}) :
         zl_packet(servo_id, "PULK");
}

std::vector<std::uint8_t> encode_position_read(
  BusProtocol protocol, std::uint16_t servo_id)
{
  return protocol == BusProtocol::kLx ? lx_packet(servo_id, 0x1C, {}) :
         zl_packet(servo_id, "PRAD");
}

std::optional<std::int32_t> decode_position(
  BusProtocol protocol, const std::vector<std::uint8_t> & data,
  std::uint16_t expected_servo_id)
{
  return protocol == BusProtocol::kLx ? decode_lx_position(data, expected_servo_id) :
         decode_zl_position(data, expected_servo_id);
}

}  // namespace robot_hardware
