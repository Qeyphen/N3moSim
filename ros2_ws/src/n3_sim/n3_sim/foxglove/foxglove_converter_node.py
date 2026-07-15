from __future__ import annotations

import math

import n3_common.ros as ros
import rclpy
from n3_common.geo.local_cartesian_projector import LocalCartesianProjector
from n3_common.math_utils.angles import Deg
from n3_common.models import BoatVelocity, Direction, GeoPose2D, Pose2D
from n3_common.n3_const import DEG2RAD
from n3_common.ros.time import now_stamp
from n3_common.topics.n3mo_topics import (
    BOAT_POSE,
    BOAT_VELOCITY,
    CURRENT_WAYPOINT,
    MAP_ORIGIN,
    MISSION_GOALS,
    PLAN_WAYPOINTS,
    TARGET_VELOCITY,
    WIND_TRUE,
)
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import ColorRGBA

LATCHED_QOS = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)

# Colors (RGBA 0-1)
COLOR_GOAL = ColorRGBA(r=1.0, g=0.2, b=0.2, a=1.0)  # red
COLOR_PLAN = ColorRGBA(r=0.2, g=0.8, b=1.0, a=1.0)  # cyan
COLOR_CURRENT = ColorRGBA(r=0.2, g=1.0, b=0.2, a=1.0)  # green
COLOR_WIND = ColorRGBA(r=0.4, g=0.7, b=1.0, a=0.8)  # light blue / sky
COLOR_WIND_ARROW = ColorRGBA(r=0.2, g=0.5, b=0.9, a=0.9)  # darker blue
COLOR_TARGET_VEL = ColorRGBA(r=0.8, g=0.2, b=1.0, a=0.9)  # purple

MARKER_SCALE_POINT = 3.0
MARKER_SCALE_CURRENT = 5.0

# Wind marker placement: 20m upwind of boat
WIND_MARKER_DISTANCE = 20.0


