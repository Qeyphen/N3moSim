# Architecture

## Overview

The project has four layers:

1. Unity runtime
2. ROS 2 services in Docker
3. Scenario generation and ego-drive orchestration
4. Dataset post-processing on the host

At runtime, the loop is:

1. Unity loads the scene from `config/Scene.json`
2. Unity publishes a static occupancy grid on `/map`
3. ROS scenario generation uses `/map` as navigable water / obstacle input
4. ROS publishes dynamic traffic on `/sim/tracks`
5. Unity spawns and updates those traffic objects
6. Unity Perception cameras capture RGB and annotations
7. Host-side tools convert SOLO output into previews, masks, and YOLO datasets

## Main Directories

- `Assets/Scripts/`
  - Unity-side logic
- `config/`
  - scene definition, RViz config, URDF
- `ros2_ws/src/n3_sim/`
  - scenario generator, simulator-side ROS nodes
- `ros2_ws/src/n3mo_control/`
  - ego control, environment control, dataset sweep
- `tools/`
  - host-side orchestration and export scripts
- `docker-compose.yml`
  - ROS bridge, scenario service, optional RViz

## Docker Services

### `ros_bridge`

Purpose:

- exposes the ROS TCP endpoint on port `10000`
- lets Unity talk to ROS through the ROS-TCP-Connector
- hosts the overlay workspace for `n3_sim`, `n3mo_control`, and `n3_common`

### `scenario`

Purpose:

- runs `tracks_markers`
- runs `scenario_generator`
- consumes Unity's `/map`
- publishes `/sim/tracks`

Important detail:

- the `scenario` service is under the `rviz` profile in `docker-compose.yml`
- but you can still start it directly with:

```bash
docker compose up -d ros_bridge scenario
```

### `rviz`

Purpose:

- optional visual debugging
- shows the map, generated tracks, and ego pose

## Key ROS Topics

### Unity -> ROS

- `/map`
  - `nav_msgs/OccupancyGrid`
  - static authored obstacles rasterized by Unity
- `/sim/boat/pose`
  - ego boat pose
- `/scene/objects`
  - authored scene-object list published as tracks
- `/env/state`
  - current environment state as JSON

### ROS -> Unity

- `/sim/tracks`
  - generated moving traffic
- `/env/time_of_day`
- `/env/weather`
- `/env/fog`
- `/env/wind`
- `/env/wave`
- `/env/cloudiness`
- `/env/rain`
- `/dataset/control`
- `/dataset/capture_hz`
- `/dataset/scenario_info`
- `/camera/resolution`

## Unity Runtime Scripts

### Scene and control

- `SceneBuilder.cs`
  - reads `config/Scene.json`
  - spawns authored scene objects
- `BoatControlSwitcher.cs`
  - switches ego boat between manual and auto
- `AutonomousBoatController.cs`
  - drives the ego boat toward ROS-selected targets
- `ManualBoatController.cs`
  - keyboard/manual control

### ROS publishing and spawning

- `OccupancyGridPublisher.cs`
  - publishes `/map`
  - rasterizes authored static obstacles
  - can include additional authored obstacles through `Extra Obstacles`
- `TrackSpawner.cs`
  - subscribes to `/sim/tracks`
  - instantiates and updates generated traffic objects
- `EgoPosePublisher.cs`
  - publishes ego boat pose
- `DynamicObstaclePublisher.cs`
  - publishes generated dynamic obstacles back out if needed by other systems

### Capture and metadata

- `DatasetCaptureScheduler.cs`
  - triggers Perception capture manually at a requested Hz
  - starts/stops on `/dataset/control`
  - updates capture rate from `/dataset/capture_hz`
  - attaches scenario metadata from `/dataset/scenario_info`
- `CaptureResolution.cs`
  - sets Perception camera output pixel size by assigning a `RenderTexture`
  - can apply to all Perception cameras
  - listens on `/camera/resolution`
- `RunMetadata.cs`
  - writes per-run metadata files into the SOLO directory
