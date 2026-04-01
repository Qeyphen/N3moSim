# N3moSim — Marine Autonomous Sailboat Simulation

![Unity](https://img.shields.io/badge/Unity-6.0-black?logo=unity)
![HDRP](https://img.shields.io/badge/Render-HDRP-blue)
![ROS2](https://img.shields.io/badge/ROS2-Humble-green)

N3moSim is a high-definition marine simulation environment built in Unity HDRP for training and testing autonomous sailboat ML models. It provides a realistic ocean environment with dynamic and static objects that can be controlled via ROS2 commands.

---

## 🌊 Overview

N3moSim simulates a realistic marine environment where an autonomous sailboat can navigate, avoid obstacles, and respond to environmental conditions such as wind and waves. The simulation is designed to generate high-quality training data for machine learning models and to receive real-time control commands from external ROS2 nodes.

---

## ✨ Features

- **High Definition Marine Environment** — HDRP ocean with realistic waves, sky, clouds and island terrain
- **Dynamic Object Spawning** — Objects spawned at runtime from a JSON config file
- **ROS2 Integration** — Sailboat and dynamic objects controlled via ROS2 TCP bridge
- **Static & Dynamic Objects** — Objects can be static (fixed position) or dynamic (ROS2 controlled)
- **Buoyancy System** — All objects float realistically on water surface
- **Configurable Scenarios** — Change entire scene setup by editing one JSON file

---

## 🗂️ Project Structure

---

## 🏗️ Architecture

### Scene Population:
```
scene_config.json
      ↓ read by
SceneLoader.cs (on SceneManager GameObject)
      ↓ spawns objects at runtime
Sailboat, Buoy(s), Catamaran appear in scene
      ↓ dynamic objects get
ROSController.cs attached automatically
      ↓ waits for
ROS2 commands → moves objects
```

---

## 🚀 Getting Started

### Prerequisites
- Unity 6.0 or later
- HDRP (High Definition Render Pipeline)
- ROS2 Humble (or later) — for ROS2 integration
- Python 3.8+ — for ROS2 nodes

### Installation

#### 1. Clone the repository
```bash
git clone https://github.com/Qeyphen/N3moSim.git
cd N3moSim
```

#### 2. Open in Unity
1. Open **Unity Hub**
2. Click **"Add project from disk"**
3. Select the **N3moSim** folder
4. Open with **Unity 6.0+**

#### 3. Install ROS TCP Connector (Unity)
1. In Unity → **Window → Package Manager**
2. Click **"+"** → **"Add package from git URL"**
3. Paste:
```
https://github.com/Unity-Technologies/ROS-TCP-Connector.git?path=/com.unity.robotics.ros-tcp-connector
```

#### 4. Configure ROS Settings (Unity)
1. **Robotics → ROS Settings**
2. Set **Protocol → ROS2**
3. Set **ROS IP Address** → your ROS2 machine IP
4. Set **Port → 10000**

#### 5. Install ROS TCP Endpoint (ROS2 machine)
```bash
cd ~/ros2_ws/src
git clone https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git
cd ~/ros2_ws
colcon build
source install/setup.bash
```

#### 6. Launch ROS TCP Bridge
```bash
ros2 run ros_tcp_endpoint default_server_endpoint \
  --ros-args -p ROS_IP:=0.0.0.0 -p ROS_TCP_PORT:=10000
```

---

## ⚙️ Configuration

All scene objects are configured via **Assets/Config/scene_config.json**:

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
      "ros2_topic": "/sailboat/cmd_vel",
      "position": [0, 0, 10],
      "rotation": [0, 180, 0]
    },
    {
      "id": "buoy_01",
      "type": "Buoy",
      "dynamic": false,
      "position": [20, 0, 30],
      "rotation": [90, 0, 0]
    },
    {
      "id": "catamaran_01",
      "type": "Catamaran",
      "dynamic": true,
      "ros2_topic": "/catamaran/cmd_vel",
      "position": [10, 0, 25],
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
| `ros2_topic` | string | ROS2 topic to subscribe to (dynamic only) |
| `position` | [x,y,z] | Spawn position in world space |
| `rotation` | [x,y,z] | Spawn rotation in euler angles |

### Environment Options:

| Field | Values | Description |
|---|---|---|
| `time_of_day` | `day`, `sunset`, `night`, `dawn` | Scene lighting |
| `wind_speed` | float | Wind zone strength |
| `wave_height` | float | Ocean wave amplitude |

---

## 🤖 ROS2 Control

### Controlling the Sailboat
Publish a `geometry_msgs/Twist` message to move the sailboat:

```bash
# Move forward
ros2 topic pub /sailboat/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 1.0, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.0}}"

# Turn right
ros2 topic pub /sailboat/cmd_vel geometry_msgs/msg/Twist \
  "{linear: {x: 0.5, y: 0.0, z: 0.0}, angular: {x: 0.0, y: 0.0, z: 0.5}}"
```

### Twist Message Fields:

| Field | Effect |
|---|---|
| `linear.x` | Forward/backward speed (-1.0 to 1.0) |
| `angular.z` | Turn left/right (-1.0 to 1.0) |

### Available ROS2 Topics:

| Topic | Object | Message Type |
|---|---|---|
| `/sailboat/cmd_vel` | Sailboat | `geometry_msgs/Twist` |
| `/catamaran/cmd_vel` | Catamaran | `geometry_msgs/Twist` |
| `/buoy_03/cmd_vel` | Dynamic Buoy | `geometry_msgs/Twist` |

---

## 🎮 Prefabs

### Sailboat
- **Model:** Low-poly PBR sailboat (FBX, 4K textures)
- **Physics:** Rigidbody + Buoyancy
- **Control:** ROSController via `/sailboat/cmd_vel`
- **Settings:** Mass: 50, Buoyancy Force: 100

### Buoy
- **Model:** Realistic navigation buoy (FBX)
- **Physics:** Rigidbody + Buoyancy
- **Control:** Static or dynamic via config
- **Settings:** Mass: 50, Buoyancy Force: 10

### Catamaran
- **Model:** Low-poly racing catamaran (FBX)
- **Physics:** Rigidbody + Buoyancy
- **Control:** ROSController via `/catamaran/cmd_vel`
- **Settings:** Mass: 400, Buoyancy Force: 15

---

## 📜 Scripts

### SceneLoader.cs
Reads `scene_config.json` at startup and spawns all objects into the scene. Automatically attaches `ROSController` to dynamic objects.

### ROSController.cs
Attached to dynamic objects. Subscribes to ROS2 topics and applies forces to move objects based on incoming `Twist` messages.

### Buoyancy.cs
Simple buoyancy simulation. Detects when object is below water level and applies upward force to keep it floating.

---

## 🗺️ Roadmap

- [x] Base marine environment (HDRP ocean, sky, island)
- [x] Sailboat prefab
- [x] Buoy prefab
- [x] Catamaran prefab
- [x] JSON config-based scene loading
- [x] Buoyancy physics system
- [ ] ROS TCP Connector integration
- [ ] GPS sensor publisher (Unity → ROS2)
- [ ] Camera/image sensor publisher
- [ ] Lidar sensor
- [ ] Wind simulation system
- [ ] Weather randomization
- [ ] Multiple scenario configs
- [ ] Seagull and swimmer prefabs
---