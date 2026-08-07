#!/usr/bin/env bash
# Launch the built N3moSim Linux player headless (no window) on the GPU for dataset generation.
#
# Prereqs (fix the old HDRP/Vulkan crash):
#   * a GPU + driver + Vulkan  (check: `vulkaninfo` and `nvidia-smi` both work)
#   * built a NORMAL Linux player (not Dedicated Server) with, in Player Settings:
#       Graphics APIs = Vulkan (Auto Graphics API OFF), Graphics Jobs = OFF
#
# HDRP needs the GPU, so we do NOT pass -nographics. If a display is already available on the GPU
# (DISPLAY set), we use it; otherwise we start a virtual one with xvfb-run.
#
# Usage: ./run_headless.sh [path-to-N3moSim.x86_64] [width] [height]
set -euo pipefail

APP="${1:-./N3moSim.x86_64}"
W="${2:-1920}"
H="${3:-1080}"
LOG="headless_$(date +%Y%m%d_%H%M%S).log"

if [ ! -x "$APP" ]; then
  echo "app not found/executable: $APP  (build a Linux player first)"; exit 1
fi

RUN=("$APP" -batchmode -force-vulkan -screen-width "$W" -screen-height "$H" -logFile "$LOG")

echo "launching $APP at ${W}x${H}  (log: $LOG)"
if [ -n "${DISPLAY:-}" ]; then
  echo "using existing DISPLAY=$DISPLAY"
  "${RUN[@]}" &
else
  echo "no DISPLAY — starting a virtual one with xvfb-run"
  xvfb-run -a -s "-screen 0 ${W}x${H}x24" "${RUN[@]}" &
fi

echo "started (PID $!). Watch it:   tail -f $LOG"
echo "drive recording over ROS, e.g.:"
echo "  ros2 topic pub --once /camera/resolution std_msgs/msg/String '{data: 1080p}'"
echo "  ros2 topic pub --once /dataset/control std_msgs/msg/Bool '{data: true}'    # start"
echo "  ros2 topic pub --once /dataset/control std_msgs/msg/Bool '{data: false}'   # stop"
