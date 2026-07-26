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


#ifndef ROBOT_HARDWARE__CONVERSION_HPP_
#define ROBOT_HARDWARE__CONVERSION_HPP_

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace robot_hardware
{

struct PositionCalibration
{
  double position_min{-1.5707963267948966};
  double position_max{1.5707963267948966};
  double raw_min{0.0};
  double raw_max{1000.0};
  double offset{0.0};
  double direction{1.0};
};

inline void validate_calibration(const PositionCalibration & value)
{
  if (!std::isfinite(value.position_min) || !std::isfinite(value.position_max) ||
    !std::isfinite(value.raw_min) || !std::isfinite(value.raw_max) ||
    !std::isfinite(value.offset) || !std::isfinite(value.direction) ||
    value.position_min >= value.position_max || value.raw_min >= value.raw_max ||
    (value.direction != 1.0 && value.direction != -1.0))
  {
    throw std::invalid_argument("invalid position calibration");
  }
}

inline double position_to_raw(double position, const PositionCalibration & calibration)
{
  validate_calibration(calibration);
  if (!std::isfinite(position)) {
    throw std::invalid_argument("position command must be finite");
  }
  const double directed = calibration.direction * position + calibration.offset;
  const double bounded = std::clamp(
    directed, calibration.position_min, calibration.position_max);
  const double ratio = (bounded - calibration.position_min) /
    (calibration.position_max - calibration.position_min);
  return calibration.raw_min + ratio * (calibration.raw_max - calibration.raw_min);
}

inline double raw_to_position(double raw, const PositionCalibration & calibration)
{
  validate_calibration(calibration);
  if (!std::isfinite(raw)) {
    throw std::invalid_argument("raw position must be finite");
  }
  const double bounded = std::clamp(raw, calibration.raw_min, calibration.raw_max);
  const double ratio = (bounded - calibration.raw_min) /
    (calibration.raw_max - calibration.raw_min);
  const double directed = calibration.position_min +
    ratio * (calibration.position_max - calibration.position_min);
  return calibration.direction * (directed - calibration.offset);
}

}  // namespace robot_hardware

#endif  // ROBOT_HARDWARE__CONVERSION_HPP_
