#!/bin/bash
# send_command.sh
# Helper script to send movement commands to N3moSim objects
#
# Usage:
#   ./send_command.sh <object_id> <linear_x> <angular_z> [times]
#
# Examples:
#   ./send_command.sh sailboat_01 1.0 0.0       ← move forward
#   ./send_command.sh sailboat_01 0.5 1.0       ← forward + turn right
#   ./send_command.sh catamaran_01 0.3 -0.5     ← slow + turn left
#   ./send_command.sh buoy_03 0.0 0.0           ← stop
#   ./send_command.sh all stop                  ← stop all objects
#   ./send_command.sh sailboat_01 1.0 0.0 keep  ← keep sending continuously
#

OBJECT_ID=$1
LINEAR_X=$2
ANGULAR_Z=$3
MODE=$4  # optional: "keep" for continuous, number for times

# ROS2 source command 
ROS_SOURCE="source /opt/ros/humble/setup.bash && \
    export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH && \
    source /root/ros2_ws/install/setup.bash"

# Validate inputs 
if [ -z "$OBJECT_ID" ]; then
    echo "Usage: ./send_command.sh <object_id> <linear_x> <angular_z> [keep|N]"
    echo ""
    echo "Examples:"
    echo "  ./send_command.sh sailboat_01 1.0 0.0        # send 20 times"
    echo "  ./send_command.sh sailboat_01 1.0 0.0 keep   # continuous"
    echo "  ./send_command.sh sailboat_01 1.0 0.0 50     # send 50 times"
    echo "  ./send_command.sh catamaran_01 0.5 1.0"
    echo "  ./send_command.sh buoy_03 0.0 0.0"
    echo "  ./send_command.sh all stop"
    exit 1
fi

# Stop all objects 
if [ "$OBJECT_ID" = "all" ] && [ "$LINEAR_X" = "stop" ]; then
    echo "Stopping all objects..."

    OBJECTS=("sailboat_01" "catamaran_01" "catamaran_02" "buoy_03")

    for obj in "${OBJECTS[@]}"; do
        docker exec n3mo_bridge bash -c "
            ${ROS_SOURCE} &&
            ros2 topic pub --times 20 /mission/${obj}/cmd_vel \
                geometry_msgs/msg/Twist \
                '{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}' \
                2>/dev/null
        " &
        echo "  Stopped: $obj"
    done

    wait
    echo "All objects stopped! ✅"
    exit 0
fi

# Validate linear_x and angular_z 
if [ -z "$LINEAR_X" ] || [ -z "$ANGULAR_Z" ]; then
    echo "Error: missing linear_x or angular_z"
    echo "Usage: ./send_command.sh <object_id> <linear_x> <angular_z>"
    exit 1
fi

echo "Sending command to $OBJECT_ID:"
echo "  linear.x  = $LINEAR_X"
echo "  angular.z = $ANGULAR_Z"

# Continuous mode 
if [ "$MODE" = "keep" ]; then
    echo "  mode: continuous (Ctrl+C to stop)"
    docker exec n3mo_bridge bash -c "
        ${ROS_SOURCE} &&
        ros2 topic pub --rate 10 /mission/${OBJECT_ID}/cmd_vel \
            geometry_msgs/msg/Twist \
            '{linear: {x: ${LINEAR_X}, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: ${ANGULAR_Z}}}'
    "
    exit 0
fi

# N times mode 
# Default 20 times — enough for n3mo_controller to receive and forward to Unity
TIMES=${MODE:-20}

echo "  mode: sending ${TIMES} times"

docker exec n3mo_bridge bash -c "
    ${ROS_SOURCE} &&
    ros2 topic pub --times ${TIMES} /mission/${OBJECT_ID}/cmd_vel \
        geometry_msgs/msg/Twist \
        '{linear: {x: ${LINEAR_X}, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: ${ANGULAR_Z}}}' \
        2>/dev/null
"

echo "Command sent to $OBJECT_ID ✅"