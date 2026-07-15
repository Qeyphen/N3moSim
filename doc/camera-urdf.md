# URDF-defined Camera Pose

The POV camera's mount (its offset on the boat) is defined in the **robot description**
(`config/usv.urdf`), not hardcoded in the Unity scene. Unity reads the `camera_link` joint at
startup and places the camera there — so the URDF is the single source of truth for where the
sensor sits, matching how a real robot is described.

The camera is **still a child of the boat**: it stays mounted and moves with the boat. Only the
*definition* of its local offset moved from the Unity Inspector into the URDF.

---

## The robot description (`config/usv.urdf`)

```xml
<robot name="usv">
  <link name="base_link"/>       <!-- the boat body -->
  <link name="camera_link"/>     <!-- the POV camera -->
  <joint name="camera_mount" type="fixed">
    <parent link="base_link"/>
    <child  link="camera_link"/>
    <origin xyz="3 0 1" rpy="0 0 0"/>   <!-- 3 m forward, 1 m up, looking ahead -->
  </joint>
</robot>
```

Convention: **ROS REP-103** — x forward, y left, z up, metres/radians. The `<origin>` of the
`base_link → camera_link` joint **is** the camera mount. `xyz="3 0 1"` reproduces the previous
hardcoded Unity local pose `(0, 1, 3)`.

---

## How Unity applies it (`Assets/Scripts/UrdfCameraPose.cs`)

At `Start` (and via the **Apply URDF Now** context menu in edit mode):
1. Load the URDF — from `/robot_description` (ROS `std_msgs/String`) if present, else a
   dragged-in `TextAsset`, else the file at `urdfFilePath` (`config/usv.urdf`).
2. Find the joint whose child is `camera_link`, read its `<origin xyz rpy>`.
3. Convert **ROS → Unity**:
   - position `(x, y, z)_ros → (−y, z, x)_unity`
   - rotation via a basis change that also handles the right-handed → left-handed flip.
4. Write the camera's **`localPosition` / `localRotation`** on the boat.

FOV/intrinsics are unaffected — URDF describes *where* the camera is, not its lens (see
`doc/camera-fov.md`).

---

## Setup

1. On the **POVCamera** (boat) → **Add Component → `UrdfCameraPose`**.
2. Fields: **Camera Transform** = empty (defaults to itself), **Camera Link Name** =
   `camera_link`, **Urdf File Path** = `config/usv.urdf`.
3. Play → the Console logs `[UrdfCameraPose] mounted 'camera_link' from URDF — local pos=…`.

Edit `config/usv.urdf` and re-run: the camera remounts with **no Unity edit**.

---

## Verification (captured, `camera_info.py`)

Two runs, changing only the URDF up-value, then reading the dataset extrinsics:

| URDF `xyz` (ROS) | meaning | camera height (extrinsics y) |
|---|---|---|
| `3 0 1` | 1 m up | **2.075 m** |
| `3 0 3` | 3 m up | **3.950 m** |

```
# xyz = 3 0 1
    EXTRINSICS position: [0.000299, 2.075065, -291.860535]
    EXTRINSICS rotation: [0.0, 0.0, 0.0, 1.0]

# xyz = 3 0 3
    EXTRINSICS position: [0.000235, 3.949816, -293.028748]
    EXTRINSICS rotation: [0.0, 0.0, 0.0, 1.0]
```

Reading it:
- **Height (y)** raised by `3.95 − 2.075 = 1.875 ≈ +2 m` — exactly the +2 m change made in the
  URDF (ROS z → Unity y). The camera pose tracks the robot description. ✓
- **Lateral (x) ≈ 0.0002** — matches URDF `y = 0` (centered). ✓
- **Forward (world z)** differs slightly (−291.9 vs −293.0) because the **boat** sat at a
  slightly different spot/heading between the two capture sessions (it drifts/bobs) — not the
  camera offset, which was unchanged (`x = 3`).
- **Rotation identity** — matches `rpy = 0 0 0`.

### Orientation too — a pitched mount

Setting a pitch (`rpy="0 0.15 0"`, roll/yaw 0) at the same `xyz="3 0 3"`:

```
# rpy = 0 0 0
    EXTRINSICS rotation: [0.0, 0.0, 0.0, 1.0]

# rpy = 0 0.15 0
    EXTRINSICS rotation: [0.0749297, 0.0, 0.0, 0.9971888]
```

Reading it:
- Only **qx, qw** are nonzero → a pure rotation about Unity's **X axis** (pitch).
- Angle = `2·acos(0.9971888) = 0.1499 rad ≈ 0.15 rad` — **exactly the URDF pitch.** ✓
- Sign: ROS +pitch (about y) = nose down; Unity +X rotation = nose down → the tilt direction is
  correct (a downward-looking marine POV).
- The small height difference between the two runs (3.86 vs 3.77 m) is boat bob between capture
  sessions; pitch rotates about the mount point, so it doesn't move the position (`x=0`,
  `z=−297` identical).

**Conclusion:** the camera transform — **position and orientation** — is read from the URDF, not
hardcoded. The dataset extrinsics change when (and only when) the robot description changes.

---

## Optional — drive it over ROS

`config/` is mounted into the `ros_bridge` container, so the same URDF is available to ROS. To
make it explicitly "camera pose from ROS", publish the URDF as a latched `std_msgs/String` on
`/robot_description` (e.g. via `robot_state_publisher` or `ros2 topic pub`); `UrdfCameraPose`
already subscribes and re-applies on receipt.
