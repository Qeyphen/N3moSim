# N3moSim — System Architecture

A complete, demo-ready walkthrough of the whole system: what each part does, how data
flows, and **exactly where in the code each behaviour is controlled** (file + symbol).

---

## 1. What this project is

**N3moSim** is a marine simulator built in **Unity 6.3 (HDRP)** and bridged to **ROS 2
Humble**. It exists to do two things:

1. **Simulate a marine scene** — an ego boat on water, with procedurally generated traffic
   (sailboats, kayaks, swimmers, buoys, …) that the boat can perceive and navigate around.
2. **Generate auto-labelled training data** — using the **Unity Perception** package, every
   frame can be captured with ground-truth labels (2D/3D boxes, instance & semantic
   segmentation, depth) in the **SOLO** dataset format, for training ML obstacle
   detection/segmentation models.

Unity does the **rendering and physics**; ROS 2 does the **autonomy, traffic generation, and
tooling**. They talk over TCP.

```
                 target poses, traffic, maps
   ┌────────────┐   (ROS messages over TCP)   ┌──────────────────────┐   DDS    ┌─────────────┐
   │   UNITY    │ ◄──────────────────────────► │  ros_tcp_endpoint    │ ◄──────► │  ROS 2      │
   │  (HDRP)    │      port 10000 (TCP)        │  (Docker container)  │          │  nodes,RViz,│
   │  the world │ ──────────────────────────►  │  the real ROS node   │          │  CLI, tools │
   └────────────┘   ego pose, scene, /map       └──────────────────────┘          └─────────────┘
```

Key idea: **Unity never speaks ROS natively.** It opens a TCP socket to a Dockerised
`ros_tcp_endpoint`, which is the actual ROS 2 node that owns every publisher/subscriber and
forwards traffic onto the DDS network.

---

## 2. The two halves

| | Unity side | ROS 2 side (Docker) |
|---|---|---|
| **Runs** | The 3D world, physics, cameras, Perception capture | Autonomy, traffic generation, RViz, CLI tools |
| **Language** | C# (`Assets/Scripts`, `Assets/Editor`) | Python (`ros2_ws/src`) |
| **Connects via** | `ROSConnection` (ROS-TCP-Connector) → `127.0.0.1:10000` | `default_server_endpoint` bound to `0.0.0.0:10000` |
| **Owns** | Ego boat, traffic prefabs, water, dataset | Scenario generator, target-pose publisher, message defs |

---

## 3. End-to-end data flow (the topics)

Everything crossing the Unity↔ROS boundary is a ROS topic tunnelled through the endpoint.

| Topic | Type | Direction | Rate / QoS | Produced by | Consumed by |
|---|---|---|---|---|---|
| `/ego_boat/target_pose` | `geometry_msgs/PoseStamped` | ROS → Unity | republished, RELIABLE+TRANSIENT_LOCAL | `target_pose_publisher` | `AutonomousBoatController` |
| `/sim/boat/pose` | `geometry_msgs/PoseStamped` | Unity → ROS | 10 Hz | `EgoPosePublisher` | RViz, scenario tooling |
| `/map` | `nav_msgs/OccupancyGrid` | Unity → ROS | once, **latched** | `OccupancyGridPublisher` | scenario generator (as costmap), RViz |
| `/sim/tracks` | `n3_new_msgs/TrackArray` | ROS → Unity | 10 Hz, RELIABLE | `scenario_generator` | `TrackSpawner` |
| `/sim/tracks/markers` | `visualization_msgs/MarkerArray` | ROS → RViz | on each track msg | `tracks_markers_node` | RViz |
| `/scene/objects` | `n3_new_msgs/TrackArray` | Unity → ROS | 10 Hz | `DynamicObstaclePublisher` | scenario generator exclusions, external consumers, debug |
| `/dataset/control` | `std_msgs/Bool` | ROS → Unity | on demand | CLI / you | `DatasetCaptureScheduler` |
| `/dataset/capture_hz` | `std_msgs/Float32` | ROS → Unity | on demand | scenario batch tooling / CLI | `DatasetCaptureScheduler` |
| `/env/time_of_day`, `/env/fog`, `/env/wind`, `/env/wave`, `/env/cloudiness`, `/env/rain` | `std_msgs/Float32` | ROS → Unity | on demand | `env_control` / CLI | `EnvironmentController` |
| `/env/weather` (String), `/env/randomize` (Int32) | `std_msgs/*` | ROS → Unity | on demand | `env_control` / CLI | `EnvironmentController` |
| `/env/state` | `std_msgs/String` | Unity → ROS | on change | `EnvironmentController` | logging / capture |

