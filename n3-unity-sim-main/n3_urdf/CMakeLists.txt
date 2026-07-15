cmake_minimum_required(VERSION 3.8)
project(n3_urdf)

find_package(ament_cmake REQUIRED)

install(DIRECTORY
  urdf
  launch
  meshes
  textures
  rviz
  DESTINATION share/${PROJECT_NAME}
)

ament_package()
