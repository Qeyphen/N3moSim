#!/bin/bash
# stop_record.sh
# Stops the active ROS2 bag recording cleanly.

echo "Stopping recording..."

docker exec n3mo_bridge bash -c "
  pkill -f 'ros2 bag record' && echo 'Recording stopped.'
"

echo ""
echo "Done. Check recordings/ folder for your session files."
ls -la recordings/ 2>/dev/null || echo "No recordings folder found locally."
