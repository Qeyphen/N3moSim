# N3moSim — Testing & Recording Runbook

> End-to-end pipeline verification for occupancy grid, live map, recording, and ML dataset export.

| | |
|---|---|
| **Stack** | Unity 6 + ROS2 Humble + Docker |
| **Project** | N3moSim / Marine Autonomous Vessel |

---

## Overview

Follow these 10 phases in order every time you run the simulation, verify the occupancy grid, record a session, and export an ML-ready dataset.

```
Phase 0  — Clean start            stop and restart all Docker containers
Phase 1  — Occupancy grid         verify static buoys appear (no Unity yet)
Phase 2  — Connect Unity          verify sailboat appears on the grid
Phase 3  — Start pose publisher   boat moves in circles
Phase 4  — Verify camera          frames flowing at ~10Hz
Phase 5  — Start recording        capture all 8 topics
Phase 6  — Stop recording
Phase 7  — Verify the bag         check message counts per topic
Phase 8  — Export to CSV + frames convert bag to ML files
Phase 9  — Verify exported data   check files, sizes, trajectory
Phase 10 — ML readiness check     final validation
```

> ⚠️ **Run phases in order. Do not skip ahead.** Starting the recording before Unity is playing will produce empty CSV files.

---

## Phase 0 — Clean Start

Stop and restart all Docker containers.

```bash
# Stop everything
docker compose -f docker-compose-ros2.yml down

# Start fresh
docker compose -f docker-compose-ros2.yml up -d

# Watch all containers start
docker compose -f docker-compose-ros2.yml logs -f
```

Wait until you see **all five** of these messages before continuing:

```
✓ Starting ROS TCP Bridge on 0.0.0.0:10000
✓ Starting N3mo Controller
✓ OccupancyGridServer ready — 1000.0x1000.0m @ 1.0m/cell
✓ Starting Grid Visualiser on http://localhost:8080
✓ Starting Image Bridge
```

> 💡 Ctrl+C to stop watching logs once you see all five. The containers keep running in the background.

---

## Phase 1 — Verify Occupancy Grid

Static buoys only — Unity not connected yet.

Before starting Unity, verify the occupancy grid server is running and the static buoys appear.

```bash
docker exec -it n3mo_grid bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control grid_checker
"
```

Expected — 39 occupied cells (3 buoys × 13 cells each):

```
✓ Map size    : 1000x1000 cells
✓ Occupied    : 39  (value=100)
✓ Free        : 999961  (value=0)
```

Open the browser map. You should see 3 cyan dot clusters (the buoys). No moving dot yet.

```
http://localhost:8080
```

> ⚠️ If Occupied shows 0 — the occupancy grid server is not running. Check: `docker logs n3mo_grid`

---

## Phase 2 — Connect Unity

Hit **Play** in Unity. Wait 3 seconds for the ROS TCP connection to establish.

### Verify Unity is connected

```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 topic hz /unity/all_poses
"
```

```
✓ average rate: ~2.0
```

### Verify grid updated with sailboat

Run the grid checker again. Occupied should now be 52:

```
✓ Occupied    : 52  (value=100)   ← 39 buoys + 13 sailboat
```

The browser map at `http://localhost:8080` should now show 4 dot clusters: 3 static buoys + 1 sailboat.

> ⚠️ If `/unity/all_poses` shows no rate — Unity is not connected. Check the Unity Console for connection errors.

> 💡 If connection fails on Mac: `docker compose -f docker-compose-ros2.yml down && docker compose -f docker-compose-ros2.yml up -d` then hit Play again.

---

## Phase 3 — Start Pose Publisher

Open a **new terminal** and run the pose publisher. The sailboat will start moving in a 50m radius circle centred at (0, -300).

```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control pose_publisher --ros-args \
    -p scenario:=circle \
    -p radius:=50.0 \
    -p speed:=0.3
"
```

Watch the browser map — the sailboat dot should start moving in a circle. **Wait 5 seconds** to let it settle before recording.

