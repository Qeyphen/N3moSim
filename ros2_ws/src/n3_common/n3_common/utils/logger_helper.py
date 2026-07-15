from __future__ import annotations

import time

from rclpy.impl.rcutils_logger import RcutilsLogger
from rclpy.node import Node

_DEFAULT_THROTTLE_SEC = 1.0

# Manual throttle state: (logger_name, caller_key) → last_log_time
_throttle_state: dict[tuple[str, str], float] = {}


class _Throttled:
    """Thin wrapper that adds throttle to every log call.

    Uses manual time-based throttling to avoid ROS2's call-site restriction
    that prevents different throttle durations from the same Python line.
    """

    __slots__ = ("_l", "_dt", "_key")

    def __init__(self, logger: RcutilsLogger, dt_sec: float, key: str) -> None:
        self._l = logger
        self._dt = dt_sec
        self._key = key

    def _should_log(self) -> bool:
        now = time.monotonic()
        state_key = (self._l.name, self._key)
        last = _throttle_state.get(state_key, 0.0)
        if now - last >= self._dt:
            _throttle_state[state_key] = now
            return True
        return False

    def debug(self, msg: str) -> None:
        if self._should_log():
            self._l.debug(msg)

    def info(self, msg: str) -> None:
        if self._should_log():
            self._l.info(msg)

    def warn(self, msg: str) -> None:
        if self._should_log():
            self._l.warning(msg)

    def error(self, msg: str) -> None:
        if self._should_log():
            self._l.error(msg)

    def fatal(self, msg: str) -> None:
        if self._should_log():
            self._l.fatal(msg)


def logt(
    node: Node, dt_sec: float = _DEFAULT_THROTTLE_SEC, key: str = ""
) -> _Throttled:
    """Return a throttled logger for *node*.

    At most one message per *dt_sec* seconds is emitted for each unique key.
    If no key is provided, the caller's filename:lineno is used automatically.

    Usage::

        logt(self).info("hello")              # 1 msg/s (default)
        logt(self, dt_sec=5.0).warn("slow")   # 1 msg per 5s
    """
    if not key:
        import inspect

        frame = inspect.currentframe()
        caller = frame.f_back if frame else None
        if caller:
            key = f"{caller.f_code.co_filename}:{caller.f_lineno}"
        else:
            key = "unknown"
    return _Throttled(node.get_logger(), dt_sec, key)


def log(node: Node) -> RcutilsLogger:
    """Convenience wrapper for node.get_logger()"""
    return node.get_logger()
