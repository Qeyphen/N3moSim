# Phase 2 — Enrich the Labels

**Goal:** take the Phase-1 vertical slice (RGB + boxes + seg + depth) and make each frame
**richer and correct** — exclude the ego boat, verify depth is metric, surface the camera
calibration, add per-object range/bearing/closing-speed, and extend the semantic taxonomy to
the marine-standard `water / sky / static_obstacle / dynamic_obstacle`.

Branch: `phase-2` (rebased on top of the scenario-generator work, so Phase 2 can be validated
against varied moving traffic instead of just static buoys).

A theme of Phase 2: **don't fight the engine — read the ground truth Unity already produces and
verify it with small read-only Python tools.** Five tools resulted (one per concern), all
auto-finding the latest SOLO dataset.

---

## Item 1 — Ego-vessel exclusion  ✅

**Problem:** the POV camera sits on the ego boat and sees its own hull/bow; Perception would
label that hull as a `vessel` obstacle — a false positive in every frame.

**Fix (`DatasetCaptureScheduler.cs`):** a new `excludeOwnVessel` (default true). In `Start()`:
```csharp
Labeling own = GetComponentInParent<Labeling>();   // the boat root; camera is its child
if (own != null) { own.labels.Clear(); own.RefreshLabeling(); }
```
Clearing the labels + `RefreshLabeling()` makes the ego boat carry **no label**, so no labeler
captures it. It targets only *this* camera's vessel (`GetComponentInParent`), so the traffic
catamarans (separate instances) are untouched.

---

## Item 2 — Depth sanity  ✅ (with a finding)

**Goal:** the camera writes a depth EXR every frame; confirm the values are real **metres** and
make depth viewable.

**Tool — `tools/depth_preview.py`** (OpenCV, because Pillow can't read float EXR). It opens the
depth file, prints stats, and saves a colorized PNG (no-data = black, near = blue, far = red).

**Findings (technical):**
- The depth is a **4-channel (RGBA) float EXR**; OpenCV reads it as **BGRA**, and the depth
  lives in **channel 2 (the R channel)**; channel 3 is a 0/1 mask. The tool auto-picks the
  channel with real data.
- **Values are metres** — confirmed by geometry: the buoy/island pixels read ~120–380 m, which
  matches the boat-at-`(0,−300)`→obstacle distances. (Cross-checked again by Item 4's range.)
- **Coverage ≈ 28%.** ~72% of pixels are 0, and the nearest depth is ~118 m — i.e. **the water
  surface in front of the boat writes no depth.** Only *solid* geometry (island, buoys, traffic)
  has depth.

**Root cause:** the **HDRP water is a transparent surface that doesn't participate in
Perception's depth pass.** This is fine for obstacle *range* (depth exists exactly on the
obstacles), but full-scene/water depth is missing → folded into the **P3 marine-surface task**.

---

## Item 3 — Camera intrinsics + extrinsics  ✅

**Goal:** each frame must carry the camera math so 3D boxes/depth can be projected world↔image.

**Result:** Perception **already writes them** into every SOLO capture — no new capture code.
Verified with **`tools/camera_info.py`**:
- **Extrinsics:** `position` + `rotation` (quaternion) — the camera pose. Confirmed sitting on
  the ego boat (`~[0.07, 2.6, −297]`, slight pitch-down).
- **Intrinsics:** the `matrix` field — but in **Unity NDC form**, *not* pixel units:
  `fx = 1/tan(hfov/2)`, `fy = 1/tan(vfov/2)`, principal point in NDC (0 = centre).
  Observed `fx=0.97, fy=1.73` ⇒ `fy/fx = 1.78 = 16:9` ⇒ **60° vertical / 92° horizontal FOV**.

**The conversion (important — a common 2× mistake):** to get OpenCV pixel intrinsics,
```
fx_px = fx · width/2   (≈ 621)        cx_px = (1+cx)·width/2  = 640
fy_px = fy · height/2  (≈ 623)        cy_px = (1−cy)·height/2 = 360
```
It is **width/2**, not width. The tool prints both the NDC values and the converted pixel
intrinsics + FOV so downstream code (3D-box projection, Item 4) uses the right numbers.

---

## Item 4 — Per-object range / bearing / closing speed  ✅

**Goal:** augment each visible obstacle with metric *relative geometry* — how far, which way,
approaching how fast.

**Tool — `tools/range_bearing.py`.** It reads each frame's **3D bounding boxes** (Unity ground
truth, **camera-space** centre `(x,y,z)`: z forward, x starboard, y up) and computes, per object:
```
range   = √(x² + z²)             # horizontal distance across the water (metres)
range3d = √(x² + y² + z²)
bearing = atan2(x, z)            # degrees; 0 = dead ahead, + = starboard, − = port
```
(These are just **polar coordinates of the obstacle relative to the bow** — see the range/bearing
explainer.) Validated exactly: buoy_03 read `range=213.9 m, bearing=−37°`, matching
`√(120² + 177²)=213.8 m` for the camera→buoy geometry, confirming the translation is camera-space.