class FoxgloveConverterNode(Node):
    """
    Convert navigation topics to Foxglove-friendly visualization messages.

    Subscriptions:
        /navigation/map/origin  (GeoPointStamped) — ENU origin for geo projection
        /mission/goals          (WaypointList)    — mission goal waypoints
        /plan/waypoints         (Path)            — planned ENU path
        /plan/waypoint          (PoseStamped)     — current target waypoint (ENU)
        /wind/true              (Wind)            — true wind direction and speed
        /boat/pose              (PoseStamped)     — boat position (ENU)

    Publications (map — NavSatFix):
        /debug/map/mission_goals    — one NavSatFix per goal (batch)
        /debug/map/plan_waypoints   — one NavSatFix per path point (batch)
        /debug/map/current_waypoint — single NavSatFix
        /debug/map/true_wind        — wind position on map

    Publications (3D — MarkerArray / TwistStamped):
        /debug/3d/mission_goals    — sphere markers at goal positions
        /debug/3d/plan_waypoints   — line strip + sphere markers
        /debug/3d/current_waypoint — large sphere marker
        /debug/3d/true_wind        — wind arrow + streamlines
        /debug/3d/velocity         — TwistStamped (COG arrow in map frame)
    """

    def __init__(self) -> None:
        super().__init__("foxglove_converter_node")

        self.projector: LocalCartesianProjector | None = None
        self.boat_x = 0.0
        self.boat_y = 0.0
        self.last_target_velocity: ros.Velocity | None = None
        self.last_mission_goals: ros.WaypointList | None = None

        # Tunable parameter visible in Foxglove
        self.declare_parameter("wind_marker_scale", 0.5)

        # --- map publishers (NavSatFix) ---
        self.map_goals_pub = self.create_publisher(
            ros.NavSatFix, "/debug/map/mission_goals", LATCHED_QOS
        )
        self.map_plan_pub = self.create_publisher(
            ros.NavSatFix, "/debug/map/plan_waypoints", LATCHED_QOS
        )
        self.map_current_pub = self.create_publisher(
            ros.NavSatFix, "/debug/map/current_waypoint", LATCHED_QOS
        )
        self.map_wind_pub = self.create_publisher(
            ros.NavSatFix, "/debug/map/true_wind", 10
        )

        # --- 3D publishers (MarkerArray) ---
        self.viz_goals_pub = self.create_publisher(
            ros.MarkerArray, "/debug/map3d/mission_goals", LATCHED_QOS
        )
        self.viz_plan_pub = self.create_publisher(
            ros.MarkerArray, "/debug/map3d/plan_waypoints", LATCHED_QOS
        )
        self.viz_current_pub = self.create_publisher(
            ros.MarkerArray, "/debug/map3d/current_waypoint", LATCHED_QOS
        )
        self.viz_wind_pub = self.create_publisher(
            ros.MarkerArray, "/debug/map3d/true_wind", 10
        )
        self.viz_velocity_pub = self.create_publisher(
            ros.MarkerArray, "/debug/map3d/velocity", 10
        )
        self.viz_target_velocity_pub = self.create_publisher(
            ros.MarkerArray, "/debug/map3d/target_velocity", 10
        )

        # --- subscriptions ---
        self.create_subscription(
            ros.GeoPointStamped,
            MAP_ORIGIN.name,
            self.on_origin,
            MAP_ORIGIN.qos,
        )
        self.create_subscription(
            ros.WaypointList,
            MISSION_GOALS.name,
            self.on_mission_goals,
            MISSION_GOALS.qos,
        )
        self.create_subscription(
            ros.Path,
            PLAN_WAYPOINTS.name,
            self.on_plan_waypoints,
            PLAN_WAYPOINTS.qos,
        )
        self.create_subscription(
            ros.PoseStamped,
            CURRENT_WAYPOINT.name,
            self.on_current_waypoint,
            CURRENT_WAYPOINT.qos,
        )
        self.create_subscription(
            ros.Wind,
            WIND_TRUE.name,
            self.on_true_wind,
            WIND_TRUE.qos,
        )
        self.create_subscription(
            ros.PoseStamped,
            BOAT_POSE.name,
            self.on_boat_pose,
            BOAT_POSE.qos,
        )
        self.create_subscription(
            ros.Velocity,
            BOAT_VELOCITY.name,
            self.on_boat_velocity,
            BOAT_VELOCITY.qos,
        )
        self.create_subscription(
            ros.Velocity,
            TARGET_VELOCITY.name,
            self.on_target_velocity,
            TARGET_VELOCITY.qos,
        )

        self.get_logger().info("FoxgloveConverterNode ready")

    # --- callbacks ---
    def on_origin(self, msg: ros.GeoPointStamped) -> None:
        if self.projector is None:
            self.projector = LocalCartesianProjector.from_ros_geopoint(msg)
            self.get_logger().info(
                f"Map origin received — projector initialized at lat={msg.position.latitude:.6f} lon={msg.position.longitude:.6f}"
            )
            # if the date of origin has changed, it means we have changed of local map and we need to recompute the projector
        elif self.projector.origin_date != msg.header.stamp.sec:
            self.projector = LocalCartesianProjector.from_ros_geopoint(msg)
            self.get_logger().info(
                f"Map origin changed — projector re-initialized at lat={msg.position.latitude:.6f} lon={msg.position.longitude:.6f}"
            )
        # Republish latched data that arrived before the projector was ready
        if self.last_mission_goals is not None:
            self.on_mission_goals(self.last_mission_goals)

    def on_boat_velocity(self, msg: ros.Velocity) -> None:
        vel = BoatVelocity.from_ros_velocity(msg)
        markers = _make_velocity_markers(
            stamp=now_stamp(self),
            boat_x=self.boat_x,
            boat_y=self.boat_y,
            cog_deg=msg.cog_deg,
            speed_kts=vel.sog_kts,
            ns="velocity",
            color=ColorRGBA(r=1.0, g=0.8, b=0.0, a=0.9),
            label=f"{vel.sog_kts:.1f} kts",
            z=1.0,
            shaft=0.4,
            head=0.8,
        )
        self.viz_velocity_pub.publish(markers)

    def on_target_velocity(self, msg: ros.Velocity) -> None:
        self.last_target_velocity = msg
        self._publish_target_velocity()

    def _publish_target_velocity(self) -> None:
        if self.last_target_velocity is None:
            return
        msg = self.last_target_velocity
        markers = _make_velocity_markers(
            stamp=now_stamp(self),
            boat_x=self.boat_x,
            boat_y=self.boat_y,
            cog_deg=msg.cog_deg,
            speed_kts=msg.sog_kts,
            ns="target_velocity",
            color=COLOR_TARGET_VEL,
            label=f"TGT {msg.sog_kts:.1f} kts",
            z=1.5,
            shaft=0.3,
            head=0.6,
        )
        self.viz_target_velocity_pub.publish(markers)

    def on_boat_pose(self, msg: ros.PoseStamped) -> None:
        self.boat_x = msg.pose.position.x
        self.boat_y = msg.pose.position.y
        self._publish_target_velocity()

    def on_mission_goals(self, msg: ros.WaypointList) -> None:
        self.last_mission_goals = msg
        stamp = now_stamp(self)

        # Map: one NavSatFix per goal (lat/lon already in the message)
        for wp in msg.waypoints:
            fix = _make_navsat(stamp, wp.lat_deg, wp.lon_deg)
            self.map_goals_pub.publish(fix)

        # 3D: need projector to convert lat/lon to ENU
        if not self.projector:
            return

        markers = ros.MarkerArray()
        for i, wp in enumerate(msg.waypoints):
            m = _make_sphere_marker(
                stamp, "mission_goals", i, COLOR_GOAL, MARKER_SCALE_POINT
            )
            geo = GeoPose2D(
                lat_deg=wp.lat_deg,
                lon_deg=wp.lon_deg,
                heading=Direction(deg=Deg(wp.heading_deg)),
            )
            pose = self.projector.geopose2d_to_pose2d(geo)
            m.pose.position.x = pose.x
            m.pose.position.y = pose.y
            markers.markers.append(m)
        self.viz_goals_pub.publish(markers)

    def on_plan_waypoints(self, msg: ros.Path) -> None:
        if not self.projector:
            return
        stamp = now_stamp(self)

        # Map: inverse-project ENU poses to NavSatFix
        for ps in msg.poses:
            pose = Pose2D.from_ros_pose(ps.pose)
            geo = self.projector.pose2d_to_geopose2d(pose)
            fix = _make_navsat(stamp, geo.lat_deg, geo.lon_deg)
            self.map_plan_pub.publish(fix)

        # 3D: line strip + point markers
        markers = ros.MarkerArray()

        # line strip connecting all waypoints
        if len(msg.poses) >= 2:
            line = _make_base_marker(stamp, "plan_line", 0)
            line.type = ros.Marker.LINE_STRIP
            line.scale.x = 0.5
            line.color = COLOR_PLAN
            for ps in msg.poses:
                line.points.append(ps.pose.position)
            markers.markers.append(line)

        # sphere at each waypoint
        for i, ps in enumerate(msg.poses):
            m = _make_sphere_marker(
                stamp, "plan_waypoints", i, COLOR_PLAN, MARKER_SCALE_POINT
            )
            m.pose = ps.pose
            markers.markers.append(m)

        self.viz_plan_pub.publish(markers)

    def on_current_waypoint(self, msg: ros.PoseStamped) -> None:
        if not self.projector:
            return
        stamp = now_stamp(self)

        # Map: single NavSatFix
        pose = Pose2D.from_ros_pose(msg.pose)
        geo = self.projector.pose2d_to_geopose2d(pose)
        fix = _make_navsat(stamp, geo.lat_deg, geo.lon_deg)
        self.map_current_pub.publish(fix)

        # 3D: single large sphere
        markers = ros.MarkerArray()
        m = _make_sphere_marker(
            stamp, "current_waypoint", 0, COLOR_CURRENT, MARKER_SCALE_CURRENT
        )
        m.pose = msg.pose
        markers.markers.append(m)
        self.viz_current_pub.publish(markers)

    def on_true_wind(self, msg: ros.Wind) -> None:
        stamp = now_stamp(self)

        # Wind direction: "coming from" in deg CW from North
        # Convert to ENU angle: direction the wind blows TOWARD
        # Wind from North (0) blows toward South = ENU angle -pi/2
        wind_from_deg = msg.direction_deg
        # Direction wind is going TO (opposite of coming from)
        wind_to_rad = math.radians(90.0 - wind_from_deg + 180.0)

        # Position the marker 20m upwind of the boat
        # Upwind = where the wind comes FROM
        wind_from_rad = math.radians(90.0 - wind_from_deg)
        wind_x = self.boat_x + WIND_MARKER_DISTANCE * math.cos(wind_from_rad)
        wind_y = self.boat_y + WIND_MARKER_DISTANCE * math.sin(wind_from_rad)

        # --- 3D markers ---
        scale = self.get_parameter("wind_marker_scale").value
        markers = ros.MarkerArray()
        markers.markers.extend(
            _make_wind_markers(
                stamp, wind_x, wind_y, wind_to_rad, msg.speed_kts, wind_from_deg, scale
            )
        )
        self.viz_wind_pub.publish(markers)

        # --- Map: NavSatFix at wind marker position (requires projector) ---
        if self.projector:
            pose = Pose2D(
                x=wind_x, y=wind_y, yaw=Direction(deg=Deg(0.0)).to_enu_angle()
            )
            geo = self.projector.pose2d_to_geopose2d(pose)
            fix = _make_navsat(stamp, geo.lat_deg, geo.lon_deg)
            self.map_wind_pub.publish(fix)


