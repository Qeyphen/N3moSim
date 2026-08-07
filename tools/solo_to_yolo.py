#!/usr/bin/env python3
"""Convert a Unity Perception SOLO dataset to YOLO detection format.

Usage: python3 solo_to_yolo.py [/path/to/solo] [--out yolo] [--min 10] [--val-frac 0.2]
"""

import argparse
import glob
import json
import os
import shutil

BBOX2D = "BoundingBox2DAnnotation"


def find_latest_solo():
    home = os.path.expanduser("~")
    pats = [os.path.join(home, ".config/unity3d/*/*/solo*"),
            os.path.join(home, "Library/Application Support/*/*/solo*")]
    dirs = [d for p in pats for d in glob.glob(p) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def collect_class_names(frames):
    """Gather every label name so class ids are stable across the dataset."""
    names = set()
    for fp in frames:
        data = json.load(open(fp))
        for cap in data.get("captures", []):
            for ann in cap.get("annotations", []):
                if BBOX2D in ann.get("@type", ""):
                    for b in ann.get("values", []):
                        names.add(b.get("labelName", "object"))
    return sorted(names)


def frame_boxes(cap):
    for ann in cap.get("annotations", []):
        if BBOX2D in ann.get("@type", ""):
            return ann.get("values", [])
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="*", help="one or more SOLO dirs (default: latest). Multiple "
                    "dirs are merged with one shared class list.")
    ap.add_argument("--out", default="yolo", help="output dataset dir (default ./yolo)")
    ap.add_argument("--min", type=int, default=10, help="drop boxes with smaller side < this (px)")
    ap.add_argument("--val-frac", type=float, default=0.2, help="fraction of frames for val")
    ap.add_argument("--classes", default=None, help="comma-separated class list to FIX id order "
                    "(default: union of classes found across all dirs)")
    args = ap.parse_args()

    roots = args.roots or ([find_latest_solo()] if find_latest_solo() else [])
    roots = [r for r in roots if r]
    if not roots:
        print("No SOLO dataset found. Pass the path(s): solo_to_yolo.py <dir> [<dir> ...]")
        return

    # (frame_data.json, dir-tag) across every root; the tag prefixes filenames so identical
    # sequence folder names (both runs have sequence.0/…) don't collide in the merged output.
    items = []
    for r in roots:
        tag = os.path.basename(os.path.normpath(r))
        for fp in sorted(glob.glob(os.path.join(r, "**", "*frame_data.json"), recursive=True)):
            items.append((fp, tag))
    if not items:
        print(f"no *frame_data.json under {roots}")
        return
    items.sort()

    if args.classes:
        names = [c.strip() for c in args.classes.split(",") if c.strip()]
    else:
        names = collect_class_names([fp for fp, _ in items])   # union across all dirs
    if not names:
        print("no 2D bounding boxes found in the dataset")
        return
    class_id = {n: i for i, n in enumerate(names)}

    out = os.path.abspath(args.out)
    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        os.makedirs(os.path.join(out, sub), exist_ok=True)

    every = max(1, int(round(1.0 / args.val_frac))) if args.val_frac > 0 else 0
    n_boxes = n_dropped = n_unknown = n_train = n_val = 0

    for i, (fp, tag) in enumerate(items):
        data = json.load(open(fp))
        base_dir = os.path.dirname(fp)
        split = "val" if (every and i % every == 0) else "train"

        for cap in data.get("captures", []):
            rgb = cap.get("filename")
            if not rgb:
                continue
            src = os.path.join(base_dir, rgb)
            if not os.path.exists(src):
                continue
            W, H = cap.get("dimension", [0, 0])
            if not W or not H:
                continue

            # flat name, prefixed by the solo dir tag, to avoid collisions across dirs/sequences
            stem = f"{tag}_{os.path.basename(base_dir)}_{os.path.splitext(os.path.basename(rgb))[0]}"
            lines = []
            for b in frame_boxes(cap):
                x, y = b["origin"]
                w, h = b["dimension"]
                if min(w, h) < args.min:
                    n_dropped += 1
                    continue
                cid = class_id.get(b.get("labelName", "object"))
                if cid is None:   # label not in a fixed --classes list
                    n_unknown += 1
                    continue
                cx, cy = (x + w / 2) / W, (y + h / 2) / H
                lines.append(f"{cid} {cx:.6f} {cy:.6f} {w / W:.6f} {h / H:.6f}")
                n_boxes += 1

            shutil.copy2(src, os.path.join(out, "images", split, stem + ".png"))
            with open(os.path.join(out, "labels", split, stem + ".txt"), "w") as f:
                f.write("\n".join(lines))
            if split == "val":
                n_val += 1
            else:
                n_train += 1

    with open(os.path.join(out, "data.yaml"), "w") as f:
        f.write(f"path: {out}\n")
        f.write("train: images/train\n")
        f.write("val: images/val\n")
        f.write(f"nc: {len(names)}\n")
        f.write("names: [" + ", ".join(names) + "]\n")

    print(f"dirs: {roots}")
    print(f"classes ({len(names)}): {names}")
    print(f"frames -> train {n_train}, val {n_val}")
    print(f"boxes kept {n_boxes}, tiny dropped {n_dropped}, unknown-label dropped {n_unknown} (min side {args.min}px)")
    print(f"\nwrote YOLO dataset -> {out}\n  data.yaml, images/{{train,val}}, labels/{{train,val}}")
    print("train:  yolo detect train data=" + os.path.join(out, "data.yaml") + " model=yolo11n.pt")


if __name__ == "__main__":
    main()
