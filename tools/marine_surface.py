#!/usr/bin/env python3
"""Label water/sky per-pixel via horizon synthesis; keep Perception obstacle pixels.

Obstacle pixels are preserved from:
- semantic segmentation, when available
- instance segmentation, as a fallback/union for assets missing semantic labels

Usage: python3 marine_surface.py [/path/to/solo] [--flip]
"""

import argparse
import glob
import json
import os

import numpy as np
from PIL import Image

SEMSEG = "SemanticSegmentationAnnotation"
INSTSEG = "InstanceSegmentationAnnotation"
WATER_RGB = (30, 90, 200)
SKY_RGB   = (150, 205, 255)
OBSTACLE_RGB = (255, 40, 40)

CLS_WATER, CLS_SKY, CLS_OBSTACLE = 0, 1, 2


def find_latest_solo():
    home = os.path.expanduser("~")
    pats = [os.path.join(home, ".config/unity3d/*/*/solo*"),
            os.path.join(home, "Library/Application Support/*/*/solo*")]
    dirs = [d for p in pats for d in glob.glob(p) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def quat_to_matrix(q):
    """Unity quaternion [x,y,z,w] -> 3x3 rotation matrix (camera-local -> world)."""
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z),     2 * (x * z + w * y)],
        [2 * (x * y + w * z),     1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y),     2 * (y * z + w * x),     1 - 2 * (x * x + y * y)],
    ])


def semantic_annotation(cap):
    for ann in cap.get("annotations", []):
        if SEMSEG in ann.get("@type", ""):
            return ann
    return None


def instance_annotation(cap):
    for ann in cap.get("annotations", []):
        if INSTSEG in ann.get("@type", ""):
            return ann
    return None


def capture_key(cap):
    rgb_name = cap.get("filename")
    if rgb_name:
        return os.path.splitext(os.path.basename(rgb_name))[0]
    cap_id = cap.get("id", "camera")
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in cap_id).strip("_") or "camera"


def apply_annotation_mask(obstacle, frame_dir, ann):
    if not ann:
        return obstacle, False

    png = os.path.join(frame_dir, ann.get("filename", ""))
    if not os.path.exists(png):
        return obstacle, False

    seg = np.array(Image.open(png).convert("RGB"))
    used = False
    for inst in ann.get("instances", []):
        pv = inst.get("pixelValue") or inst.get("color")
        if not pv:
            continue
        c = tuple(int(x) for x in pv[:3])
        obstacle |= ((seg[:, :, 0] == c[0]) &
                     (seg[:, :, 1] == c[1]) &
                     (seg[:, :, 2] == c[2]))
        used = True
    return obstacle, used


def dominant_corner_color(seg):
    h, w = seg.shape[:2]
    samples = np.array([
        seg[0, 0],
        seg[0, max(0, w - 1)],
        seg[max(0, h - 1), 0],
        seg[max(0, h - 1), max(0, w - 1)],
    ], dtype=np.uint8)
    colors, counts = np.unique(samples.reshape(-1, 3), axis=0, return_counts=True)
    return tuple(int(v) for v in colors[np.argmax(counts)])


def apply_instance_image_fallback(obstacle, frame_dir, ann):
    if not ann:
        return obstacle, False

    png = os.path.join(frame_dir, ann.get("filename", ""))
    if not os.path.exists(png):
        return obstacle, False

    seg = np.array(Image.open(png).convert("RGB"))
    background = dominant_corner_color(seg)
    fallback_mask = (
        (seg[:, :, 0] != background[0]) |
        (seg[:, :, 1] != background[1]) |
        (seg[:, :, 2] != background[2])
    )
    if not fallback_mask.any():
        return obstacle, False
    obstacle |= fallback_mask
    return obstacle, True


