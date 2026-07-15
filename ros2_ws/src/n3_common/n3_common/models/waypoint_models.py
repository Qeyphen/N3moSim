from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

import n3_common.ros as ros
from n3_common.math_utils.angles import Deg

from .angle_models import Direction
from .pose_models import GeoPose2D, Pose2D
from .wind_angle_models import Tack

if TYPE_CHECKING:
    from n3_common.geo.local_cartesian_projector import LocalCartesianProjector


class Waypoint(BaseModel):
    """
    Geographic position the vessel should reach.

    position is stored in geographic frame (GeoPose2D) as the canonical form —
    this is stable regardless of when/where the local ENU origin is initialised.
    Call to_local_pose(projector) to get the ENU Pose2D for guidance computation.

    position.heading: optional approach bearing hint for guidance.
    acceptance_radius_m: distance at which the waypoint is considered reached.
    forced_tack: optional tack constraint on approach (None = guidance decides).
    label: human-readable name for logging and UI.
    """

    position: GeoPose2D
    acceptance_radius_m: float = Field(default=20.0, gt=0.0)
    label: str = ""
    forced_tack: Tack | None = None

    def to_local_pose(self, projector: LocalCartesianProjector) -> Pose2D:
        """Project geographic position into the local ENU map frame."""
        return projector.geopose2d_to_pose2d(self.position)

    def to_ros(self) -> ros.Waypoint:
        return ros.Waypoint(
            lat_deg=self.position.lat_deg,
            lon_deg=self.position.lon_deg,
            heading_deg=self.position.heading.deg.value,
            acceptance_radius_m=self.acceptance_radius_m,
            label=self.label,
            forced_tack=int(self.forced_tack) if self.forced_tack is not None else 0,
        )

    @classmethod
    def from_ros(cls, msg: ros.Waypoint) -> Waypoint:
        forced_tack = Tack(msg.forced_tack) if msg.forced_tack != 0 else None
        return cls(
            position=GeoPose2D(
                lat_deg=msg.lat_deg,
                lon_deg=msg.lon_deg,
                heading=Direction(deg=Deg(msg.heading_deg)),
            ),
            acceptance_radius_m=msg.acceptance_radius_m,
            label=msg.label,
            forced_tack=forced_tack,
        )


class Route(BaseModel):
    """
    Ordered sequence of waypoints with a pointer to the active one.

    The full waypoint list is always preserved — visited waypoints remain
    accessible for logging, display, and replanning.
    advance() mutates current_index in place (no list copy).
    """

    model_config = {"validate_assignment": True}

    waypoints: list[Waypoint] = Field(default_factory=list)
    current_index: int = 0

    @property
    def is_complete(self) -> bool:
        """True when all waypoints have been reached."""
        return self.current_index >= len(self.waypoints)

    @property
    def current(self) -> Waypoint | None:
        """Active waypoint, or None if the route is complete."""
        if self.is_complete:
            return None
        return self.waypoints[self.current_index]

    @property
    def remaining(self) -> list[Waypoint]:
        """Waypoints not yet reached, including the current one."""
        return self.waypoints[self.current_index :]

    @property
    def visited(self) -> list[Waypoint]:
        """Waypoints already passed."""
        return self.waypoints[: self.current_index]

    def advance(self) -> None:
        """Mark the current waypoint as reached and move to the next."""
        self.current_index += 1

    def reset(self) -> None:
        """Restart the route from the first waypoint."""
        self.current_index = 0

    def __len__(self) -> int:
        return len(self.waypoints)

    def __getitem__(self, i: int) -> Waypoint:
        return self.waypoints[i]

    def to_ros(self) -> ros.WaypointList:
        return ros.WaypointList(
            waypoints=[wp.to_ros() for wp in self.waypoints],
            current_index=self.current_index,
        )

    @classmethod
    def from_ros(cls, msg: ros.WaypointList) -> Route:
        return cls(
            waypoints=[Waypoint.from_ros(wp) for wp in msg.waypoints],
            current_index=msg.current_index,
        )

    def to_ros_path(
        self, projector: LocalCartesianProjector, frame_id: str = "map"
    ) -> ros.Path:
        """
        Standard nav_msgs/Path for rviz visualisation.
        Projects all waypoints into the local ENU map frame.
        """
        path = ros.Path()
        path.header.frame_id = frame_id
        for wp in self.waypoints:
            ps = ros.PoseStamped()
            ps.header.frame_id = frame_id
            ps.pose = wp.to_local_pose(projector).to_ros_pose()
            path.poses.append(ps)
        return path
