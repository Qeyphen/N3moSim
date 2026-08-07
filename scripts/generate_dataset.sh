#!/usr/bin/env bash
# Unattended dataset run: record while the boat drives + weather/traffic randomise, stop at N frames.
#
# Drives the whole thing over ROS via the dataset_sweep node. You just need the sim connected
# to the bridge and the boat in AUTO mode; this starts recording, moves the boat through traffic,
# randomises the environment, keeps traffic fresh, and stops when Unity reports FRAMES frames.
#
# Prereqs:
#   * `docker compose build` after pulling (dataset_sweep is a new node — the image must rebuild)
#   * bridge + scenario up:    docker compose up -d ros_bridge scenario
#       (scenario is profile-gated, so a plain `up -d` skips it and there is NO traffic —
#        TrackSpawner needs /sim/tracks from the scenario generator)
#   * Unity in Play (editor) OR the headless player running (scripts/run_headless.sh), connected
#   * the boat in AUTO mode (Scene.json control_mode: "auto") so it follows the waypoints
#
# Then, when it stops, generate YOLO manually:
#   python3 tools/filter_boxes.py <solo_dir> --apply
#   python3 tools/solo_to_yolo.py <solo_dir> yolo/
#
# Usage: ./scripts/generate_dataset.sh [frames] [hz]
set -euo pipefail

FRAMES="${1:-10000}"
HZ="${2:-10}"
case "$HZ" in *.*) ;; *) HZ="${HZ}.0" ;; esac   # ROS needs a float for the hz param (8 -> 8.0)

echo "Recording ${FRAMES} frames. The boat will drive itself; weather + traffic will vary."
echo "Ctrl-C stops the sweep (recording is left ON if you interrupt — send /dataset/control false to stop)."

# The scenario generator feeds /sim/tracks -> TrackSpawner. It is profile-gated, so make sure
# it (and the bridge) are up; without it there is no traffic and frames are empty water.
echo "Ensuring bridge + scenario generator are running..."
docker compose up -d ros_bridge scenario

docker compose exec ros_bridge bash -lc "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  ros2 run n3mo_control dataset_sweep --ros-args -p frames:=${FRAMES} -p hz:=${HZ}
"

echo
echo "Done. The latest solo* folder now holds ~${FRAMES} frames + run_metadata_*.json."
echo "Generate YOLO:"
echo "  python3 tools/filter_boxes.py <solo_dir> --apply"
echo "  python3 tools/solo_to_yolo.py <solo_dir> yolo/"
