"""TrackArray -> MarkerArray for RViz: a class-specific shape, colour and text label per track."""

from __future__ import annotations

import copy

import n3_common.ros as ros
import rclpy
from n3_common.topics.sim_topics import SIM_TRACKS, SIM_TRACKS_MARKERS
from n3_common.topics.topics_model import RELIABLE_QOS
from rclpy.node import Node

# type -> (shape, size (x,y,z) m, colour (r,g,b), label). For vessels x = length (along heading).
_CUBE = "cube"
_SPHERE = "sphere"
_CYLINDER = "cylinder"

_SPEC: dict[int, tuple[str, tuple[float, float, float], tuple[float, float, float], str]] = {
    0:  (_CUBE,     (3.0, 3.0, 3.0),     (0.8, 0.8, 0.8), "unknown"),
    1:  (_CUBE,     (11.0, 3.2, 3.5),    (0.2, 0.6, 1.0), "sailboat"),
    2:  (_CUBE,     (7.0, 2.6, 2.0),     (1.0, 0.5, 0.0), "motorboat"),
    3:  (_CUBE,     (3.0, 1.2, 1.0),     (1.0, 0.1, 0.1), "jetski"),
    4:  (_CUBE,     (5.0, 0.8, 0.6),     (0.2, 0.9, 0.3), "kayak"),
    5:  (_CUBE,     (3.2, 0.7, 0.25),    (0.0, 0.7, 0.7), "paddleboard"),
    6:  (_SPHERE,   (0.6, 0.6, 1.0),     (1.0, 0.1, 0.8), "swimmer"),
    7:  (_CUBE,     (4.0, 1.8, 1.0),     (0.1, 0.9, 0.9), "dinghy"),
    8:  (_CUBE,     (12.0, 4.0, 3.5),    (0.6, 0.4, 0.2), "fishing_boat"),
    9:  (_CUBE,     (30.0, 8.0, 6.0),    (0.6, 0.2, 0.9), "ferry"),
    10: (_CUBE,     (120.0, 18.0, 12.0), (0.3, 0.3, 0.3), "cargo"),
    11: (_CYLINDER, (2.0, 2.0, 3.0),     (1.0, 1.0, 0.0), "buoy"),
    12: (_CUBE,     (1.5, 1.5, 0.5),     (0.5, 0.5, 0.5), "debris"),
    13: (_CUBE,     (3.0, 1.0, 0.25),    (1.0, 0.4, 0.7), "windsurf"),
    14: (_CUBE,     (2.5, 0.8, 0.25),    (0.6, 1.0, 0.3), "kitesurf"),
    15: (_CUBE,     (3.0, 2.0, 1.2),     (0.4, 0.7, 1.0), "pedalo"),
}
_DEFAULT = (_CUBE, (3.0, 3.0, 3.0), (0.8, 0.8, 0.8), "unknown")

_SHAPE_MARKER = {_CUBE: None, _SPHERE: None, _CYLINDER: None}   # filled lazily from ros.Marker


def _marker_type(shape: str):
    if _SHAPE_MARKER[shape] is None:
        _SHAPE_MARKER[_CUBE] = ros.Marker.CUBE
        _SHAPE_MARKER[_SPHERE] = ros.Marker.SPHERE
        _SHAPE_MARKER[_CYLINDER] = ros.Marker.CYLINDER
    return _SHAPE_MARKER[shape]


class TracksMarkersNode(Node):
    def __init__(self) -> None:
        super().__init__("tracks_markers_node")
        self.pub = self.create_publisher(
            ros.MarkerArray, SIM_TRACKS_MARKERS.name, RELIABLE_QOS
        )
        self.create_subscription(
            ros.TrackArray, SIM_TRACKS.name, self.on_tracks, SIM_TRACKS.qos
        )
        self.prev_ids: set[int] = set()
        self.get_logger().info(
            f"tracks_markers_node ready ({SIM_TRACKS.name} -> {SIM_TRACKS_MARKERS.name})"
        )

    def on_tracks(self, msg: ros.TrackArray) -> None:
        markers = []
        ids: set[int] = set()
        for t in msg.tracks:
            ids.add(t.id)
            shape, size, color, name = _SPEC.get(t.type, _DEFAULT)
            r, g, b = color

            body = ros.Marker()
            body.header = msg.header
            body.ns = "tracks"
            body.id = int(t.id)
            body.type = _marker_type(shape)
            body.action = ros.Marker.ADD
            body.pose = t.pose
            body.scale.x, body.scale.y, body.scale.z = size
            body.color.r, body.color.g, body.color.b, body.color.a = r, g, b, 0.95
            markers.append(body)

            label = ros.Marker()
            label.header = msg.header
            label.ns = "labels"
            label.id = int(t.id)
            label.type = ros.Marker.TEXT_VIEW_FACING
            label.action = ros.Marker.ADD
            label.pose = copy.deepcopy(t.pose)   # own copy: raising z must not move the body
            label.pose.position.z = t.pose.position.z + size[2] * 0.5 + 2.0
            label.scale.z = 3.0
            label.color.r, label.color.g, label.color.b, label.color.a = 1.0, 1.0, 1.0, 1.0
            label.text = f"{name} #{int(t.id)}"
            markers.append(label)

        for old in self.prev_ids - ids:
            for ns in ("tracks", "labels"):
                d = ros.Marker()
                d.header = msg.header
                d.ns = ns
                d.id = int(old)
                d.action = ros.Marker.DELETE
                markers.append(d)
        self.prev_ids = ids

        self.pub.publish(ros.MarkerArray(markers=markers))


def main() -> None:
    rclpy.init()
    node = TracksMarkersNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
