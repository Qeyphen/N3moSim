#!/usr/bin/env python3
"""Clip SOLO 2D boxes to the visible, emerged part of each instance.

This uses:
- Unity instance segmentation to isolate each object instance
- marine_surface.py output (marine_classes.png) to remove water-covered pixels

Objects with no remaining emerged pixels are dropped. By default this reports only;
--apply rewrites frame_data.json in place (keeps a .bak backup).

Usage:
  python3 tools/clip_boxes_to_emerged.py [/path/to/solo] [--min 10] [--apply]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil

import numpy as np
from PIL import Image

BBOX2D = "BoundingBox2DAnnotation"
INSTSEG = "InstanceSegmentationAnnotation"
CLS_WATER = 0


def find_latest_solo():
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".config/unity3d/*/*/solo*"),
        os.path.join(home, "Library/Application Support/*/*/solo*"),
    ]
    dirs = [d for pat in patterns for d in glob.glob(pat) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def instance_annotation(cap):
    for ann in cap.get("annotations", []):
        if INSTSEG in ann.get("@type", ""):
            return ann
    return None


def bbox_annotation(cap):
    for ann in cap.get("annotations", []):
        if BBOX2D in ann.get("@type", ""):
            return ann
    return None


def load_rgb_mask(path):
    if not os.path.exists(path):
        return None
    return np.array(Image.open(path).convert("RGB"))


def load_class_mask(path):
    if not os.path.exists(path):
        return None
    return np.array(Image.open(path))


def marine_mask_path(frame_json_path, cap):
    rgb_name = cap.get("filename", "")
    stem = os.path.splitext(os.path.basename(rgb_name))[0]
    return os.path.join(os.path.dirname(frame_json_path), "marine_seg", stem + ".marine_classes.png")


def color_legend(inst_ann):
    legend = {}
    for inst in inst_ann.get("instances", []):
        inst_id = inst.get("instanceId")
        pv = inst.get("pixelValue") or inst.get("color")
        if inst_id is None or not pv:
            continue
        legend[int(inst_id)] = tuple(int(c) for c in pv[:3])
    return legend


def clip_frame(path, min_side, apply):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    changed = False
    kept = dropped_no_emerged = dropped_tiny = clipped = untouched = 0

    for cap in data.get("captures", []):
        bbox_ann = bbox_annotation(cap)
        inst_ann = instance_annotation(cap)
        if bbox_ann is None or inst_ann is None:
            continue

        inst_png = os.path.join(os.path.dirname(path), inst_ann.get("filename", ""))
        inst_img = load_rgb_mask(inst_png)
        marine_path = marine_mask_path(path, cap)
        marine_cls = load_class_mask(marine_path)
        if inst_img is None or marine_cls is None:
            continue

        legend = color_legend(inst_ann)
        new_values = []
        for box in bbox_ann.get("values", []):
            inst_id = box.get("instanceId")
            color = legend.get(int(inst_id)) if inst_id is not None else None
            if color is None:
                new_values.append(box)
                untouched += 1
                kept += 1
                continue

            inst_mask = (
                (inst_img[:, :, 0] == color[0]) &
                (inst_img[:, :, 1] == color[1]) &
                (inst_img[:, :, 2] == color[2])
            )
            emerged = inst_mask & (marine_cls != CLS_WATER)
            ys, xs = np.where(emerged)
            if xs.size == 0 or ys.size == 0:
                dropped_no_emerged += 1
                changed = True
                continue

            x0, x1 = int(xs.min()), int(xs.max())
            y0, y1 = int(ys.min()), int(ys.max())
            w = x1 - x0 + 1
            h = y1 - y0 + 1
            if min(w, h) < min_side:
                dropped_tiny += 1
                changed = True
                continue

            old_x, old_y = box["origin"]
            old_w, old_h = box["dimension"]
            if [x0, y0] != [old_x, old_y] or [w, h] != [old_w, old_h]:
                box["origin"] = [x0, y0]
                box["dimension"] = [w, h]
                clipped += 1
                changed = True
            else:
                untouched += 1
            new_values.append(box)
            kept += 1

        bbox_ann["values"] = new_values

    if apply and changed:
        shutil.copy2(path, path + ".bak")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    return {
        "kept": kept,
        "clipped": clipped,
        "untouched": untouched,
        "dropped_no_emerged": dropped_no_emerged,
        "dropped_tiny": dropped_tiny,
        "changed": changed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=None)
    ap.add_argument("--min", type=int, default=10, help="drop clipped boxes with smaller side < this (px)")
    ap.add_argument("--apply", action="store_true", help="rewrite frame_data.json in place (keeps .bak)")
    args = ap.parse_args()

    root = args.root or find_latest_solo()
    if not root:
        print("No SOLO dataset found. Pass the path: clip_boxes_to_emerged.py <dir>")
        return
    frames = sorted(glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True))
    if not frames:
        print(f"no *frame_data.json under {root}")
        return

    mode = "APPLY (rewriting)" if args.apply else "report only (use --apply to write)"
    print(f"dataset: {root}\n{len(frames)} frame(s), min {args.min}px — {mode}\n")
    print("Requires marine_surface.py output in marine_seg/*.png for each frame.\n")

    totals = {
        "kept": 0,
        "clipped": 0,
        "untouched": 0,
        "dropped_no_emerged": 0,
        "dropped_tiny": 0,
    }
    for fp in frames:
        stats = clip_frame(fp, args.min, args.apply)
        for key in totals:
            totals[key] += stats[key]
        if stats["changed"]:
            print(
                f"  {os.path.relpath(fp, root)}: kept {stats['kept']}, "
                f"clipped {stats['clipped']}, dropped_no_emerged {stats['dropped_no_emerged']}, "
                f"dropped_tiny {stats['dropped_tiny']}"
            )

    print(
        "\ntotal: kept {kept}, clipped {clipped}, untouched {untouched}, "
        "dropped_no_emerged {dropped_no_emerged}, dropped_tiny {dropped_tiny}.".format(**totals)
    )
    if not args.apply:
        print("re-run with --apply to rewrite the dataset.")


if __name__ == "__main__":
    main()
