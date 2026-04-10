#!/bin/bash
# Usage: ./switch_scenario.sh circles | eight | mixed
SCENARIO="scenario_${1}.json"
echo "Switching to: $SCENARIO"
docker stop n3mo_trajectory 2>/dev/null
docker exec n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  ros2 run n3mo_control trajectory_publisher \
  --ros-args -p scenario_file:=${SCENARIO} &
"
echo "Scenario active: $SCENARIO ✅"