from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

import n3_common.models as pyd
import n3_common.ros as ros

from .pose_models import Pose2D
from .velocity_models import BoatVelocity

# TODO-after classes a compléter pour la detection et tracking d'obstacles


class BoatState(BaseModel):
    """
    Own boat's current kinematic state — full sensor fusion result.

    local_pose: ENU map position + heading after local cartesian projection
                (None until the local projector has been initialised)
    velocity:   course and speed over ground from GPS

    heading (geo_pose.heading) and cog (velocity.cog) are intentionally separate:
    their difference is the drift angle caused by current and leeway.
    """

    local_pose: Pose2D | None = None
    velocity: BoatVelocity

    def to_ros_pose_stamped(self, frame_id: str = "map") -> ros.PoseStamped:
        """Local ENU pose as ROS PoseStamped. Requires local_pose to be set."""
        if self.local_pose is None:
            raise ValueError(
                "local_pose is not set — run local cartesian projection first"
            )
        ps = ros.PoseStamped()
        ps.header.frame_id = frame_id
        ps.pose = self.local_pose.to_ros_pose()
        return ps


class TrackedVessel(BaseModel):
    """
    Externally observed vessel (AIS, radar, vision).
    Used as an obstacle in collision avoidance.

    local_pose:      ENU map frame position + heading (from projection or radar)
    velocity:        COG + SOG (if known from AIS or tracker)
    pose_covariance: 6x6 covariance matrix in row-major order [x,y,z,rx,ry,rz]
                     matching the ROS PoseWithCovariance convention (36 floats)
    timestamp:       when data was last received — mandatory for staleness checks
    """

    label: str
    local_pose: Pose2D | None = None
    velocity: BoatVelocity | None = None
    pose_covariance: list[float] = Field(default_factory=lambda: [0.0] * 36)
    timestamp: datetime

    def age_s(self, now: datetime) -> float:
        """Seconds elapsed since last data update."""
        return (now - self.timestamp).total_seconds()

    def to_ros_pose_with_covariance_stamped(
        self, frame_id: str = "map"
    ) -> ros.PoseWithCovarianceStamped:
        """Local ENU pose + covariance as ROS PoseWithCovarianceStamped."""
        if self.local_pose is None:
            raise ValueError(
                "local_pose is not set — project geographic position first"
            )
        msg = ros.PoseWithCovarianceStamped()
        msg.header.frame_id = frame_id
        msg.pose.pose = self.local_pose.to_ros_pose()
        msg.pose.covariance = self.pose_covariance
        return msg

    @classmethod
    def from_ros_pose_with_covariance_stamped(
        cls,
        msg: ros.PoseWithCovarianceStamped,
        label: str,
    ) -> TrackedVessel:
        """Build from ROS PoseWithCovarianceStamped (radar / tracker output)."""
        return cls(
            label=label,
            local_pose=Pose2D.from_ros_pose(msg.pose.pose),
            pose_covariance=list(msg.pose.covariance),
            timestamp=pyd.RosTime.stamp_to_datetime(msg.header.stamp),
        )
