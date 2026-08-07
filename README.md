# N3moSim

Unity marine simulator with a ROS 2 bridge. Boats are spawned from a JSON scene,
driven either manually (keyboard) or autonomously (toward a ROS target pose), and
the scene is exposed to ROS 2 as an occupancy grid (`/map`).

On top of that, a **ROS scenario generator** procedurally populates the water with
**moving traffic** (sailboats, swimmers, buoys, …) on `/sim/tracks`, which Unity renders
and RViz visualizes. Unity's own `/map` is fed back to the generator as a **costmap**, so
traffic spawns only in navigable water — a closed loop (see §10). This is the source of
varied, auto-labeled obstacles for the perception dataset (§9).

```
Unity  ──TCP(10000)──►  ros_tcp_endpoint (Docker)  ──DDS──►  ROS 2 nodes / RViz / CLI
```

Unity never speaks ROS directly — it talks to the `ros_bridge` container, which is
the real ROS 2 node that owns all publishers/subscribers.

---

## 1. Prerequisites

- **Docker** (Docker Desktop on macOS, Docker Engine on Linux).
- **Unity** with the project open (ROS-TCP-Connector package already included).
- The Unity **ROSConnectionPrefab** in the scene, pointing at `127.0.0.1` port `10000`.

---

## 2. Start / stop the ROS side (Docker)

```bash
docker compose build          # first time, or after editing the Dockerfile / ROS package
docker compose up -d          # start the bridge (port 10000)
docker compose ps             # check it's running
docker compose logs -f ros_bridge   # follow bridge logs
docker compose down           # stop everything
```

Then press **Play** in Unity. The bridge and Unity connect automatically.

> If you change the Python ROS node, rebuild it without a full image rebuild:
> ```bash
> docker compose exec ros_bridge bash -lc \
>   "cd /root/ros2_ws && source /opt/ros/humble/setup.bash && colcon build --packages-select n3mo_control"
> ```

---

## 3. Topics

| Topic | Type | Direction | Notes |
|---|---|---|---|
| `/agent_01/target_pose` | `geometry_msgs/PoseStamped` | → Unity | goal for the boat; published on demand |
| `/map` | `nav_msgs/OccupancyGrid` | Unity → | static obstacles (island + buoys); latched |
| `/sim/tracks` | `n3_new_msgs/TrackArray` | ROS → Unity | procedural moving traffic (id/type/pose/vel); 10 Hz |
| `/sim/tracks/markers` | `visualization_msgs/MarkerArray` | ROS → RViz | traffic as colored cubes |
| `/sim/boat/pose` | `geometry_msgs/PoseStamped` | Unity → | ego boat pose; 10 Hz |
| `/scene/objects` | `n3_new_msgs/TrackArray` | Unity → | ALL authored scene objects (ego + buoys): id/type/pose/vel; 10 Hz |
| `/map/costmap_static` | `nav_msgs/OccupancyGrid` | — | the costmap the generator reads (= `/map`, remapped) |
| `/env/time_of_day` | `std_msgs/Float32` | → Unity | set the hour 0–24 (sun angle + lighting) |
| `/env/fog` | `std_msgs/Float32` | → Unity | fog / visibility, 0–1 |
| `/env/wind` | `std_msgs/Float32` | → Unity | wind speed → sea state, 0–1 |
| `/env/wave` | `std_msgs/Float32` | → Unity | wave height, 0–1 |
| `/env/cloudiness` | `std_msgs/Float32` | → Unity | cloud cover, 0–1 |
| `/env/rain` | `std_msgs/Float32` | → Unity | rain intensity, 0–1 |
| `/env/weather` | `std_msgs/String` | → Unity | preset: clear/cloudy/overcast/foggy/stormy |
| `/env/randomize` | `std_msgs/Int32` | → Unity | randomise conditions (0 = random seed, else seeded) |
| `/env/state` | `std_msgs/String` | Unity → | current conditions as JSON (log per capture) |
| `/camera/resolution` | `std_msgs/String` | → Unity | capture output pixels: `WxH` (`1920x1080`) or `360p/720p/1080p/4k` |

**Coordinate conventions (important):**
- Control channel (`target_pose`): `position.x` = Unity x, `position.z` = Unity z, `y = 0`.
- Map layer (`/map`, dynamic obstacles): ROS ground plane = XY, so Unity x → ROS x,
  **Unity z → ROS y**, ROS z = 0.

---

## 4. Send a target pose (autonomous control)

