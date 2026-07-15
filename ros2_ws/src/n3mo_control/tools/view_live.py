#!/usr/bin/env python3
"""Live colour ASCII view of the whole scene: static map + moving boats.

Subscribes to BOTH layers and redraws a few times a second:
  /map               (nav_msgs/OccupancyGrid)  -> static buoys, BLUE dots
  /dynamic_obstacles (geometry_msgs/PoseArray)  -> live boats,   RED dots

A text panel lists each object's (x, z) position; boats update as they move.

Run inside the bridge container (Ctrl-C to quit):
  python3 /root/ros2_ws/src/n3mo_control/tools/view_live.py
"""

import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import (QoSProfile, QoSDurabilityPolicy,
                       QoSReliabilityPolicy, QoSHistoryPolicy)
from nav_msgs.msg import OccupancyGrid
from geometry_msgs.msg import PoseArray

MAX_COLS = 100
MAX_ROWS = 50
REDRAW_HZ = 4.0

BLUE  = "\033[94m"
RED   = "\033[91m"
DIM   = "\033[2m"
RESET = "\033[0m"
DOT   = "●"   # ●


class LiveViewer(Node):
    def __init__(self):
        super().__init__('live_viewer')

        latched = QoSProfile(depth=1, history=QoSHistoryPolicy.KEEP_LAST,
                             durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=QoSReliabilityPolicy.RELIABLE)
        self.create_subscription(OccupancyGrid, '/map', self.on_map, latched)
        self.create_subscription(PoseArray, '/dynamic_obstacles', self.on_boats, 10)

        self.meta = None        # cached grid geometry + static layer
        self.boats = []         # list of (x, z) world metres
        self.create_timer(1.0 / REDRAW_HZ, self.redraw)

    # ---- static layer: computed once when the (latched) map arrives ----
    def on_map(self, msg):
        w, h, data = msg.info.width, msg.info.height, msg.data
        res = msg.info.resolution
        ox, oy = msg.info.origin.position.x, msg.info.origin.position.y
        step_x = max(1, w // MAX_COLS)
        step_y = max(1, h // MAX_ROWS)
        rows_out = len(range(h - 1, -1, -step_y))
        cols_out = len(range(0, w, step_x))

        occ = [i for i, v in enumerate(data) if v >= 50]
        self.meta = dict(w=w, h=h, res=res, ox=ox, oy=oy,
                         step_x=step_x, step_y=step_y,
                         rows_out=rows_out, cols_out=cols_out,
                         buoys=self.cluster_buoys(occ, w, res, ox, oy))

    def on_boats(self, msg):
        # convention: position.x = Unity x, position.y = Unity z.
        self.boats = [(p.position.x, p.position.y) for p in msg.poses]

    def redraw(self):
        sys.stdout.write("\033[2J\033[H")
        if self.meta is None:
            print("waiting for /map ... (is Unity in Play?)")
            return
        m = self.meta

        grid = [['.' for _ in range(m['cols_out'])] for _ in range(m['rows_out'])]
        used = set()        # cells taken by dots + already-placed labels
        labels = []         # (di, dj, color, text) to place after all dots

        for (x, z) in m['buoys']:
            self.add_dot(grid, m, x, z, BLUE, used, labels)
        for (x, z) in self.boats:
            self.add_dot(grid, m, x, z, RED, used, labels)
        for (di, dj, color, text) in labels:
            self.place_label(grid, m, di, dj, color, text, used)

        print(f"{BLUE}{DOT} static{RESET} [{len(m['buoys'])}]   "
              f"{RED}{DOT} dynamic{RESET} [{len(self.boats)}]   {DIM}res={m['res']} m{RESET}\n")
        print('\n'.join(''.join(r) for r in grid))

    def add_dot(self, grid, m, x, z, color, used, labels):
        col = int((x - m['ox']) / m['res'])
        row = int((z - m['oy']) / m['res'])
        if not (0 <= col < m['w'] and 0 <= row < m['h']):
            return
        di = (m['h'] - 1 - row) // m['step_y']
        dj = col // m['step_x']
        if not (0 <= di < m['rows_out'] and 0 <= dj < m['cols_out']):
            return
        grid[di][dj] = color + DOT + RESET
        used.add((di, dj))
        labels.append((di, dj, color, f"({x:.0f},{z:.0f})"))

    # Place a label near its dot, in the first candidate row where it doesn't
    # collide with a dot or another label.
    def place_label(self, grid, m, di, dj, color, text, used):
        n = len(text)
        start = max(0, min(dj, m['cols_out'] - n))
        span = list(range(start, start + n))

        for li in (di - 1, di + 1, di - 2, di + 2, di - 3, di + 3):
            if not (0 <= li < m['rows_out']):
                continue
            if any((li, c) in used for c in span):
                continue
            for k, ch in enumerate(text):
                grid[li][start + k] = color + ch + RESET
                used.add((li, start + k))
            return
        # No clear row found — drop this label rather than overwrite another.

    # Group occupied cells into objects (8-connected) and return their world centroids.
    @staticmethod
    def cluster_buoys(occ, w, res, ox, oy):
        cells = set(occ)
        seen = set()
        centroids = []
        for start in occ:
            if start in seen:
                continue
            stack = [start]
            seen.add(start)
            group = []
            while stack:
                idx = stack.pop()
                group.append(idx)
                cx, cy = idx % w, idx // w
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        n = (cy + dy) * w + (cx + dx)
                        if n in cells and n not in seen:
                            seen.add(n)
                            stack.append(n)
            mx = sum(i % w for i in group) / len(group)
            my = sum(i // w for i in group) / len(group)
            centroids.append((ox + (mx + 0.5) * res, oy + (my + 0.5) * res))
        return centroids


def main():
    rclpy.init()
    node = LiveViewer()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