See **`doc/environment.md`** for the full procedural-environment (weather + time-of-day) design.
| `/map/costmap_static` | `nav_msgs/OccupancyGrid` | (internal) | latched | = `/map` **remapped** | scenario generator |

**The closed loop:** Unity rasterises its static obstacles into `/map` → the scenario
generator reads `/map` as a costmap, generates traffic that avoids land, and publishes
`/sim/tracks` → Unity's `TrackSpawner` renders that traffic → meanwhile you send
`/ego_boat/target_pose` and the ego boat drives there, perceiving the traffic.

---

## 4. Coordinate conventions (important — often the first question)

There are **two** Unity↔ROS mappings in this codebase. Mixing them up is the usual cause of
"it moves sideways / wrong place" bugs.

### A. Control channel — Unity-native `x` / `z`
`target_pose` is expressed directly in **Unity** axes: `position.x` = Unity right,
`position.z` = Unity forward, `y` = 0. No axis swap.
- Sent by `target_pose_publisher.py` (`x`, `z` params).
- Read by `AutonomousBoatController.OnTargetPoseReceived` → `targetPos = (x, 0, z)`.

### B. Map layer — ENU swap `Unity z → ROS y`
Everything map/perception-related uses **ENU**: ROS `x` = East, ROS `y` = North, so
**Unity x → ROS x, Unity z → ROS y, Unity y (up) → 0**.
- `EgoPosePublisher`: `position.x = p.x`, `position.y = p.z`.
- `DynamicObstaclePublisher`, `OccupancyGridPublisher`: same swap.
- `TrackSpawner` does the **inverse**: ROS `(x, y)` → Unity `(x, 0, y)`.
- Heading: ENU yaw about ROS z, `yaw = atan2(forward.z, forward.x)`,
  quaternion `(0, 0, sin(yaw/2), cos(yaw/2))`.

> Memory aid: **control = x/z (no swap); map/perception = Unity z becomes ROS y.**

---

## 5. Unity side — every script and where it's controlled

All paths are under `Assets/Scripts/` unless noted. Components live on GameObjects in the
scene (`Assets/scene1_with_sample_island.unity`).

### 5.1 Scene bootstrap

**`SceneBuilder.cs`** — the entry point that builds the scene from config.
- Reads `config/Scene.json` (`LoadConfig`), spawns each object at its position/rotation
  (`SpawnObjects`).
- Wires the **Cinemachine** follow camera onto the boat.
- For the boat, calls `BoatControlSwitcher.Configure(mode, "/{id}/target_pose")` — **this is
  where Auto mode and the target topic are seeded** (`ActivateController`, ~L173).
- Hands static obstacles to `OccupancyGridPublisher.Publish` (→ `/map`) and all objects to
  `DynamicObstaclePublisher.SetObjects` (→ `/scene/objects`).
- `TypeToTrackType` maps config type strings → `TrackType` bytes (boat→SAILBOAT, buoy→BUOY).
- Defines the shared `ControlMode { Manual, Auto }` enum and the JSON config classes.

### 5.2 Ego boat control

The ego boat has **one** active controller at a time, chosen by a switcher.

