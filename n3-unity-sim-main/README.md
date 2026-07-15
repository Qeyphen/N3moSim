# n3-unity-sim



## Getting started

* add the n3_* packages to your ros2 workspace/src/
* build the workspace: `colcon build --symlink-install`
* source the workspace: `source install/setup.bash`
* run the simulation : `ros2 launch n3_sim n3_uni_sim.launch`


## Configure

The simulation is composed of two independent generators wired together by `n3_sim/launch/n3_uni_sim.launch`:

| Node                       | Topic(s) published                                            | Role                                                          |
|----------------------------|---------------------------------------------------------------|---------------------------------------------------------------|
| `scenario_generator`       | `/sim/tracks` (`TrackArray`)                                  | Plays back surrounding traffic from a YAML scenario.          |
| `boat_traj_generator`      | `/sim/boat/pose`, `/tf` (`map -> boat_link`), `/debug/gps/fix` | Drives the *own* boat along a cyclic trajectory.              |
| `track_foxglove_converter` | `/sim/tracks/markers`, `/debug/map/tracks`                    | Converts traffic to MarkerArray + per-track NavSatFix.        |
| `map_manager`              | `/navigation/map/origin`                                      | Publishes the local ENU origin used by all geo projections.   |

All node parameters live in **`n3_sim/launch/param.yaml`**. The launch file just wires nodes together and points each at that file.

### Map manager — origin + empty costmap fallback
`map_manager` owns two responsibilities:

1. Publishing the local ENU origin on `/navigation/map/origin` (the geographic anchor every other node projects against).
2. Optionally latching a blank navigable grid on `/map/costmap_static` so consumers (`scenario_generator`, `boat_traj_generator`) don't need their own fallback. Disable this once a real costmap producer joins the system.

| Param                       | Meaning                                                                                  |
|-----------------------------|------------------------------------------------------------------------------------------|
| `use_fixed_origin`          | `true` ⇒ publish the lat/lon below at startup; `false` ⇒ wait for a fix on `/drivers/gps/fix`. |
| `fixed_origin_lat_deg`      | Latitude (deg) of the local ENU origin.                                                  |
| `fixed_origin_lon_deg`      | Longitude (deg) of the local ENU origin.                                                 |
| `fixed_origin_alt_m`        | Altitude (m) of the local ENU origin.                                                    |
| `publish_empty_costmap`     | `true` ⇒ latch a blank grid on `/map/costmap_static` at startup.                         |
| `empty_costmap_size_m`      | Side length (m) of the square fallback grid, centered on `(0, 0)` ENU.                   |
| `empty_costmap_resolution_m`| Cell size (m).                                                                           |

### Scenario generator — surrounding traffic
Two modes share the same node:

**Playback** of a hand-written YAML scenario (default) (autoloaded if `gen_autostart: true`)

| Param              | Meaning                                                              |
|--------------------|----------------------------------------------------------------------|
| `scenario_file`    | Absolute path to a scenario YAML (e.g. `open_water_scenario.yaml`).  |
| `publish_rate_hz`  | Track publication rate (Hz).                                         |
| `loop`             | Restart the scenario when its `duration_s` is reached.               |

**Procedural generation**, triggered at runtime via the service `/sim/generate_scenario` (a `std_srvs/srv/Trigger`; the `gen_*` params below configure it):
```bash
ros2 service call /sim/generate_scenario std_srvs/srv/Trigger {}
```
The service requires a costmap on `/map/costmap_static` (the empty fallback published by `map_manager` is enough). The output file gets a `_YYYY_MM_DD__HH:MM` timestamp suffix on every call, so successive calls never overwrite each other; the actual path is returned in `response.message`. If `gen_autostart: true`, the new scenario is loaded immediately and replaces the playback.

| Param                | Meaning                                                                       |
|----------------------|-------------------------------------------------------------------------------|
| `gen_output_file`    | Base output path; an `_YYYY_MM_DD__HH:MM` suffix is always appended.          |
| `gen_duration_s`     | Scenario duration in seconds.                                                 |
| `gen_track_count`    | Hard count of tracks. `0` ⇒ use `gen_density`.                                |
| `gen_density`        | Tracks per km² (when `gen_track_count == 0`).                                 |
| `gen_area_type`      | `lake` \| `coastal` \| `harbor` \| `open_sea` — controls track-type mix.      |
| `gen_min/max_speed_kts` | Speed clamp. `0` ⇒ use per-type defaults.                                  |
| `gen_min/max_waypoints` | Waypoint count range per track.                                            |
| `gen_spawn_spread_s` | Tracks spawn randomly within `[0, N]` seconds.                                |
| `gen_margin_m`       | Safety margin from costmap obstacles.                                         |
| `gen_random_seed`    | `0` ⇒ non-reproducible.                                                       |
| `gen_autostart`      | Load the generated scenario immediately after generation.                     |

A scenario YAML lists tracks with waypoints in ENU meters relative to the map origin; see `n3_sim/launch/open_water_scenario.yaml` for the format.

