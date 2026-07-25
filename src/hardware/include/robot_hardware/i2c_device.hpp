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


#ifndef ROBOT_HARDWARE__I2C_DEVICE_HPP_
#define ROBOT_HARDWARE__I2C_DEVICE_HPP_

#include <cstddef>
#include <cstdint>
#include <string>
#include <vector>

namespace robot_hardware
{

class I2cDevice
{
public:
  I2cDevice() = default;
  ~I2cDevice();

  I2cDevice(const I2cDevice &) = delete;
  I2cDevice & operator=(const I2cDevice &) = delete;

  void open(const std::string & device, std::uint8_t address);
  void close() noexcept;
  [[nodiscard]] bool is_open() const noexcept;
  void write_byte(std::uint8_t reg, std::uint8_t value);
  void write_block(std::uint8_t reg, const std::vector<std::uint8_t> & data);
  std::vector<std::uint8_t> read_block(std::uint8_t reg, std::size_t size);

private:
  int fd_{-1};
};

}  // namespace robot_hardware

#endif  // ROBOT_HARDWARE__I2C_DEVICE_HPP_
