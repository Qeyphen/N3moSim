from __future__ import annotations

import cmath
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, Field

import n3_common.ros as ros
from n3_common.math_utils.angles import Deg, Rad
from n3_common.n3_const import KTS_TO_MS, MS_TO_KTS

from .wind_angle_models import (
    ApparentWindAngle,
    Direction,
    TrueWindAngle,
)

if TYPE_CHECKING:
    from .velocity_models import BoatVelocity


class Wind(BaseModel):
    """
    Wind measurement in geographic frame (direction from North).

    Conventions:
    - direction: where the wind comes FROM (CW from North, maritime)
    - speed in m/s (SI unit)
    """

    direction: Direction
    speed_ms: float = Field(ge=0.0)

    @property
    def speed_kts(self) -> float:
        """Speed in knots (display convenience)."""
        return self.speed_ms * MS_TO_KTS

    def to_z_complex(self) -> complex:
        """Convert to complex number representation (for vector math)."""
        return self.speed_ms * cmath.exp(1j * self.direction.deg.to_rad())

    def to_ros(self) -> ros.Wind:
        """Convert to n3_new_msgs/Wind ROS message."""
        msg = ros.Wind()
        msg.direction_deg = self.direction.deg.value
        msg.speed_kts = float(self.speed_kts)
        return msg

    @classmethod
    def from_z_complex(cls, z: complex) -> Self:
        """Build from complex number representation (for vector math)."""
        angle_rad = cmath.phase(z)
        speed_ms = abs(z)
        return cls(
            direction=Direction(deg=Rad(angle_rad).to_deg()),
            speed_ms=speed_ms,
        )

    @classmethod
    def from_ros(cls, msg: ros.Wind) -> Self:
        """Build from n3_new_msgs/Wind ROS message."""
        return cls(
            direction=Direction(deg=Deg(msg.direction_deg)),
            speed_ms=msg.speed_kts * KTS_TO_MS,
        )

    def __repr__(self) -> str:
        return f"Wind(dir={self.direction!r}, {self.speed_ms:.2f}m/s)"

    def __str__(self) -> str:
        return f"{self.direction} @ {self.speed_ms:.2f}m/s"


class ApparentWind(Wind):
    """
    Apparent wind in geographic frame (direction from North).

    The anemometer (wind vane + cups) measures wind in the boat's reference
    frame: angle from the bow->stern + speed relative to the boat. To obtain
    ApparentWind (geographic frame), rotate the raw sensor reading by the
    boat's heading:
        apparent_direction_from_north = boat_heading rotated by anemometer_angle_from_stern

    ApparentWind still includes the boat's own motion effect.
    Subtract the boat velocity vector to obtain TrueWind.
    """

    @classmethod
    def from_true_wind(
        cls, true_wind: TrueWind, velocity: BoatVelocity
    ) -> ApparentWind:
        """Apparent wind = true wind vector - boat velocity vector."""
        z_apparent = true_wind.to_z_complex() - velocity.to_z_complex()
        return cls.from_z_complex(z_apparent)

    def awa_from_heading(self, heading: Direction) -> ApparentWindAngle:
        """Compute Apparent Wind Angle = apparent wind direction relative to heading."""
        return ApparentWindAngle.from_directions(heading=heading, awd=self.direction)

    def to_ros_anemometer(self, heading: Direction) -> ros.Anemometer:
        """Convert to Anemometer message (angle_deg from heading, speed_kts)."""
        awa = self.awa_from_heading(heading)
        return ros.Anemometer(angle_deg=awa.deg.value, speed_kts=float(self.speed_kts))

    def __repr__(self) -> str:
        return f"ApparentWind(dir={self.direction!r}, {self.speed_ms:.2f}m/s)"


class TrueWind(Wind):
    """
    True wind relative to ground, in geographic frame.

    Computed from ApparentWind by subtracting the boat velocity vector:
        true_wind_vector = apparent_wind_vector - boat_velocity_vector
    """

    @property
    def twd(self) -> Direction:
        """True Wind Direction (TWD) in geographic frame."""
        return self.direction

    def twa_from_heading(self, heading: Direction) -> TrueWindAngle:
        """Compute True Wind Angle = true wind direction relative to heading."""
        return TrueWindAngle.from_directions(heading=heading, twd=self.direction)

    def __repr__(self) -> str:
        return f"TrueWind(dir={self.direction!r}, {self.speed_ms:.2f}m/s)"
