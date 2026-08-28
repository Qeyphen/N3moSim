#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ROS_ENV='source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && '

SCENE_SEED="${SCENE_SEED:-12345}"
TRACK_COUNT="${TRACK_COUNT:-18}"
AREA_TYPE="${AREA_TYPE:-coastal}"
OCCUPIED_FRACTION="${OCCUPIED_FRACTION:-0.8}"
TIME_OF_DAY="${TIME_OF_DAY:-8.0}"
WEATHER="${WEATHER:-foggy}"
FOG="${FOG:-0.5}"
WAVE="${WAVE:-0.85}"
WIND="${WIND:-0.6}"
CLOUDINESS="${CLOUDINESS:-0.6}"
RUN_DURATION_S="${RUN_DURATION_S:-60.0}"
CAPTURE_HZ="${CAPTURE_HZ:-8.0}"
WAYPOINT_PERIOD_S="${WAYPOINT_PERIOD_S:-12.0}"
RECORD_START_DELAY_S="${RECORD_START_DELAY_S:-2.0}"

as_float() {
  local value="$1"
  if [[ "$value" =~ ^[0-9]+$ ]]; then
    printf '%s.0' "$value"
  else
    printf '%s' "$value"
  fi
}

RUN_DURATION_S="$(as_float "$RUN_DURATION_S")"
CAPTURE_HZ="$(as_float "$CAPTURE_HZ")"
WAYPOINT_PERIOD_S="$(as_float "$WAYPOINT_PERIOD_S")"
RECORD_START_DELAY_S="$(as_float "$RECORD_START_DELAY_S")"
TIME_OF_DAY="$(as_float "$TIME_OF_DAY")"
FOG="$(as_float "$FOG")"
WAVE="$(as_float "$WAVE")"
WIND="$(as_float "$WIND")"
CLOUDINESS="$(as_float "$CLOUDINESS")"

ros_exec() {
  docker compose exec ros_bridge bash -lc "${ROS_ENV}$1"
}

echo "Starting ros_bridge and scenario services..."
docker compose up -d ros_bridge scenario

echo "Generating one deterministic scene for the defense video..."
ros_exec "ros2 param set /scenario_generator_node gen_random_seed ${SCENE_SEED}"
ros_exec "ros2 param set /scenario_generator_node gen_track_count ${TRACK_COUNT}"
ros_exec "ros2 param set /scenario_generator_node gen_area_type ${AREA_TYPE}"
ros_exec "ros2 param set /scenario_generator_node gen_bias_to_ego_view true"
ros_exec "ros2 param set /scenario_generator_node gen_ego_view_fraction ${OCCUPIED_FRACTION}"
ros_exec "ros2 service call /sim/generate_scenario std_srvs/srv/Trigger '{}'"

echo "Applying defense environment: time=${TIME_OF_DAY}, weather=${WEATHER}, fog=${FOG}, wave=${WAVE}, wind=${WIND}, cloudiness=${CLOUDINESS}"
ros_exec "ros2 run n3mo_control env_control --ros-args -p time:=${TIME_OF_DAY} -p weather:=${WEATHER}"
ros_exec "ros2 run n3mo_control env_control --ros-args -p fog:=${FOG} -p wave:=${WAVE} -p wind:=${WIND} -p cloudiness:=${CLOUDINESS}"

echo
echo "Unity must already be open in Play mode with the ego boat in Auto."
echo "Running auto-drive pass for ${RUN_DURATION_S}s..."

ros_exec "ros2 run n3mo_control dataset_sweep --ros-args \
  -p duration_s:=${RUN_DURATION_S} \
  -p hz:=${CAPTURE_HZ} \
  -p waypoint_period:=${WAYPOINT_PERIOD_S} \
  -p randomize_env_on_start:=false \
  -p randomize_env_during_run:=false \
  -p regenerate_on_start:=false \
  -p regenerate_during_run:=false \
  -p record_start_delay_s:=${RECORD_START_DELAY_S}"

echo
echo "Defense scene run complete."