Set `agent_01` to **Auto** (in `config/Scene.json` `"control_mode": "auto"`, or live in the
boat's `BoatControlSwitcher` Inspector), then publish a target. `x`/`z` are Unity
coordinates; the publisher sends once and exits.

```bash
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && \
  ros2 launch n3mo_control target_pose.launch.py x:=-190.0 z:=-110.0"
```

Other options:
```bash
# pick a different agent's topic
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && \
  ros2 launch n3mo_control target_pose.launch.py topic:=/agent_02/target_pose x:=10 z:=25"

# run the node directly instead of the launch file
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && \
  ros2 run n3mo_control target_pose_publisher --ros-args -p x:=-190.0 -p z:=-110.0"
```

The boat turns toward the target, then thrusts; watch its `AutonomousBoatController.Status`
in the Inspector cycle **Turning → Thrusting → Settled**.

---

## 5. Inspect topics (CLI)

These use only standard message types, so they need just the base ROS source.

```bash
# what's being published
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && ros2 topic list"

# watch target poses
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && ros2 topic echo /agent_01/target_pose"

# watch live boat positions
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && ros2 topic echo /dynamic_obstacles"

# map metadata only (don't echo the huge data array); latched, so --once returns it
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && ros2 topic echo /map --field info --once"

# publish rate
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && ros2 topic hz /dynamic_obstacles"
```

> **Tip — shell shortcut.** Add this to `~/.zshrc` (or `~/.bashrc`) to skip the boilerplate.
> It sources both setups, which works for every command (the workspace overlay re-exposes
> base ROS):
> ```bash
> dros() { docker exec -it n3mo_bridge bash -lc \
>   "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && ros2 $*"; }
> ```
> Then: `dros topic list`, `dros topic echo /dynamic_obstacles`,
> `dros launch n3mo_control target_pose.launch.py x:=-190 z:=-110`.

---

## 6. View the map (terminal tools)

What each tool shows: `/map` is the **static** layer (buoys); `/dynamic_obstacles` is the
**live** layer (boats). `view_map.py`/`save_map.py` show only the static map;
`view_live.py` overlays both.

### Live scene — static + moving boats (colour, headless)
```bash
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && python3 /root/ros2_ws/src/n3mo_control/tools/view_live.py"
```
Redraws ~4×/s: **blue dots = static buoys**, **red dots = live boats** (move as you drive),
each labelled with its `(x, z)` position just above the dot. Ctrl-C to quit. No GUI needed.

### Static map only (ASCII)
```bash
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && python3 /root/ros2_ws/src/n3mo_control/tools/view_map.py"
```
`#` = occupied (buoy), `.` = free. First line shows `occupied=N` (true occupied-cell count).

### Save the static map to an image
```bash
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && python3 /root/ros2_ws/src/n3mo_control/tools/save_map.py"
```
Writes `recordings/map.png` (full, 1 px/cell — mostly white, zoom in to see buoys),
`recordings/map_zoom.png` (cropped + 8× upscaled — buoys clearly visible), and
`recordings/map.yaml` (ROS map metadata). Open the PNGs on the host.

---

## 7. RViz2 (integrated view)

The `rviz` profile starts **everything**: the bridge, the **scenario engine** (traffic +
markers, see §10), and RViz with the preloaded config (`config/n3mo.rviz`). Displays: **Map**
(`/map`), **Tracks** (`/sim/tracks/markers`, colored cubes), **Ego** (`/sim/boat/pose`, green
arrow). Run `docker compose build` once first so the image has the scenario nodes.

### Linux
```bash
xhost +local:docker                      # allow containers to use your X server (per session)
docker compose --profile rviz up         # bridge + scenario engine + RViz window
```

### macOS (needs XQuartz)
```bash
brew install --cask xquartz
open -a XQuartz                          # Settings → Security → ✅ "Allow connections from network clients", then reopen
xhost + 127.0.0.1
export DISPLAY=host.docker.internal:0
docker compose --profile rviz up
```

Fixed Frame is `map`. Press **Play** in Unity so `/map` is published — the generator then
auto-generates traffic and RViz fills in. Stop: `docker compose --profile rviz down` (or Ctrl-C).

---

## 8. Control modes

Each dynamic boat picks its controller via `config/Scene.json` `control_mode`
(`"manual"` | `"auto"`), and you can switch it live in the boat's `BoatControlSwitcher`
Inspector while playing.

- **Manual** — keyboard: `W` forward, `S` back, `A`/`D` steer.
- **Auto** — follows `/{id}/target_pose` (see §4).

---

## 9. Synthetic dataset capture (Unity Perception)

Captures **labeled boat-POV training data** for ML perception / obstacle detection, using
the Unity **Perception** package. Each captured frame yields RGB + 2D & 3D bounding boxes +
instance & semantic segmentation + depth, written in **SOLO** format.

Taxonomy: segmentation `water / sky / static_obstacle / dynamic_obstacle`; detection `buoy`,
`vessel`. (Phase 1 covers buoy/vessel + static/dynamic obstacle; water/sky come later.)

### One-time Unity setup
1. **Label the prefabs** — Add Component → **Labeling**:
   - Buoy prefab → `buoy`, `static_obstacle`
   - boat prefab(s) → `vessel`, `dynamic_obstacle`
2. **Label configs** (in `Assets/Perception/`): **IdLabelConfig** (`buoy`, `vessel`),
   **SemanticLabelConfig** (`static_obstacle`, `dynamic_obstacle`).
3. **Boat POV camera** — a forward-facing Camera on the boat prefab with **Perception Camera**
   + labelers (BoundingBox2D/3D, Instance, Semantic, Depth) assigned to those configs;
   **Capture Trigger Mode = Manual**; render to a **1280×720** Render Texture (fixes
   resolution + keeps it off the main view).
4. **Add `DatasetCaptureScheduler`** to that camera — `Capture Hz = 3`,
   `Control Topic = /dataset/control`.

### Start / stop recording
Capture only happens while recording is on. Toggle it any of three ways:
```bash
# START (ROS)
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && ros2 topic pub --once /dataset/control std_msgs/Bool '{data: true}'"
# STOP (ROS)
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && ros2 topic pub --once /dataset/control std_msgs/Bool '{data: false}'"
```
- **Hotkey:** press **R** in the Unity Game window.
- **Inspector:** toggle **Capturing** on the scheduler.

Console logs `▶ START` / `■ STOP — N frames captured`. The dataset is finalized when you
**stop Play**.

### Output + preview
SOLO output goes under `~/.config/unity3d/<Company>/<Product>/solo/` (exact path logged in
the Console).

**`solo_preview.py`** is a sanity check on your *labels*: a JSON number like
`origin: [1001, 281]` doesn't tell you if a label is actually *correct*, so the tool reads
each frame's `frame_data.json`, takes the 2D bounding boxes, and **draws them onto the RGB
image** (red box + yellow label). Open the results and you can instantly see whether each
box sits tightly on the right object — the fastest way to confirm the dataset is trainable
before generating thousands of frames. It's read-only: it never changes the dataset, just
writes annotated copies into a `preview/` subfolder.

Run it from a Python venv in the project root (Pillow is its only dependency):
```bash
# one-time
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install pillow                   # (or: pip install -r requirements.txt)

# each time
python3 tools/solo_preview.py        # auto-finds the latest SOLO dataset
# or point it at a specific one:
python3 tools/solo_preview.py ~/.config/unity3d/<Company>/<Product>/solo
```
With no path it auto-discovers the most recent SOLO dataset under
`~/.config/unity3d/*/*/solo*`. Annotated frames land in a `preview/` subfolder next to
each captured frame.

**Depth sanity + preview — `depth_preview.py`.** Perception also writes a depth image per
frame (32-bit float EXR = distance from the camera, in **metres**). Pillow can't read EXR, so
this companion tool uses OpenCV: it prints each frame's depth **min/max/mean/median** (so you
can confirm the values really are metres — e.g. a buoy ~30 m away reads ~30) and saves a
colorized `*_depth.png` (near = blue, far = red) into the same `preview/` folder.
```bash
pip install opencv-python numpy          # one-time, in the venv
python3 tools/depth_preview.py           # auto-finds the latest SOLO dataset
```