> 💡 For a figure-8 instead: `-p scenario:=eight`

---

## Phase 4 — Verify Camera

Confirm frames are flowing at ~10Hz.

```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 topic hz /camera/compressed
"
```

```
✓ average rate: ~8-10
```

Check the live preview frame:

```bash
open recordings/latest_frame.jpg
```

Should show a 320x240 ocean view from the bow of the sailboat. The file updates every 3 seconds so the view changes as the boat rotates.

> ⚠️ If `/camera/compressed` shows 0 — the `CameraStreamer` component is missing from `StreamCamera` in Unity, or Unity is not in Play mode.

---

## Phase 5 — Start Recording

Start the recording in a **new terminal**.

```bash
./scripts/record.sh
```

```
✓ Starting recording: session_2026_05_04_XXXXXX
✓ Recording started
```

Let it run for **at least 60 seconds** to capture one full circle. Watch the browser map throughout — the dot should be moving continuously.

> 💡 The longer you record, the more training data you collect. A 10-minute session at 10fps = ~6000 camera frames.

---

## Phase 6 — Stop Recording

```bash
./scripts/stop_record.sh
```

```
✓ Recording stopped.
```

> ⚠️ Always use `stop_record.sh` to stop. Killing the container without stopping cleanly can corrupt the `.db3` file.

---

## Phase 7 — Verify the Bag

Check all 8 topics were captured with correct rates.

```bash
SESSION=$(ls recordings/ | grep session | grep -v '.gitkeep' | tail -1)
echo "Session: $SESSION"

docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  ros2 bag info /recordings/${SESSION}
"
```

Expected message counts for a 60-second recording:

| Topic | Expected | Rate | If 0 |
|---|---|---|---|
| `/camera/compressed` | ~480 msgs | 8Hz × 60s | Camera not streaming |
| `/sailboat_01/pose` | ~600 msgs | 10Hz × 60s | Pose publisher not running |
| `/sailboat_01/cmd_vel` | ~600 msgs | 10Hz × 60s | n3mo_controller down |
| `/sailboat/gps` | ~600 msgs | 10Hz × 60s | sensor_publisher down |
| `/sailboat/imu` | ~600 msgs | 10Hz × 60s | sensor_publisher down |
| `/environment/wind` | ~600 msgs | 10Hz × 60s | sensor_publisher down |
| `/unity/all_poses` | ~120 msgs | 2Hz × 60s | Unity not connected |
| `/occupancy_grid` | ~60 msgs | 1Hz × 60s | grid server down |

---

## Phase 8 — Export to CSV and Frames

Convert the bag to ML-ready files.

```bash
SESSION=$(ls recordings/ | grep session | grep -v '.gitkeep' | tail -1)

docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  python3 /root/ros2_ws/src/n3mo_control/n3mo_control/bag_to_csv.py /recordings/${SESSION}
"
```

Expected output:

```
✓ Frames extracted: NNN
✓ dataset.csv (NNN rows — ML ready)
```

Output files in `recordings/session_NAME/`:

| File | Contents | Used for |
|---|---|---|
| `poses.csv` | Vessel positions over time | Trajectory analysis |
| `commands.csv` | Velocity commands issued | Command analysis |
| `gps.csv` | GPS coordinates over time | Geographic track |
| `wind.csv` | Wind speed and direction | Environment data |
| `grid_stats.csv` | Occupied cell counts over time | Grid consistency check |
| `frames/` | JPEG camera frames (000001.jpg...) | ML training images |
| `dataset.csv` | Frames aligned with pose + command | **Primary ML dataset** |

---

## Phase 9 — Verify Exported Data

Run this full verification script on your Mac.

