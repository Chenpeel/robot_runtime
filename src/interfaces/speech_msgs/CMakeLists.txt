cmake_minimum_required(VERSION 3.8)
project(speech_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/SpeechIntent.msg"
  DEPENDENCIES builtin_interfaces
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)

  ament_add_pytest_test(test_speech_intent_contract
    "${CMAKE_CURRENT_SOURCE_DIR}/test/test_speech_intent_contract.py"
    APPEND_ENV "PYTHONDONTWRITEBYTECODE=1"
    TIMEOUT 60
  )
endif()

ament_export_dependencies(rosidl_default_runtime)

ament_package()
