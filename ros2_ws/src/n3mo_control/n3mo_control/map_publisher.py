#!/usr/bin/env python3
"""Publish a real-world costmap (from realworld_scene.py) as a latched nav_msgs/OccupancyGrid on /map.

The scenario generator then spawns traffic on the real lake. Reads <dir>/<name>_costmap.png +
<name>_meta.json.

  ros2 run n3mo_control map_publisher --ros-args -p name:=lake_geneva
"""

import json
import os

import numpy as np
import rclpy
from PIL import Image
from nav_msgs.msg import OccupancyGrid
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy


class MapPublisher(Node):
    def __init__(self):
        super().__init__("map_publisher")
        self.declare_parameter("name", "lake_geneva")
        self.declare_parameter("dir", "/n3mosim/config/realworld")
        self.declare_parameter("topic", "/map")

        name = self.get_parameter("name").value
        base = os.path.join(self.get_parameter("dir").value, name)
        meta = json.load(open(base + "_meta.json"))
        img = np.array(Image.open(base + "_costmap.png").convert("L"))

        # PNG is top-row-first; OccupancyGrid is bottom-row-first. white(255)=land=100, black=water=0.
        occ = np.where(np.flipud(img) > 127, 100, 0).astype(np.int8)

        grid = OccupancyGrid()
        grid.header.frame_id = "map"
        grid.info.resolution = float(meta["resolution_m"])
        grid.info.width = int(meta["width"])
        grid.info.height = int(meta["height"])
        grid.info.origin.position.x = float(meta["origin_x_m"])
        grid.info.origin.position.y = float(meta["origin_y_m"])
        grid.info.origin.orientation.w = 1.0
        grid.data = occ.flatten().tolist()

        qos = QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                         reliability=QoSReliabilityPolicy.RELIABLE)
        self.pub = self.create_publisher(OccupancyGrid, self.get_parameter("topic").value, qos)
        self.pub.publish(grid)
        self.get_logger().info(
            f"published '{name}' costmap: {grid.info.width}x{grid.info.height} @ "
            f"{grid.info.resolution} m/cell on {self.get_parameter('topic').value} (latched).")


def main():
    rclpy.init()
    node = MapPublisher()
    rclpy.spin(node)      # keep the latched publisher alive
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
