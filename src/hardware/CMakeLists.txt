cmake_minimum_required(VERSION 3.10)
project(robot_hardware)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(hardware_interface REQUIRED)
find_package(pluginlib REQUIRED)
find_package(rclcpp REQUIRED)
find_package(rclcpp_lifecycle REQUIRED)

add_library(${PROJECT_NAME} SHARED
  src/bus_servo_protocol.cpp
  src/bus_servo_system.cpp
  src/i2c_device.cpp
  src/pca9685_system.cpp
  src/position_actuator_system.cpp
  src/serial_port.cpp
  src/yb_imu_sensor.cpp
)
target_include_directories(${PROJECT_NAME} PUBLIC
  $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
  $<INSTALL_INTERFACE:include>
)
ament_target_dependencies(${PROJECT_NAME}
  hardware_interface
  pluginlib
  rclcpp
  rclcpp_lifecycle
)

pluginlib_export_plugin_description_file(
  hardware_interface robot_hardware_plugins.xml)

install(
  TARGETS ${PROJECT_NAME}
  EXPORT export_${PROJECT_NAME}
  ARCHIVE DESTINATION lib
  LIBRARY DESTINATION lib
  RUNTIME DESTINATION bin
)
install(DIRECTORY include/ DESTINATION include)
install(DIRECTORY config launch urdf DESTINATION share/${PROJECT_NAME})
install(FILES README.md robot_hardware_plugins.xml DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()

  ament_add_gtest(test_bus_servo_protocol test/test_bus_servo_protocol.cpp)
  target_link_libraries(test_bus_servo_protocol ${PROJECT_NAME})
  set_tests_properties(test_bus_servo_protocol PROPERTIES TIMEOUT 60)

  ament_add_gtest(test_conversion test/test_conversion.cpp)
  target_link_libraries(test_conversion ${PROJECT_NAME})

endif()

ament_export_targets(export_${PROJECT_NAME} HAS_LIBRARY_TARGET)
ament_export_dependencies(
  hardware_interface
  pluginlib
  rclcpp
  rclcpp_lifecycle
)
ament_package()

if(BUILD_TESTING)
  get_property(package_tests DIRECTORY PROPERTY TESTS)
  set_tests_properties(${package_tests} PROPERTIES TIMEOUT 60)
endif()
