# N3moSim — Marine Autonomous Vessel Simulation

![Unity](https://img.shields.io/badge/Unity-6.0-black?logo=unity)
![HDRP](https://img.shields.io/badge/Render-HDRP-blue)
![ROS2](https://img.shields.io/badge/ROS2-Humble-green)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow)

N3moSim is a marine simulation environment built in Unity HDRP for training and testing autonomous surface vessels. It provides a realistic ocean environment with dynamic and static objects controlled via ROS2 commands through a Docker-based ROS2 stack. Designed as a Remote Operation Center (ROC) demonstration platform, it supports camera image streaming, sensor telemetry, occupancy grid mapping, and multi-vessel autonomous scenario playback.

---

## Overview

N3moSim simulates a realistic maritime environment where autonomous vessels navigate, avoid obstacles, and respond to environmental conditions such as wind and waves. The simulation is designed to stream high-quality sensor data (camera, GPS, IMU) to external systems and to receive real-time control commands from external ROS2 nodes. Object poses are fully driven by external ROS2 topics, making it straightforward to integrate with any ROS2-compatible controller, mission planner, or ML model.

A live occupancy grid is generated from the scene and published continuously to `/occupancy_grid`, giving any external subscriber a real-time 2D map of all obstacles and vessels.

---

## ✨ Features

- **High Definition Marine Environment** — HDRP ocean with realistic waves, foam, volumetric fog, physically-based sky, and island terrain
- **Dynamic Object Spawning** — Objects spawned at runtime from a shared JSON config file
- **ROS2 Integration** — All vessels controlled via ROS2 TCP bridge; pose fully defined through external ROS topics
- **Pose Control Mode** — Exact position teleport via `PoseStamped` — perfect circles, zero physics drift
- **Velocity Control Mode** — Physics-based movement via `Twist` commands
- **Occupancy Grid** — Live 2D map of all obstacles published to `/occupancy_grid` at 1Hz
- **Browser Map Visualiser** — Real-time occupancy grid viewer at `http://localhost:8080` — no rviz needed
- **Camera Image Streaming** — Unity camera feed streamed out as binary or base64 JPEG via WebSocket
- **Sensor Telemetry** — GPS, IMU and wind data published to ROS2 network
- **Static & Dynamic Objects** — Objects can be static (fixed position) or dynamic (ROS2 controlled)
- **Configurable Scenarios** — Change entire scene setup by editing one JSON file
- **Pre-built Demo Scenarios** — Circle, figure-8 and mixed trajectory scenarios for demonstration
- **Realistic Weather** — Sun, fog, rain and time-of-day control via Volume system
- **Docker ROS2 Stack** — Full ROS2 environment containerized with Docker Compose
- **Multi-Object Control** — Each dynamic object gets a unique ROS2 topic for independent control
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
Attaches PoseController            per dynamic object
or ROSController per object
```

### Control Modes

**Pose Control (default, recommended)**
```
pose_publisher.py → /sailboat_01/pose (PoseStamped)
                          ↓
                  Unity PoseController.cs
                  teleports to exact position
                  no physics drift, perfect circles
```

**Velocity Control**
```
trajectory_publisher.py → /mission/{id}/cmd_vel (Twist)
                                ↓
                        n3mo_controller.py
                                ↓
                        /{id}/cmd_vel → Unity
                        ROSController.cs applies physics force
```

### Occupancy Grid Pipeline

```
Unity (playing)
  └── OccupancyGridPublisher.cs
        sends live object positions → /unity/all_poses @ 2Hz
                    ↓
        occupancy_grid_server.py
          ├── static obstacles from scene_config.json
          ├── live poses from /unity/all_poses
          └── publishes /occupancy_grid @ 1Hz
                    ↓
        grid_visualiser.py → http://localhost:8080
        any external subscriber (path planner, ML agent)
```

### Multi-Object Control

```
n3mo_controller
  ├── /sailboat_01/cmd_vel   → sailboat_01 moves independently
  ├── /catamaran_01/cmd_vel  → catamaran_01 moves independently
  ├── /catamaran_02/cmd_vel  → catamaran_02 moves independently
  └── /buoy_03/cmd_vel       → buoy_03 moves independently
```

---

## 🚀 Getting Started

### Prerequisites

- Unity 6.0 or later with HDRP
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
4. Open with **Unity 6.0+**

#### 3. Install ROS TCP Connector in Unity

1. **Window → Package Manager**
2. Click **"+"** → **"Add package from git URL"**
3. Paste:

```
https://github.com/Unity-Technologies/ROS-TCP-Connector.git?path=/com.unity.robotics.ros-tcp-connector
```

#### 4. Configure Unity ROS Settings

1. **Robotics → ROS Settings**
2. Set:

| Setting            | Value       |
| ------------------ | ----------- |
| Protocol           | ROS2        |
| ROS IP Address     | `127.0.0.1` |
| Port               | `10000`     |
| Connect on Startup | ✅ Enabled  |

#### 5. Configure SceneManager in Unity

1. In the Hierarchy select **SceneManager**
2. In the Inspector confirm these are assigned:

| Slot              | Value              |
| ----------------- | ------------------ |
| Sailboat Prefab   | Sailboat prefab    |
| Buoy Prefab       | Buoy prefab        |
| Catamaran Prefab  | Catamaran prefab   |
| Virtual Camera    | Virtual Camera     |
| Use Pose Control  | ✅ checked         |
| Config File Name  | scene_config.json  |

3. Also confirm **Occupancy Grid Publisher** component is attached to SceneManager

#### 6. Build Docker ROS2 image

```bash
docker compose -f docker-compose-ros2.yml build --no-cache
```

#### 7. Start ROS2 services

```bash
docker compose -f docker-compose-ros2.yml up -d
```

---

## 🎮 Running the Simulation

### Step 1 — Start ROS2 stack

```bash
docker compose -f docker-compose-ros2.yml up -d
```

### Step 2 — Wait for services to be ready

```bash
docker compose -f docker-compose-ros2.yml logs -f
```

Wait until you see:
```
OccupancyGridServer ready — 1000.0x1000.0m @ 1.0m/cell
Starting Grid Visualiser on http://localhost:8080
```

### Step 3 — Press Play in Unity

Objects spawn from config. Unity connects to ROS TCP Bridge on port 10000.

### Step 4 — Verify connection

```bash
docker compose -f docker-compose-ros2.yml logs ros_bridge
# Should show: New connection from 127.0.0.1
```

### Step 5 — Open the map visualiser

Open your browser at:
```
http://localhost:8080
```

You will see a live top-down map showing all buoys and vessels as cyan dots updating in real time.

### Step 6 — Run a demo scenario

```bash
# Circle trajectory
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  ros2 run n3mo_control pose_publisher --ros-args -p scenario:=circle
"

# Figure-8 trajectory
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  ros2 run n3mo_control pose_publisher --ros-args -p scenario:=eight
"
```

---

## 🗺️ Occupancy Grid

The occupancy grid is a 2D map of the environment published continuously to `/occupancy_grid` as a `nav_msgs/OccupancyGrid` message.

### Cell values

| Value | Meaning  |
| ----- | -------- |
| `0`   | Free     |
| `100` | Occupied |
| `-1`  | Unknown  |

### Default parameters

| Parameter    | Default   | Description               |
| ------------ | --------- | ------------------------- |
| `resolution` | `1.0`     | Metres per cell           |
| `width_m`    | `1000.0`  | Map width in metres       |
| `height_m`   | `1000.0`  | Map height in metres      |
| `origin_x`   | `-500.0`  | World X of cell (0,0)     |
| `origin_y`   | `-500.0`  | World Z of cell (0,0)     |

### Object radii (cells)

| Object    | Radius | Cells marked |
| --------- | ------ | ------------ |
| Sailboat  | 3      | ~29          |
| Catamaran | 4      | ~49          |
| Buoy      | 2      | 13           |

### Checking the grid

```bash
docker exec -it n3mo_grid bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  export AMENT_PREFIX_PATH=/root/ros2_ws/install/n3mo_control:/root/ros2_ws/install/ros_tcp_endpoint:\$AMENT_PREFIX_PATH &&
  ros2 run n3mo_control grid_checker
"
```

Expected output with Unity playing:
```
Map size    : 1000x1000 cells
Total cells : 1000000
Occupied    : 52  (3 buoys + 1 sailboat)
Free        : 999948
```

### Using the grid in an external node

```python
from nav_msgs.msg import OccupancyGrid

def on_grid(self, msg):
    w = msg.info.width

    def is_safe(world_x, world_z):
        cx  = int((world_x - msg.info.origin.position.x) / msg.info.resolution)
        cy  = int((world_z - msg.info.origin.position.y) / msg.info.resolution)
        idx = cy * w + cx
        return msg.data[idx] == 0  # 0 = free, 100 = occupied

    if is_safe(target_x, target_z):
        self.set_mission('sailboat_01', 'forward')
    else:
        self.set_mission('sailboat_01', 'turn_left')
```

---

## ⚙️ Scene Configuration

Single config file at `N3moSim/config/scene_config.json` — used by both Unity and ROS2:

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
      "ros2_topic": "/sailboat_01/cmd_vel",
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

### Config fields

| Field        | Type    | Description                                  |
| ------------ | ------- | -------------------------------------------- |
| `id`         | string  | Unique object identifier                     |
| `type`       | string  | Prefab type: `Sailboat`, `Buoy`, `Catamaran` |
| `dynamic`    | bool    | `true` = ROS2 controlled, `false` = static   |
| `ros2_topic` | string  | Unique ROS2 topic per object                 |
| `position`   | [x,y,z] | Spawn position in world space                |
| `rotation`   | [x,y,z] | Spawn rotation in euler angles               |

---

## 🎬 Demo Scenarios

Three pre-built autonomous trajectory scenarios are included. Each runs without human input.

| Scenario | File                    | Description                                  |
| -------- | ----------------------- | -------------------------------------------- |
| Circles  | `scenario_circles.json` | All vessels circle independently             |
| Figure-8 | `scenario_eight.json`   | All vessels trace figure-8 paths             |
| Mixed    | `scenario_mixed.json`   | Mix of circles and figure-8 — best for demo  |

### Scenario config format

```json
{
  "scenario": "mixed",
  "description": "Mixed trajectories",
  "objects": [
    {
      "id": "sailboat_01",
      "trajectory": "circle",
      "linear_x": 2.0,
      "angular_z": 0.3,
      "phase_offset": 0.0
    },
    {
      "id": "catamaran_01",
      "trajectory": "eight",
      "linear_x": 2.5,
      "angular_z_amplitude": 0.6,
      "phase_offset": 0.0
    }
  ]
}
```

| Field                 | Values              | Description                     |
| --------------------- | ------------------- | ------------------------------- |
| `trajectory`          | `circle` \| `eight` | Path shape                      |
| `linear_x`            | float               | Forward speed (m/s)             |
| `angular_z`           | float               | Turn rate for circles (rad/s)   |
| `angular_z_amplitude` | float               | Max turn amplitude for figure-8 |
| `phase_offset`        | float (radians)     | Offset so vessels don't overlap |

---

## 🤖 ROS2 Control

### Send commands via terminal

```bash
docker exec n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  ros2 topic pub --once /mission/sailboat_01/cmd_vel \
    geometry_msgs/msg/Twist \
    '{linear: {x: 1.0}, angular: {z: 0.0}}'
"
```

### ROS2 Topics

| Topic                   | Direction        | Type           | Description                      |
| ----------------------- | ---------------- | -------------- | -------------------------------- |
| `/mission/{id}/cmd_vel` | → n3mo_controller| Twist          | Send velocity command to object  |
| `/{id}/cmd_vel`         | → Unity          | Twist          | Forwarded from controller        |
| `/{id}/pose`            | → Unity          | PoseStamped    | Exact position (pose mode)       |
| `/unity/all_poses`      | Unity → ROS2     | PoseArray      | All live object positions        |
| `/occupancy_grid`       | ROS2 publish     | OccupancyGrid  | Live 2D obstacle map             |
| `/sailboat/gps`         | Unity → ROS2     | NavSatFix      | Boat GPS position                |
| `/sailboat/imu`         | Unity → ROS2     | Imu            | Boat orientation                 |
| `/environment/wind`     | Unity → ROS2     | Vector3        | Wind speed and direction         |
| `/obstacles`            | → mission_planner| String         | All detected obstacles           |

---

## 🐳 Docker Services

| Service                 | Container        | Port  | Description                                      |
| ----------------------- | ---------------- | ----- | ------------------------------------------------ |
| `ros_bridge`            | n3mo_bridge      | 10000 | ROS TCP Bridge — connects Unity to ROS2          |
| `n3mo_controller`       | n3mo_controller  | —     | Master controller for all dynamic objects        |
| `mission_planner`       | n3mo_mission     | —     | High level mission brain                         |
| `sensor_publisher`      | n3mo_sensors     | —     | Publishes sensor data from Unity to ROS2         |
| `obstacle_detector`     | n3mo_obstacles   | —     | Detects obstacles within radius                  |
| `trajectory_publisher`  | n3mo_trajectory  | —     | Autonomous demo trajectory scenarios             |
| `occupancy_grid_server` | n3mo_grid        | —     | Builds and publishes live occupancy grid         |
| `grid_visualiser`       | n3mo_viz         | 8080  | Browser-based live map at http://localhost:8080  |

### Useful Docker commands

```bash
# View all service logs
docker compose -f docker-compose-ros2.yml logs -f

# View specific service
docker compose -f docker-compose-ros2.yml logs -f n3mo_grid

# Check service status
docker compose -f docker-compose-ros2.yml ps

# Stop all services
docker compose -f docker-compose-ros2.yml down

# Rebuild after code changes
docker compose -f docker-compose-ros2.yml build --no-cache

# List active ROS2 topics
docker exec n3mo_bridge bash -c \
  "source /opt/ros/humble/setup.bash && ros2 topic list"

# Check occupancy grid live
docker exec -it n3mo_grid bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  ros2 run n3mo_control grid_checker
"
```

---

## 🧩 Unity Scripts

### SceneLoader.cs

Reads `scene_config.json` at startup and spawns all objects. Searches two locations: project root `../../config/` first, then `Assets/Config/`. Automatically attaches `PoseController` or `ROSController` to dynamic objects based on the `Use Pose Control` toggle. Assigns the first sailboat as the Cinemachine camera follow target.

### PoseController.cs

Attached automatically to dynamic objects when `Use Pose Control` is enabled. Subscribes to `/{id}/pose` and teleports the object to the exact received position each frame. Applies a per-type rotation offset to match each prefab's forward axis. No physics drift.

### ROSController.cs

Attached automatically to dynamic objects when `Use Pose Control` is disabled. Subscribes to the object's unique ROS2 topic. Applies physics forces based on incoming `Twist` messages. Supports `useUpAsForward` for prefabs with -90 X rotation (catamaran, buoy).

### OccupancyGridPublisher.cs

Attached to SceneManager. Reads live positions of all tracked objects from SceneLoader every 0.5 seconds and publishes them as a `PoseArray` to `/unity/all_poses`. The occupancy grid server subscribes to this topic to update the live map.

---

## 🐍 ROS2 Nodes

### config_loader.py

Shared utility used by all nodes. Searches for `scene_config.json` in multiple locations — Docker mounted path first (`/n3mosim/config/`), then ROS2 package share directory, then relative fallback.

### n3mo_controller.py

Master controller. Reads config and creates one publisher per dynamic object on unique topic `/{object_id}/cmd_vel`. Subscribes to `/mission/{object_id}/cmd_vel` from mission planner and forwards to Unity.

### mission_planner.py

High level mission brain. Manages per-object state machines (`idle`, `forward`, `patrol`, `turn_left`, `turn_right`, `stop`). Publishes to `/mission/{object_id}/cmd_vel`.

### pose_publisher.py

Publishes exact `PoseStamped` positions for circle and figure-8 trajectories directly to `/{id}/pose`. Used with `PoseController` mode for perfect, drift-free paths.

```bash
ros2 run n3mo_control pose_publisher --ros-args -p scenario:=circle
ros2 run n3mo_control pose_publisher --ros-args -p scenario:=eight
```

### trajectory_publisher.py

Demo scenario runner using velocity commands. Reads a scenario JSON file and publishes `Twist` commands for each vessel. Used with `ROSController` mode.

### occupancy_grid_server.py

Builds and publishes a 2D occupancy grid from static obstacles (scene_config.json) and live object poses from Unity (/unity/all_poses). Publishes to `/occupancy_grid` at 1Hz. Grid is 1000x1000m by default, covering any reasonable spawn position.

### grid_checker.py

Diagnostic node. Subscribes to `/occupancy_grid` and prints live stats — map size, resolution, occupied cell count, free cell count. Run any time to verify the pipeline.

### grid_visualiser.py

Flask-based web server. Subscribes to `/occupancy_grid` and serves a live browser map at `http://localhost:8080`. Shows all occupied cells as cyan dots on a dark background, updating at 2Hz. No rviz required.

### sensor_publisher.py

Receives Unity simulation data and publishes as standard ROS2 sensor messages — GPS (`NavSatFix`), IMU (`Imu`), wind (`Vector3`). GPS origin set to Brest, France (48.3833°N, 4.4833°W).

### obstacle_detector.py

Receives all object positions from Unity. Filters obstacles within configurable detection radius (default 50m). Publishes to `/obstacles` and `/obstacles/nearby`.

---

## 🗺️ Roadmap

### Core Simulation
- [x] Base marine environment (HDRP ocean, sky, island terrain, volumetric fog)
- [x] Sailboat prefab (PBR model + physics)
- [x] Buoy prefab (navigation buoy + physics)
- [x] Catamaran prefab (racing catamaran + physics)
- [x] JSON config-based dynamic scene loading
- [x] ROS TCP Connector integration
- [x] Docker Compose ROS2 stack
- [x] Multi-object independent ROS2 control
- [x] Shared scene_config.json (Unity + ROS2)
- [x] Mission planner with per-object state machine
- [x] Pose control mode (PoseStamped — zero drift)
- [x] Velocity control mode (Twist — physics-based)
- [x] Trajectory publisher — circle and figure-8 demo scenarios
- [ ] Buoyancy physics system
- [ ] Realistic weather randomization (storm, fog, rain, night)
- [ ] Seagull and swimmer prefabs

### Data Export & Recording
- [x] Occupancy grid map — generate and export from Unity scene
- [x] Realtime update of scene over ROS2 — update environment parameters (wind, time of day, wave height)
- [ ] How much data — estimate volume of data to be exported based on a 10-15 min window
- [ ] ROS bag & Unity Recorder — record all ROS2 topics with timestamps for replay and dataset creation; Unity Recorder captures camera feeds and scene state in sync

### Scene & World Generation
- [ ] Generate world scene — procedural scene generation inside Unity
- [ ] Generate scene from real-world maps — research importing real coastline and maritime data into Unity
- [ ] Map integration — connect external map sources to Unity scene generator
- [ ] Generate map in Unity and export — bidirectional map pipeline
- [ ] Scenario generation — integrate existing scenario generation work from Christophe

### Physics & Movement
- [ ] Physics-based movement — replace current pose teleportation with physics-driven vessel motion for realism and higher-quality training data

### Camera System
- [ ] Field of view — define and configure camera FOV parameters
- [ ] Physics-based camera motion — camera should react to boat motion and wave dynamics
- [ ] Camera attached to boat frame — camera observes boat from a fixed pose relative to the vessel
- [ ] URDF-defined camera pose — camera transform read from URDF, not hardcoded in Unity

### Sensor & Streaming
- [ ] Camera image streaming (binary + base64 JPEG via WebSocket)
- [ ] AUV telemetry streaming (GPS, heading, speed)
- [ ] Unity → ROS2 full GPS/IMU pipeline (live from scene)
- [ ] LiDAR sensor simulation
- [ ] Multiple vessel telemetry in single ROS2 message

### Integration
- [ ] ROC web-app integration
- [ ] LiDAR sensor simulation

---

## Troubleshooting

### Unity can't connect to ROS bridge

Docker networking on Mac can break after a restart. Fix:
```bash
docker compose -f docker-compose-ros2.yml down
docker compose -f docker-compose-ros2.yml up -d
```
Then hit Play in Unity again.

### Objects not spawning in Unity

Check the Console tab for `[SceneLoader] Config not found!`. The config must exist at either:
- `YourProject/../../config/scene_config.json`
- `YourProject/Assets/Config/scene_config.json`

### Occupancy grid shows 0 occupied cells

Run the grid checker to confirm the server is running, then check Unity is connected:
```bash
docker exec -it n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  ros2 topic hz /unity/all_poses
"
```
Should show `average rate: 2.0`. If nothing — Unity isn't connected or `OccupancyGridPublisher` component is missing from SceneManager.

### Sailboat outside grid bounds

The default grid covers -500m to +500m. If your sailboat spawns outside this range increase the grid size in `docker-compose-ros2.yml`:
```
ros2 run n3mo_control occupancy_grid_server --ros-args -p origin_x:=-500.0 -p origin_y:=-500.0 -p width_m:=1000.0 -p height_m:=1000.0
```