> `.venv/` is gitignored — don't commit it. `requirements.txt` is the dependency record.

### Capture rate

`DatasetCaptureScheduler.captureHz` defaults to **10 Hz**, matching the scenario generator's
`/sim/tracks` rate, so image samples line up with the traffic updates. On `STOP` it logs the
**actual** achieved rate (`… = 9.8 Hz actual (target 10)`) — if HDRP can't sustain 10 in the
editor, lower it (e.g. 5) or run a built player. Capture is on-demand: start/stop via
`/dataset/control` (`std_msgs/Bool`) or the `R` hotkey.

### Capture resolution (output image pixels)

The output image size is configurable via the **`CaptureResolution`** component (add it to any
persistent object; it auto-finds the PerceptionCamera and gives it a RenderTexture of the chosen
size). Set **Width/Height** in the Inspector, or over ROS:

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && \
  ros2 topic pub --once /camera/resolution std_msgs/msg/String '{data: 720p}'"
```

`data` accepts a preset `360p / 720p / 1080p / 4k` (all 16:9, so the 60° FOV is preserved) or an
exact `WxH` like `1920x1080`. Verify with `python3 tools/camera_info.py` — the `image dimension`
line shows the new size and the pixel `fx/fy` scale with it while the FOV stays 60°. Generate
datasets at different resolutions by setting the size, recording, then repeating at another size.

### Run metadata (data card)

On **every recording STOP**, `DatasetCaptureScheduler` writes a `run_metadata_<timestamp>.json`
into the SOLO dataset folder — a data card of that run. Start/stop again → another timestamped
file, so each record is documented separately. It captures (live, at stop time):

- **capture**: target + **actual** Hz, frames, duration
- **image**: width/height, total pixels, megapixels, aspect
- **camera**: FOV (vertical/horizontal), pixel intrinsics (fx/fy/cx/cy, scaled to the resolution),
  near/far, pose, and the URDF mount (`xyz`/`rpy`) if `UrdfCameraPose` is present
- **environment**: time-of-day, weather, cloudiness, fog, wind, wave, rain, randomize seed
- **scene**: object count, ego control mode, the `Scene.json` environment block
- **labels**: the classes present (from the scene's `Labeling` components)
- **system**: Unity version, platform

Example:
```json
{
  "run_id": "solo_1",
  "capture": { "target_hz": 10, "actual_hz": 8.13, "frames": 36, "duration_s": 4.43 },
  "image":   { "width": 1920, "height": 1080, "pixels": 2073600, "aspect": 1.78 },
  "camera":  { "fov_vertical_deg": 60, "intrinsics_px": { "fx": 935.3, "fy": 935.3, "cx": 960, "cy": 540 } },
  "environment": { "time_of_day": 12, "weather": "clear", "fog": 0.05, "seed": -1 },
  "labels":  { "classes": ["buoy", "kayak", "paddleboard", "..."] }
}
```
(`actual_hz` below `target_hz` means the editor couldn't sustain the rate at that resolution —
lower the resolution or run a built player. Scenario-generator params are ROS-side and not yet
included.)

### Label water and sky — `marine_surface.py`

HDRP water is transparent (doesn't render into Perception's segmentation pass) and sky has no
geometry, so water/sky are labeled **geometrically** by horizon synthesis from the camera pose +
intrinsics. No Unity changes needed.
```bash
python3 tools/marine_surface.py          # -> marine_seg/ per frame
python3 tools/marine_surface.py --flip    # if water/sky come out swapped
```
Outputs per frame: `*_marine_seg.png` (colored preview) and `*_marine_classes.png`
(class-index mask: 0=water, 1=sky, 2=obstacle). See `doc/water-sky-and-yolo.md`.

### Export to YOLO — `solo_to_yolo.py`

Convert the SOLO 2D boxes to an Ultralytics-YOLO **detection** dataset (boxes come from Unity's
labeler — no manual boxing):
```bash
python3 tools/solo_to_yolo.py                       # -> ./yolo (min 10px, 20% val)
python3 tools/solo_to_yolo.py --out yolo --min 10 --val-frac 0.2
```
Produces `yolo/{images,labels}/{train,val}` + `data.yaml`. Train with
`yolo detect train data=yolo/data.yaml model=yolo11n.pt`. See `doc/water-sky-and-yolo.md`.

---

## 10. Procedural traffic + map architecture (scenario generator)

A **ROS scenario generator** (vendored from `n3-unity-sim` into `ros2_ws/src/`) populates the
water with **procedural moving traffic** that Unity renders and RViz visualizes. It's the
source of varied, labeled obstacles for the dataset (§9).

### The two map layers — static vs dynamic

The sim exposes the scene to ROS as **two distinct layers**; don't conflate them:

| Layer | Topic | What it is | Owner / direction |
|---|---|---|---|
| **Static map** | `/map` (`OccupancyGrid`) | fixed geometry: island + buoys, as a grid of free/occupied cells | Unity `OccupancyGridPublisher` (Unity → ROS) |
| **Dynamic traffic** | `/sim/tracks` (`TrackArray`) | moving obstacles, each id/type/pose/velocity | ROS `scenario_generator` (ROS → Unity) |

The **static** layer flows Unity → ROS (Unity knows the geometry). The **dynamic** layer flows
ROS → Unity (the generator invents the traffic; Unity renders it via `TrackSpawner.cs`).

> **`DynamicObstaclePublisher` was repurposed.** It used to export Unity-spawned moving boats as
> `/dynamic_obstacles` (a bare `PoseArray`) — obsolete once traffic moved to `/sim/tracks`. It
> now publishes **ALL authored scene objects** (ego + buoys) as a `TrackArray` on
> **`/scene/objects`** (id + type + pose + velocity each). So the full scene over ROS is:
> `/sim/tracks` (procedural traffic) **+** `/scene/objects` (authored objects) = every object.

### Query every object in the scene

The full scene lives on **two** `TrackArray` topics (same message type): `/scene/objects`
(authored: ego + buoys) and `/sim/tracks` (procedural traffic). **All objects = both topics.**

Dump everything in one command:
```bash
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && \
  echo '===== AUTHORED (ego + buoys) =====' && ros2 topic echo /scene/objects --once && \
  echo '===== PROCEDURAL TRAFFIC =====' && ros2 topic echo /sim/tracks --once"
