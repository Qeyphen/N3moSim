#!/usr/bin/env python3
"""Per-object range + bearing from a Unity Perception SOLO dataset's 3D boxes.

Writes metadata/<frame>_objects.json per frame and prints a summary.
Usage: python3 range_bearing.py [/path/to/solo]
"""

import glob
import json
import math
import os
import re
import sys

BBOX3D = "BoundingBox3DAnnotation"
DEFAULT_HZ = 3.0   # capture rate — used as the dt for closing speed (no per-frame timestamp)


def step_num(fp):
    """Numeric step index from 'stepN.frame_data.json' for correct time ordering."""
    m = re.search(r"step(\d+)", os.path.basename(fp))
    return int(m.group(1)) if m else 0


def find_latest_solo():
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".config/unity3d/*/*/solo*"),
        os.path.join(home, "Library/Application Support/*/*/solo*"),
    ]
    dirs = [d for pat in patterns for d in glob.glob(pat) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def boxes3d(data):
    for cap in data.get("captures", []):
        for ann in cap.get("annotations", []):
            if BBOX3D in ann.get("@type", ""):
                return ann.get("values", [])
    return []


def process_frame(fp, dump_format=False):
    data = json.load(open(fp))
    boxes = boxes3d(data)

    if dump_format:
        print(f"  3D-box annotation found: {bool(boxes)}; {len(boxes)} box(es)")
        if boxes:
            print(f"  sample box keys: {sorted(boxes[0].keys())}")
            print(f"  sample box: {json.dumps(boxes[0])[:300]}")

    out = []
    for b in boxes:
        t = b.get("translation") or b.get("position")   # camera-space box center
        if not t or len(t) < 3:
            continue
        tx, ty, tz = float(t[0]), float(t[1]), float(t[2])
        rng   = math.hypot(tx, tz)                       # horizontal range across the water
        rng3d = math.sqrt(tx * tx + ty * ty + tz * tz)
        bearing = math.degrees(math.atan2(tx, tz))       # 0 = ahead, + = starboard
        out.append({
            "label": b.get("labelName"),
            "instanceId": b.get("instanceId"),
            "range_m": round(rng, 2),
            "range3d_m": round(rng3d, 2),
            "bearing_deg": round(bearing, 1),
            "translation": [round(tx, 2), round(ty, 2), round(tz, 2)],
        })

    return out


def write_metadata(fp, objs):
    out_dir = os.path.join(os.path.dirname(fp), "metadata")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.basename(fp).replace("frame_data.json", "objects.json")
    with open(os.path.join(out_dir, stem), "w") as f:
        json.dump(objs, f, indent=2)


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else find_latest_solo()
    if not root:
        print("No SOLO dataset found. Pass the path: range_bearing.py <dir>")
        return

    frames = sorted(glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True))
    if not frames:
        print(f"no *frame_data.json under {root}")
        return

    # Time order: group by sequence dir, then by numeric step (so closing speed is correct).
    frames.sort(key=lambda fp: (os.path.dirname(fp), step_num(fp)))
    dt = 1.0 / DEFAULT_HZ

    print(f"dataset: {root}\nfound {len(frames)} frame(s)  (closing speed dt = {dt:.3f}s @ {DEFAULT_HZ}Hz)\n")
    prev = {}          # instanceId -> range_m, within the current sequence
    cur_seq = None
    first = True
    for fp in frames:
        seq = os.path.dirname(fp)
        if seq != cur_seq:          # reset history at a sequence boundary
            prev, cur_seq = {}, seq
        objs = process_frame(fp, dump_format=first)
        first = False

        for o in objs:              # closing speed = range rate (+ = approaching)
            inst = o["instanceId"]
            o["closing_mps"] = round((prev[inst] - o["range_m"]) / dt, 2) if inst in prev else None
            prev[inst] = o["range_m"]

        write_metadata(fp, objs)

        rel = os.path.relpath(fp, root)
        if not objs:
            print(f"{rel}: (no 3D boxes / no objects)")
            continue
        print(f"{rel}: {len(objs)} object(s)")
        for o in objs[:8]:
            cs = "  n/a" if o["closing_mps"] is None else f"{o['closing_mps']:>6.2f}"
            print(f"    {o['label']:<10} id={o['instanceId']}  "
                  f"range={o['range_m']:>7.1f} m  bearing={o['bearing_deg']:>6.1f}°  "
                  f"closing={cs} m/s")
    print("\ndone — per-frame metadata (range/bearing/closing) in each sequence's metadata/ folder.")


if __name__ == "__main__":
    main()
