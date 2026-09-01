# ROS Interfaces

This document is the operational ROS reference for the Unity simulator and dataset pipeline.

It covers:

- active topics used by Unity, orchestration scripts, and dataset tooling
- services used in normal operation
- key message and service types
- full parameter surfaces for the main ROS nodes used in the workflow

It does not try to exhaustively document every experimental node in the repository. It focuses on the interfaces you actually use for simulator operation, scenario generation, and dataset capture.

## Core Runtime Topics

## ROS -> Unity

| Topic | Type | Producer | Consumer | Purpose |
|---|---|---|---|---|
| `/ego_boat/target_pose` | `geometry_msgs/PoseStamped` | `target_pose_publisher`, `dataset_sweep` | `AutonomousBoatController` | target point for the ego boat in Auto mode |
| `/sim/tracks` | `n3_new_msgs/TrackArray` | `scenario_generator` | `TrackSpawner` | generated moving traffic |
| `/env/time_of_day` | `std_msgs/Float32` | `env_control`, orchestration scripts | `EnvironmentController` | set Unity time of day |
| `/env/weather` | `std_msgs/String` | `env_control`, orchestration scripts | `EnvironmentController` | set weather preset |
| `/env/fog` | `std_msgs/Float32` | `env_control`, orchestration scripts | `EnvironmentController` | set fog intensity |
| `/env/wind` | `std_msgs/Float32` | `env_control`, orchestration scripts | `EnvironmentController` | set wind |
| `/env/wave` | `std_msgs/Float32` | `env_control`, orchestration scripts | `EnvironmentController` | set wave intensity |
| `/env/cloudiness` | `std_msgs/Float32` | `env_control`, orchestration scripts | `EnvironmentController` | set cloud cover |
| `/env/rain` | `std_msgs/Float32` | `env_control`, orchestration scripts | `EnvironmentController` | set rain |
| `/env/randomize` | `std_msgs/Int32` | `env_control`, `dataset_sweep` | `EnvironmentController` | ask Unity to randomize environment with a seed |
| `/dataset/control` | `std_msgs/Bool` | `dataset_sweep`, CLI | `DatasetCaptureScheduler` | start/stop recording |
| `/dataset/capture_hz` | `std_msgs/Float32` | `run_scenario.py`, CLI | `DatasetCaptureScheduler` | change capture frequency |
| `/dataset/scenario_info` | `std_msgs/String` | `run_scenario.py` | `ScenarioMetadataContext` | publish current scenario metadata as JSON |
| `/camera/resolution` | `std_msgs/String` | CLI | `CaptureResolution` | change Perception render size |

## Unity -> ROS

| Topic | Type | Producer | Consumer | Purpose |
|---|---|---|---|---|
| `/map` | `nav_msgs/OccupancyGrid` | `OccupancyGridPublisher` | `scenario_generator`, RViz, tools | static costmap from authored scene obstacles |
| `/sim/boat/pose` | `geometry_msgs/PoseStamped` | `EgoPosePublisher` | `dataset_sweep`, `scenario_generator`, RViz | ego boat pose |
| `/scene/objects` | `n3_new_msgs/TrackArray` | `DynamicObstaclePublisher` | `scenario_generator` | authored scene objects as exclusion zones |
| `/env/state` | `std_msgs/String` | `EnvironmentController` | metadata/logging consumers | current environment state as JSON |
| `/dataset/frames` | `std_msgs/Int32` | `DatasetCaptureScheduler` | `dataset_sweep` | live captured-frame count |

## Internal Remap

| Topic | Type | Purpose |
|---|---|---|
| `/map/costmap_static` | `nav_msgs/OccupancyGrid` | scenario-generator costmap input; remapped from Unity `/map` |

The `scenario` service starts the node with:

```text
-r /map/costmap_static:=/map
```

So Unity's published map is the generator's navigable-area input.

## Services

## `/sim/generate_scenario`

- Type: `std_srvs/srv/Trigger`
- Server: `scenario_generator`
- Purpose: generate one procedural scenario YAML using the current generator parameters

Response meaning:

- `success=true`
- `message=<path to generated YAML>`

This is what `run_scenario.py` and `run_defense_scene.sh` use when they ask ROS to build a new deterministic scene.