**`BoatControlSwitcher.cs`** — owns the two controllers, enables exactly one.
- `Awake` caches `ManualBoatController`, adds `AutonomousBoatController` if missing, starts it
  disabled.
- `Update` re-applies whenever `mode` changes → you can flip Manual/Auto **live in the
  Inspector during Play** (`Apply`: `manual.enabled = !auto; autonomous.enabled = auto`).

**`ManualBoatController.cs`** — keyboard control (the "proven" force model).
- `FixedUpdate`: A/D apply lateral force at the stern `motor` to steer; W/S call
  `ApplyForceToReachVelocity(±maxSpeed)`; `drag` rotates velocity toward heading to kill side
  drift. No ROS.

**`AutonomousBoatController.cs`** — ROS target-following (mirrors the manual force model).
- **Subscribes** `geometry_msgs/PoseStamped` on `/{id}/target_pose` (subscribe in
  `Subscribe`, topic set by `Configure`). Only active in **Auto** mode (the switcher enables
  it; subscription happens in `OnEnable`).
- `FixedUpdate` is the control law:
  - within `arrivalRadius` → brake (`ApplyForceToReachVelocity(zero)`) and return;
  - else compute `headingError` (`SignedAngle`), apply steering force `∝ -headingError`;
  - thrust forward **only** when `|headingError| ≤ headingTolerance`, else keep turning.
- This is **proportional steering** — it relies on water drag (below) to settle.

**`WaterFloater.cs`** — buoyancy + water drag for the ego boat (HDRP `WaterSurface`).
- `Awake`: `useGravity = false` (gravity is supplied per-floater to avoid 2g),
  **freezes roll/pitch** (`FreezeRotationX|Z`) so it can't capsize, and sets
  `linearDamping`/`angularDamping` (water drag).
- `FixedUpdate`: per floater point, adds gravity, projects the point onto the water surface,
  and adds upward lift scaled by submersion depth.
- **Why drag lives here:** the controller is proportional-only, so without `linearDamping`
  the boat overshoots its target and oscillates, and without `angularDamping` the yaw
  overshoots. Both are tunable in the Inspector.

> `BoatController.cs` also exists — a standalone WASD arcade controller. It is **not** part of
> the SceneBuilder/Switcher flow (which uses Manual/Auto + WaterFloater). Treat it as legacy.

### 5.3 Traffic (ROS-driven)

**`TrackSpawner.cs`** — renders the scenario generator's traffic.
- **Subscribes** `n3_new_msgs/TrackArray` on `/sim/tracks` (`Subscribe` in `Start`).
- For each track: spawns a prefab the first time the id appears (random variant via
  `PrefabFor` when several prefabs share a `TrackType`), makes it **kinematic**
  (`MakeKinematic`), writes its **position directly** (ROS `(x,y)` → Unity `(x,0,y)`), and
  despawns it when the id stops appearing.
- **Heading from motion:** points local **+Z** along the actual movement delta
  (`motionHeadingThreshold` guards against spinning when nearly still); the orientation
  quaternion only seeds the first frame.
- The `TrackType` enum (0–15) mirrors the ROS Track type constants. `prefabOverrides` is the
  type→prefab table; **repeat a type to register colour/variant alternatives**.
- Runtime debug counters (`totalMessagesReceived`, `lastMessageTrackCount`, `activeTrackCount`)
  make it obvious whether Unity is receiving traffic even when prefab setup is wrong. If a
  prefab cannot be resolved, the spawner falls back to a primitive placeholder instead of
  silently dropping the track.

**`KinematicBob.cs`** — physics-free bob/sway for traffic.
- Traffic is kinematic, so `WaterFloater` (forces) does nothing on it. This oscillates the
  **model child's local pose** (vertical bob + roll/pitch sway) for a floating look. Lives on
  the child, never the spawner-driven root.

### 5.4 Publishers (Unity → ROS)

