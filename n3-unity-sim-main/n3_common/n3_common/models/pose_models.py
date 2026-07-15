from __future__ import annotations

import math

from pydantic import BaseModel, Field

import n3_common.ros as ros
from n3_common.math_utils.angles import Rad

from .angle_models import Direction, EnuAngle


class Point2D(BaseModel):
    """2D point in ENU frame (no orientation)."""

    x: float
    y: float

    def __sub__(self, other: Point2D) -> Pose2D:
        """Vector from other to self, with yaw pointing from other to self."""
        dx = self.x - other.x
        dy = self.y - other.y
        return Pose2D(x=dx, y=dy, yaw=EnuAngle(rad=Rad(math.atan2(dy, dx))))


class Pose2D(BaseModel):
    """
    Local cartesian pose in ENU frame.

    Conventions:
    - x points East, y points North
    - yaw is referenced from East (+X)
    - yaw is CCW positive
    """

    model_config = {"validate_assignment": True}

    x: float
    y: float
    yaw: EnuAngle

    @classmethod
    def from_ros_pose(cls, pose: ros.Pose) -> Pose2D:
        return cls(
            x=pose.position.x,
            y=pose.position.y,
            yaw=EnuAngle.from_quaternion(pose.orientation),
        )

    def to_ros_vector3(self, z: float = 0.0) -> ros.Vector3:
        return ros.Vector3(x=self.x, y=self.y, z=z)

    def to_ros_point(self, z: float = 0.0) -> ros.Point:
        return ros.Point(x=self.x, y=self.y, z=z)

    def to_ros_pose(self, z: float = 0.0) -> ros.Pose:
        return ros.Pose(
            position=self.to_ros_point(z=z),
            orientation=self.yaw.to_quaternion(),
        )

    def bearing_to(self, dest: Pose2D) -> Direction:
        """Maritime direction (CW from North) from this pose to dest."""
        dx = dest.x - self.x
        dy = dest.y - self.y
        return EnuAngle(rad=Rad(math.atan2(dy, dx))).to_direction()

    def relative_bearing_to(self, direction_ref: Direction, dest: Pose2D) -> Direction:
        """Relative bearing (CW from direction_ref) from this pose to dest."""
        absolute_bearing = self.bearing_to(dest)
        relative_bearing_deg = absolute_bearing.deg - direction_ref.deg
        return Direction(deg=relative_bearing_deg)

    def distance_to(self, dest: Pose2D) -> float:
        """Distance from this pose to dest."""
        dx = dest.x - self.x
        dy = dest.y - self.y
        return math.hypot(dx, dy)

    def __str__(self) -> str:
        return f"Pose2D(x={self.x:.2f}, y={self.y:.2f}, yaw={self.yaw.deg})"

    def __repr__(self) -> str:
        return f"Pose2D(x={self.x:.2f}, y={self.y:.2f}, yaw={self.yaw!r})"


class GeoPose2D(BaseModel):
    """
    Geographic navigation pose.

    Conventions:
    - lat_deg, lon_deg are geodetic coordinates in degrees decimal (dd.xx)
    - heading is CW from North, auto-normalized to [0, 360)

    heading = 90° -> pointing East
    """

    lat_deg: float = Field(ge=-90.0, le=90.0)
    lon_deg: float = Field(ge=-180.0, le=180.0)
    heading: Direction

    @classmethod
    def from_ros_geo_pose(cls, pose: ros.GeoPose) -> GeoPose2D:
        return cls(
            lat_deg=pose.position.latitude,
            lon_deg=pose.position.longitude,
            heading=Direction.from_quaternion_in_enu(pose.orientation),
        )

    def to_ros_geo_pose(self) -> ros.GeoPose:
        return ros.GeoPose(
            position=ros.GeoPoint(
                latitude=self.lat_deg,
                longitude=self.lon_deg,
            ),
            orientation=self.heading.to_enu_angle().to_quaternion(),
        )

    def __str__(self) -> str:
        return f"GeoPose2D(lat={self.lat_deg:.2f}°, lon={self.lon_deg:.2f}°, heading={self.heading.deg})"

    def __repr__(self) -> str:
        return f"GeoPose2D(lat={self.lat_deg:.2f}°, lon={self.lon_deg:.2f}°, heading={self.heading!r})"