```

Or each on its own:
```bash
ros2 topic echo /scene/objects --once   # authored: ego (id 9000) + buoys (9001…)
ros2 topic echo /sim/tracks --once        # procedural traffic (ids 1…)
```
Each entry has `id`, `type`, `pose`, `twist`. The **id ranges distinguish the source**: ≥ 9000 =
authored (logged in Unity, e.g. `id 9000 = agent_01`), < 1000 = generated. `type` is the
`n3_new_msgs/Track` constant (`1` = sailboat/ego, `11` = buoy, …).

In code, a consumer subscribes to **both** topics and merges by `id` for a live, complete scene.

### What is a costmap?

A **costmap** is an occupancy grid used for *planning*: a 2D grid where each cell marks that
patch of world as **free** (`0`, navigable water) or **occupied** (`100`, obstacle). The
generator reads the static map **as a costmap** to decide where traffic may go — it samples
spawn points and waypoint paths only in free cells, eroded by a safety margin around
obstacles. So **`/map` *is* the costmap**: the generator subscribes to it (remapped to
`/map/costmap_static`) and places boats only in navigable water, automatically avoiding the
island and buoys. Add scene geometry not spawned by SceneBuilder (e.g. the island) to
`OccupancyGridPublisher → Extra Obstacles` so it appears in the costmap.

### The closed loop

```
Unity /map (island+buoys) ──► scenario_generator ──► /sim/tracks ──► TrackSpawner (Unity 3D)
   ▲  OccupancyGridPublisher     (samples free water)      └────────► /sim/tracks/markers ─► RViz
   └───────────── ego /sim/boat/pose ◄── EgoPosePublisher ──────────────────────────────► RViz
