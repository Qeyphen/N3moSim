# #!/bin/bash
# # switch_scenario.sh
# # Usage: ./scripts/switch_scenario.sh <circles|eight|mixed|stop>

# MODE=$1

# if [ -z "$MODE" ]; then
#     echo "Usage: ./scripts/switch_scenario.sh <circles|eight|mixed|stop>"
#     echo ""
#     echo "  circles  — all vessels circle"
#     echo "  eight    — all vessels figure-8"
#     echo "  mixed    — mixed (best for demo)"
#     echo "  stop     — stop all vessels"
#     exit 1
# fi

# # Kill any existing trajectory publisher
# docker exec n3mo_controller bash -c "pkill -f trajectory_publisher 2>/dev/null || true" 2>/dev/null
# sleep 1

# # Handle stop
# if [ "$MODE" = "stop" ]; then
#     echo "Stopping all vessels..."
#     OBJECTS=("sailboat_01" "catamaran_01" "catamaran_02" "buoy_03")
#     for obj in "${OBJECTS[@]}"; do
#         docker exec n3mo_controller bash -c "
#             source /opt/ros/humble/setup.bash &&
#             source /root/ros2_ws/install/setup.bash &&
#             ros2 topic pub --times 30 /mission/${obj}/cmd_vel \
#                 geometry_msgs/msg/Twist \
#                 '{linear: {x: 0.0}, angular: {z: 0.0}}' 2>/dev/null
#         " &
#     done
#     wait
#     echo "All vessels stopped ✅"
#     exit 0
# fi

# SCENARIO="scenario_${MODE}.json"
# echo "Starting scenario: $SCENARIO"

# # Start trajectory publisher in n3mo_controller container
# docker exec -d n3mo_controller bash -c "
#     source /opt/ros/humble/setup.bash &&
#     export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
#     source /root/ros2_ws/install/setup.bash &&
#     ros2 run n3mo_control trajectory_publisher \
#         --ros-args -p scenario_file:=${SCENARIO}
# "

# echo "✅ Scenario active: ${MODE}"
# echo "   Watch: docker logs -f n3mo_controller"

#!/bin/bash
MODE=$1
docker exec n3mo_controller bash -c "pkill -f pose_publisher 2>/dev/null || true"
sleep 1

if [ "$MODE" = "stop" ]; then
    echo "Stopped ✅"
    exit 0
fi

docker exec -d n3mo_controller bash -c "
  source /opt/ros/humble/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  source /root/ros2_ws/install/setup.bash &&
  ros2 run n3mo_control pose_publisher \
    --ros-args -p scenario:=${MODE} -p radius:=50.0 -p speed:=0.3
"
echo "✅ Scenario: ${MODE}"