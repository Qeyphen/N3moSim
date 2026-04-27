import numpy as np
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseArray
from nav_msgs.msg import OccupancyGrid, MapMetaData
from n3mo_control.config_loader import load_config

OBJECT_RADIUS_CELLS = {
    "sailboat":  3,
    "catamaran": 4,
    "buoy":      2,
}
DEFAULT_RADIUS = 2

class OccupancyGridServer(Node):
    def __init__(self):
        super().__init__('occupancy_grid_server')

        self.declare_parameter('resolution', 1.0)
        self.declare_parameter('width_m',   500.0)
        self.declare_parameter('height_m',  500.0)
        self.declare_parameter('origin_x', -250.0)
        self.declare_parameter('origin_y', -250.0)

        self.resolution = self.get_parameter('resolution').value
        self.width_m    = self.get_parameter('width_m').value
        self.height_m   = self.get_parameter('height_m').value
        self.origin_x   = self.get_parameter('origin_x').value
        self.origin_y   = self.get_parameter('origin_y').value

        self.config     = load_config(self.get_logger())
        self.live_poses = []

        self.create_subscription(
            PoseArray, '/unity/all_poses', self._on_poses, 10)

        self.grid_pub = self.create_publisher(
            OccupancyGrid, '/occupancy_grid', 10)

        self.create_timer(1.0, self._publish_grid)

        self.get_logger().info(
            f'OccupancyGridServer ready — '
            f'{self.width_m}x{self.height_m}m @ {self.resolution}m/cell'
        )

    def _on_poses(self, msg: PoseArray):
        self.live_poses = [(p.position.x, p.position.z) for p in msg.poses]

    def _build_grid(self):
        res  = self.resolution
        cols = int(self.width_m  / res)
        rows = int(self.height_m / res)

        # use plain Python list of ints — avoids numpy int8 serialization issues
        data = [0] * (rows * cols)

        def mark(wx, wz, obj_type):
            cx = int((wx - self.origin_x) / res)
            cy = int((wz - self.origin_y) / res)
            r  = OBJECT_RADIUS_CELLS.get(obj_type, DEFAULT_RADIUS)
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dx*dx + dy*dy <= r*r:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < cols and 0 <= ny < rows:
                            data[ny * cols + nx] = 100

        if self.config:
            for obj in self.config.get('objects', []):
                if obj.get('dynamic', False):
                    continue
                pos   = obj.get('position', [0, 0, 0])
                otype = obj.get('type', 'buoy').lower()
                mark(pos[0], pos[2], otype)
                self.get_logger().info(
                    f'Static obstacle: {obj.get("id")} at cell '
                    f'({int((pos[0]-self.origin_x)/res)}, '
                    f'{int((pos[2]-self.origin_y)/res)})'
                )

        for wx, wz in self.live_poses:
            mark(wx, wz, 'unknown')

        occupied = data.count(100)
        self.get_logger().debug(f'Grid built: {occupied} occupied cells')

        grid                        = OccupancyGrid()
        grid.header.frame_id        = 'world'
        grid.header.stamp           = self.get_clock().now().to_msg()
        grid.info                   = MapMetaData()
        grid.info.resolution        = float(res)
        grid.info.width             = cols
        grid.info.height            = rows
        grid.info.origin.position.x = float(self.origin_x)
        grid.info.origin.position.y = float(self.origin_y)
        grid.data                   = data
        return grid

    def _publish_grid(self):
        self.grid_pub.publish(self._build_grid())


def main(args=None):
    rclpy.init(args=args)
    node = OccupancyGridServer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
