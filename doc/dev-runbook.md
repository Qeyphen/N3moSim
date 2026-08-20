# Dev Runbook

## 1. Start ROS

```bash
docker compose up -d ros_bridge scenario
```

Starts the ROS bridge and scenario generator containers.

```bash
docker compose exec ros_bridge bash -lc "cd /root/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select n3_sim n3mo_control"
```

Rebuilds the ROS packages used by scenario generation and dataset capture.

```bash
docker compose restart ros_bridge scenario
```

Reloads the rebuilt ROS code and parameters.

## 2. Unity Pre-Check

Before pressing Play, confirm:

- the island is labeled `land`
- `POVCamera_Left` and `POVCamera_Right` both exist on the boat
- both cameras have enabled:
  - `Camera`
  - `PerceptionCamera`
  - `DatasetCaptureScheduler`
  - the full Perception labeler set
- only one Perception visualization is active if Unity warns about visualization conflicts

## 3. Enter Play Mode

Press Play in Unity.

Confirms:

- the scene loads with island and buoys
- both Perception cameras exist at runtime
- `CaptureResolution` logs appear for both cameras

## 4. Resolution Test

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic pub --once /camera/resolution std_msgs/msg/String '{data: 720p}'"
```

Sets both capture cameras to `1280x720`.

```bash
python3 tools/generate_scenarios.py \
  --count 1 \
  --duration 10 \
  --capture-hz 5 \
  --track-count 12 \
  --area-type coastal \
  --time-mode fixed \
  --out scenarios_res_720.json
```

Creates one short 10-second scenario manifest for 720p validation.

```bash
python3 tools/run_scenario_batch.py scenarios_res_720.json --limit 1
```

Runs the 720p validation scenario.

Check one `frame_data.json` and confirm:

- both captures report `"dimension": [1280.0, 720.0]`

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic pub --once /camera/resolution std_msgs/msg/String '{data: 1080p}'"
```

Sets both capture cameras to `1920x1080`.

```bash
python3 tools/generate_scenarios.py \
  --count 1 \
  --duration 10 \
  --capture-hz 5 \
  --track-count 12 \
  --area-type coastal \
  --time-mode fixed \
  --out scenarios_res_1080.json
```

Creates one short 1080p scenario manifest.

```bash
python3 tools/run_scenario_batch.py scenarios_res_1080.json --limit 1
```

Runs the 1080p validation scenario.

Check one `frame_data.json` and confirm:

- both captures report `"dimension": [1920.0, 1080.0]`

## 5. Full Dense Scenario Run

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic pub --once /camera/resolution std_msgs/msg/String '{data: 720p}'"
```

Sets the final capture resolution for the full run.

```bash
python3 tools/generate_scenarios.py \
  --count 3 \
  --duration 20 \
  --capture-hz 8 \
  --track-count 18 \
  --area-type coastal \
  --time-mode linear \
  --out scenarios_full_dense_dual.json
```

Creates three dense 20-second coastal scenarios with smooth time progression.

```bash
python3 tools/run_scenario_batch.py scenarios_full_dense_dual.json --limit 1
```

Runs one dense scenario as a smoke test.

Validate in Unity:

- ego boat avoids island/land
- traffic appears early and often
- `ferry` and `fishing_boat` can appear
- weather stays fixed inside a scenario
- time changes slowly
- both cameras stay attached and stable

```bash
python3 tools/run_scenario_batch.py scenarios_full_dense_dual.json
```

Runs the full small dense batch.

## 6. Dual-Camera Dataset Check

Open one `frame_data.json` from the latest SOLO dataset.

Confirm:

- `captures` contains two entries
- one capture id is `camera_left`
- one capture id is `camera_right`
- each capture has RGB, depth, semantic segmentation, instance segmentation, 2D boxes, and 3D boxes

## 7. Metadata Check

In the latest SOLO folder, confirm these files exist:

- `run_metadata_povcamera_left_*.json`
- `run_metadata_povcamera_right_*.json`
- `scenario_start_povcamera_left_*.json`
- `scenario_start_povcamera_right_*.json`
- `scenario_end_povcamera_left_*.json`
- `scenario_end_povcamera_right_*.json`
- `unity_defaults_*.json`

Confirm:

- resolution matches the chosen capture size
- scenario info is present
- left/right metadata files do not overwrite each other

## 8. Preview Both Cameras

```bash
python3 tools/solo_preview.py
```

Generates preview images with all 2D boxes for both cameras.

```bash
python3 tools/solo_preview.py --min-box-side 10
```

Generates preview images while hiding boxes whose smaller side is below 10 pixels.

## 9. Generate Water/Sky Masks

```bash
python3 tools/marine_surface.py
```

Creates per-camera `water / sky / obstacle` masks in `marine_seg/`.

Confirm files exist for both cameras:

- `*.camera_left.marine_seg.png`
- `*.camera_left.marine_classes.png`
- `*.camera_right.marine_seg.png`
- `*.camera_right.marine_classes.png`

Confirm visually:

- sky is above
- water is below
- island remains obstacle
- boats remain obstacle

## 10. Export YOLO

```bash
python3 tools/solo_to_yolo.py --out yolo_raw_dual
```

Exports the latest SOLO dataset to raw YOLO detection format without creating a train/val split.

```bash
python3 tools/solo_to_yolo.py --split scenario --val-frac 0.2 --out yolo_split_dual
```

Optionally exports a coarse scenario-style split. Use raw export as the primary validation path.

## 11. Validation Checklist

Confirm all of the following:

- multiple scenarios were generated
- scenarios are short (`~20s`)
- capture rate is configurable and reflected in the recorded dimensions/metadata
- weather stays fixed per scenario
- time stays fixed or progresses slowly per scenario
- times stay within visible hours
- ego boat avoids island/obstacles
- traffic density is clearly improved
- `ferry` and `fishing_boat` appear
- both cameras record into the same SOLO dataset with separate capture entries
- camera-specific metadata files are written
- water/sky masks exist for both cameras
- emerged-only clipping improves visible object boxes
- YOLO raw export produces no forced train/val split
