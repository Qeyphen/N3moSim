#!/bin/bash
MODE=$1

if [ -z "$MODE" ]; then
    echo "Usage: ./switch_scenario.sh <circles|eight|mixed|stop>"
    exit 1
fi

# Kill any existing trajectory publisher
docker exec n3mo_controller bash -c "
    pkill -f trajectory_publisher 2>/dev/null || true
" 2>/dev/null

if [ "$MODE" = "stop" ]; then
    echo "Trajectory stopped ✅"
    exit 0
fi

SCENARIO="scenario_${MODE}.json"
echo "Starting scenario: $SCENARIO"

docker exec -d n3mo_controller bash -c "
    source /opt/ros/humble/setup.bash &&
    export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
    source /root/ros2_ws/install/setup.bash &&
    ros2 run n3mo_control trajectory_publisher \
        --ros-args -p scenario_file:=${SCENARIO}
"

echo "✅ Scenario active: ${MODE}"
echo "Verify: docker exec n3mo_controller bash -c 'source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 topic echo /mission/sailboat_01/cmd_vel --once'"