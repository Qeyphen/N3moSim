#!/usr/bin/env python3
"""Clean a SOLO dataset's 2D boxes: drop tiny (unlearnable) boxes and submerged/underwater objects.

Submerged = the object's 3D-box centre is below the water line (world y), which HDRP's transparent
water doesn't occlude in the label pass, so Perception over-labels it. Reports by default; --apply
rewrites frame_data.json in place (keeps a .bak).

Usage:
  python3 filter_boxes.py [/path/to/solo] [--min 10] [--water-level 0.0] [--apply]
"""

import argparse
import glob
import json
import os
import shutil

BBOX2D = "BoundingBox2DAnnotation"
BBOX3D = "BoundingBox3DAnnotation"


def find_latest_solo():
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".config/unity3d/*/*/solo*"),               # Linux
        os.path.join(home, "Library/Application Support/*/*/solo*"),   # macOS
    ]
    dirs = [d for pat in patterns for d in glob.glob(pat) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def qrot(q, v):
    """Rotate v by Unity quaternion q=[x,y,z,w]."""
    x, y, z, w = q
    tx = 2 * (y * v[2] - z * v[1])
    ty = 2 * (z * v[0] - x * v[2])
    tz = 2 * (x * v[1] - y * v[0])
    return (v[0] + w * tx + (y * tz - z * ty),
            v[1] + w * ty + (z * tx - x * tz),
            v[2] + w * tz + (x * ty - y * tx))


def submerged_ids(cap, water_level):
    """instanceIds whose 3D-box centre is below the water line (world y)."""
    pos = cap.get("position")
    rot = cap.get("rotation")
    ids = set()
    if not pos or not rot:
        return ids
    for ann in cap.get("annotations", []):
        if BBOX3D not in ann.get("@type", ""):
            continue
        for b in ann.get("values", []):
            t = b.get("translation") or b.get("position")
            if not t:
                continue
            world_y = pos[1] + qrot(rot, t)[1]
            if world_y < water_level:
                ids.add(b.get("instanceId"))
    return ids


def filter_frame(path, min_side, water_level, apply):
    with open(path) as f:
        data = json.load(f)

    kept = tiny = sub = 0
    changed = False
    for cap in data.get("captures", []):
        under = submerged_ids(cap, water_level)
        for ann in cap.get("annotations", []):
            if BBOX2D not in ann.get("@type", ""):
                continue
            values = ann.get("values", [])
            keep = []
            for b in values:
                if min(b["dimension"]) < min_side:
                    tiny += 1
                elif b.get("instanceId") in under:
                    sub += 1
                else:
                    keep.append(b)
            kept += len(keep)
            if len(keep) != len(values):
                ann["values"] = keep
                changed = True

    if apply and changed:
        shutil.copy2(path, path + ".bak")
        with open(path, "w") as f:
            json.dump(data, f)
    return kept, tiny, sub


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=None)
    ap.add_argument("--min", type=int, default=10, help="min box side in px (default 10)")
    ap.add_argument("--water-level", type=float, default=0.0, help="world y of the water surface")
    ap.add_argument("--apply", action="store_true", help="rewrite the dataset (keeps .bak)")
    args = ap.parse_args()

    root = args.root or find_latest_solo()
    if not root:
        print("No SOLO dataset found. Pass the path: filter_boxes.py <dir>")
        return
    frames = sorted(glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True))
    if not frames:
        print(f"no *frame_data.json under {root}")
        return

    mode = "APPLY (rewriting)" if args.apply else "report only (use --apply to write)"
    print(f"dataset: {root}\n{len(frames)} frame(s), min {args.min}px, water y={args.water_level} — {mode}\n")

    tk = tt = ts = 0
    for fp in frames:
        kept, tiny, sub = filter_frame(fp, args.min, args.water_level, args.apply)
        tk += kept; tt += tiny; ts += sub
        if tiny or sub:
            print(f"  {os.path.relpath(fp, root)}: kept {kept}, tiny {tiny}, submerged {sub}")

    print(f"\ntotal: kept {tk}, dropped {tt} tiny + {ts} submerged.")
    if (tt or ts) and not args.apply:
        print("re-run with --apply to remove them from the dataset.")


if __name__ == "__main__":
    main()
