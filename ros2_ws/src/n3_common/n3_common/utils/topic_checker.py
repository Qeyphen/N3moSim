from __future__ import annotations

from rclpy.node import Node

from n3_common.ros.time import now_stamp, stamp_dt_sec
from n3_common.utils.logger_helper import logt


def all_ready(
    node: Node,
    **named_values: object | None,
) -> bool:
    """Check that every value is not None.

    Logs a warning listing the names of any None values (throttled at max 1 every 2 seconds).
    Works with any data: ROS messages, pydantic models, scalars, etc.
    Returns True only if all values are present.

    Usage::

        if not all_ready(self, anemo=self.anemo_msg, velocity=self.boat_velocity):
            return
    """
    missing = [name for name, val in named_values.items() if val is None]
    if missing:
        logt(node, dt_sec=2).warn(f"Waiting for: [ {', '.join(missing)} ]")
        return False
    return True


def is_msg_fresh(
    node: Node,
    msg: object,
    max_age_s: float,
    msg_name: str = "",
) -> bool:
    """Check that a stamped ROS message is not older than *max_age_s*.

    * No ``header.stamp`` → warn + return True (can't check).
    * Too old → error + return False.
    * Otherwise → True.
    """
    label = msg_name or type(msg).__name__

    header = getattr(msg, "header", None)
    stamp = getattr(header, "stamp", None) if header else None

    if stamp is None:
        logt(node).warn(f"{label}: no stamp")
        return True

    age = stamp_dt_sec(now_stamp(node), stamp)
    if age > max_age_s:
        logt(node).error(f"{label}: msg too old ({age:.2f}s > {max_age_s:.1f}s)")
        return False
    return True
