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


#include <cmath>
#include <limits>

#include "gtest/gtest.h"
#include "robot_hardware/conversion.hpp"

namespace robot_hardware
{

TEST(PositionConversion, MapsAndClampsEndpoints)
{
  PositionCalibration calibration;
  calibration.position_min = -1.0;
  calibration.position_max = 1.0;
  calibration.raw_min = 500.0;
  calibration.raw_max = 2500.0;

  EXPECT_DOUBLE_EQ(position_to_raw(-1.0, calibration), 500.0);
  EXPECT_DOUBLE_EQ(position_to_raw(0.0, calibration), 1500.0);
  EXPECT_DOUBLE_EQ(position_to_raw(2.0, calibration), 2500.0);
  EXPECT_DOUBLE_EQ(raw_to_position(1500.0, calibration), 0.0);
}

TEST(PositionConversion, RoundTripsDirectionAndOffset)
{
  PositionCalibration calibration;
  calibration.position_min = -1.5;
  calibration.position_max = 1.5;
  calibration.raw_min = 0.0;
  calibration.raw_max = 1000.0;
  calibration.direction = -1.0;
  calibration.offset = 0.1;

  for (const double value : {-1.0, -0.25, 0.0, 0.75}) {
    EXPECT_NEAR(raw_to_position(position_to_raw(value, calibration), calibration), value, 1e-12);
  }
}

TEST(PositionConversion, RejectsInvalidOrNonFiniteValues)
{
  PositionCalibration calibration;
  calibration.raw_max = calibration.raw_min;
  EXPECT_THROW(validate_calibration(calibration), std::invalid_argument);

  calibration.raw_max = 1000.0;
  EXPECT_THROW(
    position_to_raw(std::numeric_limits<double>::quiet_NaN(), calibration),
    std::invalid_argument);
}

}  // namespace robot_hardware
