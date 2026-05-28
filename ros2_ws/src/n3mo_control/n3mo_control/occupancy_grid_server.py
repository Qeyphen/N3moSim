import rclpy
from rclpy.node import Node
from rclpy.executors import MultiThreadedExecutor
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
        self.declare_parameter('width_m',    1000.0)
        self.declare_parameter('height_m',   1000.0)
        self.declare_parameter('origin_x',   -500.0)
        self.declare_parameter('origin_y',   -500.0)

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
        if self.live_poses:
            self.get_logger().info(
                f'[poses] received {len(self.live_poses)} objects — '
                f'first: ({self.live_poses[0][0]:.1f}, {self.live_poses[0][1]:.1f})'
            )

    def _build_grid(self):
        res  = self.resolution
        cols = int(self.width_m  / res)
        rows = int(self.height_m / res)

        data = [0] * (rows * cols)

        def mark(wx, wz, obj_type):
            cx = int((wx - self.origin_x) / res)
            cy = int((wz - self.origin_y) / res)
            r  = OBJECT_RADIUS_CELLS.get(obj_type, DEFAULT_RADIUS)
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if dx * dx + dy * dy <= r * r:
                        nx, ny = cx + dx, cy + dy
                        if 0 <= nx < cols and 0 <= ny < rows:
                            data[ny * cols + nx] = 100

        # ── static obstacles from config ──────────────────────
        if self.config:
            for obj in self.config.get('objects', []):
                if obj.get('dynamic', False):
                    continue
                pos   = obj.get('position', [0, 0, 0])
                otype = obj.get('type', 'buoy').lower()
                mark(pos[0], pos[2], otype)
                self.get_logger().info(
                    f'Static obstacle: {obj.get("id")} at cell '
                    f'({int((pos[0] - self.origin_x) / res)}, '
                    f'{int((pos[2] - self.origin_y) / res)})'
                )

        # ── live poses from Unity ─────────────────────────────
        # index 0 = sailboat_01 (dynamic, first in config)
        # index 1+ = buoys (static, already marked above — skip)
        # we only mark index 0 (the vessel) to avoid double-marking buoys
        if self.live_poses:
            wx, wz = self.live_poses[0]
            mark(wx, wz, 'sailboat')
            self.get_logger().info(
                f'Live vessel at ({wx:.1f}, {wz:.1f}) → '
                f'cell ({int((wx - self.origin_x) / res)}, '
                f'{int((wz - self.origin_y) / res)})'
            )

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

    # MultiThreadedExecutor allows subscription and timer to run concurrently
    # without this the _on_poses callback gets blocked by _publish_grid timer
    executor = MultiThreadedExecutor()
    executor.add_node(node)

    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()