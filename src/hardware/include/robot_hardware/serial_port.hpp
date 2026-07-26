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


#ifndef ROBOT_HARDWARE__SERIAL_PORT_HPP_
#define ROBOT_HARDWARE__SERIAL_PORT_HPP_

#include <chrono>
#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace robot_hardware
{

class SerialPort
{
public:
  SerialPort() = default;
  ~SerialPort();

  SerialPort(const SerialPort &) = delete;
  SerialPort & operator=(const SerialPort &) = delete;

  void open(const std::string & device, int baud_rate);
  void close() noexcept;
  [[nodiscard]] bool is_open() const noexcept;
  void flush_input();
  void write_all(const std::vector<std::uint8_t> & data);
  std::vector<std::uint8_t> read_some(
    std::size_t max_size, std::chrono::milliseconds timeout);
  std::vector<std::uint8_t> exchange(
    const std::vector<std::uint8_t> & request,
    std::chrono::milliseconds response_timeout,
    std::chrono::milliseconds inter_byte_timeout = std::chrono::milliseconds(2));

private:
  int fd_{-1};
};

}  // namespace robot_hardware

#endif  // ROBOT_HARDWARE__SERIAL_PORT_HPP_
