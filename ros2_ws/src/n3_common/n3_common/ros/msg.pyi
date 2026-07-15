"""
Type stubs for n3_common.ros.msg.

Runtime behavior comes from msg.py (ROS message classes with
__init__(**kwargs)). This stub re-declares a typed __init__ for the
most-constructed messages so ty catches typos and wrong types at call sites.

Design rules:
- Every stub class inherits from the real underlying ROS message class.
  That keeps instances assignable to rclpy publishers, tf2, etc.
- Stubs ONLY declare __init__. Instance attributes and class-level constants
  (SailAngle.BOAT_REF, Waypoint.TACK_NONE, ...) are inherited from the real
  class — redeclaring them would conflict with the ROS property descriptors.
- Messages not listed here fall back to the untyped ROS class.
"""

from __future__ import annotations

import builtin_interfaces.msg as _bi
import geographic_msgs.msg as _geo
import geometry_msgs.msg as _geom
import n3_new_msgs.msg as _n3
import n3_new_msgs.srv as _n3_srv
import nav_msgs.msg as _nav
import sensor_msgs.msg as _sensor
import std_msgs.msg as _std
import visualization_msgs.msg as _viz

# ---------------------------------------------------------------------------
# std_msgs
# ---------------------------------------------------------------------------
class Header(_std.Header):
    def __init__(
        self, *, stamp: _bi.Time = ..., frame_id: str = ...
    ) -> None: ...

Float = _std.Float32
Int = _std.Int32
Bool = _std.Bool

# ---------------------------------------------------------------------------
# geometry_msgs
# ---------------------------------------------------------------------------
class Point(_geom.Point):
    def __init__(self, *, x: float = ..., y: float = ..., z: float = ...) -> None: ...

class Quaternion(_geom.Quaternion):
    def __init__(
        self, *, x: float = ..., y: float = ..., z: float = ..., w: float = ...
    ) -> None: ...

class Vector3(_geom.Vector3):
    def __init__(self, *, x: float = ..., y: float = ..., z: float = ...) -> None: ...

class Pose(_geom.Pose):
    def __init__(
        self, *, position: Point = ..., orientation: Quaternion = ...
    ) -> None: ...

class PoseWithCovariance(_geom.PoseWithCovariance):
    def __init__(
        self, *, pose: Pose = ..., covariance: list[float] = ...
    ) -> None: ...

class PoseStamped(_geom.PoseStamped):
    def __init__(self, *, header: Header = ..., pose: Pose = ...) -> None: ...

class PointStamped(_geom.PointStamped):
    def __init__(self, *, header: Header = ..., point: Point = ...) -> None: ...

class PoseArray(_geom.PoseArray):
    def __init__(self, *, header: Header = ..., poses: list[Pose] = ...) -> None: ...

class PoseWithCovarianceStamped(_geom.PoseWithCovarianceStamped):
    def __init__(
        self, *, header: Header = ..., pose: PoseWithCovariance = ...
    ) -> None: ...

class Twist(_geom.Twist):
    def __init__(
        self, *, linear: Vector3 = ..., angular: Vector3 = ...
    ) -> None: ...

class TwistStamped(_geom.TwistStamped):
    def __init__(self, *, header: Header = ..., twist: Twist = ...) -> None: ...

class Transform(_geom.Transform):
    def __init__(
        self, *, translation: Vector3 = ..., rotation: Quaternion = ...
    ) -> None: ...

class TransformStamped(_geom.TransformStamped):
    def __init__(
        self,
        *,
        header: Header = ...,
        child_frame_id: str = ...,
        transform: Transform = ...,
    ) -> None: ...

# ---------------------------------------------------------------------------
# geographic_msgs
# ---------------------------------------------------------------------------
class GeoPoint(_geo.GeoPoint):
    def __init__(
        self, *, latitude: float = ..., longitude: float = ..., altitude: float = ...
    ) -> None: ...

class GeoPointStamped(_geo.GeoPointStamped):
    def __init__(
        self, *, header: Header = ..., position: GeoPoint = ...
    ) -> None: ...

class GeoPose(_geo.GeoPose):
    def __init__(
        self, *, position: GeoPoint = ..., orientation: Quaternion = ...
    ) -> None: ...

class GeoPoseStamped(_geo.GeoPoseStamped):
    def __init__(self, *, header: Header = ..., pose: GeoPose = ...) -> None: ...

# ---------------------------------------------------------------------------
# n3_new_msgs — custom N3 messages. Field definitions mirror the .msg files
# in ros/src/n3_new_msgs/msg/. Keep in sync when .msg files change.
# ---------------------------------------------------------------------------
class Anemometer(_n3.Anemometer):
    def __init__(
        self, *, angle_deg: float = ..., speed_kts: float = ...
    ) -> None: ...

