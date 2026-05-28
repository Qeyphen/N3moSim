# N3moSim — Testing & Recording Runbook

> End-to-end pipeline verification for occupancy grid, static nav map, environment control, live map, recording, and ML dataset export.

| | |
|---|---|
| **Stack** | Unity 6.3 LTS + ROS2 Humble + Docker |
| **Project** | N3moSim / Marine Autonomous Vessel |

---

## Overview

Follow these phases in order every time you run the simulation.

```
Phase 0  — Clean start              stop and restart all Docker containers
Phase 1  — Occupancy grid           verify static buoys appear (no Unity yet)
Phase 2  — Connect Unity            verify sailboat appears and moves on the grid
Phase 3  — Verify static nav map    check /map topic and open map.pgm
Phase 4  — Environment control      test weather, time of day, wave height
Phase 5  — Start pose publisher     boat moves in circles for recording
Phase 6  — Verify camera            frames flowing at ~10Hz
Phase 7  — Start recording          capture all topics
Phase 8  — Stop recording
Phase 9  — Verify the bag           check message counts per topic
Phase 10 — Export to CSV + frames   convert bag to ML files
Phase 11 — Verify exported data     check files, sizes, trajectory
Phase 12 — ML readiness check       final validation
```

> ⚠️ **Run phases in order. Do not skip ahead.**

---

## Phase 0 — Clean Start

```bash
docker compose -f docker-compose-ros2.yml down
docker compose -f docker-compose-ros2.yml up -d
docker compose -f docker-compose-ros2.yml logs -f
```

Wait until you see **all five** of these:

```
✓ Starting ROS TCP Bridge on 0.0.0.0:10000
✓ Starting N3mo Controller
✓ OccupancyGridServer ready — 1000.0x1000.0m @ 1.0m/cell
✓ Starting Grid Visualiser on http://localhost:8080
✓ Starting Image Bridge
```

> 💡 Ctrl+C to stop watching logs. Containers keep running.

---

## Phase 1 — Verify Occupancy Grid (no Unity yet)

```bash
docker exec -it n3mo_grid bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control grid_checker
"
```

Expected — 39 occupied cells (3 buoys × 13 cells):

```
✓ Map size    : 1000x1000 cells
✓ Occupied    : 39
✓ Free        : 999961
```

Open browser map — should show 3 cyan dot clusters:

```
http://localhost:8080
```

> ⚠️ If Occupied shows 0 — check `docker logs n3mo_grid`

---

## Phase 2 — Connect Unity and Move Boat

Hit **Play** in Unity. Wait 3 seconds.

### Verify Unity connected

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

### Verify Unity Console shows all components found

In the Unity Console you should see:

```
✓ [SceneLoader] Loaded 4 objects from: .../scene_config.json
✓ [SceneLoader] Runtime weather installed.
✓ [PhysicsController] 'sailboat_01' ready
✓ [CameraStreamer] Publishing 320x240 @ 10fps → /unity/camera/compressed
✓ [EnvironmentController] components found:
    WaterSurface     : Ocean
    WeatherController: RuntimeWeather
    DayNightCycle    : RuntimeWeather
✓ [MapGenerator] Starting map generation...
✓ [MapGenerator] Map generated: Grid : 1000x1000 cells
✓ [MapGenerator] Published /map → 1000x1000 resolution=1m/cell
✓ [MapGenerator] Saved map.pgm (1000x1000)
✓ [MapGenerator] Saved map.yaml
✓ [MapGenerator] Map saved to: .../recordings/map_<timestamp>
```

### Start the boat moving in circles

Open a **new terminal** and run:

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

### Verify boat appears and moves on the grid

Run the grid checker again:

```bash
docker exec -it n3mo_grid bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control grid_checker
"
```

```
✓ Occupied : 52  (39 buoys + 13 sailboat)
```

Watch `http://localhost:8080` — you should now see **4 dot clusters**, with the sailboat dot moving in a circle around the 3 static buoy dots.

> 💡 Keep the waypoint publisher running while you continue through the phases — it keeps the boat moving so you can watch it on the map.

---

## Phase 3 — Verify Static Nav Map

### Check ROS2 topic

```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  ros2 topic info /map
"
```

Expected:

```
✓ Type: nav_msgs/msg/OccupancyGrid
✓ Publisher count: 1
```

### Open the saved map file

```bash
open ~/Dev/n3mo/N3moSim/recordings/$(ls -t ~/Dev/n3mo/N3moSim/recordings/ | grep map | head -1)/map.pgm
```

What you should see in Preview:

