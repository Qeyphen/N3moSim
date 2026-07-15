from __future__ import annotations

from enum import IntEnum

import n3_common.ros as ros
from n3_common.math_utils.angles import Deg

from .angle_models import Angle


class SailAngleRef(IntEnum):
    """
    Reference for sail angle command.

    - BOAT_REF: angle relative to boat centerline (default)
    - WIND_REF: angle relative to apparent wind direction (for wind-referenced control)
    """

    BOAT_REF = 0
    WIND_REF = 1


class SailAngle(Angle):
    """
    Pydantic model for ros SailAngle.msg interface

    Sail angle in rad CCW positive.

    Angle is from BOAT centerline

    Conventions:
    - 0 rad = sail aligned with SailAngleRef
    - Positive = sail angled to starboard side
    - Negative = sail angled to port side
    """

    reference: SailAngleRef

    def angle_from_boat(self, awa: Angle) -> Angle:
        """
        Returns angle of sail relative to boat centerline
        Take awa (apparent wind angle) into account if WIND ref.
        """
        # if WIND ref, add awa to self angle
        if self.reference == SailAngleRef.WIND_REF:
            return awa + self
        # if BOAT ref just return self angle
        return self

    @classmethod
    def from_ros(cls, msg: ros.SailAngle) -> SailAngle:
        return cls(
            rad=Deg(msg.angle_deg).to_rad(), reference=SailAngleRef(msg.reference)
        )

    def to_ros(self) -> ros.SailAngle:
        msg = ros.SailAngle()
        msg.angle_deg = self.deg.value
        msg.reference = self.reference.value
        return msg

    def __str__(self) -> str:
        return f"{self.deg} CCW from ref={self.reference.name}"

    def __repr__(self) -> str:
        return f"SailAngle({self.rad!r}, ref={self.reference.name})"
