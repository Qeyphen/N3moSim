#!/usr/bin/env python3
"""Print the camera intrinsics + extrinsics Unity Perception writes per SOLO frame.

Usage: python3 camera_info.py [/path/to/solo]
"""

import glob
import json
import math
import os
import sys


def find_latest_solo():
    home = os.path.expanduser("~")
    patterns = [
        os.path.join(home, ".config/unity3d/*/*/solo*"),               # Linux
        os.path.join(home, "Library/Application Support/*/*/solo*"),   # macOS
    ]
    dirs = [d for pat in patterns for d in glob.glob(pat) if os.path.isdir(d)]
    return max(dirs, key=os.path.getmtime) if dirs else None


def show_intrinsics(matrix, dimension):
    """SOLO 'matrix' is Unity's NORMALIZED (NDC) projection diagonal, not pixel units:
       fx = 1/tan(hfov/2), fy = 1/tan(vfov/2), principal point in NDC (0 = centre).
       Convert to pixels with width/2, height/2 (NOT width/height)."""
    if not matrix or len(matrix) < 6:
        print(f"    INTRINSICS (raw): {matrix}")
        return
    fx, cx = matrix[0], matrix[2]
    fy, cy = matrix[4], matrix[5]
    print(f"    INTRINSICS (Unity NDC): fx={fx:.4f} fy={fy:.4f} cx={cx:.4f} cy={cy:.4f}")
    if fx and fy:
        hfov = math.degrees(2 * math.atan(1.0 / fx))
        vfov = math.degrees(2 * math.atan(1.0 / fy))
        print(f"      -> FOV: horizontal={hfov:.1f}deg  vertical={vfov:.1f}deg")
    if dimension and len(dimension) >= 2:
        w, h = float(dimension[0]), float(dimension[1])
        print(f"    INTRINSICS (pixels):   fx={fx * w / 2:.1f} fy={fy * h / 2:.1f} "
              f"cx={(1 + cx) * w / 2:.1f} cy={(1 - cy) * h / 2:.1f}   "
              f"(for OpenCV / projecting 3D boxes)")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else find_latest_solo()
    if not root:
        print("No SOLO dataset found. Pass the path: camera_info.py <dir>")
        return

    frames = sorted(glob.glob(os.path.join(root, "**", "*frame_data.json"), recursive=True))
    if not frames:
        print(f"no *frame_data.json under {root}")
        return

    fp = frames[0]
    print(f"dataset: {root}\ninspecting: {os.path.relpath(fp, root)}\n")
    data = json.load(open(fp))

    for cap in data.get("captures", []):
        print(f"capture id='{cap.get('id')}'  @type='{cap.get('@type')}'")
        print(f"  available keys: {sorted(cap.keys())}")
        print(f"    EXTRINSICS position: {cap.get('position', '<missing>')}")
        print(f"    EXTRINSICS rotation: {cap.get('rotation', '<missing>')}")
        print(f"    image dimension (w,h): {cap.get('dimension', '<missing>')}")
        show_intrinsics(cap.get("matrix"), cap.get("dimension"))
        has_ext = cap.get("position") is not None and cap.get("rotation") is not None
        has_int = bool(cap.get("matrix"))
        print(f"    -> extrinsics: {'OK' if has_ext else 'MISSING'} | "
              f"intrinsics: {'OK' if has_int else 'MISSING'}\n")


if __name__ == "__main__":
    main()
