from __future__ import annotations

from enum import IntEnum, StrEnum

from n3_common.math_utils.angles import Deg
from n3_common.n3_const import PI

from .angle_models import Angle, Direction


class Tack(IntEnum):
    """
    Which side the wind comes from.

    Matches the sign of TrueWindAngle.rad:
    PORT = +1  (positive TWA, wind from left / CCW side)
    STARBOARD = -1  (negative TWA, wind from right / CW side)
    """

    PORT = 1
    STARBOARD = -1

    @staticmethod
    def from_twa(twa: Angle) -> Tack:
        """Tack derived from TrueWindAngle sign. Positive = port, negative = starboard."""
        return Tack.PORT if twa.rad >= 0 else Tack.STARBOARD

    def __repr__(self) -> str:
        return f"Tack.{self.name}"

    def __str__(self) -> str:
        return self.name


class PointOfSail(StrEnum):
    """
    Categorical point of sail derived from TrueWindAngle magnitude.

    IN_IRONS    [0°,  20°)  head to wind, sails luffing, no drive
    CLOSE_HAULED [20°, 50°)  beating upwind, sails sheeted tight
    CLOSE_REACH  [50°, 70°)  between close-hauled and beam reach
    BEAM_REACH   [70°, 110°) wind roughly abeam
    BROAD_REACH  [110°,150°) wind from behind the beam
    RUNNING      [150°,180°] dead downwind, wind from astern
    """

    IN_IRONS = "IN_IRONS"
    CLOSE_HAULED = "CLOSE_HAULED"
    CLOSE_REACH = "CLOSE_REACH"
    BEAM_REACH = "BEAM_REACH"
    BROAD_REACH = "BROAD_REACH"
    RUNNING = "RUNNING"


class ManeuverName(StrEnum):
    """
    Coarse sailing maneuver used by the skipper state machine.

    UPWIND   — close-hauled, beating
    REACH    — beam or broad reach
    DOWNWIND — running
    TACKING  — in-progress tack maneuver
    JIBING   — in-progress jibe maneuver
    """

    UPWIND = "UPWIND"
    REACH = "REACH"
    DOWNWIND = "DOWNWIND"
    TACKING = "TACKING"
    JIBING = "JIBING"


class ApparentWindAngle(Angle):
    """
    Signed angle from boat heading to apparent wind direction.

    Note about Maritime vs Robotics conventions
    - Maritime convention used for Maritime displays, gives awa in degrees, CW positive
    - Robotics convention used for Robotics computations, gives awa in radians, CCW positive
    Here we use Robotics convention and the method to_maritime_convention() convert it for display only

    Conventions (Robotics one)
    - radians, CCW positive
    - normalized to (-π, π]
    - sign encodes tack: positive = port, negative = starboard
    - abs(rad) = point of sail [0, π]: 0 = head to wind, π = dead downwind
    """

    @classmethod
    def from_directions(cls, heading: Direction, awd: Direction) -> ApparentWindAngle:
        """Compute AWA from current heading and apparent wind direction (AWD)."""
        return cls(rad=awd.angle_from(heading).rad)

    def to_maritime_convention_deg_cw(self) -> Deg:
        """AWA in maritime convention in degrees [-180, 180] CW."""
        return -self.deg

    def __repr__(self) -> str:
        return f"ApparentWindAngle({self.rad!r})"


class TrueWindAngle(Angle):
    """
    Signed angle from boat heading to true wind direction.

    Note about Maritime vs Robotics conventions
    - Maritime convention used for Maritime displays, gives awa in degrees, CW positive
    - Robotics convention used for Robotics computations, gives awa in radians, CCW positive
    Here we use Robotics convention and the method to_maritime_convention() convert it for display only

    Conventions (Robotics one)
    - radians, CCW positive
    - normalized to (-π, π]
    - sign encodes tack: positive = port, negative = starboard
    - abs(rad) = point of sail [0, π]: 0 = head to wind, π = dead downwind
    """

    @classmethod
    def from_directions(cls, heading: Direction, twd: Direction) -> TrueWindAngle:
        """Compute TWA from current heading and true wind direction (TWD)."""
        return cls(rad=twd.angle_from(heading).rad)

    @property
    def tack(self) -> Tack:
        """Tack derived from sign — no separate field needed."""
        return Tack.PORT if self.rad >= 0 else Tack.STARBOARD

    def to_maritime_convention_deg_cw(self) -> Deg:
        """TWA in maritime convention in degrees [-180, 180] CW."""
        return -self.deg

    # --- Points of sail ---
    # Thresholds are conventional approximations; actual limits depend on polar diagram. # TODO-after constantes a integrer en parametre selon les polaires du bateau

    def is_in_irons(self) -> bool:
        """< 20°: head to wind, sails luffing, no drive."""
        return abs(self.deg) < Deg(20)

    def is_close_hauled(self) -> bool:
        """20°–50°: beating upwind, sails sheeted tight."""
        return Deg(20) <= abs(self.deg) < Deg(50)

    def is_close_reach(self) -> bool:
        """50°–70°: between close-hauled and beam reach."""
        return Deg(50) <= abs(self.deg) < Deg(70)

    def is_beam_reach(self) -> bool:
        """70°–110°: wind roughly abeam."""
        return Deg(70) <= abs(self.deg) < Deg(110)

    def is_broad_reach(self) -> bool:
        """110°–150°: wind from behind the beam."""
        return Deg(110) <= abs(self.deg) < Deg(150)

    def is_running(self) -> bool:
        """>= 150°: dead downwind, wind from astern."""
        return abs(self.deg) >= Deg(150)

    def is_upwind(self) -> bool:
        """True if point of sail is less than 90° from wind (close-hauled or close reach)."""
        return abs(self.rad) < PI / 2

    def is_downwind(self) -> bool:
        """True if point of sail is more than 110° from wind (broad reach or running)."""
        return abs(self.deg) > Deg(110)

    @property
    def point_of_sail(self) -> PointOfSail:
        """Categorical point of sail derived from TWA magnitude."""
        if self.is_in_irons():
            return PointOfSail.IN_IRONS
        if self.is_close_hauled():
            return PointOfSail.CLOSE_HAULED
        if self.is_close_reach():
            return PointOfSail.CLOSE_REACH
        if self.is_beam_reach():
            return PointOfSail.BEAM_REACH
        if self.is_broad_reach():
            return PointOfSail.BROAD_REACH
        return PointOfSail.RUNNING

    def on_opposite_tack(self) -> TrueWindAngle:
        """Same point of sail, opposite tack."""
        return TrueWindAngle(rad=-self.rad)

    def __repr__(self) -> str:
        return f"TrueWindAngle({self.rad!r})"
