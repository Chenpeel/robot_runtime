cmake_minimum_required(VERSION 3.8)
project(motion_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(action_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "action/ExecuteMotion.action"
  "msg/ActuatorState.msg"
  "msg/MotionCommand.msg"
  "msg/ExecutionState.msg"
  "msg/TaskExecutionControl.msg"
  "msg/TaskExecutionState.msg"
  "msg/TeleopControl.msg"
  "srv/ReadActuatorPosition.srv"
  "srv/StopActuators.srv"
  DEPENDENCIES action_msgs builtin_interfaces
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)

  ament_add_pytest_test(test_motion_command_speed_migration
    "${CMAKE_CURRENT_SOURCE_DIR}/test/test_motion_command_speed_migration.py"
    APPEND_ENV "PYTHONDONTWRITEBYTECODE=1"
    TIMEOUT 60
  )

  ament_add_pytest_test(test_phase3_execution_boundary
    "${CMAKE_CURRENT_SOURCE_DIR}/test/test_phase3_execution_boundary.py"
    APPEND_ENV "PYTHONDONTWRITEBYTECODE=1"
    TIMEOUT 60
  )

  ament_add_pytest_test(test_phase4_task_admission_boundary
    "${CMAKE_CURRENT_SOURCE_DIR}/test/test_phase4_task_admission_boundary.py"
    APPEND_ENV "PYTHONDONTWRITEBYTECODE=1"
    TIMEOUT 60
  )

  ament_add_pytest_test(test_execute_motion_action_contract
    "${CMAKE_CURRENT_SOURCE_DIR}/test/test_execute_motion_action_contract.py"
    APPEND_ENV "PYTHONDONTWRITEBYTECODE=1"
    TIMEOUT 60
  )

  ament_add_pytest_test(test_actuator_service_contracts
    "${CMAKE_CURRENT_SOURCE_DIR}/test/test_actuator_service_contracts.py"
    APPEND_ENV "PYTHONDONTWRITEBYTECODE=1"
    TIMEOUT 60
  )
endif()

ament_export_dependencies(rosidl_default_runtime)

ament_package()
