# Dataset Pipeline

## Capture Model

The simulator captures synthetic data with Unity Perception. Each Perception camera can produce:

- RGB
- BoundingBox2D
- BoundingBox3D
- semantic segmentation
- instance segmentation
- depth

The current setup supports dual boat-mounted cameras, for example:

- `camera_left`
- `camera_right`

Each camera writes its own capture entries into the same SOLO frame JSON.

## Dual-Camera Requirements

Each capture camera should have:

- `Camera`
- `PerceptionCamera`
- labelers enabled
- unique Perception camera identity
- `Capture Trigger Mode = Manual`

The current host-side scripts are written to iterate per capture entry, so they can process both left and right cameras from the same frame JSON.

## Capture Resolution

`Assets/Scripts/CaptureResolution.cs` controls output pixel size.

It does not change the display window size. It changes the render target assigned to the Perception camera.

That means:

- recorded image pixel dimensions change
- camera FOV stays the same
- the Game view size is not the authoritative capture size

### Supported ROS resolution commands

```bash
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic pub --once /camera/resolution std_msgs/msg/String '{data: 720p}'"
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic pub --once /camera/resolution std_msgs/msg/String '{data: 1080p}'"
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && ros2 topic pub --once /camera/resolution std_msgs/msg/String '{data: 1920x1080}'"
```

Supported formats:

- `360p`
- `720p`
- `1080p`
- `4k`
- explicit `WxH`

### Inspector behavior

If you change `width` and `height` in the Inspector, the script only takes effect after `Apply Resolution` or runtime re-application logic runs.

Expected log:

```text
[CaptureResolution] capture size = 1280x720 on 'POVCamera_Left'
[CaptureResolution] capture size = 1280x720 on 'POVCamera_Right'
```

## Dataset Capture Scheduler

`Assets/Scripts/DatasetCaptureScheduler.cs` drives capture.

Important points:

- capture is manual, not Perception scheduled mode
- this avoids breaking physics timing
- recording starts and stops on `/dataset/control`
- capture frequency is updated on `/dataset/capture_hz`
- scenario metadata is consumed from `/dataset/scenario_info`

Expected logs per camera:

```text
[DatasetCapture:camera_left] Awake ...
[DatasetCapture:camera_left] Ready ...
[DatasetCapture:camera_left] ▶ START recording ...
[DatasetCapture:camera_left] ■ STOP ...
```

If SOLO never appears, common causes are:

- Perception camera disabled
- wrong trigger mode
- no valid Perception camera on that object

## SOLO Output

By default Unity writes under `Application.persistentDataPath`, typically:

- Linux:
  - `~/.config/unity3d/<Company>/<Product>/solo*`
- macOS:
  - `~/Library/Application Support/<Company>/<Product>/solo*`

Host-side runners can then:

- leave the data there
- or move/archive it into a target directory

## Unity Metadata Files

## `run_metadata_<camera_key>_<timestamp>.json`

Written by `RunMetadata.cs` when recording stops.

Contains:

- run identity
- capture stats
- image size
- camera intrinsics/extrinsics
- environment state
- scene summary from `config/Scene.json`
- occupancy-grid settings
- ego pose publisher settings
- boat controller settings
- label set
- scenario metadata pushed from ROS
- Unity/system summary

## `scenario_start_<camera_key>_<timestamp>.json`
## `scenario_end_<camera_key>_<timestamp>.json`

Boundary snapshots associated with the active scenario metadata.

Use these to prove:

- which scenario id was active
- which environment policy was in effect
- which manifest or scene spec originated the run

## `unity_defaults_<timestamp>.json`

Written by `UnityDefaultsDump.cs`.

This is separate from run metadata.

It captures startup/default state such as:

- Unity application info
- loaded scenes
- screen info
- quality settings
- time settings
- physics settings
- rendering settings
- counts of key scene objects
- raw `config/Scene.json`
- snapshots of key runtime components
- camera inventory
- selected `ProjectSettings` file contents

The data is cached at startup and later flushed into SOLO.

