#!/bin/bash
# record.sh
# Starts a new ROS2 bag recording session inside the bridge container.
# Creates a timestamped folder in /recordings.

TIMESTAMP=$(date +%Y_%m_%d_%H%M%S)
SESSION="session_${TIMESTAMP}"
OUTPUT_PATH="/recordings/${SESSION}"

echo "Starting recording: ${SESSION}"
echo "Output: ${OUTPUT_PATH}"

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
    -o ${OUTPUT_PATH} \
    --storage sqlite3
"

echo ""
echo "Recording started — session: ${SESSION}"
echo "Run ./scripts/stop_record.sh to stop"
echo "Run ./scripts/bag_to_csv.py ${SESSION} to export CSV"
