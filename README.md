# N3moSim

Unity marine simulator with a ROS 2 bridge, procedural traffic generation, dual-camera Unity Perception capture, and host-side tooling to export SOLO datasets to YOLO.

This repository now supports two main dataset-generation workflows:

- `tools/run_scenario.py`: run one explicit scene once, with the exact weather and time-of-day you pass.
- `tools/run_dataset_plan.py`: run a full dataset plan, one `run_scenario.py` run per scenario declared in a YAML plan file.

The current pipeline is built around:

- Unity as the simulator and renderer
- Dockerized ROS 2 for bridge, control, and scenario generation
- Unity Perception for RGB, 2D/3D boxes, semantic segmentation, instance segmentation, and depth
- Host-side Python tools for preview, masking, clipping, and YOLO export

## Documentation Map

- [docs/architecture.md](docs/architecture.md): project structure, major scripts, ROS topics, Unity components, and the occupancy-grid/costmap loop
- [docs/scenario_workflows.md](docs/scenario_workflows.md): `run_scenario.py`, `run_dataset_plan.py` plan files, and the defense-scene helper
- [docs/dataset_pipeline.md](docs/dataset_pipeline.md): Perception setup, dual-camera capture, metadata files, preview tools, masks, and SOLO-to-YOLO export
- [docs/traffic_assets.md](docs/traffic_assets.md): traffic prefab rebuild steps, spawner axis contract, and the per-type visual validation checklist
- [docs/ros_interfaces.md](docs/ros_interfaces.md): operational ROS topics, services, message types, and the key parameters for `dataset_sweep`, `env_control`, and `scenario_generator`

## Repository Layout

- `Assets/Scripts/`: Unity runtime scripts
- `config/`: scene JSON, RViz config, URDF
- `ros2_ws/src/n3_sim/`: ROS-side scenario generator and simulator nodes
- `ros2_ws/src/n3mo_control/`: ROS-side control and dataset sweep tools
- `tools/`: host-side orchestration and dataset-processing scripts
- `docker-compose.yml`: ROS bridge, scenario service, and optional RViz wiring

## Quick Start

### 1. Start ROS services

```bash
docker compose up -d ros_bridge scenario
```

### 2. Rebuild Python ROS packages after code changes

```bash
docker compose exec ros_bridge bash -lc "cd /root/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select n3_sim n3mo_control n3_new_msgs"
docker compose restart ros_bridge scenario
```

### 3. Open Unity

- Open the project in Unity.
- Press `Play`.
- Keep `ego_boat` in `Auto` mode if you want the ROS sweep to drive it.

### 4. Run one explicit scenario

```bash
python3 tools/run_scenario.py \
  --output /Users/you/path/to/run_output \
  --duration 60 \
  --capture-hz 8 \
  --track-count 24 \
  --area-type coastal \
  --occupied-fraction 0.8 \
  --scene-seed 12345 \
  --time-of-day 8.0 \
  --weather foggy \
  --fog 0.45 \
  --wave 0.9 \
  --wind 0.6 \
  --cloudiness 0.6
```

### 5. Preview the generated SOLO data

```bash
python3 tools/solo_preview.py /path/to/output
python3 tools/marine_surface.py /path/to/output
```

### 6. Export to YOLO

```bash
python3 tools/solo_to_yolo.py /path/to/output --out yolo_raw
```

If you omit the SOLO path, `solo_to_yolo.py` uses the latest SOLO directory automatically:

```bash
python3 tools/solo_to_yolo.py --out yolo_raw
```

## Current Recommended Workflow

For hand-authored or demo runs, use `tools/run_scenario.py`.

Use it when you need:

- one exact scene
- one exact weather preset
- one exact time of day
- one output folder
- no repeated random environment sampling

For a complete dataset with controlled variety, use `tools/run_dataset_plan.py`.

Use it when you need:

- many scenarios varying lighting, weather, time of day, area type and traffic
- one YAML plan file declaring every `run_scenario.py` invocation (see `tools/plans/dataset-1k.yaml`)
- numbered subfolders per scenario and a global `manifest.json`
- deterministic, seeded, reproducible runs

## Occupancy Grid and Costmap Summary

Unity publishes `/map` through `OccupancyGridPublisher`. The ROS scenario generator reads that map as a costmap so generated tracks stay in navigable water and avoid authored static obstacles.

The default log:

```text
[OccupancyGridPublisher] Published 1000x1000 grid on '/map' (res=1m, ...)
```

comes from:

- `widthMeters = 1000`
- `heightMeters = 1000`
- `resolution = 1`

which yields:

- `1000 / 1 = 1000` columns
- `1000 / 1 = 1000` rows

The preferred way to change this is in the Unity Inspector on the GameObject that has `OccupancyGridPublisher`:

- `Origin X`
- `Origin Z`
- `Width Meters`
- `Height Meters`
- `Resolution`
- `Inflation Radius`
- `Extra Obstacles`

See [docs/architecture.md](docs/architecture.md) for the full explanation.

## Metadata Summary

Unity writes capture metadata into the SOLO run:

- `run_metadata_<camera_key>_<timestamp>.json`
- `scenario_start_<camera_key>_<timestamp>.json`
- `scenario_end_<camera_key>_<timestamp>.json`
- `unity_defaults_<timestamp>.json`

Host-side runners add orchestration metadata:

- single-run mode: `scene_spec.json`, `run_summary.json`
- plan mode: `manifest.json` at the output root, plus the single-run files in each numbered scenario folder

## Notes

- `solo_to_yolo.py` defaults to `--split none`, which means no forced train/val split is created unless you explicitly ask for one.
- `occupied-fraction` biases a fraction of generated traffic into the ego boat forward view cone. It improves the probability of visible traffic but is not a hard guarantee that the same fraction of frames will contain objects.