Example:

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 service call /sim/generate_scenario std_srvs/srv/Trigger '{}'"
```

## `/sim/scenario/command`

- Type: `n3_new_msgs/srv/ScenarioCommand`
- Server: `scenario_generator`
- Request:
  - `string json_request`
- Response:
  - `bool success`
  - `string json_response`

This is a JSON-command service for manipulating scenario playback and runtime-injected tracks.

Supported commands from [scenario_generator_node.py](/Users/kifen/Dev/n3mo/N3moSim/ros2_ws/src/n3_sim/n3_sim/scenario_generator/scenario_generator_node.py:331):

- `add_track`
- `remove_track`
- `list_tracks`
- `clear_tracks`
- `load_scenario`
- `reset_scenario_clock`
- `scenario_status`

### `add_track`

Request payload:

```json
{
  "cmd": "add_track",
  "type_name": "motorboat",
  "duration_s": 120.0,
  "heading_mode": "tangent",
  "waypoints": [
    {"x": 10.0, "y": -30.0, "speed_kts": 12.0},
    {"x": 80.0, "y": -10.0, "speed_kts": 12.0}
  ]
}
```

Response:

```json
{"id": 1000, "type": "motorboat"}
```

### `remove_track`

Request payload:

```json
{"cmd": "remove_track", "id": 1000}
```

### `list_tracks`

Request payload:

```json
{"cmd": "list_tracks"}
```

Response:

- list of currently injected runtime tracks

### `clear_tracks`

Request payload:

```json
{"cmd": "clear_tracks"}
```

### `load_scenario`

Request payload:

```json
{"cmd": "load_scenario", "path": "/tmp/scenario_generated_2026_08_28__10:00.yaml"}
```

Purpose:

- load a specific generated or saved scenario YAML for playback

### `reset_scenario_clock`

Request payload:

```json
{"cmd": "reset_scenario_clock"}
```

Purpose:

- restart the playback timebase without regenerating the scene

### `scenario_status`

Request payload:

```json
{"cmd": "scenario_status"}
```

Returns:

- whether a scenario is loaded
- scenario name
- scenario duration
- generated track count
- injected runtime track count

Example:

```bash
docker compose exec scenario bash -lc 'source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 service call /sim/scenario/command n3_new_msgs/srv/ScenarioCommand '\''{json_request: "{\"cmd\":\"scenario_status\"}"}'\'''
```

## Message Types

## `n3_new_msgs/msg/Track`

Defined in [Track.msg](/Users/kifen/Dev/n3mo/N3moSim/ros2_ws/src/n3_new_msgs/msg/Track.msg:1).

Fields:

- `uint32 id`
- `geometry_msgs/Pose pose`
- `geometry_msgs/Twist twist`
- `uint8 type`

Type enum values:

- `0 UNKNOWN`
- `1 SAILBOAT`
- `2 MOTORBOAT`
- `3 JETSKI`
- `4 KAYAK`
- `5 PADDLEBOARD`
- `6 SWIMMER`
- `7 DINGHY`
- `8 FISHING_BOAT`
- `9 FERRY`
- `10 CARGO`
- `11 BUOY`
- `12 DEBRIS`
- `13 WINDSURF`
- `14 KITESURF`
- `15 PEDALO`

## `n3_new_msgs/msg/TrackArray`

Defined in [TrackArray.msg](/Users/kifen/Dev/n3mo/N3moSim/ros2_ws/src/n3_new_msgs/msg/TrackArray.msg:1).

Fields:

- `std_msgs/Header header`
- `Track[] tracks`

This is the main traffic message used by:

- `scenario_generator`
- `TrackSpawner`
- `DynamicObstaclePublisher`

## `n3_new_msgs/srv/ScenarioCommand`

Defined in [ScenarioCommand.srv](/Users/kifen/Dev/n3mo/N3moSim/ros2_ws/src/n3_new_msgs/srv/ScenarioCommand.srv:1).

Fields:

- request:
  - `string json_request`
- response:
  - `bool success`
  - `string json_response`

## Operational Nodes and Parameters

## `n3mo_control/dataset_sweep.py`

Purpose:

- drives the ego boat automatically
- can start/stop recording
- can randomize environment and regenerate traffic in legacy mode
- can stop either on frame target or wall-clock duration

Main publishers/subscribers:

- publishes `/dataset/control`
- publishes `/ego_boat/target_pose`
- publishes `/env/randomize`
- subscribes `/dataset/frames`
- subscribes `/sim/tracks`
- subscribes `/map`
- subscribes `/sim/boat/pose`

Parameters from [dataset_sweep.py](/Users/kifen/Dev/n3mo/N3moSim/ros2_ws/src/n3mo_control/n3mo_control/dataset_sweep.py:40):

### Stop conditions

- `frames`
  - target captured frames when using frame-based mode
- `duration_s`
  - wall-clock duration override
- `hz`
  - assumed capture rate used for timeout estimation

### Target scheduling

- `waypoint_period`
  - seconds between target updates
- `wp_range`
  - waypoint sampling half-range in Unity meters
- `max_target_samples`
  - retries when sampling a valid target

### Obstacle-view policy

- `obstacle_bias`
  - target fraction of waypoints aimed toward obstacles/traffic
- `min_obstacle_frac`
  - hard lower bound on obstacle-facing target fraction
- `obstacle_target_jitter_m`
  - random offset around obstacle-facing targets

### Environment/scenario randomization

- `randomize_env_on_start`
- `randomize_env_during_run`
- `regenerate_on_start`
- `regenerate_during_run`
- `env_period`
- `regen_period`

In `run_scenario.py`, all four booleans are forced to `false` so the run remains fixed.

### Recording behavior

- `record_start_delay_s`
  - delay after traffic is ready before recording starts

### Safety and clearance

- `min_static_clearance_m`
  - clearance from land/authored static obstacles
- `min_dynamic_clearance_m`
  - clearance from moving traffic
- `arrival_clearance_m`
  - considered too close to an obstacle if below this
- `path_sample_step_m`
  - sampling step for path clearance checks

### Stuck recovery

- `recovery_wp_range`
  - smaller resampling range used during recovery
- `stuck_timeout_s`
  - how long low-speed stagnation counts as stuck
- `stuck_speed_mps`
  - speed threshold used to detect being stuck
- `progress_timeout_s`
  - how long without progress before recovery triggers
- `min_progress_m`
  - minimum movement required to count as progress

## `n3mo_control/env_control.py`

Purpose:

- one-shot environment publisher
- sends only the parameters you pass
- exits immediately after publishing

Parameters from [env_control.py](/Users/kifen/Dev/n3mo/N3moSim/ros2_ws/src/n3mo_control/n3mo_control/env_control.py:35):

- `time`
  - publishes `/env/time_of_day`
- `fog`
  - publishes `/env/fog`
- `wind`
  - publishes `/env/wind`
- `wave`
  - publishes `/env/wave`
- `cloudiness`
  - publishes `/env/cloudiness`
- `rain`
  - publishes `/env/rain`
- `weather`
  - publishes `/env/weather`
- `randomize`
  - publishes `/env/randomize`

Example:

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 run n3mo_control env_control --ros-args -p time:=8.0 -p weather:=foggy -p fog:=0.45 -p wave:=0.9 -p wind:=0.6 -p cloudiness:=0.6"
```