**`EgoPosePublisher.cs`** — ego pose on `/sim/boat/pose` at 10 Hz (ENU swap; yaw from
forward). Lets ROS/RViz/tooling know where the boat is.

**`DynamicObstaclePublisher.cs`** — publishes **all SceneBuilder objects** (ego + buoys) as a
`TrackArray` on `/scene/objects` at 10 Hz. Authored-object ids start at **9000** (so they
never collide with generator ids `<1000`). Computes velocity for dynamic objects.

**`OccupancyGridPublisher.cs`** — rasterises static obstacles into a `nav_msgs/OccupancyGrid`,
published **once, latched**, on `/map`. This is the **costmap** the scenario generator reads.
- Default 1000×1000 m grid; `resolution`, `inflationRadius`, and `extraObstacles` (e.g. the
  island) are Inspector fields. (Set `Resolution = 5` to keep generation fast — see README.)
- Mapping: Unity x → column, Unity z → row; origin at `(originX, originZ)`.

### 5.5 Dataset capture

**`DatasetCaptureScheduler.cs`** — on-demand Unity Perception recorder
(`[RequireComponent(PerceptionCamera)]`, sits on the boat's POV camera).
- **Subscribes** `std_msgs/Bool` on `/dataset/control` (true=start, false=stop); also an `R`
  hotkey and an Inspector toggle.
- **Subscribes** `std_msgs/Float32` on `/dataset/capture_hz` to update the capture rate live
  without restarting Unity.
- Uses **manual capture** (`perceptionCamera.RequestCapture()` at `captureHz`, default 10 Hz)
  rather than
  Perception's Scheduled mode, so live physics/water isn't frozen.
- `excludeOwnVessel=true` clears the **ego boat's own `Labeling`** in `Start` so the boat
  doesn't label its own hull.

### 5.6 Editor tools (`Assets/Editor/`) — prefab authoring, not runtime

These add a top-level **`N3mo`** menu in the Unity Editor:
- **`KayakPrefabBuilder.cs`** (`N3mo → Build Kayak Prefabs From Selection`) — turns each
  selected kayak mesh into a traffic prefab: root with `Labeling`(`kayak`,`dynamic_obstacle`)
  + fitted BoxCollider, model child with `KinematicBob`. No Rigidbody (traffic is kinematic).
- **`SwimmerPrefabBuilder.cs`** (`N3mo → Build Swimmer Prefab`) — builds `Swimmer.prefab` from
  `SWIM.fbx`: loops the swim clip, creates an AnimatorController, adds the swimmer `Labeling`,
  `applyRootMotion = false` (position is spawner-driven).
- **`ModelOrientationFixer.cs`** (`N3mo → Fix Model Orientation`) — sets the model child's
  local Euler across selected prefabs so its nose faces **+Z** (TrackSpawner aligns +Z to
  heading). Fixes traffic that travels sideways.

### 5.7 Unity ROS message definitions (`Assets/RosMessages/N3New/msg/`)
Hand-written to mirror the ROS `n3_new_msgs` package so Unity can (de)serialise them:
- **`TrackMsg.cs`** = `n3_new_msgs/Track`: `uint id`, `Pose pose` (ENU), `Twist twist`,
  `byte type` (UNKNOWN=0 … PEDALO=15).
- **`TrackArrayMsg.cs`** = `n3_new_msgs/TrackArray`: `Header header`, `Track[] tracks`.

---

## 6. ROS 2 side — `ros2_ws/src`

Four packages. Three are **volume-mounted** into the container (live-editable); `n3_new_msgs`
is compiled in, so message changes need a rebuild.

### 6.1 `n3mo_control` — the control entry point
- **`target_pose_publisher.py`** — publishes `/ego_boat/target_pose` (Unity convention `x`,
  `z`; `y=0`) then exits. **Republishes** until a subscriber has been present for `hold_time`
  (or warns after `wait_timeout`), because Unity only subscribes while the boat is in **Auto**
  mode and the relayed subscription can appear a moment late. QoS is RELIABLE +
  TRANSIENT_LOCAL.
- **`launch/target_pose.launch.py`** — wraps it so you run
  `ros2 launch n3mo_control target_pose.launch.py x:=-190.0 z:=-110.0`.
- In-container map tools: `tools/view_live.py`, `view_map.py`, `save_map.py`.

### 6.2 `n3_sim` — the scenario/traffic engine
The core is the **scenario generator**, which turns a costmap into moving traffic.

**`scenario_generator/scenario_generator_node.py`** (`ScenarioGeneratorNode`)
- **Subscribes** `/map/costmap_static` (the OccupancyGrid; remapped from Unity's `/map`).
- **Subscribes** `/scene/objects` and converts authored Unity objects into exclusion zones, so
  generated traffic avoids spawning on top of static/authored scene content.
- **Publishes** `/sim/tracks` (`TrackArray`) on a timer at `publish_rate_hz` (10 Hz).
- On the **first costmap** (with `gen_on_first_costmap:=true`) it auto-generates a scenario
  (`on_costmap` → `_generate`).
- Each tick (`on_timer`) it interpolates every active track to the current time and publishes
  the batch. Also exposes services: `/sim/generate_scenario` (Trigger) and
  `/sim/scenario/command` (JSON add/remove/list/clear tracks, for runtime injection).

**`scenario_generator/scenario_model.py`** — pure-Python algorithm (no ROS), the heart:
1. **`extract_navigable_area`** — turns the OccupancyGrid into a boolean "water" mask (free
   cells = value 0), then **erodes by a margin** so traffic keeps clear of land.
2. **`generate_scenario`** — seeded RNG; for each of `track_count` tracks: pick a type from an
   **area preset** (lake/coastal/harbor/open_sea) weighted distribution, pick a speed from the
   type's range, then do a **random walk** of waypoints across navigable water (with boundary
   reflection so it stays on water), while rejecting candidate points inside authored-object
   exclusion zones or too close to other generated tracks. Writes a YAML scenario.
3. **`interpolate_track`** — given a track and a time, finds the current segment and linearly
   interpolates position; **heading = `atan2(dy, dx)`** (the path tangent = direction of
   travel), and velocity from speed × unit tangent. Returns a `TrackState`.
- `_track_state_to_ros` (in the node) converts a `TrackState` → `Track` message: position
  `(x, y, 0)`, orientation = yaw quaternion, twist = `(vx, vy, 0)`, `type`.
- **`TRACK_TYPE_TABLE`** defines all 16 types with `(enum, min_kts, max_kts, heading_sigma)`.

**`scenario_generator/tracks_markers_node.py`** — converts `/sim/tracks` →
`/sim/tracks/markers` (`MarkerArray`) for RViz. Each track becomes a **class-specific shape**
(CUBE/SPHERE/CYLINDER) at realistic size, a **unique per-class colour**, and a floating **text
label** (`kayak #4`). One `_SPEC` table drives shape/size/colour/name for all 16 types; stale
tracks delete both the body and label markers.

Other nodes in the package (`map_manager_node`, `scenario_bridge_node`, converters, sims)
exist but are **not** used by the default Docker run — the live setup feeds Unity's `/map`
straight into the generator.

### 6.3 `n3_common` — shared library
- **`topics/sim_topics.py`** — central topic registry (`TopicSpec(name, qos)`):
  `SIM_TRACKS = /sim/tracks` (RELIABLE), `COSTMAP_STATIC = /map/costmap_static` (LATCHED),
  `SIM_POSE = /sim/boat/pose`, `SIM_TRACKS_MARKERS = /sim/tracks/markers`, etc.
- **`topics/topics_model.py`** — the QoS profiles (`RELIABLE_QOS`, `BEST_EFFORT_QOS`,
  `LATCHED_QOS`).
- **`ros.py`** — aliases ROS message classes so nodes write `ros.Track`, `ros.Marker`, etc.
- **`params/`** — pydantic-based parameter base (backported to Python 3.10).

### 6.4 `n3_new_msgs` — custom messages
`Track.msg` (`id`, `pose`, `twist`, `type`) and `TrackArray.msg` (`header`, `tracks[]`), plus
detection/service types. **Compiled into the image** (not mounted) → message changes require
`docker compose build`.

---

## 7. The bridge — ROS-TCP

- **Unity side:** `Assets/Resources/ROSConnectionPrefab.prefab` holds a `ROSConnection`
  component set to `127.0.0.1:10000`, connect-on-start. Scripts get it via
  `ROSConnection.GetOrCreateInstance()`.
- **ROS side:** the `ros_bridge` container runs
  `ros2 run ros_tcp_endpoint default_server_endpoint -p ROS_IP:=0.0.0.0 -p ROS_TCP_PORT:=10000`,
  published to the host as `10000:10000`. This endpoint is the **real ROS node** that owns
  every pub/sub; Unity messages tunnel through it onto CycloneDDS.
- **Latch patch:** the Dockerfile patches the endpoint's `publisher.py` so `latch=True`
  creates a **TRANSIENT_LOCAL** publisher — this is what makes Unity's latched `/map` reach
  late subscribers (like the scenario generator and RViz).

---

## 8. Deployment — Docker

**`Dockerfile`** (base `ros:humble`): installs CycloneDDS + msg deps + pydantic/pyyaml,
clones the **ROS-TCP-Endpoint**, copies & `colcon build`s the four packages, applies the
endpoint latch/None-guard patches.

**`docker-compose.yml`** — three services on the `ros_net` bridge network:
| Service | Profile | Purpose |
|---|---|---|
| `ros_bridge` | (default) | The ROS-TCP endpoint on port **10000** — always needed. Mounts the 3 live packages + `config/`. |
| `scenario` | `rviz` | Runs `tracks_markers` + `scenario_generator` (with `/map/costmap_static:=/map`, `gen_on_first_costmap:=true`, `gen_track_count:=10`). |
| `rviz` | `rviz` | `osrf/ros:humble-desktop-full` running `rviz2 -d /config/n3mo.rviz` + a `map→base_link` static TF. |

**Run modes:**
- `docker compose up -d` → just the bridge (Unity ↔ ROS works; you drive via CLI).
- `docker compose --profile rviz up` → bridge + scenario generator + RViz (the full
  integrated view).
- After editing **Python nodes** that are mounted: just restart. After editing
  **messages / Dockerfile**: `docker compose build`.

---

## 9. The dataset / Perception pipeline

**In Unity:** a `PerceptionCamera` on the boat's POV camera, with labelers (BoundingBox2D/3D,
Instance & Semantic Segmentation, Depth) and two label configs in `Assets/Perception/`
(`IdLabelConfig` for detection ids, `SemanticSegmentationLabelConfig` for class→colour).
Capture Trigger = **Manual**; `DatasetCaptureScheduler` requests captures while recording, at a
rate that can be changed live over `/dataset/capture_hz`. Output is a **SOLO** dataset under
`~/.config/unity3d/<Company>/<Product>/solo*/` (Linux) or
`~/Library/Application Support/...` (macOS), finalised when Play stops.