```

Unity's own map drives the traffic; the traffic renders in both Unity and RViz; the ego is tracked.

### Run the whole thing — one command

```bash
docker compose build                 # once (bakes the scenario nodes into the image)
docker compose --profile rviz up     # ros_bridge + scenario engine + tracks_markers + RViz
```
Then press **Play** in Unity. The generator **auto-generates the moment Unity's `/map`
arrives** (`gen_on_first_costmap`) — no manual trigger. In RViz you'll see the map (occupied
island/buoys), colored cubes (traffic, moving, in the water), and a green arrow (the ego). In
Unity, `TrackSpawner` spawns catamarans/buoys in open water.

> ⚠️ **Set `OccupancyGridPublisher → Resolution = 5` (m/cell).** At the 1 m default a 1 km map
> is 1,000,000 cells and the generator's margin erosion takes ~a minute. 5 m → instant.

Unity wiring (one-time): add the island to `OccupancyGridPublisher → Extra Obstacles`, put
`EgoPosePublisher` on the boat prefab, and disable `DynamicObstaclePublisher`.

### Run / tune the engine manually

```bash
# start detached, leave running while Unity plays
docker compose exec -d ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && \
  ros2 run n3_sim scenario_generator --ros-args -r /map/costmap_static:=/map \
    -p gen_on_first_costmap:=true -p gen_track_count:=10"
docker compose exec -d ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && \
  ros2 run n3_sim tracks_markers"

