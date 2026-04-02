#!/bin/bash
# send_command.sh
# Helper script to send movement commands to N3moSim objects
#
# Usage:
#   ./send_command.sh <object_id> <linear_x> <angular_z>
#
# Examples:
#   ./send_command.sh sailboat_01 1.0 0.0    ← move forward
#   ./send_command.sh sailboat_01 0.5 1.0    ← forward + turn right
#   ./send_command.sh catamaran_01 0.3 -0.5  ← slow + turn left
#   ./send_command.sh buoy_03 0.0 0.0        ← stop
#   ./send_command.sh all stop               ← stop all objects

OBJECT_ID=$1
LINEAR_X=$2
ANGULAR_Z=$3

if [ -z "$OBJECT_ID" ]; then
    echo "Usage: ./send_command.sh <object_id> <linear_x> <angular_z>"
    echo ""
    echo "Examples:"
    echo "  ./send_command.sh sailboat_01 1.0 0.0"
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
            source /opt/ros/humble/setup.bash &&
            ros2 topic pub --once /mission/${obj}/cmd_vel \
                geometry_msgs/msg/Twist \
                '{linear: {x: 0.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}'
        "
        echo "  Stopped: $obj"
    done
    
    echo "All objects stopped!"
    exit 0
fi

# Send command to specific object
if [ -z "$LINEAR_X" ] || [ -z "$ANGULAR_Z" ]; then
    echo "Error: missing linear_x or angular_z"
    echo "Usage: ./send_command.sh <object_id> <linear_x> <angular_z>"
    exit 1
fi

echo "Sending command to $OBJECT_ID:"
echo "  linear.x  = $LINEAR_X"
echo "  angular.z = $ANGULAR_Z"

docker exec n3mo_bridge bash -c "
    source /opt/ros/humble/setup.bash &&
    ros2 topic pub --once /mission/${OBJECT_ID}/cmd_vel \
        geometry_msgs/msg/Twist \
        '{linear: {x: ${LINEAR_X}, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: ${ANGULAR_Z}}}'
"

echo "Command sent to $OBJECT_ID ✅"