**On the host** (`tools/`, all read-only, auto-find the latest SOLO dataset):
| Tool | Reads | Produces |
|---|---|---|
| `solo_preview.py` | RGB + 2D boxes | boxes drawn on RGB (`preview/`) |
| `depth_preview.py` | depth EXR | metres stats + colourised depth, coverage % |
| `camera_info.py` | capture pose + `matrix` | extrinsics + NDC & pixel intrinsics + FOV |
| `range_bearing.py` | 3D boxes | per-frame `metadata/*_objects.json` (range/bearing/closing) |
| `semantic_preview.py` | semantic mask | per-class coverage % |
| `marine_surface.py` | pose + intrinsics + seg | **water/sky labels** via horizon synthesis: colored preview + class-index mask (0=water,1=sky,2=obstacle) in `marine_seg/` |
| `filter_boxes.py` | 2D boxes | drops tiny boxes from the dataset (`--apply`) |
| `solo_to_yolo.py` | 2D boxes + RGB | **YOLO detection dataset** (`images/`+`labels/`+`data.yaml`, simple frame split) |

**Known limit:** HDRP water is a transparent surface that **doesn't render into Perception's
depth or segmentation passes** — so water has no depth/class from the engine. `marine_surface.py`
fills that geometrically (the Phase-3 horizon-synthesis approach).