# inspect the traffic
docker compose exec ros_bridge bash -lc \
 "source /opt/ros/humble/setup.bash && source /root/ros2_ws/install/setup.bash && \
  ros2 topic echo /sim/tracks --once"
```

Key generator params (`--ros-args -p name:=value`):

| Param | Meaning |
|---|---|
| `gen_track_count` | number of tracks (0 = use `gen_density`) |
| `gen_area_type` | type mix: `lake` / `coastal` / `harbor` / `open_sea` |
| `gen_spawn_spread_s` | spawns staggered over `[0, N]` s (0 = all at once; >0 = steady flow) |
| `gen_max_waypoints` | path length per track (longer = longer-lived) |
| `gen_on_first_costmap` | auto-generate when the costmap (`/map`) arrives |
| `gen_random_seed` | reproducible scenarios (0 = random) |

Traffic **thins as tracks finish their paths**, then repopulates when the scenario loops —
use `gen_spawn_spread_s > 0` for a steady population.

> **Testing without the real map:** `map_manager` can publish a blank navigable square instead,
> centered anywhere (e.g. on the ego boat at ENU `(0, -300)`):
> ```bash
> ros2 run n3_sim map_manager --ros-args -p publish_empty_costmap:=true \
>   -p empty_costmap_size_m:=200 -p empty_costmap_center_y_m:=-300
> ```
> A blank map has no obstacles, so traffic can land on the island — use the real `/map`
> (the `rviz` profile) for land-avoiding traffic.

---

## 11. Layout

```
config/Scene.json          scene definition (objects, positions, control_mode)
config/n3mo.rviz           preloaded RViz layout
Assets/Scripts/            Unity controllers + publishers
  SceneBuilder.cs            spawns objects, wires controllers + map publishers
  ManualBoatController.cs    keyboard control
  AutonomousBoatController.cs ROS target-following control
  BoatControlSwitcher.cs     manual/auto switch (per boat)
  OccupancyGridPublisher.cs  static /map (costmap source; + Extra Obstacles for the island)
  DynamicObstaclePublisher.cs publishes all authored scene objects (ego+buoys) -> /scene/objects (TrackArray)
  TrackSpawner.cs            subscribes /sim/tracks, spawns/moves/despawns traffic by type
  EgoPosePublisher.cs        publishes the ego boat pose to /sim/boat/pose
  DatasetCaptureScheduler.cs Perception dataset capture (ROS/hotkey controlled)
  CaptureResolution.cs       set output image pixels (Inspector + /camera/resolution)
  RunMetadata.cs             writes run_metadata_<ts>.json (data card) per recording stop
Assets/RosMessages/N3New/  hand-written Track / TrackArray C# messages (n3_new_msgs)
ros2_ws/src/n3mo_control/  ROS 2 package (target_pose_publisher, tools/)
ros2_ws/src/n3_sim/        vendored scenario generator (scenario_generator, map_manager,
                             tracks_markers) + nodes
ros2_ws/src/n3_common/     vendored shared lib (topics, params) used by n3_sim
ros2_ws/src/n3_new_msgs/   vendored custom messages (Track, TrackArray, …)
tools/solo_preview.py      overlay SOLO 2D bounding boxes onto RGB frames
tools/depth_preview.py     depth sanity (metres check) + colorized depth preview (EXR via OpenCV)
tools/camera_info.py       inspect per-frame camera intrinsics (matrix) + extrinsics (pose)
tools/range_bearing.py     per-object range + bearing from SOLO 3D boxes -> metadata/ JSON per frame
tools/semantic_preview.py  per-class semantic-segmentation coverage (water/sky/obstacle classes)
tools/marine_surface.py    label water/sky via horizon synthesis -> marine_seg/ (preview + class mask)
tools/filter_boxes.py      drop tiny 2D boxes from the dataset (--apply)
tools/solo_to_yolo.py      export SOLO 2D boxes -> Ultralytics YOLO dataset (images/labels/data.yaml)
tools/env_control (ros)    set weather/time over ROS (see doc/environment.md)
docker-compose.yml         ros_bridge; `--profile rviz` adds scenario engine + RViz
Dockerfile                 ROS 2 Humble + ROS-TCP-Endpoint + n3_sim/n3_common/n3_new_msgs (+ patches)
```

Requires the **com.unity.perception** package (for §9). The scenario generator (§10) is
vendored under `ros2_ws/src/` — see [`doc/todo.md`](doc/todo.md) for the dataset roadmap.