```
White area  = open water (navigable)
Black shape = island / land (occupied)
```

The map is the standard ROS2 Nav2 format and can be loaded directly by any path planner:

```bash
ros2 run nav2_map_server map_server --ros-args \
  -p yaml_filename:=recordings/map_<timestamp>/map.yaml
```

> ⚠️ If map.pgm is not found — check Unity Console for the exact save path in `[MapGenerator] Map saved to:`

---

## Phase 4 — Environment Control

All environment commands run inside the Docker container. Make sure Unity is in Play mode before running these.

### 4a — Weather presets

Test each preset and observe the Game view change:

**Clear (baseline):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=preset -p preset_name:=clear
"
```

**Misty (dense sea fog):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=preset -p preset_name:=misty
"
```

**Rainy (overcast + rain):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=preset -p preset_name:=rainy
"
```

**Stormy (severe weather):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=preset -p preset_name:=stormy
"
```

In the Unity Console you should see for each:
```
✓ [EnvironmentController] preset → Clear/Misty/Rainy/Stormy
✓ [SimpleWeatherController] applied preset: Clear/Misty/Rainy/Stormy
```

### 4b — Time of day

**Night (22:00):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=manual -p time_of_day:=22.0 -p instant:=true
"
```

Game view should go dark.

**Early morning (08:00):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=manual -p time_of_day:=8.0 -p instant:=true
"
```

Golden early morning light.

**Noon (12:00):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=manual -p time_of_day:=12.0 -p instant:=true
"
```

**Sunset (17:00):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=manual -p time_of_day:=17.0 -p instant:=true
"
```

In the Unity Console and RuntimeWeather Inspector you should see `Time Of Day` slider update to the set value.

**Cycle day/night automatically:**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=cycle -p cycle_speed:=2.0
"
```

Watch the lighting shift continuously. Ctrl+C to stop.

### 4c — Wave height

**Calm seas (0.5m):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=manual -p wave_height:=0.5 -p time_of_day:=12.0 -p instant:=true
"
```

Click `Ocean` in the Unity Hierarchy — `Time Multiplier` should be ~0.6.

**Rough seas (5.0m):**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=manual -p wave_height:=5.0 -p time_of_day:=12.0 -p instant:=true
"
```

`Time Multiplier` should jump to 3.0 and waves visibly animate faster.

**Gradual storm build:**
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=storm
"
```

After ~18 seconds you should see `Storm reached 30% — applying Stormy preset` in the Docker logs and the scene darken.

### 4d — Reset to default

After testing, reset to noon clear before continuing:

```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=manual \
    -p time_of_day:=12.0 \
    -p wave_height:=0.5 \
    -p instant:=true
" && \
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control environment_publisher --ros-args \
    -p mode:=preset -p preset_name:=clear
"
```

---

## Phase 5 — Start Pose Publisher (for recording)

Stop the waypoint publisher from Phase 2 with Ctrl+C, then start the pose publisher for precise circle recording:

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

Watch browser map — sailboat dot should move in a clean circle. **Wait 5 seconds** to let it settle before recording.

---

## Phase 6 — Verify Camera

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

Check live frame:
```bash
open recordings/latest_frame.jpg
```

Should show 320x240 ocean view from the bow.

---

## Phase 7 — Start Recording

```bash
./scripts/record.sh
```

```
✓ Starting recording: session_2026_XX_XX_XXXXXX
✓ Recording started
```

Record for **at least 60 seconds**. Watch browser map — dot should be moving throughout.

---

## Phase 8 — Stop Recording

```bash
./scripts/stop_record.sh
```

```
✓ Recording stopped.
```

---

## Phase 9 — Verify the Bag

```bash
SESSION=$(ls recordings/ | grep session | grep -v '.gitkeep' | tail -1)
echo "Session: $SESSION"

docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  ros2 bag info /recordings/${SESSION}
"
```

Expected for a 60-second recording:

| Topic | Expected | Rate |
|---|---|---|
| `/camera/compressed` | ~480 msgs | 8Hz |
| `/sailboat_01/pose` | ~600 msgs | 10Hz |
| `/unity/all_poses` | ~120 msgs | 2Hz |
| `/occupancy_grid` | ~60 msgs | 1Hz |

---

## Phase 10 — Export to CSV and Frames

```bash
SESSION=$(ls recordings/ | grep session | grep -v '.gitkeep' | tail -1)

docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  python3 /root/ros2_ws/src/n3mo_control/n3mo_control/bag_to_csv.py /recordings/${SESSION}
"
```

Output files in `recordings/session_NAME/`:

