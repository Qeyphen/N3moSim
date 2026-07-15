"""Track visualization — converts TrackArray to MarkerArray + NavSatFix.

3D panel: MarkerArray with per-type shapes, colors, labels.
Map panel: NavSatFix per track (projected from ENU to lat/lon).
"""

from __future__ import annotations

import math

import n3_common.models as pyd
import n3_common.ros as ros
import rclpy
from n3_common.geo.local_cartesian_projector import LocalCartesianProjector
from n3_common.topics.n3mo_topics import MAP_ORIGIN
from n3_common.topics.sim_topics import SIM_TRACKS, SIM_TRACKS_MARKERS
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import ColorRGBA

LATCHED_QOS = QoSProfile(
    depth=1,
    reliability=ReliabilityPolicy.RELIABLE,
    durability=DurabilityPolicy.TRANSIENT_LOCAL,
)

# noinspection PyTypeChecker
# Track type value → (shape, color RGBA, label, scale_xy, scale_z)
_TYPE_VIZ: dict[int, tuple[int, ColorRGBA, str, float, float]] = {
    0: (ros.Marker.SPHERE, ColorRGBA(r=0.5, g=0.5, b=0.5, a=1.0), "Unknown", 2.0, 2.0),
    1: (ros.Marker.ARROW, ColorRGBA(r=1.0, g=1.0, b=1.0, a=1.0), "Sailboat", 6.0, 2.0),
    2: (ros.Marker.CUBE, ColorRGBA(r=0.2, g=0.4, b=0.8, a=1.0), "Motorboat", 5.0, 2.0),
    3: (ros.Marker.CUBE, ColorRGBA(r=0.0, g=0.8, b=0.8, a=1.0), "Jetski", 2.5, 1.0),
    4: (ros.Marker.CYLINDER, ColorRGBA(r=1.0, g=0.6, b=0.0, a=1.0), "Kayak", 4.0, 0.5),
    5: (ros.Marker.CYLINDER, ColorRGBA(r=1.0, g=0.9, b=0.2, a=1.0), "Paddleboard", 3.0, 0.3),
    6: (ros.Marker.SPHERE, ColorRGBA(r=1.0, g=0.2, b=0.2, a=1.0), "Swimmer", 0.8, 0.8),
    7: (ros.Marker.CUBE, ColorRGBA(r=0.4, g=0.8, b=0.4, a=1.0), "Dinghy", 3.0, 1.0),
    8: (ros.Marker.CUBE, ColorRGBA(r=0.6, g=0.4, b=0.2, a=1.0), "Fishing boat", 6.0, 2.5),
    9: (ros.Marker.CUBE, ColorRGBA(r=0.6, g=0.2, b=0.8, a=1.0), "Ferry", 15.0, 4.0),
    10: (ros.Marker.CUBE, ColorRGBA(r=0.3, g=0.3, b=0.3, a=1.0), "Cargo", 30.0, 6.0),
    11: (ros.Marker.SPHERE, ColorRGBA(r=1.0, g=1.0, b=0.0, a=1.0), "Buoy", 1.5, 1.5),
    12: (ros.Marker.SPHERE, ColorRGBA(r=0.5, g=0.1, b=0.1, a=1.0), "Debris", 1.0, 0.5),
    13: (ros.Marker.ARROW, ColorRGBA(r=1.0, g=0.4, b=0.7, a=1.0), "Windsurf", 3.0, 1.0),
    14: (ros.Marker.ARROW, ColorRGBA(r=0.8, g=0.2, b=0.6, a=1.0), "Kitesurf", 3.0, 1.0),
    15: (ros.Marker.CUBE, ColorRGBA(r=0.6, g=1.0, b=0.2, a=1.0), "Pedalo", 3.0, 1.0),
}

_DEFAULT_VIZ = (ros.Marker.SPHERE, ColorRGBA(r=0.5, g=0.5, b=0.5, a=1.0), "?", 2.0, 2.0)


def _make_shape_marker(
    header: ros.Header,
    track: ros.Track,
    marker_id: int,
) -> ros.Marker:
    shape, color, _label, scale_xy, scale_z = _TYPE_VIZ.get(track.type, _DEFAULT_VIZ)
    m = ros.Marker()
    m.header = header
    m.ns = "tracks"
    m.id = marker_id
    m.type = shape
    m.action = ros.Marker.ADD
    m.pose = track.pose
    m.scale.x = scale_xy
    m.scale.y = scale_xy
    m.scale.z = scale_z
    m.color = color
    m.lifetime.sec = 0
    m.lifetime.nanosec = 300_000_000  # 300ms
    return m


