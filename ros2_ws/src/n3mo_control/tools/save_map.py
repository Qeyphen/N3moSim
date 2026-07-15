#!/usr/bin/env python3
"""Subscribe to /map (latched) and save it as a PNG + ROS map .yaml under /recordings.

Run inside the bridge container:
  python3 /root/ros2_ws/src/n3mo_control/tools/save_map.py
Outputs (host-visible via the ./recordings mount):
  recordings/map.png   grayscale image (occupied=black, free=white, unknown=grey)
  recordings/map.yaml  standard ROS map metadata (resolution + origin)

Pure stdlib (zlib) PNG encoder — no Pillow/nav2 required.
"""

import struct
import sys
import zlib

import rclpy
from rclpy.node import Node
from rclpy.qos import (QoSProfile, QoSDurabilityPolicy,
                       QoSReliabilityPolicy, QoSHistoryPolicy)
from nav_msgs.msg import OccupancyGrid

OUT_PNG  = "/recordings/map.png"        # full grid, 1 px/cell (ROS standard)
OUT_YAML = "/recordings/map.yaml"
OUT_ZOOM = "/recordings/map_zoom.png"   # cropped to obstacles + upscaled (human-viewable)
ZOOM_SCALE  = 8     # pixels per cell in the zoom image
ZOOM_MARGIN = 15    # cells of padding around the occupied region

# ROS map_server greyscale convention.
OCCUPIED = 0      # black
FREE     = 254    # white
UNKNOWN  = 205    # grey


def write_png(path, width, height, gray_rows):
    """gray_rows: list of bytes objects, one per image row (top to bottom)."""
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)  # 8-bit grayscale
    raw = bytearray()
    for row in gray_rows:
        raw.append(0)          # filter type 0 (none)
        raw.extend(row)
    png = (b"\x89PNG\r\n\x1a\n" +
           chunk(b"IHDR", ihdr) +
           chunk(b"IDAT", zlib.compress(bytes(raw), 9)) +
           chunk(b"IEND", b""))
    with open(path, "wb") as f:
        f.write(png)


class MapSaver(Node):
    def __init__(self):
        super().__init__('map_saver')
        qos = QoSProfile(
            depth=1,
            history=QoSHistoryPolicy.KEEP_LAST,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            reliability=QoSReliabilityPolicy.RELIABLE,
        )
        self.create_subscription(OccupancyGrid, '/map', self.on_map, qos)
        self.got = False

    def on_map(self, msg):
        self.got = True
        w, h, data = msg.info.width, msg.info.height, msg.data

        # Build rows top-down (row 0 of the grid is the origin / bottom).
        rows = []
        for y in range(h - 1, -1, -1):
            base = y * w
            row = bytearray(w)
            for x in range(w):
                v = data[base + x]
                row[x] = OCCUPIED if v >= 50 else (UNKNOWN if v < 0 else FREE)
            rows.append(bytes(row))
        write_png(OUT_PNG, w, h, rows)

        o = msg.info.origin.position
        with open(OUT_YAML, "w") as f:
            f.write(
                f"image: map.png\n"
                f"resolution: {msg.info.resolution}\n"
                f"origin: [{o.x}, {o.y}, 0.0]\n"
                f"negate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n"
            )

        occupied = self.write_zoom(w, h, data)
        self.get_logger().info(
            f"Saved {w}x{h} map -> {OUT_PNG} ({occupied} occupied cells); "
            f"zoom -> {OUT_ZOOM}.")

    def write_zoom(self, w, h, data):
        """Crop to the occupied region (+margin), upscale, save a viewable PNG.
        Returns the occupied-cell count."""
        occ = [i for i, v in enumerate(data) if v >= 50]
        if not occ:
            return 0

        cols = [i % w for i in occ]
        rows = [i // w for i in occ]
        cmin = max(0, min(cols) - ZOOM_MARGIN)
        cmax = min(w - 1, max(cols) + ZOOM_MARGIN)
        rmin = max(0, min(rows) - ZOOM_MARGIN)
        rmax = min(h - 1, max(rows) + ZOOM_MARGIN)

        out_rows = []
        for y in range(rmax, rmin - 1, -1):     # top-down
            base = y * w
            line = bytearray()
            for x in range(cmin, cmax + 1):
                v = data[base + x]
                px = OCCUPIED if v >= 50 else (UNKNOWN if v < 0 else FREE)
                line.extend([px] * ZOOM_SCALE)   # widen each cell
            for _ in range(ZOOM_SCALE):          # repeat each row
                out_rows.append(bytes(line))

        write_png(OUT_ZOOM, (cmax - cmin + 1) * ZOOM_SCALE,
                  (rmax - rmin + 1) * ZOOM_SCALE, out_rows)
        return len(occ)


def main():
    rclpy.init()
    node = MapSaver()
    deadline = node.get_clock().now().nanoseconds + 15_000_000_000
    while rclpy.ok() and not node.got and node.get_clock().now().nanoseconds < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
    if not node.got:
        print("No /map received within 15s — is Unity running and publishing?",
              file=sys.stderr)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