**Recommended recording mode:** many short scenarios, not one long sweep. The host-side tools
`tools/generate_scenarios.py` and `tools/run_scenario_batch.py` generate a manifest of short
scenario specs, then execute them by fixing weather/time, setting the generator seed, updating
`/dataset/capture_hz`, and invoking `dataset_sweep` in duration-based mode with no mid-run
environment changes.

**Camera FOV:** the POV camera is configured to **60° vertical / ~92° horizontal** at 1280×720,
which fixes the intrinsics (fx=fy≈623.5 px, principal point centred) baked into every frame. See
**`doc/camera-fov.md`** for the definition, configuration, and verified `camera_info.py` output.

**Camera pose (URDF):** the camera's mount on the boat is defined in **`config/usv.urdf`**
(`base_link → camera_link` joint), not hardcoded in Unity. `UrdfCameraPose.cs` reads it at
startup (file or `/robot_description`), converts ROS→Unity, and sets the camera's local
transform. See **`doc/camera-urdf.md`** for the design and verified extrinsics.

---

## 10. Config files

- **`config/Scene.json`** — the scene definition (mounted into the container): an
  `environment` block (wind, wave height, time of day) and `objects` (e.g. `ego_boat` Boat at
  `[0,1,-300]`, `control_mode: manual`, plus static buoys). Read by `SceneBuilder`.
