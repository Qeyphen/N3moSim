#!/usr/bin/env python3
"""Overlay 2D bounding boxes from a Unity Perception SOLO dataset onto its RGB frames.

Usage: python3 solo_preview.py [/path/to/solo]
"""

import glob
import json
import os
import sys

from PIL import Image, ImageDraw

BBOX2D = "BoundingBox2DAnnotation"


def process_frame(frame_json_path, min_box_side):
    with open(frame_json_path) as f:
        data = json.load(f)
    base = os.path.dirname(frame_json_path)
    out_dir = os.path.join(base, "preview")
    os.makedirs(out_dir, exist_ok=True)

    for cap in data.get("captures", []):
        rgb_name = cap.get("filename")
        if not rgb_name:
            continue
        rgb_path = os.path.join(base, rgb_name)
        if not os.path.exists(rgb_path):
            print(f"  ! missing RGB {rgb_path}")
            continue

        img = Image.open(rgb_path).convert("RGB")
        draw = ImageDraw.Draw(img)

        boxes = []
        for ann in cap.get("annotations", []):
            if BBOX2D in ann.get("@type", ""):
                boxes = ann.get("values", [])
                break

        drawn = dropped = 0
        for b in boxes:
            x, y = b["origin"]
            w, h = b["dimension"]
            if min_box_side is not None and min(w, h) < min_box_side:
                dropped += 1
                continue
            draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 0), width=3)
            draw.text((x + 3, y + 3), b.get("labelName", ""), fill=(255, 255, 0))
            drawn += 1

        out_path = os.path.join(out_dir, os.path.basename(rgb_name))
        img.save(out_path)
        print(f"  wrote {out_path} [{cap.get('id', 'camera')}]  ({drawn} boxes, {dropped} tiny skipped)")


def find_latest_solo():
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".config/unity3d/*/*/solo*"),               # Linux
        os.path.join(home, "Library/Application Support/*/*/solo*"),   # macOS
    ]
    dirs = [d for pat in patterns for d in glob.glob(pat) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def main():
    args = sys.argv[1:]
    min_box_side = None
    root = None

    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--min-box-side":
            if i + 1 >= len(args):
                print("missing value for --min-box-side")
                return
            try:
                min_box_side = int(args[i + 1])
            except ValueError:
                print("--min-box-side must be an integer")
                return
            if min_box_side < 0:
                print("--min-box-side must be >= 0")
                return
            i += 2
            continue
        if root is None:
            root = arg
            i += 1
            continue
        print(f"unrecognized argument: {arg}")
        return

    root = root or find_latest_solo()
    if not root:
        print("No SOLO dataset found automatically. Pass the path: solo_preview.py <dir>")
        return

    frames = glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True)
    if not frames:
        print(f"no *frame_data.json found under {root}")
        return
    print(f"dataset: {root}\nfound {len(frames)} frame(s)")
    if min_box_side is None:
        print("box filter: none")
    else:
        print(f"box filter: smaller side >= {min_box_side}px")
    for fp in sorted(frames):
        print(os.path.relpath(fp, root))
        process_frame(fp, min_box_side)
    print("done — open the 'preview/' subfolder(s) to view annotated frames.")


if __name__ == "__main__":
    main()
