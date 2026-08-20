# Synthetic Perception Dataset — TODO

> Historical note: this file tracks the earlier perception-roadmap work. The active
> implementation plan for the current dataset-remediation effort lives in the project root
> [`todo.md`](../todo.md).

## Goal
Generate a **production-grade synthetic labeled perception dataset** from the Unity marine
sim to train an ML model for **obstacle detection / segmentation on an autonomous sailboat**,
with **sim-to-real transfer** in mind. The sim's ground truth gives perfect, automatic labels
(2D/3D boxes + instance/semantic segmentation + depth) from the boat's own camera POV, recorded
on demand and packaged for training.

---

## Done
- [x] **Phase 0 — Spike.** Verified Unity Perception works on HDRP / Unity 6.3 (boxes +
      instance + semantic + EXR depth all render correctly).
- [x] **Phase 1 — Vertical slice.** Boat-POV Perception camera; on-demand recording via ROS
      topic `/dataset/control` (std_msgs/Bool), `R` hotkey, or Inspector toggle; captures RGB +
      2D/3D boxes + instance/semantic seg + depth at 3 Hz; `tools/solo_preview.py` overlays
      boxes to verify labels. *(on `main`)* — see [phase-1.md](phase-1.md).
- [x] **Phase 2 — Enrich the labels.** *(branch `phase-2`)* — see [phase-2.md](phase-2.md).
      - [x] Ego-vessel exclusion — `DatasetCaptureScheduler.excludeOwnVessel` clears the
            ego boat's `Labeling` so it never labels its own hull.
      - [x] Per-object metadata: range, bearing, closing speed — `tools/range_bearing.py`
            from the 3D boxes, written to `metadata/<frame>_objects.json`.
      - [x] Camera intrinsics + extrinsics — Perception already writes pose + projection
            `matrix` per frame; `tools/camera_info.py` verifies + converts NDC→pixels.
      - [x] Depth sanity — `tools/depth_preview.py` confirmed depth EXR is **metres**
            (channel 2 / R), on solid obstacles. **Water/sky depth is missing** (HDRP water
            doesn't write to the depth pass) → folded into the P3 water-surface task.
      - [x] Semantic classes — obstacle classes render in seg (`tools/semantic_preview.py`);
            label `water` on the surface + `island`/`static_obstacle` on the island + `vessel`
            on traffic. **Water/sky pixels don't render** (same HDRP cause as depth) → P3.

---

## Phase 3 — Scale + realism (domain randomization)
- [x] Short-scenario manifest workflow:
      `tools/generate_scenarios.py` generates scenario specs and
      `tools/run_scenario_batch.py` executes them through Docker/ROS/Unity with fixed per-scenario
      environment settings and duration-based `dataset_sweep` runs.
- [x] Keep weather/time stable within a scenario by driving them once per scenario and disabling
      mid-run environment randomization in the batch workflow.
- [x] Live capture-rate control via `/dataset/capture_hz`, so the scenario manifest can specify
      the sampling rate explicitly.
- [x] Keep generated traffic away from authored scene objects and from overlapping generated
      spawns by using `/scene/objects` as exclusion zones in the scenario generator.
- [ ] **Marine-surface ground truth (carried from P2):** make the HDRP water participate in
      Perception's depth + semantic-seg passes — it currently writes neither (transparent
      surface skipped by the labeler passes). Two routes: (a) **horizon synthesis** — derive
      water/sky from the camera pitch/height (extrinsics) + obstacle masks: below horizon −
      obstacles = water, above = sky; (b) make HDRP water write depth/seg directly. Covers
      both **water depth** (P2 #2) and **water/sky semantic** (P2 #5).
- [ ] Randomize: sea state/waves, time-of-day/sun, fog/weather, water color
- [ ] Randomize: obstacle types/counts/positions (← scenario generator), camera jitter, sensor noise
- [ ] Seeded for reproducibility
- [ ] Headless batch generation (`-batchmode`) — thousands of frames across scenarios
      *(blocked by the Perception/HDRP shader-warmup segfault under Vulkan/Xvfb — see headless.md)*

## Phase 4 — ROS temporal layer + packaging
- [ ] Record rosbag (poses, controls, agents) synced to frames via `/dataset/frame` marker
- [ ] Package each session: images + masks + depth + rosbag + manifest → versioned zip

## Phase 5 — Export + dataset hygiene
- [ ] Exporters: SOLO → COCO/YOLO (detection), palette PNG (seg), depth tensors, npz/WebDataset
- [ ] Leakage-free train/val/test splits (split by **scenario**, not frame)
- [ ] Dataset manifest / data card
- [ ] QC: class balance, label-overlay audits
