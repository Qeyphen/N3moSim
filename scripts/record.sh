#!/bin/bash
TIMESTAMP=$(date +%Y_%m_%d_%H%M%S)
SESSION="session_${TIMESTAMP}"
OUTPUT_PATH="/recordings/${SESSION}"

echo "Starting recording: ${SESSION}"

docker exec -d n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 bag record \
    /occupancy_grid \
    /unity/all_poses \
    /sailboat/gps \
    /sailboat/imu \
    /environment/wind \
    /sailboat_01/cmd_vel \
    /sailboat_01/pose \
    /camera/compressed \
    -o ${OUTPUT_PATH} \
    --storage sqlite3
"

echo "Recording started — session: ${SESSION}"
echo "Run ./scripts/stop_record.sh to stop"
