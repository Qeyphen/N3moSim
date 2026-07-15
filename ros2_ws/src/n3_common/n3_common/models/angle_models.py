from __future__ import annotations

import math
from typing import Self

import numpy as np
from pydantic import BaseModel, Field, field_validator

import n3_common.ros as ros
from n3_common.math_utils.angles import (
    Deg,
    Rad,
    euler_from_ros_quaternion,
    ros_quaternion_from_euler,
    wrap_360,
    wrap_mpi_pi,
)


class Angle(BaseModel):
    """
    Signed angular difference between two directions.

    Conventions:
    - radians
    - CCW positive
    - auto-normalized to [-π, π]
    - no reference frame implied
    """

    model_config = {"validate_assignment": True}

    rad: Rad = Field(description="Angle in radians, CCW positive.")

    @field_validator("rad")
    @classmethod
    def _normalize(cls, v: Rad) -> Rad:
        return wrap_mpi_pi(v)

    @classmethod
    def from_deg(cls, deg: Deg) -> Angle:
        """Construct Angle from degrees."""
        return cls(rad=deg.to_rad())

    @property
    def deg(self) -> Deg:
        return self.rad.to_deg()

    @property
    def deg_normalized(self) -> Deg:
        return wrap_mpi_pi(self.rad).to_deg()

    # --- Arithmetic (preserves subclass type via Self) ---

    def __add__(self, other: Angle) -> Self:
        return type(self)(rad=self.rad + other.rad)

    def __sub__(self, other: Angle) -> Self:
        return type(self)(rad=self.rad - other.rad)

    def __neg__(self) -> Self:
        return type(self)(rad=-self.rad)

    def __mul__(self, scalar: float) -> Self:
        return type(self)(rad=self.rad * scalar)

    def __rmul__(self, scalar: float) -> Self:
        return type(self)(rad=self.rad * scalar)

    # --- Trigonometry ---

    def sin(self) -> float:
        return math.sin(self.rad)

    def cos(self) -> float:
        return math.cos(self.rad)

    # --- Display ---

    def __repr__(self) -> str:
        return f"Angle({self.rad!r})"

    def __str__(self) -> str:
        return f"{self.deg} CCW"


class EnuAngle(Angle):
    """
    Angle in the ENU frame.

    Conventions:
    - referenced from East (+X axis)
    - CCW positive
    - this is the ROS2 yaw convention
    """

    @classmethod
    def from_quaternion(cls, q: ros.Quaternion) -> EnuAngle:
        """Extract ENU yaw from a ROS Quaternion."""
        _, _, yaw = euler_from_ros_quaternion(q)
        return cls(rad=Rad(yaw))

    def to_direction(self) -> Direction:
        """Convert ENU yaw to navigation Direction (CW from North)."""
        return Direction(deg=Deg(90.0) - self.deg)

    def to_unit_vector(self) -> np.ndarray:
        """Unit vector in ENU frame [East, North]."""
        return np.array([math.cos(self.rad), math.sin(self.rad)])

    def to_quaternion(self) -> ros.Quaternion:
        """Convert ENU yaw to a ROS Quaternion (rotation around Z axis)."""
        return ros_quaternion_from_euler(roll=0.0, pitch=0.0, yaw=self.rad)

    def __repr__(self) -> str:
        return f"EnuAngle({self.rad!r})"

    def __str__(self) -> str:
        return f"{self.deg} CCW from E"


class Direction(BaseModel):
    """
    Navigation direction.

    Conventions:
    - degrees
    - CW from North
    - auto-normalized to [0, 360)
    """

    model_config = {"validate_assignment": True}
    deg: Deg = Field(description="Direction in degrees, CW from North.")

    @field_validator("deg")
    @classmethod
    def _normalize(cls, v: Deg) -> Deg:
        return wrap_360(v)

    # --- Frame conversion ---

    def to_enu_angle(self) -> EnuAngle:
        """Convert navigation direction to ENU yaw angle (CCW from East)."""
        return EnuAngle(rad=(Deg(90.0) - self.deg).to_rad())

    def to_unit_vector(self) -> np.ndarray:
        """Unit vector in ENU frame [East, North]."""
        r = self.deg.to_rad()
        return np.array([math.sin(r), math.cos(r)])

    # --- Geometry ---
    @classmethod
    def from_enu_angle(cls, angle: EnuAngle) -> Direction:
        """Convert ENU yaw angle to navigation direction (CW from North)."""
        return cls(deg=Deg(90.0) - angle.deg)

    @classmethod
    def from_quaternion_in_enu(cls, q: ros.Quaternion) -> Direction:
        """Extract navigation heading from a ROS Quaternion supposed in an ENU frame."""
        return EnuAngle.from_quaternion(q).to_direction()

    @classmethod
    def from_pose_stamped(cls, pose_msg: ros.PoseStamped) -> Direction:
        """Extract navigation heading from a ROS PoseStamped message."""
        return cls.from_quaternion_in_enu(pose_msg.pose.orientation)

    def opposite(self) -> Direction:
        """Opposite direction (+180°)."""
        return Direction(deg=self.deg + Deg(180.0))

    def angle_from(self, src: Direction) -> Angle:
        """Signed angle from src to self. CCW positive."""
        return angle_between(src=src, dest=self)

    def angle_to(self, dest: Direction) -> Angle:
        """Signed angle from self to dest. CCW positive."""
        return angle_between(src=self, dest=dest)

    def rotate_by_angle(self, angle: Angle) -> Direction:
        """Rotate self counter-clockwise by angle (Angles are CCW by definition)."""
        enu_angle_rotated = self.to_enu_angle() + angle
        return enu_angle_rotated.to_direction()

    # --- Display ---
    def __repr__(self) -> str:
        return f"Direction({self.deg!r})"

    def __str__(self) -> str:
        return f"{self.deg} from N CW"


# predefined the four cardinal directions
NORTH_DIR = Direction(deg=Deg(0.0))
EAST_DIR = Direction(deg=Deg(90.0))
SOUTH_DIR = Direction(deg=Deg(180.0))
WEST_DIR = Direction(deg=Deg(270.0))


def angle_between(src: Direction, dest: Direction) -> Angle:
    """
    Signed angle to rotate src onto dest. CCW positive. Result in [-π, π].

    Example:
        twa = angle_between(src=heading, dest=twd)
    """
    return Angle(rad=dest.to_enu_angle().rad - src.to_enu_angle().rad)
