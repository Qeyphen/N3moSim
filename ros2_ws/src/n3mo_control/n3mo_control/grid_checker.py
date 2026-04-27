"""
grid_checker.py
===============
Diagnostic node — subscribes to /occupancy_grid and prints stats.
Run any time to verify the occupancy grid is working correctly.

Usage:
  ros2 run n3mo_control grid_checker
"""

import rclpy
from rclpy.node import Node
from nav_msgs.msg import OccupancyGrid


class GridChecker(Node):
    def __init__(self):
        super().__init__('grid_checker')
        self.create_subscription(
            OccupancyGrid, '/occupancy_grid', self.on_grid, 10)
        self.get_logger().info('Waiting for /occupancy_grid...')

    def on_grid(self, msg):
        total    = len(msg.data)
        occupied = sum(1 for v in msg.data if v == 100)
        free     = sum(1 for v in msg.data if v == 0)
        unknown  = sum(1 for v in msg.data if v == -1)

        self.get_logger().info('─' * 40)
        self.get_logger().info(f'Map size    : {msg.info.width}x{msg.info.height} cells')
        self.get_logger().info(f'Resolution  : {msg.info.resolution}m/cell')
        self.get_logger().info(f'Origin      : ({msg.info.origin.position.x}, {msg.info.origin.position.y})')
        self.get_logger().info(f'Total cells : {total}')
        self.get_logger().info(f'Occupied    : {occupied}  (value=100)')
        self.get_logger().info(f'Free        : {free}  (value=0)')
        self.get_logger().info(f'Unknown     : {unknown}  (value=-1)')
        self.get_logger().info('─' * 40)


def main(args=None):
    rclpy.init(args=args)
    node = GridChecker()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
