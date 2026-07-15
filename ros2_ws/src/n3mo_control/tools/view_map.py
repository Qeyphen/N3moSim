#!/usr/bin/env python3
"""Subscribe to /map (latched) and render the occupancy grid as ASCII in the terminal.

Run inside the bridge container:
  python3 /root/ros2_ws/src/n3mo_control/tools/view_map.py

'#' = occupied, '.' = free, ' ' = unknown. The grid is downsampled to fit the
terminal; a block is '#' if ANY cell in it is occupied, so small obstacles show.
"""

import sys

import rclpy
from rclpy.node import Node
from rclpy.qos import (QoSProfile, QoSDurabilityPolicy,
                       QoSReliabilityPolicy, QoSHistoryPolicy)
from nav_msgs.msg import OccupancyGrid

MAX_COLS = 100
MAX_ROWS = 50


class MapViewer(Node):
    def __init__(self):
        super().__init__('map_viewer')
        # Match the latched publisher so we receive the retained map.
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
        step_x = max(1, w // MAX_COLS)
        step_y = max(1, h // MAX_ROWS)

        occupied = sum(1 for v in data if v >= 50)
        o = msg.info.origin.position
        print(f"/map  {w}x{h} cells  res={msg.info.resolution} m  "
              f"origin=({o.x:.0f}, {o.y:.0f})  occupied={occupied}\n")

        # Row 0 is the origin (bottom), so print from the top row downward.
        for by in range(h - 1, -1, -step_y):
            chars = []
            for bx in range(0, w, step_x):
                state = self.block_state(data, w, h, bx, by, step_x, step_y)
                chars.append(state)
            print(''.join(chars))

    @staticmethod
    def block_state(data, w, h, bx, by, step_x, step_y):
        any_known = False
        for yy in range(by, max(by - step_y, -1), -1):
            row = yy * w
            for xx in range(bx, min(bx + step_x, w)):
                v = data[row + xx]
                if v >= 50:
                    return '#'
                if v >= 0:
                    any_known = True
        return '.' if any_known else ' '


def main():
    rclpy.init()
    node = MapViewer()
    deadline = node.get_clock().now().nanoseconds + 15_000_000_000  # 15 s
    while rclpy.ok() and not node.got and node.get_clock().now().nanoseconds < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)
    if not node.got:
        print("No /map received within 6s — is Unity running and publishing?",
              file=sys.stderr)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
