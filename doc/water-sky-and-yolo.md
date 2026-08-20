# Water/Sky Labeling & YOLO Export

Two dataset deliverables:
1. **Label water and sky** — per-pixel semantic regions (`tools/marine_surface.py`).
2. **YOLO export** — object-detection boxes in Ultralytics format (`tools/solo_to_yolo.py`).

They are different output *types*: water/sky are **regions** (segmentation); YOLO is **boxes**
(detection). Both are read-only over the SOLO dataset and auto-find the latest one.

---

## 1. Label water and sky (`marine_surface.py`)

### Why it's a post-process, not a Unity label
HDRP water is a **transparent surface**, so it does **not** render into Perception's
segmentation pass; sky has **no geometry** at all. In the seg image both come out as background,
and the engine can't tell them apart. So water/sky are labeled **geometrically** by horizon
synthesis — a standard method in marine perception. **No Unity wiring is needed.**

### How it works
For every pixel it casts a world-space viewing ray from the camera **pose (extrinsics)** +
**intrinsics** (the same matrix verified in the FOV doc):
- ray points **down** (toward the flat sea) → **water**
- ray points **up** → **sky**
- pixels Perception already labeled (solid obstacles) are kept as **obstacle**

### Outputs (per frame, in a `marine_seg/` folder next to the frame)
- `*_marine_seg.png` — colored preview (blue=water, light=sky, obstacle colors kept).
- `*_marine_classes.png` — **class-index mask** for training: `0=water, 1=sky, 2=obstacle`.
- Console prints water/sky/obstacle coverage %.

### Run
```bash
python3 tools/marine_surface.py            # latest dataset
python3 tools/marine_surface.py --flip      # if water/sky come out swapped
```

### Setup / test
1. In Unity, **capture** a few frames (press `R`, or `/dataset/control` = true), then stop and
   exit Play so the SOLO dataset finalises. *(No scene changes needed for water/sky.)*
2. Run `python3 tools/marine_surface.py`.
3. Open `marine_seg/*_marine_seg.png` and check the **horizon split**: water below, sky above.
4. **Sanity:** for a forward, slightly-down camera water should be the **larger** share. If
   water and sky look **swapped**, re-run with `--flip` (handedness of the camera).

---

## 2. YOLO export (`solo_to_yolo.py`)

### What it produces
An Ultralytics-YOLO **detection** dataset from the SOLO 2D boxes:
```
yolo/
  images/all/*.png     labels/all/*.txt
  data.yaml
  dataset_manifest.json
```
Each label file has one line per box: `class_id x_center y_center width height`, all
**normalized 0–1** (YOLO convention). Class ids are assigned once across the whole dataset.
Tiny boxes (smaller side `< --min` px) are dropped
(same policy as `filter_boxes.py` / `solo_preview.py`).

### Run
```bash
python3 tools/solo_to_yolo.py                       # -> ./yolo, no split by default
python3 tools/solo_to_yolo.py --split scenario --val-frac 0.2 --out yolo
```
It prints the class list, split counts, and boxes kept/dropped, then writes `data.yaml` and
`dataset_manifest.json`.

### data.yaml (example)
```yaml
path: /abs/path/yolo
train: images/train
val: images/val
nc: 3
names: [buoy, catamaran, swimmer]
```

### Train with it (Ultralytics)
```bash
pip install ultralytics
yolo detect train data=/abs/path/yolo/data.yaml model=yolo11n.pt epochs=50 imgsz=1280
```

### Notes
- **Default export makes no split.** It writes `images/all` and `labels/all`, so downstream
  tooling can preserve scenario grouping and split later.
- If you need a split at export time, use `--split scenario` so whole input roots are assigned
  to train/val together. `--split frame` exists only for compatibility and is not the preferred
  evaluation path.
- Water/sky are **not** in the YOLO output (they're regions, not detection boxes). If you later
  want YOLO **segmentation** (`-seg`) with water/sky polygons, that's a separate export from the
  `marine_classes` masks.

---

## 3. Clean the dataset first — `filter_boxes.py`

Run this on the SOLO data **before** exporting to YOLO. It drops two kinds of bad 2D boxes:
- **tiny** — objects whose box smaller side `< --min` px (too far/small to learn),
- **submerged** — objects whose 3D-box centre is **below the water line** (world y < `--water-level`).
  HDRP's transparent water doesn't occlude in Perception's label pass, so submerged objects get
  fully labeled even though the RGB hides them — this removes those over-labels.

```bash
python3 tools/filter_boxes.py                         # report only (counts)
python3 tools/filter_boxes.py --min 10 --water-level 0.0 --apply   # rewrite in place (.bak kept)
```
Submerged detection needs 3D boxes enabled on the Perception camera; without them only the tiny
filter runs.

## Recommended workflow (after stopping a recording)

```bash
# 1. finalise the recording (stop /dataset/control, exit Play so SOLO is written)
# 2. clean the labels in place
python3 tools/filter_boxes.py --apply
# 3. export the cleaned data to YOLO
python3 tools/solo_to_yolo.py
# 4. (optional) water/sky segmentation labels
python3 tools/marine_surface.py
```
`solo_to_yolo.py` reads the same `frame_data.json` that `filter_boxes.py` rewrote, so the YOLO
dataset excludes the tiny + submerged boxes automatically.

If you are using the newer scenario-manifest flow, the practical sequence is:

1. Generate and run short scenarios with `tools/generate_scenarios.py` and `tools/run_scenario_batch.py`.
2. Keep each scenario's outputs grouped together for later splitting.
3. Run `filter_boxes.py`, `marine_surface.py`, and `solo_to_yolo.py` as post-processing steps.
