from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Self

from builtin_interfaces.msg import (
    Time as MsgStamp,  # type of Header.stamp in Stamped msgs
)
from pydantic import BaseModel, Field
from rclpy.node import Node
from rclpy.time import Time

# ============================================================================
# WARNING: Never use datetime.now(), datetime.utcnow(), or time.time()
# All timestamps MUST originate from the ROS clock via RosTime.now(node)
# Using system time breaks replay and simulation.
#
# if use_sim_time == false:
#     ROS_TIME = SYSTEM_TIME
# if use_sim_time == true:
#     ROS_TIME = time received on /clock
# /clock is published by simulator or bag player
# ============================================================================


class RosTime(BaseModel):
    """
    Immutable timestamp sourced from the ROS clock.

    Always create via ``RosTime.now(node)`` or ``RosTime.from_stamp(msg)``.
    This guarantees the value tracks sim-time during replay.
    """

    nanoseconds: int = Field(description="Nanoseconds since epoch (ROS clock).")

    # --- constructors --------------------------------------------------------

    @classmethod
    def now(cls, node: Node) -> Self:
        """Capture the current ROS time from the node clock."""
        return cls(nanoseconds=node.get_clock().now().nanoseconds)

    @classmethod
    def from_stamp(cls, stamp: MsgStamp) -> Self:
        """Build from a ROS header stamp (builtin_interfaces/Time)."""
        return cls(nanoseconds=Time.from_msg(stamp).nanoseconds)

    # --- converters ----------------------------------------------------------

    def to_stamp(self) -> MsgStamp:
        """Convert to a ROS stamp (builtin_interfaces/Time) for message headers."""
        sec, nanosec = divmod(self.nanoseconds, 1_000_000_000)
        return MsgStamp(sec=int(sec), nanosec=int(nanosec))

    def to_datetime(self) -> datetime:
        """Convert to a UTC datetime (for logging, display, serialization)."""
        return datetime.fromtimestamp(self.nanoseconds * 1e-9, tz=UTC)

    # --- arithmetic ----------------------------------------------------------

    def elapsed_since(self, earlier: RosTime) -> timedelta:
        """Duration from an earlier RosTime to self."""
        return timedelta(microseconds=(self.nanoseconds - earlier.nanoseconds) / 1_000)

    def age_s(self, node: Node) -> float:
        """Seconds elapsed since this timestamp, measured with the node clock."""
        now_ns = node.get_clock().now().nanoseconds
        return (now_ns - self.nanoseconds) * 1e-9

    def is_stale(self, max_age_s: float, node: Node) -> bool:
        """True if older than max_age_s according to the node clock."""
        return self.age_s(node) > max_age_s

    # --- display -------------------------------------------------------------

    def __str__(self) -> str:
        return self.to_datetime().isoformat()

    def __repr__(self) -> str:
        return f"RosTime(ns={self.nanoseconds})"

    @staticmethod
    def stamp_to_datetime(stamp: MsgStamp) -> datetime:
        """Convenience method to convert a ROS stamp directly to datetime."""
        return RosTime.from_stamp(stamp).to_datetime()
