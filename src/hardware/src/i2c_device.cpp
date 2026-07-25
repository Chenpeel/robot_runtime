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


#include "robot_hardware/i2c_device.hpp"

#include <cerrno>
#include <stdexcept>
#include <system_error>

#if defined(__linux__)
#include <fcntl.h>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>
#include <unistd.h>
#endif

namespace robot_hardware
{
namespace
{

#if defined(__linux__)
void throw_system_error(const std::string & action)
{
  throw std::system_error(errno, std::generic_category(), action);
}
#endif

}  // namespace

I2cDevice::~I2cDevice()
{
  close();
}

void I2cDevice::open(const std::string & device, std::uint8_t address)
{
#if defined(__linux__)
  close();
  fd_ = ::open(device.c_str(), O_RDWR);
  if (fd_ < 0) {
    throw_system_error("open I2C device " + device);
  }
  if (::ioctl(fd_, I2C_SLAVE, static_cast<unsigned long>(address)) < 0) {  // NOLINT(runtime/int)
    const int saved_errno = errno;
    close();
    errno = saved_errno;
    throw_system_error("select I2C slave");
  }
#else
  (void)device;
  (void)address;
  throw std::runtime_error("I2C devices are only supported on Linux");
#endif
}

void I2cDevice::close() noexcept
{
#if defined(__linux__)
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
#endif
}

bool I2cDevice::is_open() const noexcept
{
  return fd_ >= 0;
}

void I2cDevice::write_byte(std::uint8_t reg, std::uint8_t value)
{
  write_block(reg, {value});
}

void I2cDevice::write_block(std::uint8_t reg, const std::vector<std::uint8_t> & data)
{
#if defined(__linux__)
  if (!is_open()) {
    throw std::logic_error("I2C device is not open");
  }
  if (data.size() > 31) {
    throw std::invalid_argument("I2C block payload exceeds 31 bytes");
  }
  std::vector<std::uint8_t> frame;
  frame.reserve(data.size() + 1);
  frame.push_back(reg);
  frame.insert(frame.end(), data.begin(), data.end());
  const ssize_t count = ::write(fd_, frame.data(), frame.size());
  if (count != static_cast<ssize_t>(frame.size())) {
    throw_system_error("write I2C block");
  }
#else
  (void)reg;
  (void)data;
#endif
}

std::vector<std::uint8_t> I2cDevice::read_block(std::uint8_t reg, std::size_t size)
{
  if (size == 0 || size > 32) {
    throw std::invalid_argument("I2C read size must be in [1, 32]");
  }
  std::vector<std::uint8_t> result(size);
#if defined(__linux__)
  if (!is_open()) {
    throw std::logic_error("I2C device is not open");
  }
  if (::write(fd_, &reg, 1) != 1) {
    throw_system_error("select I2C register");
  }
  const ssize_t count = ::read(fd_, result.data(), result.size());
  if (count != static_cast<ssize_t>(result.size())) {
    throw_system_error("read I2C block");
  }
#else
  (void)reg;
#endif
  return result;
}

}  // namespace robot_hardware
