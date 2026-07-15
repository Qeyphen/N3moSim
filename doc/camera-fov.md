# Camera Field of View (FOV) — definition, configuration & verification

The POV camera's **field of view** is the angular width of the world it sees. It's not just a
look — FOV defines the **camera intrinsics** (focal length + principal point) written into every
labeled SOLO frame, which is what lets the 3D boxes and depth be projected onto the image. So
configuring FOV = choosing/calibrating the virtual lens the dataset is captured through.

---

## What FOV is

FOV is measured in degrees. Because the image is a rectangle (1280×720, 16:9), it has two
linked values:

- **Vertical FOV (vFOV)** — angle top-to-bottom. Unity's `Camera.fieldOfView` stores this.
- **Horizontal FOV (hFOV)** — angle left-to-right; wider than vertical on 16:9.
- Related by aspect: `hFOV = 2·atan( tan(vFOV/2) · aspect )`.

Wide FOV = sees more, objects look small/far (GoPro). Narrow FOV = thin slice, objects look
zoomed-in (telephoto). Same position, different FOV = a completely different image.

---

## Configuration (POV camera, Unity)

On the POV camera's **Camera** component:

| Parameter | Value | Why |
|---|---|---|
| **Projection** | Perspective | FOV only applies to perspective (not orthographic) |
| **FOV Axis** | Vertical | keeps a fixed vertical framing regardless of aspect |
| **Field of View** | **60°** | the chosen vertical FOV; 16:9 makes horizontal ≈ 92° |
| **Clipping — Near** | 0.3 m | standard; smaller wastes depth precision |
| **Clipping — Far** | 1000 m | max render distance; also sets the depth EXR range |
| **Capture resolution** | 1280×720 (16:9) | fixes the horizontal FOV; the SOLO image size |

Notes:
- Vertical axis is deliberate: vertical FOV stays 60° even if the aspect changes.
- **Far plane at sea:** 1000 m covers current traffic (obstacles at ~120–380 m). Raise it to
  5000–10000 m if you want distant traffic or a visible horizon; a larger far plane slightly
  reduces depth-EXR precision.
- (Optional) **Physical Camera** mode lets you enter a real focal length (mm) + sensor size to
  emulate a specific real lens; the plain FOV angle is otherwise sufficient.

---

## Verification

FOV must actually land in the per-frame intrinsics. Capture at least one frame (press `R`, or
`/dataset/control` = true, then stop and exit Play so the SOLO dataset finalises), then run:

```bash
python3 tools/camera_info.py
```

### Verified sample output

```
capture id='camera'  @type='type.unity.com/unity.solo.RGBCamera'
    EXTRINSICS position: [0.0, 1.80755329, -297.0]
    EXTRINSICS rotation: [0.0, 0.0, 0.0, 1.0]
    image dimension (w,h): [1280.0, 720.0]
    INTRINSICS (Unity NDC): fx=0.9743 fy=1.7321 cx=0.0000 cy=0.0000
      -> FOV: horizontal=91.5deg  vertical=60.0deg
    INTRINSICS (pixels):   fx=623.5 fy=623.5 cx=640.0 cy=360.0   (for OpenCV / projecting 3D boxes)
    -> extrinsics: OK | intrinsics: OK
```

### Reading it

- **vertical = 60.0°** — exactly the value set on the camera. ✓
- **horizontal = 91.5°** — derived from 60° at 16:9 (the expected ~92°). ✓
- **fy/fx = 1.7321 / 0.9743 = 1.778 = 16:9** — confirms the aspect ratio. ✓
- **image dimension = 1280×720** — the capture resolution. ✓
- **pixel intrinsics fx = fy = 623.5 px** — the focal length in pixels produced by a 60° FOV
  (`fx_px = fx_ndc · width/2`, `fy_px = fy_ndc · height/2`).
- **cx = 640, cy = 360** — the principal point, exactly the image centre (1280/2, 720/2). ✓
- **extrinsics: OK | intrinsics: OK** — the tool validated both.

### About the extrinsics in this sample

- `position: [0, 1.81, -297]` — the camera ~1.8 m above the water at the boat's spawn point.
- `rotation: [0, 0, 0, 1]` — identity, i.e. level and looking straight along +Z (boat idle at
  spawn). Once the boat moves/turns during a real run, the per-frame rotation becomes non-identity;
  the pose is recorded every frame.

**Intrinsics (NDC) note:** Unity writes the intrinsics in NDC form, not pixels —
`fx_ndc = 1/tan(hfov/2)`, `fy_ndc = 1/tan(vfov/2)`, principal point 0 = centre. `camera_info.py`
prints both the NDC values and the OpenCV pixel conversion so downstream 3D-box projection uses
the right numbers.

---

## Summary

FOV is **defined** (60° vertical), **configured** (Vertical axis, near 0.3 / far 1000, 1280×720),
and **verified** — the intrinsics baked into every labeled frame match (60°/91.5°, fx=fy≈623.5 px,
principal point centred). This calibration makes the dataset geometrically consistent, so the 3D
boxes and depth project correctly onto the RGB image.
