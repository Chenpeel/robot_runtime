cmake_minimum_required(VERSION 3.8)
project(motion_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/MotionCommand.msg"
  "msg/ExecutionState.msg"
  "msg/TeleopControl.msg"
  DEPENDENCIES builtin_interfaces
)

if(BUILD_TESTING)
  find_package(ament_cmake_test REQUIRED)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)

  ament_add_test(test_motion_command_speed_migration
    COMMAND
      "${Python3_EXECUTABLE}"
      "${CMAKE_CURRENT_SOURCE_DIR}/test/test_motion_command_speed_migration.py"
    ENV "PYTHONDONTWRITEBYTECODE=1"
    TIMEOUT 60
  )
endif()

ament_export_dependencies(rosidl_default_runtime)

ament_package()
