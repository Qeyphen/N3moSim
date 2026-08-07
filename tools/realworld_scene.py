#!/usr/bin/env python3
"""Generate a sim scene from a real-world lake: fetch OSM water, project to metres, rasterize a costmap.

Outputs (into --out): <name>_costmap.png (water=black/free, land=white/occupied),
<name>_meta.json (origin + resolution), <name>_shoreline.json (polylines in metres, for Unity),
<name>_preview.png. Feed the costmap to map_publisher (ROS -> /map) and the shoreline to Unity.

Usage:
  python3 realworld_scene.py --name lake_geneva --lat 46.30 --lon 6.30 --extent 3000 --res 5
  python3 realworld_scene.py --demo         # synthetic lake, no network
"""

import argparse
import json
import math
import os
import urllib.request
from collections import deque

import numpy as np
from PIL import Image, ImageDraw

OVERPASS = "https://overpass-api.de/api/interpreter"


def local_proj(lat0, lon0):
    """Equirectangular lat/lon -> local metres about (lat0, lon0) (accurate over a few km)."""
    mlat = 110540.0
    mlon = 111320.0 * math.cos(math.radians(lat0))
    return lambda lat, lon: ((lon - lon0) * mlon, (lat - lat0) * mlat)


def fetch_water_ways(lat, lon, extent):
    """OSM water-boundary polylines within the bbox, as lists of (lat, lon).

    Big lakes are multipolygon RELATIONS whose shoreline ways aren't individually tagged, so
    query relations too and pull their member way geometries (the actual shore).
    """
    dlat = extent / 110540.0
    dlon = extent / (111320.0 * math.cos(math.radians(lat)))
    s, w, n, e = lat - dlat, lon - dlon, lat + dlat, lon + dlon
    bbox = f"{s},{w},{n},{e}"
    q = (f"[out:json][timeout:90];("
         f"way[natural=water]({bbox});relation[natural=water]({bbox});"
         f"way[water]({bbox});relation[water]({bbox}););out geom;")
    req = urllib.request.Request(OVERPASS, data=q.encode(), headers={"User-Agent": "n3mosim"})
    data = json.load(urllib.request.urlopen(req, timeout=120))

    ways, n_way, n_rel = [], 0, 0
    for el in data.get("elements", []):
        if el.get("type") == "way" and el.get("geometry"):
            ways.append([(p["lat"], p["lon"]) for p in el["geometry"]])
            n_way += 1
        elif el.get("type") == "relation":
            for m in el.get("members", []):
                g = m.get("geometry")
                if g and len(g) >= 2:
                    ways.append([(p["lat"], p["lon"]) for p in g])
            n_rel += 1
    print(f"  {n_way} way(s) + {n_rel} relation(s) -> {len(ways)} shoreline polyline(s)")
    return ways


def demo_ways(lat, lon, extent):
    """A synthetic roughly-circular lake shoreline, for offline testing."""
    proj_inv_lat = 110540.0
    proj_inv_lon = 111320.0 * math.cos(math.radians(lat))
    r = extent * 0.7
    pts = []
    for k in range(180):
        a = 2 * math.pi * k / 180
        rr = r * (1 + 0.15 * math.sin(3 * a))       # wobble the shore
        x, y = rr * math.cos(a), rr * math.sin(a)
        pts.append((lat + y / proj_inv_lat, lon + x / proj_inv_lon))
    pts.append(pts[0])
    return [pts]


def rasterize(ways, proj, extent, res):
    """Shoreline polylines -> occupancy grid (0=water, 100=land) via flood-fill from the centre."""
    n = int(2 * extent / res)
    def to_px(x, y):
        col = int((x + extent) / res)
        row = int((extent - y) / res)      # top row = +y (north)
        return col, row

    barrier = Image.new("L", (n, n), 0)
    draw = ImageDraw.Draw(barrier)
    shorelines_m = []
    for way in ways:
        pm = [proj(lat, lon) for lat, lon in way]
        shorelines_m.append(pm)
        px = [to_px(x, y) for x, y in pm]
        draw.line(px, fill=255, width=2)
    barrier = np.array(barrier) > 0

    water = np.zeros((n, n), bool)
    cx, cy = n // 2, n // 2                 # centre assumed on the lake
    if not barrier[cy, cx]:
        q = deque([(cy, cx)])
        water[cy, cx] = True
        while q:
            r0, c0 = q.popleft()
            for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                r1, c1 = r0 + dr, c0 + dc
                if 0 <= r1 < n and 0 <= c1 < n and not water[r1, c1] and not barrier[r1, c1]:
                    water[r1, c1] = True
                    q.append((r1, c1))

    occ = np.where(water, 0, 100).astype(np.uint8)
    return occ, shorelines_m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="lake_geneva")
    ap.add_argument("--lat", type=float, default=46.30)
    ap.add_argument("--lon", type=float, default=6.30)
    ap.add_argument("--extent", type=float, default=3000.0, help="half-size of the square, metres")
    ap.add_argument("--res", type=float, default=5.0, help="metres per cell")
    ap.add_argument("--out", default="config/realworld")
    ap.add_argument("--demo", action="store_true", help="synthetic lake, no network")
    args = ap.parse_args()

    proj = local_proj(args.lat, args.lon)
    if args.demo:
        ways = demo_ways(args.lat, args.lon, args.extent)
        print("demo mode: synthetic circular lake")
    else:
        print(f"fetching OSM water near {args.lat},{args.lon} (±{args.extent} m)...")
        ways = fetch_water_ways(args.lat, args.lon, args.extent)
        print(f"  {len(ways)} water way(s)")
        if not ways:
            print("no water found — check the centre/extent, or try --demo")
            return

    occ, shorelines = rasterize(ways, proj, args.extent, args.res)
    water_pct = 100.0 * (occ == 0).mean()
    print(f"grid {occ.shape[1]}x{occ.shape[0]} @ {args.res} m/cell — water {water_pct:.1f}%")
    if water_pct < 2:
        print("  ! almost no water — the centre may be on land or the shore didn't close.")

    os.makedirs(args.out, exist_ok=True)
    base = os.path.abspath(os.path.join(args.out, args.name))

    # costmap.png: water=0 (black/free), land=255 (white/occupied). ascontiguousarray -> safe save.
    costmap = np.ascontiguousarray(np.where(occ == 0, 0, 255).astype(np.uint8))
    Image.fromarray(costmap, mode="L").save(base + "_costmap.png")
    print(f"  wrote {base}_costmap.png")

    prev = np.zeros((*occ.shape, 3), np.uint8)
    prev[occ == 0] = (30, 90, 200)      # water
    prev[occ == 100] = (60, 110, 60)    # land
    Image.fromarray(prev, mode="RGB").save(base + "_preview.png")
    print(f"  wrote {base}_preview.png")

    meta = {
        "name": args.name, "origin_lat": args.lat, "origin_lon": args.lon,
        "resolution_m": args.res, "width": occ.shape[1], "height": occ.shape[0],
        "origin_x_m": -args.extent, "origin_y_m": -args.extent,
    }
    json.dump(meta, open(base + "_meta.json", "w"), indent=2)
    json.dump({"lines_m": [[list(p) for p in ln] for ln in shorelines]},
              open(base + "_shoreline.json", "w"))
    print(f"  wrote {base}_meta.json / _shoreline.json")
    print("next: publish it with map_publisher (ROS) and load the shoreline in Unity.")


if __name__ == "__main__":
    main()
