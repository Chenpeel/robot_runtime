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


#include "robot_hardware/serial_port.hpp"

#include <cerrno>
#include <cstring>
#include <stdexcept>
#include <system_error>

#if defined(__unix__) || defined(__APPLE__)
#include <fcntl.h>
#include <poll.h>
#include <termios.h>
#include <unistd.h>
#endif

namespace robot_hardware
{
namespace
{

#if defined(__unix__) || defined(__APPLE__)
speed_t baud_constant(int baud_rate)
{
  switch (baud_rate) {
    case 9600: return B9600;
    case 19200: return B19200;
    case 38400: return B38400;
    case 57600: return B57600;
    case 115200: return B115200;
#ifdef B230400
    case 230400: return B230400;
#endif
#ifdef B460800
    case 460800: return B460800;
#endif
#ifdef B921600
    case 921600: return B921600;
#endif
    default: throw std::invalid_argument("unsupported serial baud rate");
  }
}

void throw_system_error(const std::string & action)
{
  throw std::system_error(errno, std::generic_category(), action);
}
#endif

}  // namespace

SerialPort::~SerialPort()
{
  close();
}

void SerialPort::open(const std::string & device, int baud_rate)
{
#if defined(__unix__) || defined(__APPLE__)
  close();
  fd_ = ::open(device.c_str(), O_RDWR | O_NOCTTY | O_NONBLOCK);
  if (fd_ < 0) {
    throw_system_error("open serial device " + device);
  }

  termios settings{};
  if (::tcgetattr(fd_, &settings) != 0) {
    const int saved_errno = errno;
    close();
    errno = saved_errno;
    throw_system_error("read serial settings");
  }
  ::cfmakeraw(&settings);
  const speed_t speed = baud_constant(baud_rate);
  ::cfsetispeed(&settings, speed);
  ::cfsetospeed(&settings, speed);
  settings.c_cflag |= CLOCAL | CREAD;
  settings.c_cflag &= ~CSTOPB;
  settings.c_cflag &= ~CRTSCTS;
  settings.c_cc[VMIN] = 0;
  settings.c_cc[VTIME] = 0;
  if (::tcsetattr(fd_, TCSANOW, &settings) != 0) {
    const int saved_errno = errno;
    close();
    errno = saved_errno;
    throw_system_error("configure serial device");
  }
  flush_input();
#else
  (void)device;
  (void)baud_rate;
  throw std::runtime_error("serial devices are unsupported on this platform");
#endif
}

void SerialPort::close() noexcept
{
#if defined(__unix__) || defined(__APPLE__)
  if (fd_ >= 0) {
    ::close(fd_);
    fd_ = -1;
  }
#endif
}

bool SerialPort::is_open() const noexcept
{
  return fd_ >= 0;
}

void SerialPort::flush_input()
{
#if defined(__unix__) || defined(__APPLE__)
  if (!is_open()) {
    throw std::logic_error("serial device is not open");
  }
  if (::tcflush(fd_, TCIFLUSH) != 0) {
    throw_system_error("flush serial input");
  }
#endif
}

void SerialPort::write_all(const std::vector<std::uint8_t> & data)
{
#if defined(__unix__) || defined(__APPLE__)
  if (!is_open()) {
    throw std::logic_error("serial device is not open");
  }
  std::size_t written = 0;
  while (written < data.size()) {
    const ssize_t count = ::write(fd_, data.data() + written, data.size() - written);
    if (count > 0) {
      written += static_cast<std::size_t>(count);
      continue;
    }
    if (count < 0 && (errno == EINTR || errno == EAGAIN)) {
      continue;
    }
    throw_system_error("write serial data");
  }
  if (::tcdrain(fd_) != 0) {
    throw_system_error("drain serial output");
  }
#else
  (void)data;
#endif
}

std::vector<std::uint8_t> SerialPort::read_some(
  std::size_t max_size, std::chrono::milliseconds timeout)
{
  std::vector<std::uint8_t> result;
#if defined(__unix__) || defined(__APPLE__)
  if (!is_open()) {
    throw std::logic_error("serial device is not open");
  }
  if (max_size == 0) {
    return result;
  }
  pollfd descriptor{fd_, POLLIN, 0};
  const int ready = ::poll(&descriptor, 1, static_cast<int>(timeout.count()));
  if (ready < 0) {
    if (errno == EINTR) {
      return result;
    }
    throw_system_error("poll serial input");
  }
  if (ready == 0 || !(descriptor.revents & POLLIN)) {
    return result;
  }
  result.resize(max_size);
  const ssize_t count = ::read(fd_, result.data(), result.size());
  if (count < 0) {
    if (errno == EAGAIN || errno == EINTR) {
      result.clear();
      return result;
    }
    throw_system_error("read serial data");
  }
  result.resize(static_cast<std::size_t>(count));
#else
  (void)max_size;
  (void)timeout;
#endif
  return result;
}

std::vector<std::uint8_t> SerialPort::exchange(
  const std::vector<std::uint8_t> & request,
  std::chrono::milliseconds response_timeout,
  std::chrono::milliseconds inter_byte_timeout)
{
  flush_input();
  write_all(request);

  std::vector<std::uint8_t> response;
  const auto deadline = std::chrono::steady_clock::now() + response_timeout;
  bool received_data = false;
  while (std::chrono::steady_clock::now() < deadline) {
    const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(
      deadline - std::chrono::steady_clock::now());
    const auto wait = received_data ? inter_byte_timeout : remaining;
    auto chunk = read_some(512, wait);
    if (chunk.empty()) {
      if (received_data) {
        break;
      }
      continue;
    }
    received_data = true;
    response.insert(response.end(), chunk.begin(), chunk.end());
  }
  return response;
}

}  // namespace robot_hardware
