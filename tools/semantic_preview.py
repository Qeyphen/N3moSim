#!/usr/bin/env python3
"""Semantic-segmentation class coverage (per-class pixel fraction) for a SOLO dataset.

Usage: python3 semantic_preview.py [/path/to/solo]
"""

import glob
import json
import os
import sys

import numpy as np
from PIL import Image

SEMSEG = "SemanticSegmentationAnnotation"


def find_latest_solo():
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".config/unity3d/*/*/solo*"),
        os.path.join(home, "Library/Application Support/*/*/solo*"),
    ]
    dirs = [d for pat in patterns for d in glob.glob(pat) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def sem_annotation(data):
    for cap in data.get("captures", []):
        for ann in cap.get("annotations", []):
            if SEMSEG in ann.get("@type", ""):
                return ann
    return None


def process_frame(fp, dump=False):
    data = json.load(open(fp))
    ann = sem_annotation(data)
    if not ann:
        print(f"  ! no SemanticSegmentationAnnotation in {os.path.basename(fp)}")
        return

    if dump:
        print(f"  semantic annotation keys: {sorted(ann.keys())}")
        print(f"  instances sample: {json.dumps(ann.get('instances', [])[:4])}")

    base = os.path.dirname(fp)
    png = os.path.join(base, ann.get("filename", ""))
    if not os.path.exists(png):
        print(f"  ! mask PNG not found: {png}")
        return

    img = np.array(Image.open(png).convert("RGBA"))
    total = img.shape[0] * img.shape[1]

    # color -> label
    legend = {}
    for inst in ann.get("instances", []):
        pv = inst.get("pixelValue") or inst.get("color")
        if pv:
            legend[tuple(int(c) for c in pv[:3])] = inst.get("labelName", "?")

    print(f"  {os.path.basename(png)}:")
    counted = 0
    for color, label in sorted(legend.items(), key=lambda kv: kv[1]):
        m = ((img[:, :, 0] == color[0]) &
             (img[:, :, 1] == color[1]) &
             (img[:, :, 2] == color[2]))
        n = int(m.sum()); counted += n
        print(f"    {label:<18} rgb={color}  coverage={100.0 * n / total:5.1f}%")
    print(f"    {'(unlabeled/background)':<18} {' ':>15}  coverage={100.0 * (total - counted) / total:5.1f}%")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else find_latest_solo()
    if not root:
        print("No SOLO dataset found. Pass the path: semantic_preview.py <dir>")
        return
    frames = sorted(glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True))
    if not frames:
        print(f"no *frame_data.json under {root}")
        return
    print(f"dataset: {root}\nfound {len(frames)} frame(s)\n")
    for i, fp in enumerate(frames):
        print(os.path.relpath(fp, root))
        process_frame(fp, dump=(i == 0))
    print("\ndone — check which classes have coverage; 'background' = pixels with no labeled class.")


if __name__ == "__main__":
    main()