| File | Contents |
|---|---|
| `poses.csv` | Vessel positions over time |
| `commands.csv` | Velocity commands issued |
| `gps.csv` | GPS coordinates |
| `wind.csv` | Wind data |
| `grid_stats.csv` | Occupied cell counts |
| `frames/` | JPEG camera frames |
| `dataset.csv` | Frames aligned with pose + command (primary ML dataset) |

---

## Phase 11 — Verify Exported Data

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
    print(f'Radius:   {(max(xs)-min(xs))/2:.1f}m  (should be ~50)')
PYEOF
```

---

## Phase 12 — ML Readiness Check

```bash
SESSION=$(ls recordings/ | grep session | grep -v '.gitkeep' | tail -1)
BASE="recordings/${SESSION}"

python3 << EOF
import csv, os
base = "${BASE}"
with open(f'{base}/dataset.csv') as f:
    rows = list(csv.DictReader(f))
print(f'Total training samples : {len(rows)}')
print(f'Coverage               : {len(rows)/10:.1f} seconds')
missing = [r for r in rows if not os.path.exists(f'{base}/{r["frame_file"]}')]
print(f'Missing frames         : {len(missing)}  (should be 0)')
pos_xs = set(r['pos_x'] for r in rows)
print(f'Unique positions       : {len(pos_xs)}  (should be > 1)')
print()
if len(missing) == 0 and len(pos_xs) > 1:
    print('Dataset is ML ready!')
else:
    print('Issues found — check above')
EOF
```

---

## Quick Checklist

### Pre-recording
- [ ] Docker containers started — all 5 services healthy
- [ ] Grid checker shows Occupied: 39 (buoys only, no Unity)
- [ ] Browser map shows 3 cyan clusters at `http://localhost:8080`
- [ ] Unity hit Play — no errors in Console
- [ ] Unity Console shows `[MapGenerator] Map saved to: ...`
- [ ] Map PGM opens and shows white ocean + black island
- [ ] `/map` topic shows Publisher count: 1
- [ ] Waypoint publisher running — boat moving in circles on browser map
- [ ] Grid checker shows Occupied: 52 (buoys + sailboat)
- [ ] Browser map shows 4 dot clusters with sailboat moving
- [ ] Environment control tested — preset, time of day, wave height all responding
- [ ] Reset to noon clear before recording
- [ ] Pose publisher running (Phase 5) — sailboat moving in clean circle
- [ ] `/camera/compressed` flowing at ~8-10Hz
- [ ] `latest_frame.jpg` shows ocean view

### Post-recording
- [ ] `stop_record.sh` run cleanly
- [ ] `ros2 bag info` shows all topics with expected message counts
- [ ] `bag_to_csv.py` ran without errors
- [ ] Frames folder contains expected JPEGs
- [ ] `dataset.csv` row count matches frame count
- [ ] ML readiness: 0 missing frames, unique positions > 1
- [ ] `Dataset is ML ready!`

---

## Troubleshooting

### Unity can't connect

```bash
docker compose -f docker-compose-ros2.yml down
docker compose -f docker-compose-ros2.yml up -d
```
Hit Play in Unity again.

### Map not saved / wrong path

Check Unity Console for `[MapGenerator] Map saved to:` — this shows the exact path. If the path looks wrong (contains `Assets/../../`) update `SaveMapFiles()` in `MapGenerator.cs` to use a hardcoded absolute path.

### Environment commands time out

Check Unity Console for `[EnvironmentController] components found:` — if `WeatherController` or `DayNightCycle` shows `NOT FOUND`, RuntimeWeather didn't spawn in time. Stop and hit Play again.

### Time of day changes but scene stays dark

The sun goes below the horizon below hour 6 and above hour 18. Use values between 8-17 for visible daylight.

### Occupancy grid shows 0 occupied cells

```bash
docker exec -it n3mo_bridge bash -c "source /opt/ros/humble/setup.bash && ros2 topic hz /unity/all_poses"
```
Should show `average rate: 2.0`. If nothing — Unity isn't connected.

### Boat not moving on browser map

Check the waypoint publisher terminal — if it shows `[waypoint_publisher]` logs but the dot isn't moving, the PhysicsController may not be receiving the waypoints. Confirm `[PhysicsController] 'sailboat_01' ready` appears in the Unity Console.

### Wave height doesn't change visually

Wave height via `timeMultiplier` changes how fast waves animate, not their actual height (HDRP WaterSurface nested struct not accessible in Unity 6). Combine with weather presets for visual variety — Stormy preset gives darker sky and heavier-looking seas.