class Wind(_n3.Wind):
    def __init__(
        self, *, direction_deg: float = ..., speed_kts: float = ...
    ) -> None: ...

class Velocity(_n3.Velocity):
    def __init__(self, *, cog_deg: float = ..., sog_kts: float = ...) -> None: ...

class SailAngle(_n3.SailAngle):
    def __init__(
        self, *, angle_deg: float = ..., reference: int = ...
    ) -> None: ...

class Maneuver(_n3.Maneuver):
    def __init__(self, *, name: str = ...) -> None: ...

class PilotCommand(_n3.PilotCommand):
    def __init__(
        self,
        *,
        engine_speed_pct: float = ...,
        rudder_position_pct: float = ...,
        bow_thruster_pct: float = ...,
        mast_speed_pct: float = ...,
    ) -> None: ...

class PilotStatus(_n3.PilotStatus):
    def __init__(
        self,
        *,
        position_angle_phi_deg: float = ...,
        position_angle_theta_deg: float = ...,
        position_angle_psi_deg: float = ...,
        position_angle_mast_position_pts: int = ...,
        gps_north_speed_m_s: float = ...,
        gps_east_speed_m_s: float = ...,
        gps_down_speed_m_s: float = ...,
        gps_latitude_deg: float = ...,
        gps_longitude_deg: float = ...,
        gps_altitude_m: float = ...,
        radio_tx_mode: int = ...,
        radio_tx_1: float = ...,
        radio_tx_2: float = ...,
        radio_tx_3: float = ...,
        radio_tx_4: float = ...,
        radio_tx_5: float = ...,
        radio_tx_6: float = ...,
        radio_tx_7: float = ...,
        radio_tx_8: float = ...,
    ) -> None: ...

class MissionState(_n3.MissionState):
    def __init__(self, *, state: int = ..., goal_index: int = ...) -> None: ...

class PlanState(_n3.PlanState):
    def __init__(self, *, state: int = ...) -> None: ...

class ResetPID(_n3.ResetPID):
    def __init__(
        self, *, heading: bool = ..., speed: bool = ..., sail: bool = ...
    ) -> None: ...

class Waypoint(_n3.Waypoint):
    def __init__(
        self,
        *,
        lat_deg: float = ...,
        lon_deg: float = ...,
        heading_deg: float = ...,
        acceptance_radius_m: float = ...,
        label: str = ...,
        forced_tack: int = ...,
    ) -> None: ...

class WaypointList(_n3.WaypointList):
    def __init__(
        self, *, waypoints: list[Waypoint] = ..., current_index: int = ...
    ) -> None: ...

class Track(_n3.Track):
    def __init__(
        self,
        *,
        id: int = ...,
        pose: Pose = ...,
        twist: Twist = ...,
        type: int = ...,
    ) -> None: ...

class TrackArray(_n3.TrackArray):
    def __init__(
        self, *, header: Header = ..., tracks: list[Track] = ...
    ) -> None: ...

class Detection(_n3.Detection):
    def __init__(
        self,
        *,
        id: int = ...,
        pose: PoseWithCovariance = ...,
        type: int = ...,
    ) -> None: ...

class DetectionArray(_n3.DetectionArray):
    def __init__(
        self, *, header: Header = ..., detections: list[Detection] = ...
    ) -> None: ...

# ---------------------------------------------------------------------------
# nav_msgs
# ---------------------------------------------------------------------------
class MapMetaData(_nav.MapMetaData):
    def __init__(
        self,
        *,
        map_load_time: _bi.Time = ...,
        resolution: float = ...,
        width: int = ...,
        height: int = ...,
        origin: Pose = ...,
    ) -> None: ...

class OccupancyGrid(_nav.OccupancyGrid):
    def __init__(
        self,
        *,
        header: Header = ...,
        info: MapMetaData = ...,
        data: list[int] = ...,
    ) -> None: ...

# ---------------------------------------------------------------------------
# Messages left un-stubbed (fall back to dynamic ROS classes).
# Construction is still loose; attribute access is checked via __slots__.
# ---------------------------------------------------------------------------
NavSatFix = _sensor.NavSatFix
NavSatStatus = _sensor.NavSatStatus
ImuData = _sensor.Imu
JointState = _sensor.JointState

Path = _nav.Path

Marker = _viz.Marker
MarkerArray = _viz.MarkerArray

# ---------------------------------------------------------------------------
# Services (n3_new_msgs)
# ---------------------------------------------------------------------------
ScenarioCommand = _n3_srv.ScenarioCommand