# --- helpers ---


def _make_navsat(stamp: ros.MsgStamp, lat: float, lon: float) -> ros.NavSatFix:
    fix = ros.NavSatFix()
    fix.header.stamp = stamp
    fix.header.frame_id = "map"
    fix.latitude = lat
    fix.longitude = lon
    fix.status.status = ros.NavSatStatus.STATUS_FIX
    return fix


def _make_base_marker(stamp: ros.MsgStamp, ns: str, marker_id: int) -> ros.Marker:
    m = ros.Marker()
    m.header.stamp = stamp
    m.header.frame_id = "map"
    m.ns = ns
    m.id = marker_id
    m.action = ros.Marker.ADD
    return m


def _make_sphere_marker(
    stamp: ros.MsgStamp,
    ns: str,
    marker_id: int,
    color: ColorRGBA,
    scale: float,
) -> ros.Marker:
    m = _make_base_marker(stamp, ns, marker_id)
    m.type = ros.Marker.SPHERE
    m.scale.x = scale
    m.scale.y = scale
    m.scale.z = scale
    m.color = color
    return m


def _make_velocity_markers(
    stamp: ros.MsgStamp,
    boat_x: float,
    boat_y: float,
    cog_deg: float,
    speed_kts: float,
    ns: str,
    color: ColorRGBA,
    label: str,
    z: float = 1.0,
    shaft: float = 0.4,
    head: float = 0.8,
) -> ros.MarkerArray:
    cog_enu_rad = (90.0 - cog_deg) * DEG2RAD
    arrow_len = speed_kts * 4.0
    dx = math.cos(cog_enu_rad)
    dy = math.sin(cog_enu_rad)

    arrow = _make_base_marker(stamp, ns, 0)
    arrow.type = ros.Marker.ARROW
    arrow.points = [
        ros.Point(x=boat_x, y=boat_y, z=z),
        ros.Point(x=boat_x + dx * arrow_len, y=boat_y + dy * arrow_len, z=z),
    ]
    arrow.scale.x = shaft
    arrow.scale.y = head
    arrow.scale.z = 1.0
    arrow.color = color

    text = _make_base_marker(stamp, ns, 1)
    text.type = ros.Marker.TEXT_VIEW_FACING
    text.pose.position.x = boat_x + dx * arrow_len
    text.pose.position.y = boat_y + dy * arrow_len
    text.pose.position.z = z + 2.0
    text.scale.z = 1.0
    text.color = color
    text.text = label

    markers = ros.MarkerArray()
    markers.markers = [arrow, text]
    return markers


