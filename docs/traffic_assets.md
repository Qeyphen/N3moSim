# Traffic Assets: Rebuild and Validation

How to keep every `TrackSpawner` prefab visible, upright, floating, and correctly
labeled in the captures. Follow this after touching any traffic prefab, and run
the full checklist before producing a dataset.

## Spawner contract

`TrackSpawner` assumes every prefab faces **+Z** with **+Y** up, and it
**overwrites the root transform every frame** (heading via `LookRotation`,
position at sea level). Consequences:

- Axis corrections (models authored Z-up, etc.) must live on a **child**
  transform, never on the prefab root. A correction on the root is silently
  wiped at spawn (this is how the catamaran ended up mast-down).
- `NormalizeVisualRoot` re-centres children so the aggregate renderer bounds
  sit at `waterlineOffset`; prefabs still need sane pivots for it to work.

## Rebuilding the missing wrapper prefabs (editor)

The models are tracked in `Assets/Models/`; only the wrapper prefabs are
missing. For each of `Pedalo`, `InflatableRaft`, `Swimmer`:

1. Drag the model (`Assets/Models/Pedalo.fbx`, `Assets/Models/InflatableRaft/InflatableRaft.fbx`,
   `Assets/Models/Swimmer.fbx`) into the scene.
2. Create an empty root GameObject named after the type, reset its transform,
   and parent the model instance under it.
3. Rotate/offset the **model child** so the object faces +Z, sits upright, and
   the hull rests around y=0.
4. Add a **Labeling** component on the root with the labels:
   - Pedalo: `pedalo`, `dynamic_obstacle`
   - InflatableRaft: `raft`, `dynamic_obstacle`
   - Swimmer: `dynamic_obstacle` (plus the swimmer label present in
     `Assets/Perception/IdLabelConfig.asset`)
5. Drag the root to `Assets/Prefabs/<Name>.prefab`, delete the scene instance.
6. Wire the matching `TrackSpawner` override slot in the scene
   (Pedalo type, Dinghy type for the raft, Swimmer type) and save the scene.

## Per-type validation checklist

Run the smoke plan (`tools/run_dataset_plan.py` with a 2-scenario plan), pause
Play mode, and check every spawned `track_*` object:

| Check | How |
|---|---|
| Visible | The mesh renders in Game view (not the empty-selection gizmo) |
| Upright | Mast/hull orientation correct, bow facing travel direction |
| Floating | Hull at the waterline, neither airborne nor submerged |
| Labeled | The type's label appears in the run's `*.frame_data.json` |

Then scan the annotations of the produced frames: every label present must
correspond to an object actually visible in the RGB image.

## Known limitation: water does not occlude annotations

HDRP water does not render into Perception's segmentation passes. A submerged
object is therefore still annotated while being invisible in RGB. Any type that
fails the "Floating" check pollutes the dataset with boxes on invisible
objects and must be fixed before generation.
