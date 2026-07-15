"""Boat trajectory generator — cyclic trajectory within costmap navigable area.

Publishes PoseStamped and broadcasts TF map -> boat_link.
Used for lightweight sim testing and dataset collection.
"""

from __future__ import annotations

import math
import random

import n3_common.models as pyd
import n3_common.ros as ros
import rclpy
from n3_common.geo.local_cartesian_projector import LocalCartesianProjector
from n3_common.n3_const import KTS_TO_MS
from n3_common.topics.n3mo_topics import MAP_ORIGIN
from n3_common.topics.sim_topics import COSTMAP_STATIC, SIM_POSE
from rclpy.node import Node
from tf2_ros import TransformBroadcaster

from ..scenario_generator.scenario_model import NavigableArea, extract_navigable_area
from .boat_traj_generator_params import BoatTrajGeneratorParams

DEBUG_GPS_FIX_TOPIC = "/debug/gps/fix"


Bounds = tuple[float, float, float, float]  # (min_x, max_x, min_y, max_y)


def _generate_lawnmower(
    nav: NavigableArea,
    bounds: Bounds,
    spacing_m: float = 50.0,
) -> list[tuple[float, float]]:
    """Generate a lawnmower pattern covering the bounded navigable area."""
    min_x, max_x, min_y, max_y = bounds

    points: list[tuple[float, float]] = []
    y = min_y
    forward = True
    while y <= max_y:
        if forward:
            x_range = _navigable_x_range(nav, y, min_x, max_x)
        else:
            x_range = list(reversed(_navigable_x_range(nav, y, min_x, max_x)))
        points.extend(x_range)
        y += spacing_m
        forward = not forward

    if len(points) < 2:
        cx = (min_x + max_x) / 2
        cy = (min_y + max_y) / 2
        points = [(cx - 10, cy), (cx + 10, cy)]
    return points


def _navigable_x_range(
    nav: NavigableArea,
    y: float,
    min_x: float,
    max_x: float,
) -> list[tuple[float, float]]:
    """Sample navigable points along a horizontal line."""
    step = nav.resolution * 5
    points: list[tuple[float, float]] = []
    x = min_x
    while x <= max_x:
        if nav.is_navigable(x, y):
            points.append((x, y))
        x += step
    return points


def _generate_circle(
    nav: NavigableArea,
    bounds: Bounds,
    radius_m: float = 0.0,
) -> list[tuple[float, float]]:
    """Generate a circular trajectory centered in the bounded area.

    radius_m > 0 overrides the radius derived from the area bounds.
    """
    min_x, max_x, min_y, max_y = bounds
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    if radius_m > 0.0:
        radius = radius_m
    else:
        radius = max(10.0, min(max_x - min_x, max_y - min_y) / 5 * 0.9)

    n_points = max(160, int(2 * math.pi * radius))
    points: list[tuple[float, float]] = []
    for i in range(n_points):
        angle = 2 * math.pi * i / n_points
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        if nav.is_navigable(x, y):
            points.append((x, y))

    if len(points) < 2:
        points = [(cx - 10, cy), (cx + 10, cy)]
    return points


def _generate_random_walk(
    nav: NavigableArea,
    bounds: Bounds,
    rng: random.Random,
    n_points: int = 30,
) -> list[tuple[float, float]]:
    """Generate a random walk trajectory within the bounded navigable area."""
    min_x, max_x, min_y, max_y = bounds

    def sample_in_bounds() -> tuple[float, float]:
        for _ in range(200):
            sx = rng.uniform(min_x, max_x)
            sy = rng.uniform(min_y, max_y)
            if nav.is_navigable(sx, sy):
                return sx, sy
        return (min_x + max_x) / 2, (min_y + max_y) / 2

    def in_bounds(px: float, py: float) -> bool:
        return (
            min_x <= px <= max_x
            and min_y <= py <= max_y
            and nav.is_navigable(px, py)
        )

    x, y = sample_in_bounds()
    heading = rng.uniform(0, 2 * math.pi)
    points: list[tuple[float, float]] = [(x, y)]

    for _ in range(n_points - 1):
        heading += rng.gauss(0, 0.5)
        dist = rng.uniform(20, 80)
        nx = x + dist * math.cos(heading)
        ny = y + dist * math.sin(heading)
        if not in_bounds(nx, ny):
            heading += math.pi * 0.7
            nx = x + dist * math.cos(heading)
            ny = y + dist * math.sin(heading)
            if not in_bounds(nx, ny):
                nx, ny = sample_in_bounds()
        x, y = nx, ny
        points.append((x, y))

    return points


