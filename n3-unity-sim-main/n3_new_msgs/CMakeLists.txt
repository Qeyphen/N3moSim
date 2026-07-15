cmake_minimum_required(VERSION 3.8)
project(n3_new_msgs)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME}
  "msg/Waypoint.msg"
  "msg/WaypointList.msg"
  "msg/Velocity.msg"
  "msg/Wind.msg"
  "msg/SailAngle.msg"
  "msg/MissionState.msg"
  "msg/PlanState.msg"
  "msg/Maneuver.msg"
  "msg/PilotCommand.msg"
  "msg/ResetPID.msg"
  "msg/Anemometer.msg"
  "msg/PilotStatus.msg"
  "msg/Track.msg"
  "msg/TrackArray.msg"
  "msg/Detection.msg"
  "msg/DetectionArray.msg"
  "srv/SetBringupTarget.srv"
  "srv/UpdateCode.srv"
  "srv/ScenarioCommand.srv"
  DEPENDENCIES geometry_msgs std_msgs
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
