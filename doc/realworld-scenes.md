# Real-World Scenes (lake maps, on the fly)

Generate a sim scene from a real lake. A parameterized pipeline fetches the lake's shape from
OpenStreetMap, projects it to local metres, and produces a **costmap** that drives traffic plus a
**shoreline** that builds the Unity land — so any lake/region becomes a scene by changing args.

Default target: **Lake Geneva** (cropped to a region of interest, since Léman is ~73 km).

---

## Pipeline

```
realworld_scene.py  ──►  <name>_costmap.png + _meta.json + _shoreline.json
   (fetch OSM water,          │                              │
    project, flood-fill)      ▼                              ▼
                     map_publisher (ROS)             RealWorldSceneLoader (Unity)
                     publishes /map ─► scenario_generator ─► /sim/tracks ─► traffic
                     (traffic on the real lake)      builds the land mesh (visual)
```

The costmap and the visual both derive from the **same** generated files, so they stay
consistent. The scenario generator is unchanged — it just reads a real `/map`.

---

## 1. Generate the scene (`tools/realworld_scene.py`)

```bash
# real Lake Geneva region (needs internet — OSM Overpass)
python3 tools/realworld_scene.py --name lake_geneva --lat 46.30 --lon 6.30 --extent 3000 --res 5

# offline synthetic lake, to test the whole pipeline without network
python3 tools/realworld_scene.py --demo --name demo_lake --extent 1500 --res 5
```
Args: `--lat/--lon` scene centre (**must be on water** — it's the flood-fill seed), `--extent`
half-size of the square in metres, `--res` metres/cell, `--out` (default `config/realworld`).

Outputs into `config/realworld/`:
- `<name>_costmap.png` — water=black (free), land=white (occupied)
- `<name>_meta.json` — origin (lat/lon + local metres) + resolution
- `<name>_shoreline.json` — shoreline polylines in metres (for Unity)
- `<name>_preview.png` — quick look (blue=water, green=land)

Open the preview and check the lake shape + that water is a sensible share. `config/realworld/`
is gitignored (regenerate any time).

---

## 2. Drive traffic on the real lake (ROS `map_publisher`)

`config/` is mounted into the container at `/n3mosim/config`, so the generated files are visible
to ROS. Rebuild once (new entry point), then publish:
```bash
docker compose build && docker compose up -d
docker compose exec ros_bridge bash -lc "source /opt/ros/humble/setup.bash && \
  source /root/ros2_ws/install/setup.bash && \
  ros2 run n3mo_control map_publisher --ros-args -p name:=lake_geneva"
```
It publishes the costmap as a **latched** `nav_msgs/OccupancyGrid` on `/map`. The scenario
generator (already remapped `costmap_static:=/map`, `gen_on_first_costmap:=true`) then generates
traffic on the real lake and streams `/sim/tracks`.

> Use **either** `map_publisher` **or** Unity's `OccupancyGridPublisher` as the `/map` source,
> not both. For a real-world map, disable `OccupancyGridPublisher` in the scene.

---

## 3. Build the visual land in Unity (`RealWorldSceneLoader`)

1. Empty GameObject `RealWorldScene` → add **`RealWorldSceneLoader`** (it needs a MeshFilter +
   MeshRenderer, added automatically).
2. Fields: **Scene Name** = `lake_geneva`, **Dir** = `config/realworld`, **Land Height** ≈ 2 m,
   **Max Cells** ≈ 128, **Land Material** = a terrain-ish material.
3. Play (or right-click → **Build Now**). It raises a land mesh over the land cells; the lake
   cells stay open so the existing HDRP water shows through.

The land uses the same metric frame as the costmap (ROS `(x,y)` → Unity `(x, landHeight, z=y)`,
centred at the origin), so it lines up with the traffic.

---

## Test (offline, end to end)

```bash
python3 tools/realworld_scene.py --demo --name demo_lake --extent 1500 --res 5
```
- open `config/realworld/demo_lake_preview.png` — a wobbly circular lake.
- point `map_publisher` and `RealWorldSceneLoader` at `demo_lake` to exercise the ROS + Unity
  paths without internet.

## Notes / on-the-fly use

- **Regenerate for any lake/region** by changing `--name/--lat/--lon/--extent/--res`, then
  re-run `map_publisher` (`-p name:=<new>`) and Unity **Build Now**. That's the "on the fly" loop.
- **Boat spawn** must be inside the lake water — set `agent_01`'s position (Scene.json) near the
  centre `(0,0)` of the chosen region.
- **Scale:** big lakes → crop with `--extent`, or coarsen `--res` (watch the generator's erosion
  cost at fine resolution).
- **Projection:** local equirectangular about the centre — accurate over a few km; fine for a
  regional scene.
- **Overpass limits:** the fetch hits the public OSM Overpass API; keep extents modest and don't
  hammer it. Complex multipolygon shorelines may need a larger `width` on the shoreline barrier.
