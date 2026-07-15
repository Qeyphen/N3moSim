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
MIN_BOX_SIDE = 10  # px; boxes whose smaller side is below this are skipped (too tiny to train on)


def process_frame(frame_json_path):
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
            if min(w, h) < MIN_BOX_SIDE:        # skip tiny boxes (far/occluded specks)
                dropped += 1
                continue
            draw.rectangle([x, y, x + w, y + h], outline=(255, 0, 0), width=3)
            draw.text((x + 3, y + 3), b.get("labelName", ""), fill=(255, 255, 0))
            drawn += 1

        out_path = os.path.join(out_dir, os.path.basename(rgb_name))
        img.save(out_path)
        print(f"  wrote {out_path}  ({drawn} boxes, {dropped} tiny skipped)")


def find_latest_solo():
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".config/unity3d/*/*/solo*"),               # Linux
        os.path.join(home, "Library/Application Support/*/*/solo*"),   # macOS
    ]
    dirs = [d for pat in patterns for d in glob.glob(pat) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else find_latest_solo()
    if not root:
        print("No SOLO dataset found automatically. Pass the path: solo_preview.py <dir>")
        return

    frames = glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True)
    if not frames:
        print(f"no *frame_data.json found under {root}")
        return
    print(f"dataset: {root}\nfound {len(frames)} frame(s)")
    for fp in sorted(frames):
        print(os.path.relpath(fp, root))
        process_frame(fp)
    print("done — open the 'preview/' subfolder(s) to view annotated frames.")


if __name__ == "__main__":
    main()