def _make_text_marker(
    header: ros.Header,
    track: ros.Track,
    marker_id: int,
) -> ros.Marker:
    _shape, _color, label, _sx, _sz = _TYPE_VIZ.get(track.type, _DEFAULT_VIZ)
    m = ros.Marker()
    m.header = header
    m.ns = "track_labels"
    m.id = marker_id
    m.type = ros.Marker.TEXT_VIEW_FACING
    m.action = ros.Marker.ADD
    m.pose.position.x = track.pose.position.x
    m.pose.position.y = track.pose.position.y
    m.pose.position.z = track.pose.position.z + 3.0
    m.scale.z = 2.0
    m.color = ColorRGBA(r=1.0, g=1.0, b=1.0, a=1.0)
    m.text = f"{track.id}: {label}"
    m.lifetime.sec = 0
    m.lifetime.nanosec = 300_000_000
    return m


def _make_heading_marker(
    header: ros.Header,
    track: ros.Track,
    marker_id: int,
) -> ros.Marker:
    """Arrow showing velocity direction."""
    m = ros.Marker()
    m.header = header
    m.ns = "track_heading"
    m.id = marker_id
    m.type = ros.Marker.ARROW
    m.action = ros.Marker.ADD
    m.pose = track.pose
    speed = math.hypot(track.twist.linear.x, track.twist.linear.y)
    arrow_len = max(3.0, min(15.0, speed * 2.0))
    m.scale.x = arrow_len
    m.scale.y = 0.8
    m.scale.z = 0.8
    m.color = ColorRGBA(r=0.2, g=1.0, b=0.2, a=0.7)
    m.lifetime.sec = 0
    m.lifetime.nanosec = 300_000_000
    return m


class TrackFoxgloveConverterNode(Node):
    def __init__(self) -> None:
        super().__init__("track_foxglove_converter_node", enable_logger_service=True)

        self.projector: LocalCartesianProjector | None = None

        # 3D markers
        self.markers_pub = self.create_publisher(
            ros.MarkerArray,
            SIM_TRACKS_MARKERS.name,
            SIM_TRACKS_MARKERS.qos,
        )

        # Map panel: one NavSatFix per track (batch published)
        self.map_pub = self.create_publisher(
            ros.NavSatFix,
            "/debug/map/tracks",
            SIM_TRACKS_MARKERS.qos,
        )

        # Subscriptions
        self.create_subscription(
            ros.TrackArray,
            SIM_TRACKS.name,
            self.on_tracks,
            SIM_TRACKS.qos,
        )
        self.create_subscription(
            ros.GeoPointStamped,
            MAP_ORIGIN.name,
            self.on_map_origin,
            MAP_ORIGIN.qos,
        )

        self.log = self.get_logger()
        self.log.info(
            "TrackFoxgloveConverterNode ready (waiting for map origin for map panel)"
        )

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

    def on_tracks(self, msg: ros.TrackArray) -> None:
        # 3D markers (always published)
        markers: list[ros.Marker] = []
        for i, track in enumerate(msg.tracks):
            base_id = i * 3
            markers.append(_make_shape_marker(msg.header, track, base_id))
            markers.append(_make_text_marker(msg.header, track, base_id + 1))
            markers.append(_make_heading_marker(msg.header, track, base_id + 2))
        self.markers_pub.publish(ros.MarkerArray(markers=markers))

        # Map panel (only if projector is available)
        if self.projector is None:
            return
        for track in msg.tracks:
            pose = pyd.Pose2D.from_ros_pose(track.pose)
            geopose = self.projector.pose2d_to_geopose2d(pose)
            fix = ros.NavSatFix()
            fix.header = msg.header
            fix.latitude = geopose.lat_deg
            fix.longitude = geopose.lon_deg
            fix.altitude = 0.0
            fix.status.status = ros.NavSatStatus.STATUS_FIX
            self.map_pub.publish(fix)


def main() -> None:
    rclpy.init()
    node = TrackFoxgloveConverterNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
