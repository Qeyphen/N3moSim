from __future__ import annotations

import n3_common.ros as ros
from n3_common.topics.n3mo_topics import GPS_FIX, MAP_ORIGIN
from n3_common.topics.sim_topics import COSTMAP_STATIC
from rclpy.node import Node


class LocalMapManagerNode(Node):
    """Publish the local map origin (ENU): first valid GPS fix becomes the origin, latched and re-published for late subscribers.

    Consumers subscribe to MAP_ORIGIN and build a LocalCartesianProjector from it.

    TODO-after: when too far from origin, re-initialize and publish a changeOrigin so users reproject their maps.
    """

    def __init__(self) -> None:
        super().__init__("local_map_manager")

        # use_fixed_origin: publish the given lat/lon/alt immediately instead of waiting for a GPS fix
        self.declare_parameter("use_fixed_origin", False)
        self.declare_parameter("fixed_origin_lat_deg", 0.0)
        self.declare_parameter("fixed_origin_lon_deg", 0.0)
        self.declare_parameter("fixed_origin_alt_m", 0.0)

        # publish_empty_costmap: latch a blank navigable grid so consumers need no fallback. Disable when a real costmap producer runs.
        self.declare_parameter("publish_empty_costmap", False)
        self.declare_parameter("empty_costmap_size_m", 1000.0)
        self.declare_parameter("empty_costmap_resolution_m", 5.0)
        # ENU center of the empty navigable square
        self.declare_parameter("empty_costmap_center_x_m", 0.0)
        self.declare_parameter("empty_costmap_center_y_m", 0.0)

        # stamped so the origin carries a date
        self.origin: ros.GeoPointStamped | None = None

        self.origin_pub = self.create_publisher(
            ros.GeoPointStamped,
            MAP_ORIGIN.name,
            MAP_ORIGIN.qos,
        )
        self.costmap_pub = self.create_publisher(
            ros.OccupancyGrid,
            COSTMAP_STATIC.name,
            COSTMAP_STATIC.qos,
        )

        self.gps_fix_sub = self.create_subscription(
            ros.NavSatFix,
            GPS_FIX.name,
            self.on_gps_fix,
            GPS_FIX.qos,
        )

        if self.get_parameter("use_fixed_origin").value:
            lat = float(self.get_parameter("fixed_origin_lat_deg").value)
            lon = float(self.get_parameter("fixed_origin_lon_deg").value)
            alt = float(self.get_parameter("fixed_origin_alt_m").value)
            stamp = self.get_clock().now().to_msg()
            self.origin = ros.GeoPointStamped(
                header=ros.Header(stamp=stamp, frame_id="map"),
                position=ros.GeoPoint(latitude=lat, longitude=lon, altitude=alt),
            )
            self.get_logger().info(
                f"Local map origin set from fixed params: "
                f"lat={lat:.8f}, lon={lon:.8f}, alt={alt:.3f}"
            )

        if self.get_parameter("publish_empty_costmap").value:
            self._publish_empty_costmap()

        # data is latched, but re-publish periodically to be safe
        self.publish_timer = self.create_timer(1.0, self.publish_origin)

        self.get_logger().info("local_map_manager started")

    def _publish_empty_costmap(self) -> None:
        size_m = float(self.get_parameter("empty_costmap_size_m").value)
        resolution = float(self.get_parameter("empty_costmap_resolution_m").value)
        center_x = float(self.get_parameter("empty_costmap_center_x_m").value)
        center_y = float(self.get_parameter("empty_costmap_center_y_m").value)
        cells = max(1, int(round(size_m / resolution)))
        stamp = self.get_clock().now().to_msg()
        msg = ros.OccupancyGrid(
            header=ros.Header(stamp=stamp, frame_id="map"),
            info=ros.MapMetaData(
                resolution=resolution,
                width=cells,
                height=cells,
                origin=ros.Pose(
                    position=ros.Point(
                        x=center_x - cells * resolution / 2.0,
                        y=center_y - cells * resolution / 2.0,
                        z=0.0,
                    ),
                    orientation=ros.Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
                ),
            ),
            data=[0] * (cells * cells),
        )
        self.costmap_pub.publish(msg)
        self.get_logger().info(
            f"Empty costmap published on {COSTMAP_STATIC.name}: "
            f"{cells}x{cells} cells @ {resolution} m/cell ({size_m} m square, "
            f"center=({center_x}, {center_y}))"
        )

    def on_gps_fix(self, fix_msg: ros.NavSatFix) -> None:
        if self.origin is not None:
            return
        if fix_msg.status.status < ros.NavSatStatus.STATUS_FIX:
            return
        self.origin = ros.GeoPointStamped(
            header=fix_msg.header,
            position=ros.GeoPoint(
                latitude=fix_msg.latitude,
                longitude=fix_msg.longitude,
                altitude=fix_msg.altitude,
            ),
        )

        self.get_logger().info(
            "Local map origin initialized at "
            f"lat={self.origin.position.latitude:.8f}, "
            f"lon={self.origin.position.longitude:.8f}, "
            f"alt={self.origin.position.altitude:.3f}, "
            f"date_sec={self.origin.header.stamp.sec}"
        )

        self.publish_origin()

    def publish_origin(self) -> None:
        if self.origin is None:
            return
        self.origin_pub.publish(self.origin)


def main() -> None:
    import rclpy

    rclpy.init()
    node = LocalMapManagerNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