### Boat trajectory generator — own boat
Generates one of three cyclic patterns inside a configurable area, intersected with the costmap navigable region. Subscribes to `/map/costmap_static` (the latched empty grid from `map_manager` is enough) and to `/navigation/map/origin` (used to project the boat's ENU pose back to lat/lon for `/debug/gps/fix`).

| Param                | Meaning                                                                                |
|----------------------|----------------------------------------------------------------------------------------|
| `speed_kts`          | Boat speed along the trajectory (knots).                                               |
| `publish_rate_hz`    | Pose / TF / NavSatFix publish rate (Hz).                                               |
| `trajectory_type`    | `lawnmower` \| `circle` \| `random_walk`.                                              |
| `margin_m`           | Safety margin from costmap obstacles (m).                                              |
| `random_seed`        | RNG seed for `random_walk` (`0` = non-reproducible).                                   |
| `area_center_x_m`    | ENU X center of the trajectory generation area.                                        |
| `area_center_y_m`    | ENU Y center of the trajectory generation area.                                        |
| `area_extent_x_m`    | Full X extent (m) of the trajectory area. `0` ⇒ use full costmap extent.               |
| `area_extent_y_m`    | Full Y extent (m) of the trajectory area. `0` ⇒ use full costmap extent.               |
| `circle_radius_m`    | Circle radius (m), `circle` type only. `0` ⇒ derive from `area_extent_*_m`.            |

Tips:
- To keep the boat near the scenario traffic, set `area_center_*_m` to the centroid of your scenario waypoints and `area_extent_*_m` to ~1.5× their span.
- For `lawnmower` and `random_walk`, `area_extent_*_m = 0` falls back to the full navigable map (which equals `empty_costmap_size_m` when `map_manager.publish_empty_costmap=true`).
- `circle_radius_m > 0` overrides the area-derived radius — useful to lock a tight circle in a large area.

### Wind (`anemo_sim`)
Publishes a simulated true wind around the means `twd_deg` / `tws_ms` at `publish_rate_hz`. Direction and speed each support three variation modes independently:

| Param                  | Meaning                                                                          |
|------------------------|----------------------------------------------------------------------------------|
| `twd_deg`              | Mean true wind direction (deg, clockwise from North).                            |
| `tws_ms`               | Mean true wind speed (m/s).                                                      |
| `publish_rate_hz`      | Publication rate (Hz).                                                           |
| `twd_variation_mode`   | `none` \| `sinusoidal` \| `turbulent` (Ornstein-Uhlenbeck).                      |
| `twd_sinus_period_s`   | Sinusoidal period (s) for direction.                                             |
| `twd_sinus_amplitude_deg` | Sinusoidal peak amplitude (deg) for direction.                                |
| `twd_turb_std_deg`     | Turbulent 1-sigma deviation (deg) for direction.                                 |
| `twd_turb_time_constant_s` | Turbulent correlation time (s) — higher = slower drift.                      |
| `tws_variation_mode`   | `none` \| `sinusoidal` \| `turbulent`.                                           |
| `tws_sinus_period_s`   | Sinusoidal period (s) for speed.                                                 |
| `tws_sinus_amplitude_ms` | Sinusoidal peak amplitude (m/s) for speed.                                     |
| `tws_turb_std_ms`      | Turbulent 1-sigma deviation (m/s) for speed.                                     |
| `tws_turb_time_constant_s` | Turbulent correlation time (s).                                              |
| `wind_turb_correlation` | Linear correlation in `[-1, 1]` between direction and speed turbulent noise.    |
| `random_seed`          | `0` ⇒ time-based (non-reproducible); `>0` ⇒ deterministic.                       |

### Quick checks
After `colcon build --symlink-install` and `ros2 launch n3_sim n3_uni_sim.launch`:
```bash
ros2 topic hz /sim/tracks               # ≈ scenario_generator publish_rate_hz
ros2 topic hz /sim/tracks/markers       # same — drives the Foxglove 3D markers
ros2 topic hz /tf                       # boat_traj_generator publish_rate_hz
ros2 topic hz /debug/gps/fix            # boat lat/lon stream for the Map panel
ros2 topic echo /navigation/map/origin --once   # the fixed origin (latched)
ros2 topic echo /map/costmap_static --once      # the empty fallback grid (latched)
```
In Foxglove: connect to `ws://<host>:8765`, set the 3D panel "Display frame" to `map`, and add `/debug/map/tracks` + `/debug/gps/fix` to the Map panel topics.

## Connecting to unity_sim
Architecture: Refer to [simulation](./simulation.md)

Main connexions are:
- `/sim/tracks` (TrackArray) --> obstacles
- `/sim/boat/pose` (PoseStamped) --> own boat
- `/tf` (tf2_msgs/TFMessage)
- `/sim/true_wind` (ros2_wind/Wind) 

By default an empty costmap is published on `/map/costmap_static` (the one latched by `map_manager`).
When the simulator will publish one:
- disable empty map publishing: in n3_sim/launch/param.yaml, set `publish_empty_costmap: false`
- publish on `/map/costmap_static`


To see in Foxglove 2D:
- `/debug/map/tracks` (MarkerArray)
- `/debug/gps/fix` (NavSatFix)

**urdf model** is in n3_urdf