- **`config/n3mo.rviz`** — RViz layout: Fixed Frame `map`; displays Grid, **Map** (`/map`,
  Transient Local), **Tracks** (`/sim/tracks/markers`), **Ego** (`/sim/boat/pose`, green
  arrow); top-down orthographic view.
- **`Assets/Perception/*.asset`** — the label configs (ids + class colours).

---

## 11. The closed loop, narrated (use this for the demo)

1. **Press Play in Unity.** `SceneBuilder` reads `Scene.json`, spawns the boat + buoys, points
   the camera at the boat, and starts the publishers.
2. **`OccupancyGridPublisher`** rasterises the island/buoys and publishes a latched **`/map`**.
3. **`EgoPosePublisher`** starts streaming the boat's pose on **`/sim/boat/pose`**.
4. In Docker, **`scenario_generator`** receives `/map`, extracts navigable water, and
   generates ~10 tracks; it streams **`/sim/tracks`** at 10 Hz, and `tracks_markers_node`
   mirrors them to RViz as shaped, coloured, labelled markers.
5. Back in Unity, **`TrackSpawner`** spawns a prefab per track, drives each along its path
   (facing its direction of travel), and bobs them via `KinematicBob`.
6. You run **`ros2 launch n3mo_control target_pose.launch.py x:= z:=`**. With the boat in
   **Auto**, `AutonomousBoatController` receives the goal and steers/thrusts to it, kept stable
   and afloat by `WaterFloater`.
7. You flip on capture (`/dataset/control` or `R`); **`DatasetCaptureScheduler`** records SOLO
   frames with full ground truth, which the `tools/` scripts then verify/convert.

---