## `n3_sim/scenario_generator`

Purpose:

- turn Unity's occupancy grid into a navigable water area
- generate procedural traffic
- play generated or loaded scenarios on `/sim/tracks`

Main publishers/subscribers/services:

- publishes `/sim/tracks`
- subscribes `/map/costmap_static`
- subscribes `/sim/boat/pose`
- subscribes `/scene/objects`
- serves `/sim/generate_scenario`
- serves `/sim/scenario/command`

Parameters from [scenario_generator_params.py](/Users/kifen/Dev/n3mo/N3moSim/ros2_ws/src/n3_sim/n3_sim/scenario_generator/scenario_generator_params.py:10):

### Playback

- `scenario_file`
  - load an existing YAML at startup
- `publish_rate_hz`
  - track publication rate
- `loop`
  - whether playback loops at scenario end

### Generation basics

- `gen_output_file`
  - base output path for generated YAML
- `gen_duration_s`
  - generated scenario duration
- `gen_track_count`
  - explicit track count
- `gen_density`
  - tracks per km² when `gen_track_count=0`
- `gen_area_type`
  - traffic family preset

### Type selection

- `gen_type_names`
  - explicit allowed type list
- `gen_type_weights`
  - legacy per-type weights
- `gen_type_counts_json`
  - explicit type-count override

### Generation triggers

- `gen_autostart`
  - load the scenario immediately after generating it
- `gen_on_first_costmap`
  - auto-generate after the first `/map` arrives

### Track kinematics

- `gen_min_speed_kts`
- `gen_max_speed_kts`
- `gen_min_waypoints`
- `gen_max_waypoints`
- `gen_spawn_spread_s`

### Costmap and scene exclusion

- `gen_margin_m`
  - safety erosion around occupied cells
- `gen_scene_object_clearance_m`
  - clearance from authored objects published on `/scene/objects`
- `gen_track_separation_m`
  - separation between generated spawn points

### Ego-view bias

- `gen_bias_to_ego_view`
- `gen_ego_view_fraction`
- `gen_ego_view_min_range_m`
- `gen_ego_view_max_range_m`
- `gen_ego_view_fov_deg`

### Determinism

- `gen_random_seed`
  - RNG seed used to generate the scene

## Operational Command Examples

## Inspect topics

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic list"
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic echo /sim/tracks --once"
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic hz /sim/boat/pose"
```

## Send one target pose

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 launch n3mo_control target_pose.launch.py x:=-190.0 z:=-110.0"
```

## Set one capture resolution

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic pub --once /camera/resolution std_msgs/msg/String '{data: 720p}'"
```

## Generate one scenario explicitly

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 param set /scenario_generator_node gen_random_seed 12345"
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 param set /scenario_generator_node gen_track_count 24"
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 service call /sim/generate_scenario std_srvs/srv/Trigger '{}'"
```

## Run one fixed-duration sweep

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 run n3mo_control dataset_sweep --ros-args -p duration_s:=20.0 -p hz:=8.0 -p waypoint_period:=12.0 -p min_static_clearance_m:=6.0 -p min_dynamic_clearance_m:=8.0 -p randomize_env_on_start:=false -p randomize_env_during_run:=false -p regenerate_on_start:=false -p regenerate_during_run:=false -p record_start_delay_s:=2.0"
```

## Notes and Caveats

- `/dataset/scenario_info` is a JSON string inside `std_msgs/String`, not a custom ROS message.
- `ros2 param set` parses YAML first, so JSON-like values such as `gen_type_counts_json` must be passed as string literals rather than raw mappings.
- `occupied_fraction` in host scripts maps to `gen_ego_view_fraction` in the scenario generator.
- The operational docs assume the default ego boat identity is `ego_boat`.