def process_capture(frame_json_path, cap, flip):
    W, H = int(cap["dimension"][0]), int(cap["dimension"][1])
    m = cap["matrix"]
    fx, fy = m[0] * W / 2.0, m[4] * H / 2.0
    cx, cy = (1 + m[2]) * W / 2.0, (1 - m[5]) * H / 2.0
    R = quat_to_matrix(cap["rotation"])

    uu, vv = np.meshgrid(np.arange(W), np.arange(H))
    xn = (uu - cx) / fx
    yn = (vv - cy) / fy
    # Unity camera: x right, y up, z forward; image v is down -> camera -y.
    dcx, dcy, dcz = xn, -yn, np.ones_like(xn)
    dy = R[1, 0] * dcx + R[1, 1] * dcy + R[1, 2] * dcz   # world-space y of the ray
    water = (dy > 0.0) if flip else (dy < 0.0)
    sky = ~water

    frame_dir = os.path.dirname(frame_json_path)
    obstacle = np.zeros((H, W), bool)
    preview = None

    sem_ann = semantic_annotation(cap)
    obstacle, used_sem = apply_annotation_mask(obstacle, frame_dir, sem_ann)
    if used_sem:
        sem_png = os.path.join(frame_dir, sem_ann.get("filename", ""))
        if os.path.exists(sem_png):
            preview = np.array(Image.open(sem_png).convert("RGB"))

    inst_ann = instance_annotation(cap)
    obstacle, used_inst = apply_annotation_mask(obstacle, frame_dir, inst_ann)
    obstacle, used_inst_fallback = apply_instance_image_fallback(obstacle, frame_dir, inst_ann)
    if preview is None and used_inst:
        inst_png = os.path.join(frame_dir, inst_ann.get("filename", ""))
        if os.path.exists(inst_png):
            preview = np.array(Image.open(inst_png).convert("RGB"))
    elif preview is None and used_inst_fallback:
        inst_png = os.path.join(frame_dir, inst_ann.get("filename", ""))
        if os.path.exists(inst_png):
            preview = np.array(Image.open(inst_png).convert("RGB"))

    # preview: obstacle drawn last, on top
    out = np.zeros((H, W, 3), np.uint8)
    out[sky] = SKY_RGB
    out[water] = WATER_RGB
    if preview is not None:
        out[obstacle] = preview[obstacle]

    cls = np.full((H, W), CLS_WATER, np.uint8)
    cls[sky] = CLS_SKY
    cls[obstacle] = CLS_OBSTACLE

    cap_name = cap.get("id", capture_key(cap))
    print(f"  {os.path.basename(frame_json_path)} [{cap_name}]: water={100*water.mean():5.1f}%  "
          f"sky={100*sky.mean():5.1f}%  obstacle={100*obstacle.mean():4.1f}%  "
          f"(sem={'y' if used_sem else 'n'}, inst={'y' if used_inst else 'n'}, "
          f"inst_img={'y' if used_inst_fallback else 'n'})")

    out_dir = os.path.join(os.path.dirname(frame_json_path), "marine_seg")
    os.makedirs(out_dir, exist_ok=True)
    base = capture_key(cap)
    Image.fromarray(out).save(os.path.join(out_dir, base + ".marine_seg.png"))
    Image.fromarray(cls).save(os.path.join(out_dir, base + ".marine_classes.png"))


def process_frame(fp, flip):
    data = json.load(open(fp))
    captures = [
        cap for cap in data.get("captures", [])
        if cap.get("matrix") and cap.get("rotation") and cap.get("dimension")
    ]
    if not captures:
        print(f"  ! {os.path.basename(fp)}: no camera matrix/rotation/dimension")
        return

    for cap in captures:
        process_capture(fp, cap, flip)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", nargs="?", default=None)
    ap.add_argument("--flip", action="store_true", help="swap water/sky if the horizon is inverted")
    args = ap.parse_args()

    root = args.root or find_latest_solo()
    if not root:
        print("No SOLO dataset found. Pass the path: marine_surface.py <dir>")
        return
    frames = sorted(glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True))
    if not frames:
        print(f"no *frame_data.json under {root}")
        return
    print(f"dataset: {root}\nfound {len(frames)} frame(s)  (water=below horizon, sky=above)\n")
    for fp in frames:
        process_frame(fp, args.flip)
    print("\ndone -> marine_seg/*.png (colored preview) + *.marine_classes.png (0=water,1=sky,2=obstacle).")
    print("Sanity: for a forward, slightly-down camera, water should be the LARGER share.")
    print("If water/sky look swapped, re-run with --flip.")


if __name__ == "__main__":
    main()
