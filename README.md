# N3moSim — Marine Autonomous Sailboat Simulation

![Unity](https://img.shields.io/badge/Unity-6.0-black?logo=unity)
![HDRP](https://img.shields.io/badge/Render-HDRP-blue)
![ROS2](https://img.shields.io/badge/ROS2-Humble-green)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker)
![License](https://img.shields.io/badge/License-MIT-yellow)

N3moSim is a marine simulation environment built in Unity HDRP for training and testing autonomous sailboat. It provides a realistic ocean environment with dynamic and static objects that can be controlled via ROS2 commands through a Docker-based ROS2 stack.

---

## Overview

N3moSim simulates a realistic marine environment where an autonomous sailboat can navigate, avoid obstacles, and respond to environmental conditions such as wind and waves. The simulation is designed to generate high-quality training data for machine learning models and to receive real-time control commands from external ROS2 nodes.

---

## Features

- **High Definition Marine Environment** — HDRP ocean with realistic waves, sky, clouds and island terrain
- **Dynamic Object Spawning** — Objects spawned at runtime from a shared JSON config file
- **ROS2 Integration** — Sailboat and dynamic objects controlled via ROS2 TCP bridge
- **Static & Dynamic Objects** — Objects can be static (fixed position) or dynamic (ROS2 controlled)
- **Buoyancy System** — All objects float realistically on water surface
- **Configurable Scenarios** — Change entire scene setup by editing one JSON file
- **Docker ROS2 Stack** — Full ROS2 environment containerized with Docker Compose
- **Multi-Object Control** — Each dynamic object gets unique ROS2 topic for independent control
- **Shared Config** — Single scene_config.json used by both Unity and ROS2

---

## Project Structure

```
N3moSim/
├── config/
│   └── scene_config.json          ← Shared config (Unity + ROS2)
├── Dockerfile                     ← ROS2 Humble + ROS TCP Endpoint image
├── docker-compose-ros2.yml        ← All ROS2 services
├── Makefile                       ← Easy commands
├── send_command.sh                ← Send ROS2 commands to objects
├── ros2_ws/                       ← ROS2 workspace
│   └── src/
│       └── n3mo_control/          ← ROS2 Python package
│           ├── n3mo_control/
│           │   ├── config_loader.py      ← Shared config utility
│           │   ├── n3mo_controller.py    ← Master controller
│           │   ├── mission_planner.py    ← Mission brain
│           │   ├── sensor_publisher.py   ← Sensor data publisher
│           │   └── obstacle_detector.py  ← Obstacle detection
│           ├── config/
│           │   └── scene_config.json
│           ├── package.xml
│           └── setup.py
└── Assets/                        ← Unity project assets
    ├── Prefabs/
    │   ├── Sailboat.prefab
    │   ├── Buoy.prefab
    │   └── Catamaran.prefab
    ├── Scripts/
    │   ├── SceneLoader.cs
    │   ├── ROSController.cs
    │   └── Buoyancy.cs
    └── Scenes/
        └── BaseScene.unity
```

---

## Architecture

### Scene Population:
```
scene_config.json (shared root config)
      ↓ read by both
Unity SceneLoader.cs          ROS2 n3mo_controller.py
      ↓                              ↓
Spawns objects at runtime     Creates unique publisher
with ROSController attached   per dynamic object
```

### ROS2 Control Flow:
```
Your ROS2 Node / ML Model
    ↓ publish /mission/{object_id}/cmd_vel
mission_planner.py
    ↓ forwards per object
n3mo_controller.py
    ↓ publish /{object_id}/cmd_vel
ROS TCP Bridge (port 10000)
    ↓ TCP connection
Unity ROSController.cs
    ↓ applies force
Object moves in scene!
```

### Multi-Object Control:
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
- Mac/Linux (Windows via WSL2)

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

| Setting | Value |
|---|---|
| Protocol | ROS2 |
| ROS IP Address | `127.0.0.1` |
| Port | `10000` |
| Connect on Startup | ✅ Enabled |

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

### Step 1 — Start ROS2 stack:
```bash
docker compose -f docker-compose-ros2.yml up -d
```

### Step 2 — Press Play in Unity
Objects spawn from config. Unity connects to ROS TCP Bridge on port 10000.

### Step 3 — Verify connection:
```bash
docker compose -f docker-compose-ros2.yml logs ros_bridge
# Should show: New connection from 127.0.0.1
```

### Step 4 — Send commands:
```bash
chmod +x send_command.sh

# Move sailboat forward
./send_command.sh sailboat_01 1.0 0.0

# Turn catamaran right
./send_command.sh catamaran_01 0.5 1.0

# Move dynamic buoy
./send_command.sh buoy_03 0.3 0.0

# Stop all objects
./send_command.sh all stop
```

---

## ⚙️ Configuration

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
      "position": [0, 0, 10],
      "rotation": [0, 180, 0]
    },
    {
      "id": "buoy_01",
      "type": "Buoy",
      "dynamic": false,
      "position": [-15, 0, 30],
      "rotation": [90, 0, 0]
    },
    {
      "id": "buoy_03",
      "type": "Buoy",
      "dynamic": true,
      "ros2_topic": "/buoy_03/cmd_vel",
      "position": [25, 0, 35],
      "rotation": [90, 0, 0]
    },
    {
      "id": "catamaran_01",
      "type": "Catamaran",
      "dynamic": true,
      "ros2_topic": "/catamaran_01/cmd_vel",
      "position": [10, 0, 25],
      "rotation": [-90, 180, 0]
    },
    {
      "id": "catamaran_02",
      "type": "Catamaran",
      "dynamic": true,
      "ros2_topic": "/catamaran_02/cmd_vel",
      "position": [-10, 0, 35],
      "rotation": [-90, 180, 0]
    }
  ]
}
```

### Config Options:

| Field | Type | Description |
|---|---|---|
| `id` | string | Unique object identifier |
| `type` | string | Prefab type: `Sailboat`, `Buoy`, `Catamaran` |
| `dynamic` | bool | `true` = ROS2 controlled, `false` = static |
| `ros2_topic` | string | Unique ROS2 topic per object |
| `position` | [x,y,z] | Spawn position in world space |
| `rotation` | [x,y,z] | Spawn rotation in euler angles |

---

## 🤖 ROS2 Control

### Send commands via script:
```bash
# Usage: ./send_command.sh <object_id> <linear_x> <angular_z>
./send_command.sh sailboat_01 1.0 0.0    # forward
./send_command.sh sailboat_01 0.5 1.0    # forward + turn right
./send_command.sh catamaran_01 0.3 -0.5  # slow + turn left
./send_command.sh buoy_03 0.0 0.0        # stop
./send_command.sh all stop               # stop everything
```

### Send commands via terminal:
```bash
docker exec n3mo_bridge bash -c "
  source /opt/ros/humble/setup.bash &&
  ros2 topic pub --once /mission/sailboat_01/cmd_vel \
    geometry_msgs/msg/Twist \
    '{linear: {x: 1.0}, angular: {z: 0.0}}'
"
```

### Makefile shortcuts:
```bash
make sail-forward    # sailboat forward
make sail-right      # sailboat turn right
make cat1-forward    # catamaran_01 forward
make stop-all        # stop all objects
make logs            # view all logs
```

### ROS2 Topics:

| Topic | Direction | Description |
|---|---|---|
| `/mission/{id}/cmd_vel` | → n3mo_controller | Send command to object |
| `/{id}/cmd_vel` | → Unity | Forwarded to Unity |
| `/sailboat/gps` | Unity → ROS2 | Boat GPS position |
| `/sailboat/imu` | Unity → ROS2 | Boat orientation |
| `/environment/wind` | Unity → ROS2 | Wind data |
| `/obstacles` | → mission_planner | Detected obstacles |

---

## 🐳 Docker Services

| Service | Container | Description |
|---|---|---|
| `ros_bridge` | n3mo_bridge | ROS TCP Bridge — connects Unity to ROS2 |
| `n3mo_controller` | n3mo_controller | Master controller for all dynamic objects |
| `mission_planner` | n3mo_mission | High level mission brain |
| `sensor_publisher` | n3mo_sensors | Publishes sensor data from Unity |
| `obstacle_detector` | n3mo_obstacles | Detects obstacles within radius |

### Useful Docker commands:
```bash
# View all service logs
docker compose -f docker-compose-ros2.yml logs -f

# View specific service
docker compose -f docker-compose-ros2.yml logs -f n3mo_controller

# Check service status
docker compose -f docker-compose-ros2.yml ps

# Stop all services
docker compose -f docker-compose-ros2.yml down

# List ROS2 topics
docker exec n3mo_bridge bash -c \
  "source /opt/ros/humble/setup.bash && ros2 topic list"
```

---

## Unity Scripts

### SceneLoader.cs
Reads `scene_config.json` at startup and spawns all objects. Reads from project root `/config/` first, falls back to `Assets/Config/`. Automatically attaches `ROSController` to dynamic objects.

### ROSController.cs
Attached automatically to dynamic objects by SceneLoader. Subscribes to unique ROS2 topic per object. Applies physics forces based on incoming Twist messages.

### Buoyancy.cs
Simple buoyancy physics. Detects when object is below water level and applies upward force. Works with Unity gravity for realistic floating.

---

## ROS2 Nodes

### config_loader.py
Shared utility used by all nodes. Searches for scene_config.json in multiple locations — Docker mounted path first, then package share directory.

### n3mo_controller.py
Master controller. Reads config and creates one publisher per dynamic object on unique topic `/{object_id}/cmd_vel`. Forwards mission planner commands to Unity.

### mission_planner.py
High level brain. Manages per-object mission states (idle, forward, patrol, turn). Publishes to `/mission/{object_id}/cmd_vel`.

### sensor_publisher.py
Receives Unity simulation data and publishes as standard ROS2 sensor messages — GPS (NavSatFix), IMU, wind (Vector3).

### obstacle_detector.py
Receives all object positions from Unity. Filters obstacles within detection radius. Publishes to `/obstacles` and `/obstacles/nearby`.

---

## 🗺️ Roadmap

- [x] Base marine environment (HDRP ocean, sky, island terrain)
- [x] Sailboat prefab (PBR model + physics)
- [x] Buoy prefab (navigation buoy + physics)
- [x] Catamaran prefab (racing catamaran + physics)
- [x] JSON config-based dynamic scene loading
- [x] Buoyancy physics system
- [x] ROS TCP Connector integration
- [x] Docker Compose ROS2 stack
- [x] Multi-object independent ROS2 control
- [x] Shared scene_config.json (Unity + ROS2)
- [x] n3mo_control ROS2 package
- [x] Mission planner with per-object state machine
- [x] send_command.sh helper script
- [ ] Unity → ROS2 GPS sensor publisher
- [ ] Unity → ROS2 camera/image feed
- [ ] Lidar sensor simulation
- [ ] Wind simulation system
- [ ] Weather randomization (storm, fog, night)
- [ ] Multiple scenario config files
- [ ] Seagull and swimmer prefabs
