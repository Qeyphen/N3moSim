#!/usr/bin/env python3
"""Convert Unity Perception SOLO data to YOLO detection format.

Default behavior preserves raw data without creating a train/val split. Optional
split modes exist when a downstream consumer explicitly wants them.

Usage examples:
  python3 tools/solo_to_yolo.py --out yolo_raw
  python3 tools/solo_to_yolo.py /path/to/solo --out yolo_raw
  python3 tools/solo_to_yolo.py solo_a solo_b --split scenario --val-frac 0.2 --out yolo_split
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
from collections import defaultdict

BBOX2D = "BoundingBox2DAnnotation"


def find_latest_solo():
    home = os.path.expanduser("~")
    pats = [
        os.path.join(home, ".config/unity3d/*/*/solo*"),
        os.path.join(home, "Library/Application Support/*/*/solo*"),
    ]
    dirs = [d for p in pats for d in glob.glob(p) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def collect_class_names(frames):
    names = set()
    for fp in frames:
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
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


def capture_key(cap):
    cap_id = cap.get("id", "")
    if cap_id:
        return "".join(ch.lower() if ch.isalnum() else "_" for ch in cap_id).strip("_") or "camera"
    rgb = cap.get("filename", "")
    if rgb:
        return os.path.splitext(os.path.basename(rgb))[0]
    return "camera"


def infer_tag(root: str) -> str:
    return os.path.basename(os.path.normpath(root))


def scenario_split_map(tags: list[str], val_frac: float) -> dict[str, str]:
    every = max(1, int(round(1.0 / val_frac))) if val_frac > 0 else 0
    mapping = {}
    for i, tag in enumerate(sorted(tags)):
        mapping[tag] = "val" if (every and i % every == 0) else "train"
    return mapping


def ensure_dirs(out: str, split_mode: str):
    if split_mode == "none":
        subs = ("images/all", "labels/all")
    else:
        subs = ("images/train", "images/val", "labels/train", "labels/val")
    for sub in subs:
        os.makedirs(os.path.join(out, sub), exist_ok=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "roots",
        nargs="*",
        help="optional SOLO dirs. If omitted, the latest SOLO dir is used automatically. "
        "Multiple dirs are merged with one shared class list.",
    )
    ap.add_argument("--out", default="yolo", help="output dataset dir (default ./yolo)")
    ap.add_argument("--min", type=int, default=10, help="drop boxes with smaller side < this (px)")
    ap.add_argument(
        "--classes",
        default=None,
        help="comma-separated class list to fix id order (default: union across all dirs)",
    )
    ap.add_argument(
        "--split",
        choices=["none", "frame", "scenario"],
        default="none",
        help="split policy: none = preserve raw export, frame = every-Nth-frame val split, "
        "scenario = assign whole input roots to train/val",
    )
    ap.add_argument("--val-frac", type=float, default=0.2, help="fraction for val when split != none")
    args = ap.parse_args()

    latest = find_latest_solo()
    roots = args.roots or ([latest] if latest else [])
    roots = [r for r in roots if r]
    if not roots:
        print("No SOLO dataset found. Pass path(s): solo_to_yolo.py <dir> [<dir> ...]")
        return

    items = []
    tags = []
    for root in roots:
        tag = infer_tag(root)
        tags.append(tag)
        for fp in sorted(glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True)):
            items.append((fp, tag, root))
    if not items:
        print(f"no *frame_data.json under {roots}")
        return
    items.sort()

    if args.classes:
        names = [c.strip() for c in args.classes.split(",") if c.strip()]
    else:
        names = collect_class_names([fp for fp, _tag, _root in items])
    if not names:
        print("no 2D bounding boxes found in the dataset")
        return
    class_id = {n: i for i, n in enumerate(names)}

    out = os.path.abspath(args.out)
    ensure_dirs(out, args.split)

    frame_every = max(1, int(round(1.0 / args.val_frac))) if args.val_frac > 0 else 0
    split_by_tag = scenario_split_map(tags, args.val_frac) if args.split == "scenario" else {}

    n_boxes = n_dropped = n_unknown = 0
    split_counts = defaultdict(int)
    manifest_entries = []

    for i, (fp, tag, root) in enumerate(items):
        with open(fp, encoding="utf-8") as f:
            data = json.load(f)
        base_dir = os.path.dirname(fp)

        if args.split == "none":
            split = "all"
        elif args.split == "frame":
            split = "val" if (frame_every and i % frame_every == 0) else "train"
        else:
            split = split_by_tag[tag]

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

            stem = (
                f"{tag}_{os.path.basename(base_dir)}_"
                f"{os.path.splitext(os.path.basename(rgb))[0]}_{capture_key(cap)}"
            )
            lines = []
            box_count = 0
            for b in frame_boxes(cap):
                x, y = b["origin"]
                w, h = b["dimension"]
                if min(w, h) < args.min:
                    n_dropped += 1
                    continue
                cid = class_id.get(b.get("labelName", "object"))
                if cid is None:
                    n_unknown += 1
                    continue
                cx, cy = (x + w / 2) / W, (y + h / 2) / H
                lines.append(f"{cid} {cx:.6f} {cy:.6f} {w / W:.6f} {h / H:.6f}")
                n_boxes += 1
                box_count += 1

            shutil.copy2(src, os.path.join(out, "images", split, stem + ".png"))
            with open(os.path.join(out, "labels", split, stem + ".txt"), "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            split_counts[split] += 1
            manifest_entries.append(
                {
                    "image": f"images/{split}/{stem}.png",
                    "label": f"labels/{split}/{stem}.txt",
                    "split": split,
                    "scenario_tag": tag,
                    "camera_id": cap.get("id", ""),
                    "source_root": root,
                    "source_frame_json": fp,
                    "source_capture_filename": rgb,
                    "box_count": box_count,
                }
            )

    with open(os.path.join(out, "data.yaml"), "w", encoding="utf-8") as f:
        f.write(f"path: {out}\n")
        if args.split == "none":
            f.write("train: images/all\n")
        else:
            f.write("train: images/train\n")
            f.write("val: images/val\n")
        f.write(f"nc: {len(names)}\n")
        f.write("names: [" + ", ".join(names) + "]\n")

    with open(os.path.join(out, "dataset_manifest.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "split_mode": args.split,
                "val_frac": args.val_frac,
                "class_names": names,
                "source_roots": roots,
                "entries": manifest_entries,
            },
            f,
            indent=2,
        )

    print(f"dirs: {roots}")
    print(f"classes ({len(names)}): {names}")
    print(f"split mode: {args.split}")
    print(f"frames by split: {dict(split_counts)}")
    print(
        f"boxes kept {n_boxes}, tiny dropped {n_dropped}, "
        f"unknown-label dropped {n_unknown} (min side {args.min}px)"
    )
    print(
        f"\nwrote YOLO dataset -> {out}\n"
        "  data.yaml, dataset_manifest.json, images/*, labels/*"
    )
    if args.split == "none":
        print("no train/val split was created; downstream tooling should split by scenario if needed")
    else:
        print("train:  yolo detect train data=" + os.path.join(out, "data.yaml") + " model=yolo11n.pt")


if __name__ == "__main__":
    main()
