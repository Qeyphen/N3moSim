# Phase 1 — Vertical Slice (boat-POV labeled capture)

**Goal of the whole project:** generate a production-grade *synthetic, automatically-labeled*
perception dataset from the Unity marine sim to train obstacle detection/segmentation for an
autonomous sailboat, with sim-to-real in mind. The simulator knows the exact identity, geometry
and pose of every object, so it can emit **perfect ground-truth labels for free** — no human
annotation.

**Goal of Phase 1 specifically:** prove the end-to-end loop on a *single camera* — capture one
boat-POV frame and get correct RGB + labels out, recorded **on demand**. This is the smallest
slice that proves the pipeline works before scaling.

---

## 1. The capture engine — Unity Perception

We use the **Unity Perception** package (`com.unity.perception`). Its model:

- A **`PerceptionCamera`** component on a Camera. It owns a list of **labelers**, each of which
  produces one kind of ground truth at capture time.
- Objects to be labeled carry a **`Labeling`** component listing label *strings* (e.g. `buoy`,
  `vessel`).
- **Label config assets** map those strings to ids/colors:
  - `IdLabelConfig` — for the box + instance labelers (detection classes: `buoy`, `vessel`).
  - `SemanticSegmentationLabelConfig` — class → color for semantic seg.
- The labelers enabled in Phase 1:
  - **BoundingBox2DLabeler** — 2D pixel rectangles (from the instance mask).
  - **BoundingBox3DLabeler** — oriented 3D boxes (mesh bounds + transform, camera space).
  - **InstanceSegmentationLabeler** — per-object pixel mask (unique color per instance).
  - **SemanticSegmentationLabeler** — per-class pixel mask.
  - **DepthLabeler** — per-pixel distance (float EXR).

### Capture trigger — Manual (deliberate)
The Perception Camera is set to **Capture Trigger Mode = Manual** (in the Inspector — the enum
name varies by package version, so it's not set from code). *Scheduled* mode would fix the
simulation timestep and decouple from real time, which would wreck the live physics-driven boat
and water. Manual mode lets the sim run normally; we snapshot it only when we ask.

---

## 2. On-demand recording — `DatasetCaptureScheduler.cs`

A `MonoBehaviour` on the POV camera (`[RequireComponent(typeof(PerceptionCamera))]`) that
captures **only while "recording" is on**, at a fixed real-time rate.

- **Rate:** `captureHz` (default **3 Hz**). In `Update()` it accumulates `Time.deltaTime`; once
  it crosses `1/captureHz` it calls `perceptionCamera.RequestCapture()` (which queues one
  capture for end-of-frame) and increments a frame counter.
- **Three ways to start/stop recording** (all flip the same `capturing` bool):
  - **ROS:** subscribes `std_msgs/Bool` on `controlTopic` (`/dataset/control`); `data=true`
    starts, `false` stops.
  - **Hotkey:** `toggleKey` (default `R`) toggles in the Game view.
  - **Inspector:** the `capturing` checkbox, live.
- Logs `▶ START` / `■ STOP — N frames captured`.

Why a scheduler instead of just always capturing: we want **short, intentional clips** (a few
seconds of relevant scene), not a capture every frame — and decoupled from the render rate.

> The dataset is **finalized when Play stops** (Perception flushes the SOLO dataset on exit).

---

## 3. What each frame contains — the SOLO format

Perception writes the **SOLO** dataset format to
`~/.config/unity3d/<Company>/<Product>/solo*/` (Linux) — the exact path is logged at Play.

```
solo/
  metadata.json, annotation_definitions.json, sensor_definitions.json   # dataset-level keys
  sequence.0/
    step0.camera.png                          # RGB
    step0.camera.semantic segmentation.png    # semantic mask (class → color)
    step0.camera.instance segmentation.png    # instance mask (object → color)
    step0.camera.Depth.exr                     # per-pixel depth, float metres
    step0.frame_data.json                      # ALL labels for this frame
```

`frame_data.json` per frame holds `captures` (the camera sensor) → each with `annotations`
(2D boxes, 3D boxes, segmentation refs) and the sensor's pose + projection matrix. Each box
annotation lists `labelName`, `instanceId`, `origin [x,y]`, `dimension [w,h]` (pixels).

**The key idea:** image + JSON are a *paired* (question, answer-key). The labels are computed
from ground truth (the engine renders hidden instance/semantic/depth passes via replacement
shaders + `AsyncGPUReadback`, and derives 2D boxes from the instance mask) — so they're exact
and automatic.

---

## 4. Verifying labels — `tools/solo_preview.py`

A JSON coordinate like `origin:[1001,281]` doesn't tell you if a label is *correct*. This tool
**draws the labels back onto the image** so you can eyeball them:

1. Auto-finds the most recent SOLO dataset (globs `~/.config/unity3d/*/*/solo*`).
2. For each `frame_data.json`: opens the RGB with **Pillow**, finds the
   `BoundingBox2DAnnotation`, and for each box draws a red rectangle at `origin`+`dimension`
   plus the `labelName` in yellow.
3. Writes annotated copies into a `preview/` subfolder (read-only w.r.t. the dataset).

It draws *exactly what the JSON says* — so a misconfigured label shows up visibly in the wrong
place. Dependency: `pip install pillow` (in a venv).

---

## 5. One-time Unity setup (recap)

1. **Label the prefabs** (Add Component → `Labeling`): buoy → `buoy`; boat → `vessel`.
2. **Label configs** under `Assets/Perception/`: `IdLabelConfig` (`buoy`, `vessel`) +
   `SemanticSegmentationLabelConfig`.
3. **POV camera** on the boat prefab with `PerceptionCamera` + the five labelers, each pointed
   at the configs; **Capture Trigger = Manual**.
4. **`DatasetCaptureScheduler`** on that camera (`captureHz=3`, `controlTopic=/dataset/control`).

### Findings nailed down in Phase 1
- **Capture reads the camera's *screen* render, not a render texture** — removing the camera's
  Target Texture fixed empty captures (Perception captures what the camera draws to the display).
- The POV camera, once added with Perception, drives the display; we accepted POV-as-main-view
  for now (chase-cam deferred).
- Manual trigger + on-demand `/dataset/control` is the right control model for a live sim.

---

## 6. Outcome

A working vertical slice: press Play → record via `/dataset/control` (or `R`) → get SOLO frames
with **RGB + 2D/3D boxes + instance/semantic seg + depth**, and `solo_preview.py` confirms the
2D boxes sit correctly on the buoys. This proved Perception works on **HDRP / Unity 6.3** and
that the capture/label/verify loop is sound — the foundation Phase 2 enriches.