def _make_wind_markers(
    stamp: ros.MsgStamp,
    cx: float,
    cy: float,
    wind_to_rad: float,
    speed_kts: float,
    wind_from_deg: float,
    scale: float = 0.5,
) -> list[ros.Marker]:
    """
    Create wind visualization markers at position (cx, cy).

    The wind is represented as:
    - A large arrow showing wind direction (pointing downwind)
    - Parallel streamlines (3 lines) showing wind flow
    - Arrow length proportional to wind speed

    Returns a list of Marker messages.
    """
    s = scale  # shorthand
    markers = []
    dx = math.cos(wind_to_rad)
    dy = math.sin(wind_to_rad)

    # Arrow length scales with wind speed (1 kts = 1m, capped), then scaled
    arrow_len = min(max(speed_kts * 1.0, 5.0), 30.0) * s

    # --- Main arrow (ARROW type) ---
    arrow = _make_base_marker(stamp, "true_wind", 0)
    arrow.type = ros.Marker.ARROW
    tail = ros.Point(
        x=cx - dx * arrow_len / 2,
        y=cy - dy * arrow_len / 2,
        z=3.0 * s,
    )
    tip = ros.Point(
        x=cx + dx * arrow_len / 2,
        y=cy + dy * arrow_len / 2,
        z=3.0 * s,
    )
    arrow.points = [tail, tip]
    arrow.scale.x = 1.2 * s  # shaft diameter
    arrow.scale.y = 2.5 * s  # head diameter
    arrow.scale.z = 3.0 * s  # head length
    arrow.color = COLOR_WIND_ARROW
    markers.append(arrow)

    # --- Streamlines: 3 parallel flow lines offset perpendicular to wind ---
    perp_x = -dy
    perp_y = dx
    offsets = [-6.0 * s, 0.0, 6.0 * s]

    for i, offset in enumerate(offsets):
        line = _make_base_marker(stamp, "true_wind", 1 + i)
        line.type = ros.Marker.LINE_STRIP
        line.scale.x = 0.4 * s

        ox = cx + perp_x * offset
        oy = cy + perp_y * offset

        n_points = 20
        wave_len = arrow_len * 1.2
        amplitude = 1.5 * s

        for j in range(n_points):
            t = j / (n_points - 1) - 0.5
            along = t * wave_len
            across = amplitude * math.sin(t * 4 * math.pi)
            px = ox + dx * along + perp_x * across
            py = oy + dy * along + perp_y * across
            line.points.append(ros.Point(x=px, y=py, z=2.5 * s))
            alpha = 0.3 + 0.5 * (1.0 - abs(t * 2))
            line.colors.append(ColorRGBA(r=0.4, g=0.7, b=1.0, a=float(alpha)))

        markers.append(line)

    # --- Speed text ---
    text = _make_base_marker(stamp, "true_wind", 10)
    text.type = ros.Marker.TEXT_VIEW_FACING
    text.pose.position.x = cx
    text.pose.position.y = cy
    text.pose.position.z = 6.0 * s
    text.scale.z = 2.0 * s  # text height
    text.color = COLOR_WIND_ARROW
    text.text = f"{wind_from_deg:.0f}° {speed_kts:.0f} kts"
    markers.append(text)

    return markers


def main() -> None:
    rclpy.init()
    node = FoxgloveConverterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
