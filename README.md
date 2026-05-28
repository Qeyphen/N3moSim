# N3moSim — Marine Autonomous Vessel Simulation

![Unity](https://img.shields.io/badge/Unity-6.3-black?logo=unity)
![HDRP](https://img.shields.io/badge/Render-HDRP-blue)
![ROS2](https://img.shields.io/badge/ROS2-Humble-green)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow)

N3moSim is a marine simulation environment built in Unity HDRP for training and testing autonomous surface vessels. It provides a realistic ocean environment with dynamic and static objects controlled via ROS2 commands through a Docker-based ROS2 stack. Designed as a Remote Operation Center (ROC) demonstration platform, it supports camera image streaming, sensor telemetry, occupancy grid mapping, static map generation, and real-time environment control.

---

## Overview

N3moSim simulates a realistic maritime environment where autonomous vessels navigate, avoid obstacles, and respond to environmental conditions such as wind, waves, time of day, and weather presets. The simulation streams high-quality sensor data (camera, GPS, IMU) to external systems and receives real-time control commands from external ROS2 nodes. Object poses are fully driven by external ROS2 topics, making it straightforward to integrate with any ROS2-compatible controller, mission planner, or ML model.

A live occupancy grid is published continuously to `/occupancy_grid`, giving any external subscriber a real-time 2D map of all obstacles and vessels. A static nav map of the environment is generated on scene load and published to `/map` in ROS2 Nav2 format.

---

## ✨ Features

- **High Definition Marine Environment** — HDRP ocean with realistic waves, foam, volumetric fog, physically-based sky, and island terrain
- **Dynamic Object Spawning** — Objects spawned at runtime from a shared JSON config file
- **ROS2 Integration** — All vessels controlled via ROS2 TCP bridge; pose fully defined through external ROS topics
- **Physics-Based Movement** — Waypoint-driven vessel motion using Unity Rigidbody forces for realistic acceleration and momentum
- **Pose Control Mode** — Exact position teleport via `PoseStamped` — perfect circles, zero physics drift
- **Velocity Control Mode** — Physics-based movement via `Twist` commands
- **Occupancy Grid** — Live 2D map of all obstacles published to `/occupancy_grid` at 1Hz
- **Static Nav Map** — Full environment map generated on scene load, published to `/map` as `nav_msgs/OccupancyGrid`, saved as `.pgm` + `.yaml`
- **Browser Map Visualiser** — Real-time occupancy grid viewer at `http://localhost:8080` — no RViz needed
- **Camera Image Streaming** — Unity camera feed streamed as compressed JPEG via ROS2
- **Real-Time Environment Control** — Weather presets (Clear/Misty/Rainy/Stormy), time of day, and wave height all controllable via ROS2
- **Static & Dynamic Objects** — Objects can be static (fixed position) or dynamic (ROS2 controlled)
- **Configurable Scenarios** — Change entire scene setup by editing one JSON file
- **Pre-built Demo Scenarios** — Circle, figure-8 and mixed trajectory scenarios
- **Docker ROS2 Stack** — Full ROS2 environment containerised with Docker Compose
- **Shared Config** — Single `scene_config.json` used by both Unity and all ROS2 nodes

---

## Architecture

### Scene Population

```
scene_config.json (shared root config)
        ↓ read by both
Unity SceneLoader.cs              ROS2 n3mo_controller.py
        ↓                                  ↓
Spawns objects at runtime          Creates unique publisher
Attaches PhysicsController         per dynamic object
or PoseController per object
        ↓
MapGenerator.cs
Generates static nav map → /map
Saves map.pgm + map.yaml → recordings/map_<timestamp>/
```

### Control Modes

**Physics Control (default)**
```
waypoint_publisher.py → /{id}/waypoint (PointStamped)
                              ↓
                    Unity PhysicsController.cs
                    applies Rigidbody forces
                    publishes /{id}/actual_pose
```

**Pose Control**
```
pose_publisher.py → /{id}/pose (PoseStamped)
                          ↓
                  Unity PoseController.cs
                  teleports to exact position
```

### Occupancy Grid Pipeline

```
Unity (playing)
  └── OccupancyGridPublisher.cs
        → /unity/all_poses @ 2Hz
                    ↓
        occupancy_grid_server.py
          ├── static obstacles from scene_config.json
          ├── live poses from /unity/all_poses
          └── publishes /occupancy_grid @ 1Hz
                    ↓
        grid_visualiser.py → http://localhost:8080
```

### Static Map Pipeline

```
Unity (scene load)
  └── MapGenerator.cs
        raycasts 1000x1000m from above
        Island/land → occupied (100)
        Water       → free (0)
                    ↓
        publishes /map (nav_msgs/OccupancyGrid)
        saves map.pgm + map.yaml → recordings/map_<timestamp>/
```

### Environment Control Pipeline

```
environment_publisher.py → /environment/update (Float32MultiArray)
                                    ↓
                    Unity EnvironmentController.cs
                      ├── SimpleWeatherController → Clear/Misty/Rainy/Stormy
                      ├── SimpleDayNightCycle     → SetTimeOfDay(0-24h)
                      └── WaterSurface            → timeMultiplier (wave intensity)
```

---

## 🚀 Getting Started

### Prerequisites

- Unity 6.3 LTS with HDRP
- Docker Desktop
- Mac / Linux (Windows via WSL2)

### Installation

#### 1. Clone the repository

```bash
git clone https://github.com/Qeyphen/N3moSim.git
cd N3moSim
```

#### 2. Open Unity Project

1. Open **Unity Hub**
2. Click **"Add project from disk"**
3. Select the **N3moSim** folder
4. Open with **Unity 6.3 LTS**

#### 3. Install ROS TCP Connector

1. **Window → Package Manager → "+" → Add package from git URL**
2. Paste: `https://github.com/Unity-Technologies/ROS-TCP-Connector.git?path=/com.unity.robotics.ros-tcp-connector`

#### 4. Configure ROS Settings

**Robotics → ROS Settings:**

| Setting            | Value       |
| ------------------ | ----------- |
| Protocol           | ROS2        |
| ROS IP Address     | `127.0.0.1` |
| Port               | `10000`     |
| Connect on Startup | ✅ Enabled  |

#### 5. Build and start Docker

```bash
docker compose -f docker-compose-ros2.yml build --no-cache
docker compose -f docker-compose-ros2.yml up -d
```

#### 6. Hit Play in Unity

Objects spawn, map generates, connection establishes automatically.

---

## 🌤️ Environment Control

All environment parameters are controllable in real time via ROS2.

### Message format

Topic: `/environment/update` — `std_msgs/Float32MultiArray`

| Index | Parameter      | Range  | Description                          |
| ----- | -------------- | ------ | ------------------------------------ |
| `[2]` | wave_height    | 0-5m   | Ocean wave intensity                 |
| `[3]` | time_of_day    | 0-24h  | Sun position and light intensity     |
| `[4]` | flag           | —      | See table below                      |

### Flag values

| Flag   | Meaning              |
| ------ | -------------------- |
| `0.0`  | Gradual transition   |
| `1.0`  | Instant snap         |
| `10.0` | Apply Clear preset   |
| `11.0` | Apply Misty preset   |
| `12.0` | Apply Rainy preset   |
| `13.0` | Apply Stormy preset  |

### Weather presets

| Preset  | Sky       | Fog        | Rain | Sun intensity |
| ------- | --------- | ---------- | ---- | ------------- |
| Clear   | Blue      | Minimal    | None | 120,000 lux   |
| Misty   | Grey      | Very dense | None | 35,000 lux    |
| Rainy   | Dark grey | Dense      | Full | 20,000 lux    |
| Stormy  | Very dark | Very dense | Full | 8,000 lux     |

### Publisher modes

| Mode     | Description                                    |
| -------- | ---------------------------------------------- |
| `manual` | Publish once with given parameters             |
| `preset` | Apply named weather preset instantly           |
| `cycle`  | Cycle time of day continuously                 |
| `storm`  | Gradually build wind and waves over 60 seconds |
| `calm`   | Gradually reduce wind and waves over 30 seconds|

### Example commands

```bash
# Stormy preset
ros2 run n3mo_control environment_publisher --ros-args \
  -p mode:=preset -p preset_name:=stormy

# Sunset
ros2 run n3mo_control environment_publisher --ros-args \
  -p mode:=manual -p time_of_day:=17.0 -p instant:=true

# Rough seas
ros2 run n3mo_control environment_publisher --ros-args \
  -p mode:=manual -p wave_height:=5.0 -p instant:=true

# Cycle day/night
ros2 run n3mo_control environment_publisher --ros-args \
  -p mode:=cycle -p cycle_speed:=1.0
```

---

## 🗺️ Static Nav Map

Generated automatically on every scene load.

| File       | Description                                         |
| ---------- | --------------------------------------------------- |
| `map.pgm`  | Greyscale image — white=water (free), black=land (occupied) |
| `map.yaml` | ROS2 Nav2 metadata — resolution, origin, thresholds |

| Parameter  | Value              |
| ---------- | ------------------ |
| Coverage   | 1000×1000m         |
| Resolution | 1m/cell            |
| Topic      | `/map`             |
| Type       | `nav_msgs/OccupancyGrid` |

```bash
# Verify topic
ros2 topic info /map

# Open saved map
open ~/Dev/n3mo/N3moSim/recordings/$(ls -t ~/Dev/n3mo/N3moSim/recordings/ | grep map | head -1)/map.pgm

# Load in Nav2
ros2 run nav2_map_server map_server --ros-args \
  -p yaml_filename:=recordings/map_<timestamp>/map.yaml
```

---

## 🗺️ Occupancy Grid

Live 2D obstacle map published continuously.

| Value | Meaning  |
| ----- | -------- |
| `0`   | Free     |
| `100` | Occupied |
| `-1`  | Unknown  |

Coverage: 1000×1000m at 1m/cell. Topic: `/occupancy_grid`.

---

## ⚙️ Scene Configuration

`N3moSim/config/scene_config.json`:

```json
{
  "environment": {
    "wind_speed": 5.0,
    "wave_height": 1.5,
    "time_of_day": "day"
  },
  "objects": [
    {
      "id": "sailboat_01",
      "type": "Sailboat",
      "dynamic": true,
      "ros2_topic": "/sailboat_01/waypoint",
      "position": [0, 1, -300],
      "rotation": [0, 0, 0]
    },
    {
      "id": "buoy_01",
      "type": "Buoy",
      "dynamic": false,
      "position": [-190, 0, -110],
      "rotation": [-90, 0, 0]
    }
  ]
}
```

---

## 🐳 Docker Services

| Service                 | Container        | Port  | Description                                     |
| ----------------------- | ---------------- | ----- | ----------------------------------------------- |
| `ros_bridge`            | n3mo_bridge      | 10000 | ROS TCP Bridge — connects Unity to ROS2         |
| `n3mo_controller`       | n3mo_controller  | —     | Master controller for all dynamic objects       |
| `mission_planner`       | n3mo_mission     | —     | High level mission brain                        |
| `sensor_publisher`      | n3mo_sensors     | —     | Publishes sensor data from Unity to ROS2        |
| `obstacle_detector`     | n3mo_obstacles   | —     | Detects obstacles within radius                 |
| `trajectory_publisher`  | n3mo_trajectory  | —     | Autonomous demo trajectory scenarios            |
| `occupancy_grid_server` | n3mo_grid        | —     | Builds and publishes live occupancy grid        |
| `grid_visualiser`       | n3mo_viz         | 8080  | Browser-based live map at http://localhost:8080 |

```bash
docker compose -f docker-compose-ros2.yml logs -f        # all logs
docker compose -f docker-compose-ros2.yml down           # stop
docker compose -f docker-compose-ros2.yml build --no-cache  # rebuild
```

---

## 🧩 Unity Scripts

| Script                      | Description                                                          |
| --------------------------- | -------------------------------------------------------------------- |
| `SceneLoader.cs`            | Reads config, spawns objects, attaches controllers                   |
| `PhysicsController.cs`      | Waypoint-driven movement using Rigidbody forces                      |
| `PoseController.cs`         | Teleports object to exact ROS2 PoseStamped position                  |
| `ROSController.cs`          | Physics forces from Twist velocity commands                          |
| `OccupancyGridPublisher.cs` | Publishes live positions to `/unity/all_poses` at 2Hz                |
| `CameraStreamer.cs`         | Streams camera as compressed JPEG to `/unity/camera/compressed`      |
| `EnvironmentController.cs`  | Receives `/environment/update`, drives weather/time/waves            |
| `MapGenerator.cs`           | Generates static nav map on scene load, publishes `/map`, saves files|

---

## 🗺️ Roadmap

### Core Simulation
- [x] Base marine environment (HDRP ocean, sky, island terrain)
- [x] Sailboat, buoy, catamaran prefabs
- [x] JSON config-based dynamic scene loading
- [x] ROS TCP Connector integration
- [x] Docker Compose ROS2 stack
- [x] Physics-based movement (waypoint + Rigidbody forces)
- [x] Pose control mode (PoseStamped)
- [x] Velocity control mode (Twist)
- [ ] Buoyancy physics system
- [ ] Seagull and swimmer prefabs

### Environment
- [x] Weather presets (Clear / Misty / Rainy / Stormy) via ROS2
- [x] Time of day control (0-24h) via ROS2
- [x] Wave height control via ROS2
- [ ] Continuous wind direction control (WaterSurface API limitation)

### Data Export & Recording
- [x] Live occupancy grid via ROS2
- [x] Static nav map (map.pgm + map.yaml) on scene load
- [x] Real-time environment control over ROS2
- [x] ROS bag recording of all topics
- [x] ML dataset export (frames + pose + command CSV)

### Scene & World Generation
- [ ] Procedural scene generation
- [ ] Real-world map import (coastline / maritime data)
- [ ] Scenario generation (Christophe integration)

### Camera & Sensors
- [ ] Physics-based camera motion
- [ ] Camera attached to boat frame
- [ ] URDF-defined camera pose
- [ ] LiDAR simulation
- [ ] Full GPS/IMU live pipeline

### Integration
- [ ] ROC web-app integration

---

## Troubleshooting

### Unity can't connect to ROS bridge

```bash
docker compose -f docker-compose-ros2.yml down
docker compose -f docker-compose-ros2.yml up -d
```
Then hit Play in Unity again.

### Objects not spawning

Check Console for `[SceneLoader] Config not found!`. Config must be at `YourProject/../../config/scene_config.json` or `YourProject/Assets/Config/scene_config.json`.

### Occupancy grid shows 0 occupied cells

```bash
docker exec -it n3mo_bridge bash -c "source /opt/ros/humble/setup.bash && ros2 topic hz /unity/all_poses"
```
Should show `average rate: 2.0`. If nothing — Unity isn't connected.

### Map not generating

Check Unity Console for `[MapGenerator] Starting map generation...`. If missing, confirm `MapGenerator` component is attached to a GameObject in the scene.

### Environment commands not working

Check Console for `[EnvironmentController] components found:` — all three components must show as found (WaterSurface, WeatherController, DayNightCycle).