```bash
SESSION=$(ls recordings/ | grep session | grep -v '.gitkeep' | tail -1)
BASE="recordings/${SESSION}"

echo "=== FILE SIZES ==="
ls -lh ${BASE}/*.csv
echo "Total frames: $(ls ${BASE}/frames/ | wc -l)"

echo ""
echo "=== DATASET HEADERS ==="
head -2 ${BASE}/dataset.csv

echo ""
echo "=== COMMANDS — check variety ==="
awk -F',' 'NR>1 {print $3, $8}' ${BASE}/commands.csv | sort | uniq -c | sort -rn | head -5

echo ""
echo "=== TRAJECTORY COVERAGE ==="
python3 << PYEOF
import csv
with open('${BASE}/poses.csv') as f:
    rows = list(csv.DictReader(f))
xs = [float(r['pos_x']) for r in rows if r['pose_index'] == '0']
zs = [float(r['pos_z']) for r in rows if r['pose_index'] == '0']
if xs:
    print(f'X range: {min(xs):.1f} to {max(xs):.1f}  (span {max(xs)-min(xs):.1f}m)')
    print(f'Z range: {min(zs):.1f} to {max(zs):.1f}  (span {max(zs)-min(zs):.1f}m)')
    print(f'Centre X: {(max(xs)+min(xs))/2:.1f}  (should be ~0)')
    print(f'Centre Z: {(max(zs)+min(zs))/2:.1f}  (should be ~-300)')
    print(f'Radius:   {(max(xs)-min(xs))/2:.1f}m  (should be ~50)')
PYEOF

echo ""
echo "=== GRID STATS — occupied cells constant? ==="
awk -F',' 'NR>1 {print $5}' ${BASE}/grid_stats.csv | sort | uniq -c

echo ""
echo "=== OPEN FIRST AND LAST FRAMES ==="
open ${BASE}/frames/000001.jpg
LAST=$(ls ${BASE}/frames/ | tail -1)
open ${BASE}/frames/${LAST}
```

What good output looks like:

```
Commands:     ~480 2.0000 0.3000  (circle) + a few 0.0000 0.0000 (normal)
Grid stats:   52 in every row = 3 buoys + sailboat, consistent throughout
Frames:       first and last both show ocean view from the bow

Trajectory:
  X range: -50.0 to 50.0  (span 100.0m)
  Z range: -350.0 to -250.0  (span 100.0m)
  Centre X: 0.0   ✓
  Centre Z: -300.0   ✓
  Radius:   50.0m   ✓
```

> ⚠️ If grid_stats shows 39 in early rows — those are from before Unity connected. This is normal.

---

## Phase 10 — ML Readiness Check

Final validation that the dataset is complete and usable.

```bash
SESSION=$(ls recordings/ | grep session | grep -v '.gitkeep' | tail -1)
BASE="recordings/${SESSION}"

python3 << EOF
import csv, os

base = "${BASE}"

with open(f'{base}/dataset.csv') as f:
    rows = list(csv.DictReader(f))

print(f'Total training samples : {len(rows)}')
print(f'At 10fps that covers   : {len(rows)/10:.1f} seconds of footage')

missing = [r for r in rows if not os.path.exists(f'{base}/{r["frame_file"]}')]
print(f'Missing frames         : {len(missing)}  (should be 0)')

linears  = [float(r['linear_x'])  for r in rows]
angulars = [float(r['angular_z']) for r in rows]
print(f'linear_x range         : {min(linears):.2f} to {max(linears):.2f}')
print(f'angular_z range        : {min(angulars):.2f} to {max(angulars):.2f}')

pos_xs = set(r['pos_x'] for r in rows)
print(f'Unique positions       : {len(pos_xs)}  (should be > 1)')

print()
if len(missing) == 0 and len(pos_xs) > 1:
    print('Dataset is ML ready!')
else:
    print('Issues found — check above')
EOF
```

Expected output:

```
✓ Total training samples : 480+
✓ Missing frames         : 0
✓ Unique positions       : 100+
✓ Dataset is ML ready!
```

---

## Quick Checklist

Use this before committing a session to training.