## Preview Tools

## `tools/solo_preview.py`

Draws 2D boxes onto RGB images.

Behavior:

- if no path is passed, it uses the latest SOLO directory
- if `--min-box-side` is not passed, no size filter is applied
- if `--min-box-side N` is passed, boxes with smaller side `< N` are skipped

Examples:

```bash
python3 tools/solo_preview.py
python3 tools/solo_preview.py /path/to/run_output
python3 tools/solo_preview.py /path/to/run_output --min-box-side 10
```

Output:

- `preview/` subfolders next to the processed images

## `tools/marine_surface.py`

Creates water/sky/obstacle masks.

How it works:

1. read each camera capture from `frame_data.json`
2. infer the horizon from the camera projection matrix and camera rotation
3. classify pixels geometrically:
   - above horizon -> sky
   - below horizon -> water
4. preserve obstacle pixels from Unity segmentation
5. fall back to instance segmentation image content if semantic labels are missing

This is why the output looks cartoon-like:

- it is a class mask, not a photoreal image
- sky is light blue
- water is dark blue
- obstacles are preserved from segmentation

Examples:

```bash
python3 tools/marine_surface.py
python3 tools/marine_surface.py /path/to/run_output
python3 tools/marine_surface.py /path/to/run_output --flip
```

Outputs:

- `marine_seg/*.marine_seg.png`
  - colored preview
- `marine_seg/*.marine_classes.png`
  - indexed classes
  - `0 = water`
  - `1 = sky`
  - `2 = obstacle`

### Why this exists

This helps with the requirement:

- add water and sky masks if possible
- otherwise only keep the emerged portions of objects

Even if water/sky masks are not used directly for training, they are useful as an intermediate product for clipping boxes to visible emerged object pixels.

## `tools/clip_boxes_to_emerged.py`

Uses masks to tighten boxes to visible non-water object pixels.

Example:

```bash
python3 tools/clip_boxes_to_emerged.py /path/to/run_output --apply
```

If `--apply` is used, the script rewrites `frame_data.json` in place and keeps backups.

## `tools/filter_boxes.py`

Drops unusably small boxes or boxes below a chosen water level heuristic.

Example:

```bash
python3 tools/filter_boxes.py /path/to/run_output --apply
```

## SOLO to YOLO

## What `tools/solo_to_yolo.py` does

It reads Unity SOLO data and writes a YOLO-style dataset:

- `images/...`
- `labels/...`
- `data.yaml`
- `dataset_manifest.json`

Each YOLO label text file contains normalized 2D boxes for one image.

### Default behavior

Default split mode is:

- `none`

That means:

- no `train/val` split is forced
- all samples go to `images/all` and `labels/all`

This matches the PM requirement better than a frame-based split, because the PM explicitly did not want validation images drawn from the same scenarios by frame number.

### Examples

Use latest SOLO automatically:

```bash
python3 tools/solo_to_yolo.py --out yolo_raw
```

Use a specific run:

```bash
python3 tools/solo_to_yolo.py /path/to/run_output --out yolo_raw
```

Scenario-level split across multiple roots:

```bash
python3 tools/solo_to_yolo.py /path/to/run_a /path/to/run_b --split scenario --val-frac 0.2 --out yolo_split
```

### Split modes

- `none`
  - raw export only
- `frame`
  - legacy every-Nth-frame split
  - generally not recommended for this project
- `scenario`
  - assign whole input roots to train or val

For PM-facing datasets, `none` or `scenario` are the meaningful options.

## Practical Validation Checklist

After a run, validate:

- both `camera_left` and `camera_right` exist in `captures`
- both cameras have RGB and annotations
- `run_metadata_*` exists for each camera
- `scenario_start_*` and `scenario_end_*` exist for each camera
- `unity_defaults_*` exists
- `solo_preview.py` draws expected boxes
- `marine_surface.py` produces one mask per camera
- `solo_to_yolo.py` exports both views

If the island should appear as obstacle in the marine mask, it must be labeled in Unity so segmentation can preserve it.
