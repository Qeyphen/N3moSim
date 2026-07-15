from builtin_interfaces.msg import (
    Time as MsgStamp,  # type of Header.stamp in Stamped msgs
)


# helper functions for StampedTime in ros msgs
def now_stamp(node) -> MsgStamp:
    """Return the current ROS time as a stamp, without creating a RosTime instance."""
    return node.get_clock().now().to_msg()


def stamp_dt_sec(a: MsgStamp, b: MsgStamp) -> float:
    """Return (a - b) in seconds as a float."""
    return (a.sec - b.sec) + (a.nanosec - b.nanosec) * 1e-9