## 12. Roadmap (historical phases) — for context

- **Phase 0** — Spike: proved Unity Perception works on HDRP/Unity 6.3.
- **Phase 1** (`doc/phase-1.md`) — Vertical slice: end-to-end capture on the boat POV.
- **Phase 2** (`doc/phase-2.md`) — Enrich labels: ego exclusion, metric depth, camera
  intrinsics/extrinsics, range/bearing/closing, semantic classes; found the HDRP-water gap.
- The active remediation plan for the current dataset-generation work is tracked in the project
  root [`todo.md`](../todo.md), not in this historical phase list.

---

## 13. File map (quick index)

```
Assets/Scripts/
  SceneBuilder.cs            scene bootstrap from Scene.json; wires everything
  BoatControlSwitcher.cs     Manual/Auto selector for the ego boat
  ManualBoatController.cs    WASD control (force model)
  AutonomousBoatController.cs ROS target-following control (subscribes target_pose)
  WaterFloater.cs            ego buoyancy + water drag
  TrackSpawner.cs            renders /sim/tracks traffic (subscribes TrackArray)
  KinematicBob.cs            physics-free bob for kinematic traffic
  EgoPosePublisher.cs        /sim/boat/pose
  DynamicObstaclePublisher.cs /scene/objects (authored ego+buoys)
  OccupancyGridPublisher.cs  /map (latched costmap)
  DatasetCaptureScheduler.cs Perception capture, /dataset/control, /dataset/capture_hz
  UrdfCameraPose.cs          mounts the POV camera from config/usv.urdf (not hardcoded)
  EnvironmentController.cs   procedural weather + time-of-day, ROS-controllable
  BoatController.cs          (legacy standalone arcade controller)
Assets/Editor/
  KayakPrefabBuilder.cs / SwimmerPrefabBuilder.cs / ModelOrientationFixer.cs
Assets/RosMessages/N3New/msg/  TrackMsg.cs, TrackArrayMsg.cs
Assets/Perception/             IdLabelConfig, SemanticSegmentationLabelConfig
Assets/Resources/ROSConnectionPrefab.prefab  (Unity→ROS 127.0.0.1:10000)

ros2_ws/src/
  n3mo_control/   target_pose_publisher.py, launch/target_pose.launch.py, tools/
  n3_sim/         scenario_generator/{scenario_generator_node, scenario_model,
                  tracks_markers_node, ...}
  n3_common/      topics/{sim_topics, topics_model}, ros.py, params/
  n3_new_msgs/    Track.msg, TrackArray.msg (compiled into the image)

tools/            solo_preview, depth_preview, camera_info, range_bearing,
                  semantic_preview, marine_surface, generate_scenarios,
                  run_scenario_batch
config/           Scene.json, n3mo.rviz
Dockerfile, docker-compose.yml
doc/              phase-1.md, phase-2.md, todo.md, architecture.md (this file)
```

---

## 14. Demo cheat-sheet (commands)

```bash
# Bridge only (Unity <-> ROS)
docker compose up -d
docker compose logs -f ros_bridge          # watch the endpoint

# Full integrated view (bridge + scenario generator + RViz)
docker compose --profile rviz up

# Drive the boat (boat must be in AUTO in Unity)
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && \
  ros2 launch n3mo_control target_pose.launch.py x:=-190.0 z:=-110.0"

# Inspect topics
ros2 topic list
ros2 topic echo /sim/tracks --once
ros2 topic hz /sim/boat/pose

# Verify a captured dataset (host)
python3 tools/solo_preview.py
python3 tools/range_bearing.py
```

**One-sentence summary for the professor:** *Unity renders a marine world and publishes its
static map over a TCP→ROS 2 bridge; a ROS scenario generator reads that map and streams
procedurally-generated traffic back into Unity, where an autonomous boat navigates to
ROS-sent goals while a Unity Perception camera captures fully auto-labelled training data.*