class BoatTrajGeneratorNode(Node):
    def __init__(self) -> None:
        super().__init__("boat_traj_generator_node", enable_logger_service=True)

        self.params = BoatTrajGeneratorParams(self)
        p = self.params.p

        self.trajectory: list[tuple[float, float]] = []
        self.traj_index: int = 0
        self.segment_progress: float = 0.0
        self.last_tick = self.get_clock().now()
        self.projector: LocalCartesianProjector | None = None

        # Publishers
        self.pose_pub = self.create_publisher(
            ros.PoseStamped,
            SIM_POSE.name,
            SIM_POSE.qos,
        )
        self.gps_fix_pub = self.create_publisher(
            ros.NavSatFix,
            DEBUG_GPS_FIX_TOPIC,
            10,
        )
        self.tf_broadcaster = TransformBroadcaster(self)

        # Subscriptions
        self.create_subscription(
            ros.OccupancyGrid,
            COSTMAP_STATIC.name,
            self.on_costmap,
            COSTMAP_STATIC.qos,
        )
        self.create_subscription(
            ros.GeoPointStamped,
            MAP_ORIGIN.name,
            self.on_map_origin,
            MAP_ORIGIN.qos,
        )

        # Timer (starts immediately but does nothing until costmap arrives)
        self.timer = self.create_timer(1.0 / p.publish_rate_hz, self.on_timer)

        self.log = self.get_logger()
        self.log.info("BoatTrajGeneratorNode waiting for costmap...")

    def _effective_bounds(self, nav: NavigableArea) -> Bounds:
        p = self.params.p
        min_x = nav.origin_x + p.margin_m
        max_x = nav.origin_x + nav.width * nav.resolution - p.margin_m
        min_y = nav.origin_y + p.margin_m
        max_y = nav.origin_y + nav.height * nav.resolution - p.margin_m

        if p.area_extent_x_m > 0.0:
            min_x = max(min_x, p.area_center_x_m - p.area_extent_x_m / 2.0)
            max_x = min(max_x, p.area_center_x_m + p.area_extent_x_m / 2.0)
        if p.area_extent_y_m > 0.0:
            min_y = max(min_y, p.area_center_y_m - p.area_extent_y_m / 2.0)
            max_y = min(max_y, p.area_center_y_m + p.area_extent_y_m / 2.0)
        return min_x, max_x, min_y, max_y

    def on_map_origin(self, msg: ros.GeoPointStamped) -> None:
        if self.projector is None:
            self.projector = LocalCartesianProjector.from_ros_geopoint(msg)
            self.log.info(
                f"Map origin received — projector initialized at "
                f"lat={msg.position.latitude:.6f} lon={msg.position.longitude:.6f}"
            )
        elif self.projector.origin_date != msg.header.stamp.sec:
            self.projector = LocalCartesianProjector.from_ros_geopoint(msg)
            self.log.info(
                f"Map origin changed — projector re-initialized at "
                f"lat={msg.position.latitude:.6f} lon={msg.position.longitude:.6f}"
            )

    def on_costmap(self, msg: ros.OccupancyGrid) -> None:
        p = self.params.p
        info = msg.info
        nav = extract_navigable_area(
            data=list(msg.data),
            width=info.width,
            height=info.height,
            resolution=info.resolution,
            origin_x=info.origin.position.x,
            origin_y=info.origin.position.y,
            margin_m=p.margin_m,
        )

        bounds = self._effective_bounds(nav)
        rng = random.Random(p.random_seed) if p.random_seed > 0 else random.Random()

        if p.trajectory_type == "lawnmower":
            self.trajectory = _generate_lawnmower(nav, bounds)
        elif p.trajectory_type == "circle":
            self.trajectory = _generate_circle(nav, bounds, p.circle_radius_m)
        else:
            self.trajectory = _generate_random_walk(nav, bounds, rng)

        self.traj_index = 0
        self.segment_progress = 0.0
        self.log.info(
            f"Generated {p.trajectory_type} trajectory: "
            f"{len(self.trajectory)} waypoints"
        )

    def on_timer(self) -> None:
        if len(self.trajectory) < 2:
            return

        p = self.params.p
        now = self.get_clock().now()
        dt = (now - self.last_tick).nanoseconds * 1e-9
        self.last_tick = now

        speed_ms = p.speed_kts * KTS_TO_MS

        # Current segment
        i = self.traj_index % len(self.trajectory)
        j = (i + 1) % len(self.trajectory)
        ax, ay = self.trajectory[i]
        bx, by = self.trajectory[j]

        seg_len = math.hypot(bx - ax, by - ay)
        if seg_len < 0.01:
            self.traj_index = (self.traj_index + 1) % len(self.trajectory)
            self.segment_progress = 0.0
            return

        # Advance along segment
        self.segment_progress += speed_ms * dt / seg_len

        while self.segment_progress >= 1.0:
            self.segment_progress -= 1.0
            self.traj_index = (self.traj_index + 1) % len(self.trajectory)
            i = self.traj_index % len(self.trajectory)
            j = (i + 1) % len(self.trajectory)
            ax, ay = self.trajectory[i]
            bx, by = self.trajectory[j]
            seg_len = math.hypot(bx - ax, by - ay)
            if seg_len < 0.01:
                continue

        alpha = self.segment_progress
        x = ax + alpha * (bx - ax)
        y = ay + alpha * (by - ay)
        heading_rad = math.atan2(by - ay, bx - ax)

        q_z = math.sin(heading_rad / 2.0)
        q_w = math.cos(heading_rad / 2.0)

        stamp = now.to_msg()

        # Publish PoseStamped
        pose_msg = ros.PoseStamped(
            header=ros.Header(stamp=stamp, frame_id="map"),
            pose=ros.Pose(
                position=ros.Point(x=x, y=y, z=0.0),
                orientation=ros.Quaternion(x=0.0, y=0.0, z=q_z, w=q_w),
            ),
        )
        self.pose_pub.publish(pose_msg)

        # Publish projected NavSatFix on /debug/gps/fix (for the Foxglove Map panel).
        # Requires a map origin to have been received from /navigation/map/origin.
        if self.projector is not None:
            pose2d = pyd.Pose2D.from_ros_pose(pose_msg.pose)
            geopose = self.projector.pose2d_to_geopose2d(pose2d)
            fix = ros.NavSatFix()
            fix.header = pose_msg.header
            fix.latitude = geopose.lat_deg
            fix.longitude = geopose.lon_deg
            fix.altitude = 0.0
            fix.status.status = ros.NavSatStatus.STATUS_FIX
            fix.status.service = ros.NavSatStatus.SERVICE_GPS
            self.gps_fix_pub.publish(fix)

        # Broadcast TF map -> boat_link
        self.tf_broadcaster.sendTransform(
            ros.TransformStamped(
                header=ros.Header(stamp=stamp, frame_id="map"),
                child_frame_id="boat_link",
                transform=ros.Transform(
                    translation=ros.Vector3(x=x, y=y, z=0.0),
                    rotation=ros.Quaternion(x=0.0, y=0.0, z=q_z, w=q_w),
                ),
            )
        )


def main() -> None:
    rclpy.init()
    node = BoatTrajGeneratorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