### Pre-recording
- [ ] Docker containers started — all 5 services healthy in logs
- [ ] Grid checker shows Occupied: 39 (buoys only, no Unity yet)
- [ ] Browser map at http://localhost:8080 shows 3 cyan dot clusters
- [ ] Unity hit Play — no connection errors in Console
- [ ] Grid checker shows Occupied: 52 (buoys + sailboat)
- [ ] Browser map shows 4 dot clusters including sailboat
- [ ] Pose publisher running — sailboat moving in circle on map
- [ ] `/camera/compressed` flowing at ~8-10Hz
- [ ] `recordings/latest_frame.jpg` opens and shows ocean view

### During recording
- [ ] `record.sh` confirmed started with session timestamp
- [ ] Browser map dot moving continuously for 60+ seconds

### Post-recording
- [ ] `stop_record.sh` run cleanly
- [ ] `ros2 bag info` shows all 8 topics with expected message counts
- [ ] `bag_to_csv.py` ran without errors
- [ ] Frames folder contains expected number of JPEGs
- [ ] `dataset.csv` row count matches frame count
- [ ] Trajectory coverage: centre ~(0, -300), radius ~50m
- [ ] Grid stats: consistent 52 cells throughout
- [ ] ML readiness check: 0 missing frames, unique positions > 1
- [ ] `dataset.csv`: Dataset is ML ready!

---

## Troubleshooting

### Unity cannot connect to ROS bridge

This happens on Mac after Docker restarts.

```bash
docker compose -f docker-compose-ros2.yml down
docker compose -f docker-compose-ros2.yml up -d
```

Then hit Play in Unity again. Wait 5 seconds before checking.

### Occupancy grid shows 0 occupied cells

```bash
docker logs n3mo_grid | tail -20
```

You should see `Static obstacle: buoy_01 at cell (310, 390)`. If not, rebuild:

```bash
docker compose -f docker-compose-ros2.yml build --no-cache
```

### Camera not flowing

- Stop the game in Unity
- Expand `sailboat_01 > CameraMount > StreamCamera` in Hierarchy
- In the Inspector confirm `CameraStreamer (Script)` is listed
- Hit Play again

### Recording produces empty CSV files

The recording ran but Unity was not playing or pose publisher was not running. Always verify Phase 2 and Phase 3 before Phase 5.

### Sailboat not visible on browser map

The sailboat is outside the grid bounds. Expand grid in `docker-compose-ros2.yml`:

```
ros2 run n3mo_control occupancy_grid_server --ros-args \
  -p origin_x:=-500.0 -p origin_y:=-500.0 \
  -p width_m:=1000.0 -p height_m:=1000.0
```

---

## How ML Uses This Dataset

The `dataset.csv` is formatted for **imitation learning** — the model watches a scripted trajectory and learns to replicate it autonomously.

### What each row contains

| Column | Example | Meaning |
|---|---|---|
| `frame_file` | frames/000001.jpg | What the boat saw at this moment |
| `pos_x, pos_z` | 11.77, -251.40 | Where the boat was in world space |
| `rot_y, rot_w` | -0.118, 0.992 | What direction the boat was facing |
| `linear_x` | 2.0 | Forward speed command issued |
| `angular_z` | 0.3 | Turn rate command issued |

### How a model trains on it

Each row is one training sample. The model learns the mapping:
- **Input:** camera frame (what the boat sees) + position + heading
- **Output:** predict the correct `linear_x` and `angular_z` commands
- Over thousands of samples it learns: open water → go forward, obstacle ahead → turn

### Loading in Python

```python
import pandas as pd
from PIL import Image
import numpy as np

df = pd.read_csv('recordings/session_NAME/dataset.csv')

for _, row in df.iterrows():
    # what the boat saw
    image   = np.array(Image.open(f'recordings/session_NAME/{row["frame_file"]}')) / 255.0

    # where the boat was and what direction it faced
    state   = [row['pos_x'], row['pos_z'], row['rot_y'], row['rot_w']]

    # what command was issued at that moment
    command = [row['linear_x'], row['angular_z']]

    # model.train(input=[image, state], label=command)
```