**Closing speed** = range rate vs the previous frame, `(prev_range − range)/dt` (+ = approaching),
with frames **numerically time-ordered** (step0,1,…) and `dt = 1/3 s` (the 3 Hz capture rate).
Idle boat → ~0 (correct).

**Output:** a per-frame `metadata/<frame>_objects.json` with `range_m / range3d_m / bearing_deg
/ closing_mps` per object — the "per-object metadata into each frame" deliverable.

*Coverage note:* only **labeled, in-view** objects appear. For richer metadata, label the island
and capture with traffic in frame — a scene-setup choice; the tool handles however many appear.

---

## Item 5 — Semantic classes (water / sky)  ⚠️ partial → P3

**Goal:** extend semantic seg to the full marine taxonomy.

**Tool — `tools/semantic_preview.py`** (Pillow + numpy): reads the semantic mask PNG + the
per-frame class→color map and reports **per-class pixel coverage**.

**Baseline:** only the obstacle class (`buoy`, purple) appears, at ~0% (far/tiny), and
**~100% of pixels are "background"** — i.e. **water + sky carry no class**.

**What works:** *solid* obstacles render in the seg pass (buoys, traffic, and the **island** if
labeled). Labeling those is valid Phase-2 work: `vessel` on traffic, `static_obstacle`/`island`
on the island, `buoy` on buoys.

**What doesn't:** labeling the **HDRP water surface** `water` produces **no water pixels** — the
**same transparent-surface limitation as depth** (the seg replacement-shader pass skips the
water). And **sky has no geometry**, so it can't carry a `Labeling` at all.

**Decision:** water + sky semantic seg share the *identical root cause* as the missing water
depth (Item 2). Both are folded into a single **Phase-3 "marine-surface ground truth" task**,
solved by either **horizon synthesis** (below the camera-derived horizon − obstacle masks =
water; above = sky) or making HDRP water write to the depth/seg passes.

---

## Cross-cutting finding — HDRP water vs Perception's ground-truth passes

The single most important Phase-2 discovery: **HDRP water (a transparent surface) does not
participate in Perception's GPU ground-truth passes** (depth *or* semantic/instance seg). Solid
geometry does. This is why:
- water depth is missing (Item 2), and
- water/sky semantic is missing (Item 5).

Everything Perception *can* produce for the obstacles — RGB, 2D/3D boxes, instance/semantic seg,
metric depth, pose, intrinsics, range/bearing — is verified working. The water surface is the
one gap, cleanly bucketed for P3.

---

## Tools delivered in Phase 2

| Tool | Reads | Produces |
|---|---|---|
| `solo_preview.py` *(P1)* | 2D boxes + RGB | boxes drawn on RGB |
| `depth_preview.py` | depth EXR | metres stats + colorized depth, coverage % |
| `camera_info.py` | capture pose + matrix | extrinsics + NDC & pixel intrinsics + FOV |
| `range_bearing.py` | 3D boxes | per-frame `metadata/*_objects.json` (range/bearing/closing) |
| `semantic_preview.py` | semantic mask | per-class coverage % |

All are read-only, dependency-light (`pillow`, `opencv-python`, `numpy`, stdlib), and auto-find
the latest SOLO dataset.

## Status

| # | Item | Status |
|---|---|---|
| 1 | Ego-vessel exclusion | ✅ done |
| 2 | Depth sanity | ✅ metres on obstacles; **water depth → P3** |
| 3 | Camera intrinsics/extrinsics | ✅ verified + correct pixel conversion |
| 4 | Range / bearing / closing speed | ✅ done, written per frame |
| 5 | Water / sky semantic | ⚠️ obstacles ✅; **water/sky → P3** (HDRP-water limitation) |

**Phase 2 is complete to the limit of what Perception/HDRP allow**, with the two water-surface
items merged into one well-defined Phase-3 task.
