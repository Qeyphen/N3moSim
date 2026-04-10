# N3moSim — Marine Autonomous Vessel Simulation

![Unity](https://img.shields.io/badge/Unity-6.0-black?logo=unity)
![HDRP](https://img.shields.io/badge/Render-HDRP-blue)
![ROS2](https://img.shields.io/badge/ROS2-Humble-green)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow)

N3moSim is a marine simulation environment built in Unity HDRP for training and testing autonomous surface vessels. It provides a realistic ocean environment with dynamic and static objects controlled via ROS2 commands through a Docker-based ROS2 stack. Designed as a Remote Operation Center (ROC) demonstration platform, it supports camera image streaming, sensor telemetry, and multi-vessel autonomous scenario playback.

---

## Overview

N3moSim simulates a realistic maritime environment where autonomous vessels navigate, avoid obstacles, and respond to environmental conditions such as wind and waves. The simulation is designed to stream high-quality sensor data (camera, GPS, IMU) to external systems and to receive real-time control commands from external ROS2 nodes. Objects poses are fully driven by external ROS2 topics, making it straightforward to integrate with any ROS2-compatible controller or mission planner.

---

## ✨ Features

- **High Definition Marine Environment** — HDRP ocean with realistic waves, foam, volumetric fog, physically-based sky, and island terrain
- **Dynamic Object Spawning** — Objects spawned at runtime from a shared JSON config file
- **ROS2 Integration** — All vessels controlled via ROS2 TCP bridge; pose fully defined through external ROS topics
- **Camera Image Streaming** — Unity camera feed streamed out as binary or base64 JPEG via WebSocket
- **Sensor Telemetry** — GPS, IMU and wind data published to ROS2 network
- **Static & Dynamic Objects** — Objects can be static (fixed position) or dynamic (ROS2 controlled)
- **Configurable Scenarios** — Change entire scene setup by editing one JSON file
- **Pre-built Demo Scenarios** — Circle, figure-8 and mixed trajectory scenarios for demonstration
- **Realistic Weather** — Sun, fog, rain and time-of-day control via Volume system
- **Docker ROS2 Stack** — Full ROS2 environment containerized with Docker Compose (optional — ROS2 can also run natively)
- **Multi-Object Control** — Each dynamic object gets a unique ROS2 topic for independent control
- **Shared Config** — Single `scene_config.json` used by both Unity and all ROS2 nodes

---

## Architecture

### Scene Population

```
scene_config.json (shared root config)
      ↓ read by both
Unity SceneLoader.cs          ROS2 n3mo_controller.py
      ↓                              ↓
Spawns objects at runtime     Creates unique publisher
with ROSController attached   per dynamic object
```

### ROS2 Control Flow

```
Your ROS2 Node / Trajectory Publisher / ML Model
    ↓ publish /mission/{object_id}/cmd_vel
mission_planner.py
    ↓ forwards per object
n3mo_controller.py
    ↓ publish /{object_id}/cmd_vel
ROS TCP Bridge (port 10000)
    ↓ TCP connection
Unity ROSController.cs
    ↓ applies force
Object moves in scene
```

### Multi-Object Control

```
n3mo_controller
  ├── /sailboat_01/cmd_vel   → sailboat_01 moves independently
  ├── /catamaran_01/cmd_vel  → catamaran_01 moves independently
  ├── /catamaran_02/cmd_vel  → catamaran_02 moves independently
  └── /buoy_03/cmd_vel       → buoy_03 moves independently
```

### Sensor & Image Streaming

```
Unity Camera
    ↓ JPEG frames (binary or base64)
WebSocket Server (Unity)
    ↓
Remote Operation Center / External Consumer

Unity Object Poses
    ↓
sensor_publisher.py → /sailboat/gps, /sailboat/imu, /environment/wind
```

---

## 🚀 Getting Started

### Prerequisites

- Unity 6.0 or later with HDRP
- Docker Desktop (optional — see note below)
- Mac / Linux (Windows via WSL2)

> **Docker note:** Docker is not strictly required. It packages ROS2 for easy deployment on any machine without a native ROS2 install. If ROS2 Humble is installed natively, all nodes can be run directly without Docker.

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

#### 5. Build Docker ROS2 image

```bash
cd N3moSim
docker compose -f docker-compose-ros2.yml build --no-cache
```

#### 6. Start ROS2 services

```bash
docker compose -f docker-compose-ros2.yml up -d
```

---

## 🎮 Running the Simulation

### Step 1 — Start ROS2 stack

```bash
docker compose -f docker-compose-ros2.yml up -d
```

### Step 2 — Press Play in Unity

Objects spawn from config. Unity connects to ROS TCP Bridge on port 10000.

### Step 3 — Verify connection

```bash
docker compose -f docker-compose-ros2.yml logs ros_bridge
# Should show: New connection from 127.0.0.1
```

### Step 4 — Send commands

```bash
chmod +x send_command.sh

# Move sailboat forward
./scripts/send_command.sh sailboat_01 1.0 0.0

# Turn catamaran right
./scripts/send_command.sh catamaran_01 0.5 1.0

# Move dynamic buoy
./scripts/send_command.sh buoy_03 0.3 0.0

# Stop all objects
./scripts/send_command.sh all stop
```

---

## 🎬 Demo Scenarios (April 2025)

Three pre-built autonomous trajectory scenarios are included for demonstration purposes. Each runs without human input — vessels move automatically driven by the `trajectory_publisher` node.

| Scenario | File                    | Description                                 |
| -------- | ----------------------- | ------------------------------------------- |
| Circles  | `scenario_circles.json` | All vessels circle independently            |
| Figure-8 | `scenario_eight.json`   | All vessels trace figure-8 paths            |
| Mixed    | `scenario_mixed.json`   | Mix of circles and figure-8 — best for demo |

### Running a scenario

Switch scenarios at any time without restarting Unity:

```bash
# Run circle scenario
./scripts/switch_scenario.sh circles

# Run figure-8 scenario
./scripts/switch_scenario.sh eight

# Run mixed scenario (recommended for demo)
./scripts/switch_scenario.sh mixed
```

Or start a specific scenario directly via Docker:

```bash
docker exec n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  source /root/ros2_ws/install/setup.bash &&
  ros2 run n3mo_control trajectory_publisher \
  --ros-args -p scenario_file:=scenario_mixed.json
"
```

### Scenario config format

Scenario files live in `config/` alongside `scene_config.json`:

```json
{
  "scenario": "mixed",
  "description": "Mixed trajectories - best for demo",
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
      "position": [-15, 0, -50],
      "rotation": [0, 160, 0]
    },
    {
      "id": "buoy_01",
      "type": "Buoy",
      "dynamic": false,
      "position": [-30, 0, -40],
      "rotation": [-90, 0, 0]
    },
    {
      "id": "catamaran_01",
      "type": "Catamaran",
      "dynamic": true,
      "ros2_topic": "/catamaran_01/cmd_vel",
      "position": [-5, 0, -60],
      "rotation": [-90, 150, 0]
    }
  ]
}
```

### Config Options

| Field        | Type    | Description                                  |
| ------------ | ------- | -------------------------------------------- |
| `id`         | string  | Unique object identifier                     |
| `type`       | string  | Prefab type: `Sailboat`, `Buoy`, `Catamaran` |
| `dynamic`    | bool    | `true` = ROS2 controlled, `false` = static   |
| `ros2_topic` | string  | Unique ROS2 topic per object                 |
| `position`   | [x,y,z] | Spawn position in world space                |
| `rotation`   | [x,y,z] | Spawn rotation in euler angles               |

---

## 🤖 ROS2 Control

### Send commands via script

```bash
# Usage: ./send_command.sh <object_id> <linear_x> <angular_z>
./scripts/send_command.sh sailboat_01 1.0 0.0    # forward
./scripts/send_command.sh sailboat_01 0.5 1.0    # forward + turn right
./scripts/send_command.sh catamaran_01 0.3 -0.5  # slow + turn left
./scripts/send_command.sh buoy_03 0.0 0.0        # stop
./scripts/send_command.sh all stop               # stop everything
```

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

| Topic                     | Direction         | Description                       |
| ------------------------- | ----------------- | --------------------------------- |
| `/mission/{id}/cmd_vel`   | → n3mo_controller | Send command to object            |
| `/{id}/cmd_vel`           | → Unity           | Forwarded to Unity                |
| `/sailboat/gps`           | Unity → ROS2      | Boat GPS position (NavSatFix)     |
| `/sailboat/imu`           | Unity → ROS2      | Boat orientation (Imu)            |
| `/environment/wind`       | Unity → ROS2      | Wind data (Vector3)               |
| `/unity/object_positions` | Unity → ROS2      | All object poses (PoseArray)      |
| `/obstacles`              | → mission_planner | All detected obstacles            |
| `/obstacles/nearby`       | → mission_planner | Obstacles within detection radius |

---

## 📷 Camera & Sensor Streaming

Unity streams camera frames and telemetry out via WebSocket, enabling integration with a Remote Operation Center (ROC) web application or any external consumer.

### Camera stream

- **Format:** JPEG frames, binary or base64 encoded
- **Transport:** WebSocket (Unity built-in server)
- **Use case:** Live video feed to ROC dashboard, ML training data collection

### Telemetry stream

- Ship position, heading, speed
- Wind speed and direction
- Coming: multiple vessel telemetry in a single message

To consume the camera stream from an external client:

```javascript
const ws = new WebSocket("ws://localhost:<port>");
ws.onmessage = (event) => {
  // event.data is a base64 JPEG frame
  img.src = "data:image/jpeg;base64," + event.data;
};
```

---

## 🐳 Docker Services

| Service                | Container       | Description                                            |
| ---------------------- | --------------- | ------------------------------------------------------ |
| `ros_bridge`           | n3mo_bridge     | ROS TCP Bridge — connects Unity to ROS2                |
| `n3mo_controller`      | n3mo_controller | Master controller for all dynamic objects              |
| `mission_planner`      | n3mo_mission    | High level mission brain with per-object state machine |
| `sensor_publisher`     | n3mo_sensors    | Publishes sensor data from Unity to ROS2               |
| `obstacle_detector`    | n3mo_obstacles  | Detects and tracks obstacles within radius             |
| `trajectory_publisher` | n3mo_trajectory | Autonomous demo trajectory scenarios                   |

### Useful Docker commands

```bash
# View all service logs
docker compose -f docker-compose-ros2.yml logs -f

# View specific service
docker compose -f docker-compose-ros2.yml logs -f n3mo_controller

# Check service status
docker compose -f docker-compose-ros2.yml ps

# Stop all services
docker compose -f docker-compose-ros2.yml down

# List active ROS2 topics
docker exec n3mo_bridge bash -c \
  "source /opt/ros/humble/setup.bash && ros2 topic list"

# Rebuild after code changes
docker compose -f docker-compose-ros2.yml build --no-cache
```

---

## 🧩 Unity Scripts

### SceneLoader.cs

Reads `scene_config.json` at startup and spawns all objects. Searches `/config/` at project root first, then falls back to `Assets/Config/`. Automatically attaches `ROSController` to dynamic objects.

### ROSController.cs

Attached automatically to dynamic objects by SceneLoader. Subscribes to the object's unique ROS2 topic. Applies physics forces based on incoming `geometry_msgs/Twist` messages.

### ShipBuoyancy.cs

Buoyancy physics. Detects when an object is below water level and applies upward force scaled by depth. Works with Unity gravity for realistic floating behaviour.

---

## 🐍 ROS2 Nodes

### config_loader.py

Shared utility used by all nodes. Searches for `scene_config.json` in multiple locations — Docker mounted path first, then ROS2 package share directory, then relative fallback.

### n3mo_controller.py

Master controller. Reads config and creates one publisher per dynamic object on unique topic `/{object_id}/cmd_vel`. Subscribes to `/mission/{object_id}/cmd_vel` from mission planner and forwards to Unity.

### mission_planner.py

High level mission brain. Manages per-object state machines (idle, forward, patrol, turn_left, turn_right, stop). Publishes to `/mission/{object_id}/cmd_vel`.

### trajectory_publisher.py

Demo scenario runner. Reads a scenario JSON file and publishes smooth trajectory commands (circle or figure-8) for each vessel. Accepts a `scenario_file` ROS2 parameter for runtime scenario switching.

### sensor_publisher.py

Receives Unity simulation data and publishes as standard ROS2 sensor messages — GPS (`NavSatFix`), IMU (`Imu`), wind (`Vector3`). GPS origin set to Brest, France (48.3833°N, 4.4833°W).

### obstacle_detector.py

Receives all object positions from Unity. Filters obstacles within configurable detection radius (default 50m). Publishes to `/obstacles` and `/obstacles/nearby`.

---

## 🗺️ Roadmap

- [x] Base marine environment (HDRP ocean, sky, island terrain, volumetric fog)
- [x] Sailboat prefab (PBR model + physics)
- [x] Buoy prefab (navigation buoy + physics)
- [x] Catamaran prefab (racing catamaran + physics)
- [x] JSON config-based dynamic scene loading
- [ ] Buoyancy physics system
- [x] ROS TCP Connector integration
- [x] Docker Compose ROS2 stack
- [x] Multi-object independent ROS2 control
- [x] Shared scene_config.json (Unity + ROS2)
- [x] n3mo_control ROS2 package
- [x] Mission planner with per-object state machine
- [x] send_command.sh helper script
- [ ] Camera image streaming (binary + base64 JPEG via WebSocket)
- [ ] AUV telemetry streaming (GPS, heading, speed)
- [x] Trajectory publisher — circle and figure-8 demo scenarios
- [x] switch_scenario.sh for live scenario switching
- [ ] Unity → ROS2 full GPS/IMU pipeline (live from scene)
- [ ] LiDAR sensor simulation
- [ ] Realistic weather randomization (storm, fog, rain, night)
- [ ] Multiple vessel telemetry in single ROS2 message
- [ ] ROC web-app integration (reception of control signals)
- [ ] Seagull and swimmer prefabs

---