- `UnityDefaultsDump.cs`
  - caches Unity startup/default state and later flushes it into SOLO
- `ScenarioMetadataContext.cs`
  - stores the current scenario metadata in Unity for capture bookkeeping

### Environment

- `EnvironmentController.cs`
  - owns weather and time-of-day state in Unity
  - subscribes to ROS environment topics
  - applies an override HDRP volume at runtime

## Occupancy Grid and Costmap

## What the occupancy grid is

`OccupancyGridPublisher.cs` rasterizes static scene geometry into a ROS `nav_msgs/OccupancyGrid` on `/map`.

The current default grid fields in code are:

- `originX = -500`
- `originZ = -500`
- `widthMeters = 1000`
- `heightMeters = 1000`
- `resolution = 1`

Cell count is computed as:

- `cols = ceil(widthMeters / resolution)`
- `rows = ceil(heightMeters / resolution)`

So the default values produce:

- `1000 x 1000` cells

That is why Unity logs:

```text
[OccupancyGridPublisher] Published 1000x1000 grid on '/map'
```

## What the costmap is

On the ROS side, `scenario_generator` uses the occupancy grid as a water-vs-obstacle map.

In `docker-compose.yml`, the scenario node is started with:

```text
-r /map/costmap_static:=/map
```

So Unity's `/map` becomes the generator's costmap input.

The generator then:

- extracts navigable water
- erodes it by a safety margin
- excludes authored scene objects
- samples traffic paths only in allowed water

## How to change the occupancy grid size

Preferred method: Unity Inspector.

Find the GameObject that owns `OccupancyGridPublisher` and edit:

- `Origin X`
- `Origin Z`
- `Width Meters`
- `Height Meters`
- `Resolution`
- `Inflation Radius`

Examples:

- `widthMeters = 2000`, `heightMeters = 2000`, `resolution = 1`
  - `2000 x 2000` cells
- `widthMeters = 1000`, `heightMeters = 1000`, `resolution = 0.5`
  - `2000 x 2000` cells
- `widthMeters = 600`, `heightMeters = 600`, `resolution = 1`
  - `600 x 600` cells

Important tradeoff:

- larger area or finer resolution means more cells
- more cells means more publishing cost and more scenario-generation work

## How to make the generator avoid authored obstacles such as the island

Use `OccupancyGridPublisher -> Extra Obstacles`.

Add the island prefab or island-rendering GameObject there so it is rasterized into `/map`.

If the island is not present in `/map`, the scenario generator has no authoritative static obstacle telling it to stay away from it.

## Scenario Generator Architecture

### Main files

- `ros2_ws/src/n3_sim/n3_sim/scenario_generator/scenario_generator_node.py`
- `ros2_ws/src/n3_sim/n3_sim/scenario_generator/scenario_model.py`
- `ros2_ws/src/n3_sim/n3_sim/scenario_generator/scenario_generator_params.py`

### Responsibilities

`scenario_generator_node.py`

- owns ROS subscriptions, publishers, and services
- reads costmap and ego pose
- generates scenarios
- loads scenarios
- publishes active track states
- exposes the `/sim/scenario/command` service

`scenario_model.py`

- defines scenario and track dataclasses
- interpolates track state over time
- extracts navigable water from the occupancy grid
- generates procedural tracks

`scenario_generator_params.py`

- defines the ROS-exposed generator parameters

### Traffic visibility bias

The generator supports ego-view bias through:

- `gen_bias_to_ego_view`
- `gen_ego_view_fraction`
- `gen_ego_view_min_range_m`
- `gen_ego_view_max_range_m`
- `gen_ego_view_fov_deg`

Meaning:

- some fraction of tracks are sampled ahead of the ego boat
- those tracks also preferentially sample later waypoints in the forward cone

This improves useful camera views, but it is still a probabilistic bias, not a hard per-frame guarantee.

### Traffic timing

The generator now also:

- spreads spawn times across the scenario
- avoids front-loading all traffic at the beginning
- extends tracks so traffic remains alive later into the run

This was added to avoid scenes that look dense only at the beginning.
