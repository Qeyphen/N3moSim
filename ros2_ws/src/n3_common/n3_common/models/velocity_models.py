from __future__ import annotations

import cmath

import numpy as np
from pydantic import BaseModel, Field

import n3_common.ros as ros
from n3_common.math_utils.angles import Deg, Rad
from n3_common.n3_const import KTS_TO_MS, MS_TO_KTS

from .angle_models import Direction, EnuAngle


class BoatVelocity(BaseModel):
    """
    Boat velocity over ground (from GPS).

    Polar form:    cog (Direction, CW from North) + sog (m/s, SI)
    Cartesian ENU: [east_ms, north_ms] in m/s

    Conventions:
    - cog: Course Over Ground, maritime (CW from North, [0, 360))
    - sog: Speed Over Ground in m/s (SI unit, always >= 0)
    - ENU vector: linear.x = East, linear.y = North (m/s)
    """

    cog: Direction
    sog_ms: float = Field(ge=0.0)

    @property
    def sog_kts(self) -> float:
        """Speed over ground in knots (display convenience)."""
        return self.sog_ms * MS_TO_KTS

    def to_enu_vector(self) -> np.ndarray:
        """Velocity as [east_ms, north_ms] in m/s (ENU frame)."""
        return self.cog.to_unit_vector() * self.sog_ms

    def to_z_complex(self) -> complex:
        """Velocity as complex number (for vector math)."""
        return self.sog_ms * np.exp(1j * self.cog.deg.to_rad())

    @classmethod
    def from_z_complex(cls, z: complex) -> BoatVelocity:
        """Build from complex number representation (for vector math)."""
        angle_rad = cmath.phase(z)
        sog_ms = abs(z)
        return cls(
            cog=Direction(deg=Rad(angle_rad).to_deg()),
            sog_ms=sog_ms,
        )

    @classmethod
    def from_enu_vector(cls, east_ms: float, north_ms: float) -> BoatVelocity:
        """
        Build from ENU velocity components in m/s.
        Typical source: GPS north_speed_m_s / east_speed_m_s fields.
        Returns zero velocity with cog=North when speed is negligible.
        """
        sog_ms = float(np.hypot(east_ms, north_ms))
        if sog_ms < 1e-6:
            return cls(cog=Direction(deg=Deg(0.0)), sog_ms=0.0)
        # atan2(north, east) gives angle from East CCW = ENU angle
        cog_enu_rad = Rad(float(np.arctan2(north_ms, east_ms)))
        return cls(
            cog=EnuAngle(rad=cog_enu_rad).to_direction(),
            sog_ms=sog_ms,
        )

    def to_ros_velocity(self) -> ros.Velocity:
        """
        n3_ROS Velocity Msg representation.
        cog_deg, sog_kts
        """
        return ros.Velocity(cog_deg=self.cog.deg.value, sog_kts=self.sog_kts)

    @classmethod
    def from_ros_velocity(cls, velocity: ros.Velocity) -> BoatVelocity:
        """
        Build from ROS Velocity Msg (cog_deg, sog_kts).
        """
        return cls(
            cog=Direction(deg=Deg(velocity.cog_deg)),
            sog_ms=velocity.sog_kts * KTS_TO_MS,
        )

    def to_ros_twist(self) -> ros.Twist:
        """
        ROS Twist Msg representation.
        linear.x = East (m/s), linear.y = North (m/s), linear.z = 0.
        Angular components unused.
        """
        v = self.to_enu_vector()
        return ros.Twist(
            linear=ros.Vector3(x=float(v[0]), y=float(v[1]), z=0.0),
        )

    @classmethod
    def from_ros_twist(cls, twist: ros.Twist) -> BoatVelocity:
        """Build from ROS Twist (linear.x = East, linear.y = North in m/s)."""
        return cls.from_enu_vector(east_ms=twist.linear.x, north_ms=twist.linear.y)

    def __repr__(self) -> str:
        return f"BoatVelocity(cog={self.cog!r}, sog={self.sog_ms:.2f}m/s)"

    def __str__(self) -> str:
        return f"cog={self.cog.deg} @ {self.sog_ms:.2f}m/s"
