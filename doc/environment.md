# Procedural Environment — Weather & Time of Day

Random weather and time-of-day for the marine scene, controllable over ROS 2. This is the
environment sibling to the traffic layer: the scenario generator drives *objects*; this drives
the *world look* (sun, fog, clouds, sea state, rain).

Branch: `procedural-environment`.

---

## Architecture

One Unity component — **`Assets/Scripts/EnvironmentController.cs`** — owns the whole world look.
It holds the canonical state (time + weather parameters), applies it to HDRP, exposes it in the
Inspector as live sliders, and subscribes to ROS to be driven from the container.

```
ROS 2 (/env/* commands)  ──►  EnvironmentController (Unity)  ──►  HDRP sun / fog / clouds / water / rain
                                        │
                                        └──►  /env/state (JSON, published back for logging)
```

To avoid fighting the sample scene's existing Volumes, the controller **creates its own global
Volume** at runtime with a very high priority and a fresh profile, and writes all fog/cloud
overrides there — so they always win the volume blend and never dirty a project asset.

---

## Parameters

| Parameter | Range | Drives (HDRP) |
|---|---|---|
| **time of day** | 0–24 h | directional light rotation + intensity + colour temperature |
| **fog** | 0–1 | Fog `meanFreePath` (exponential mapping so it's visible across the slider) |
| **cloudiness** | 0–1 | Volumetric Clouds density, or Cloud Layer opacity (whichever the HDRP version has) |
| **wind** | 0–1 | `WaterSurface` wind speed (sea state / swell) |
| **wave height** | 0–1 | `WaterSurface` wave band multipliers |
| **rain** | 0–1 | rain `ParticleSystem` emission (play/stop) |

**Presets** (bundle all of the above): `clear`, `cloudy`, `overcast`, `foggy`, `stormy`.

**Randomize(seed):** picks a daylight time + a random preset with jitter — **seeded**, so a seed
reproduces the exact conditions (for reproducible dataset variety).

---

## ROS 2 interface

Individual setters (all `std_msgs/Float32`, 0–1 except time 0–24):
`/env/time_of_day`, `/env/fog`, `/env/wind`, `/env/wave`, `/env/cloudiness`, `/env/rain`.

Bundled: `/env/weather` (`String`, preset name), `/env/randomize` (`Int32`, seed).

Feedback: `/env/state` (`String`, JSON of the current conditions) — published back on every
change, so each dataset capture can record the exact weather/time it was taken under.

---

## Unity setup (one-time)

1. Empty GameObject `Environment` → add **`EnvironmentController`**.
2. Assign references:
   - **Sun** → the scene Directional Light.
   - **Water** → the `ocean` `WaterSurface` (needed for wind/wave).
   - **Rain Particles** → a rain particle system (optional; only for rain).
3. The scene's global Volume needs **Fog** and a **Cloud Layer** (or Volumetric Clouds) override
   + a **Physically Based Sky**. Time-of-day and fog work with just Fog + PBS; clouds need the
   cloud override present.

Test in the editor by scrubbing the sliders (they apply live via `OnValidate`), or right-click
the component header → **Apply Now** / **Log Volumes** / **Log Effective Fog** to diagnose.

---

## Control from Docker

**Rebuild once** (new `env_control` entry point is baked into the image):
```bash
docker compose build && docker compose up -d
```

**`env_control` node** — set any subset in one call:
```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && \
  source /root/ros2_ws/install/setup.bash && \
  ros2 run n3mo_control env_control --ros-args -p time:=18.0 -p fog:=0.7"

docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && \
  source /root/ros2_ws/install/setup.bash && \
  ros2 run n3mo_control env_control --ros-args -p wind:=0.8 -p wave:=0.9"

docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && \
  source /root/ros2_ws/install/setup.bash && \
  ros2 run n3mo_control env_control --ros-args -p weather:=stormy"

docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && \
  source /root/ros2_ws/install/setup.bash && \
  ros2 run n3mo_control env_control --ros-args -p randomize:=7"
```
Args (all optional): `time` (0–24); `fog` `wind` `wave` `cloudiness` `rain` (0–1);
`weather` (preset); `randomize` (seed).

**Raw topics** (no rebuild needed — only the Unity side changed):
```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && \
  ros2 topic pub --once /env/fog std_msgs/msg/Float32 '{data: 0.8}'"
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && \
  ros2 topic pub --once /env/time_of_day std_msgs/msg/Float32 '{data: 6.0}'"
```

**Verify** what Unity is using:
```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && \
  ros2 topic echo /env/state"
# -> {"time_of_day":18.0,"weather":"clear","cloudiness":0.10,"fog":0.80,"wind":0.90,"wave":0.90,"rain":0.00}
```

---

## Dataset-generation policy

For the current dataset workflow, weather and time of day should be treated as
**scenario-level inputs**, not continuously changing variables inside one recording.

- Within a single short scenario, the environment should stay fixed.
- Variation happens **between** scenarios, driven by the host-side scenario manifest.
- `tools/run_scenario_batch.py` applies one fixed `weather` and `time_of_day` per scenario,
  then runs `dataset_sweep` with mid-run environment randomization disabled.

This keeps clips physically coherent and avoids the abrupt lighting/weather jumps that were
showing up in long continuous sweeps.

---

## Notes / troubleshooting

- **Fog looks clear at low values** — correct; it's near-invisible below ~0.5 by design. Push
  to 0.7–1.0 to see obvious fog.
- **Wind/wave doesn't move the sea** — the `WaterSurface` field names vary by HDRP version;
  they're set by reflection (`largeWindSpeed`, `largeBand0/1Multiplier`). If unresponsive, the
  exact member names for the installed HDRP version need matching.
- **Clouds** — driven by Cloud Layer opacity if that's what the scene has (this project), else
  Volumetric Clouds density. The cloud override must exist on a Volume and be enabled in HDRP
  Frame Settings.
- **`env_control` needs `docker compose build`** if the container image does not already include
  the entry point; the raw `ros2 topic pub` path works without a rebuild.
