#!/usr/bin/env python3
"""Depth sanity + colorized preview for a Unity Perception SOLO dataset (float EXR, metres).

Usage: python3 depth_preview.py [/path/to/solo]
"""

import os
# Must be set before importing cv2 to enable EXR reading.
os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")

import glob
import json
import sys

import numpy as np
import cv2


def find_depth_file(frame_json_path, data):
    """Locate this frame's depth image — from the depth annotation, else by globbing."""
    base = os.path.dirname(frame_json_path)
    for cap in data.get("captures", []):
        for ann in cap.get("annotations", []):
            if "depth" in ann.get("@type", "").lower():
                fn = ann.get("filename")
                if fn and os.path.exists(os.path.join(base, fn)):
                    return os.path.join(base, fn)
    for pat in ("*[Dd]epth*.exr", "*[Dd]epth*.png"):
        hits = glob.glob(os.path.join(base, pat))
        if hits:
            return hits[0]
    return None


def process_frame(frame_json_path):
    with open(frame_json_path) as f:
        data = json.load(f)

    depth_path = find_depth_file(frame_json_path, data)
    if not depth_path:
        print(f"  ! no depth file found for {os.path.basename(frame_json_path)}")
        return

    raw = cv2.imread(depth_path, cv2.IMREAD_UNCHANGED)
    if raw is None:
        print(f"  ! could not read {depth_path} (OpenEXR support missing?)")
        return

    name = os.path.basename(depth_path)
    arr = np.asarray(raw, dtype=np.float64)
    print(f"  {name}: shape={raw.shape} dtype={raw.dtype}")

    nan = int(np.isnan(arr).sum())
    inf = int(np.isinf(arr).sum())
    fin = arr[np.isfinite(arr)]
    if fin.size:
        print(f"    raw: min={fin.min():.4g} max={fin.max():.4g} "
              f"zeros={int((fin == 0).sum())} neg={int((fin < 0).sum())} "
              f"nan={nan} inf={inf} total={arr.size}")
    if arr.ndim == 3:
        for c in range(arr.shape[2]):
            ch = arr[:, :, c]; chf = ch[np.isfinite(ch)]
            if chf.size:
                print(f"    channel {c}: nonzero={int((chf != 0).sum())} "
                      f"min={chf.min():.4g} max={chf.max():.4g}")

    # Depth plane = channel with the most nonzero, finite values.
    if arr.ndim == 3:
        best_c = max(range(arr.shape[2]),
                     key=lambda c: int(((arr[:, :, c] != 0) & np.isfinite(arr[:, :, c])).sum()))
        depth = arr[:, :, best_c]
    else:
        depth = arr

    finite = depth[np.isfinite(depth)]
    valid = finite[(finite > 0) & (finite < 1e6)]   # drop 0 and sky/inf
    if valid.size == 0:
        print(f"  ! no valid (>0, finite) depth — see raw diagnostics above")
        return

    lo, hi = float(valid.min()), float(valid.max())
    print(f"    DEPTH: min={lo:.2f} max={hi:.2f} mean={float(valid.mean()):.2f} "
          f"median={float(np.median(valid)):.2f}   <- should read as METRES")

    # Colorize valid depth; no-data pixels stay black.
    mask = np.isfinite(depth) & (depth > 0) & (depth < 1e6)
    norm = np.clip((depth - lo) / max(hi - lo, 1e-6), 0.0, 1.0)
    colored = cv2.applyColorMap((norm * 255.0).astype(np.uint8), cv2.COLORMAP_TURBO)
    vis = np.zeros((depth.shape[0], depth.shape[1], 3), np.uint8)
    vis[mask] = colored[mask]
    coverage = 100.0 * mask.sum() / mask.size
    print(f"    coverage: {coverage:.1f}% of pixels have depth (rest = no-data, shown black)")

    out_dir = os.path.join(os.path.dirname(frame_json_path), "preview")
    os.makedirs(out_dir, exist_ok=True)
    stem = os.path.splitext(os.path.basename(depth_path))[0]
    out_path = os.path.join(out_dir, f"{stem}_depth.png")
    cv2.imwrite(out_path, vis)
    print(f"    wrote {out_path}")


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
        print("No SOLO dataset found automatically. Pass the path: depth_preview.py <dir>")
        return

    frames = glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True)
    if not frames:
        print(f"no *frame_data.json found under {root}")
        return
    print(f"dataset: {root}\nfound {len(frames)} frame(s)")
    for fp in sorted(frames):
        print(os.path.relpath(fp, root))
        process_frame(fp)
    print("done — open 'preview/*_depth.png'; the printed min/max/median should look like metres.")


if __name__ == "__main__":
    main()
