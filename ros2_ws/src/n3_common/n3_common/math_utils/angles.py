from __future__ import annotations

from typing import Any

from pydantic import GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from tf_transformations import euler_from_quaternion, quaternion_from_euler

import n3_common.ros as ros
from n3_common.n3_const import DEG2RAD, PI, RAD2DEG, TWO_PI


class Rad(float):
    """A float representing an angle in radians. Compatible with math.sin() etc."""

    def __new__(cls, value: float = 0.0) -> Rad:
        # noinspection PyTypeChecker
        return super().__new__(cls, float(value))

    def to_deg(self) -> Deg:
        """Convert radians to Deg."""
        return Deg(float(self) * RAD2DEG)

    def __add__(self, other: float) -> Rad:
        return Rad(float.__add__(self, other))

    def __radd__(self, other: float) -> Rad:
        return Rad(float.__radd__(self, other))

    def __sub__(self, other: float) -> Rad:
        return Rad(float.__sub__(self, other))

    def __rsub__(self, other: float) -> Rad:
        return Rad(float.__rsub__(self, other))

    def __neg__(self) -> Rad:
        return Rad(float.__neg__(self))

    def __abs__(self) -> Rad:
        return Rad(float.__abs__(self))

    def __mul__(self, other: float) -> Rad:
        return Rad(float.__mul__(self, other))

    def __rmul__(self, other: float) -> Rad:
        return Rad(float.__rmul__(self, other))

    def __repr__(self) -> str:
        return f"Rad({float(self):.4f})"

    def __str__(self) -> str:
        return f"{float(self):.4f}rad"

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            lambda v: cls(v),
            serialization=core_schema.plain_serializer_function_ser_schema(float),
        )


class Deg:
    """An angle in degrees. Does NOT inherit from float to prevent accidental use in trig functions."""

    __slots__ = ("_value",)

    def __init__(self, value: float = 0.0) -> None:
        self._value = float(value)

    @property
    def value(self) -> float:
        return self._value

    def to_rad(self) -> Rad:
        """Convert degrees to Rad."""
        return Rad(self._value * DEG2RAD)

    def __repr__(self) -> str:
        return f"Deg({self._value:.1f})"

    def __str__(self) -> str:
        return f"{self._value:.1f}°"

    def __eq__(self, other: Deg) -> bool:  # type: ignore[override]
        return self._value == other._value

    def __hash__(self) -> int:
        return hash(self._value)

    def __lt__(self, other: Deg) -> bool:
        return self._value < other._value

    def __le__(self, other: Deg) -> bool:
        return self._value <= other._value

    def __gt__(self, other: Deg) -> bool:
        return self._value > other._value

    def __ge__(self, other: Deg) -> bool:
        return self._value >= other._value

    def __add__(self, other: Deg) -> Deg:
        return Deg(self._value + other._value)

    def __sub__(self, other: Deg) -> Deg:
        return Deg(self._value - other._value)

    def __neg__(self) -> Deg:
        return Deg(-self._value)

    def __abs__(self) -> Deg:
        return Deg(abs(self._value))

    def __mul__(self, scalar: float) -> Deg:
        return Deg(self._value * scalar)

    def __rmul__(self, scalar: float) -> Deg:
        return Deg(self._value * scalar)

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source_type: Any, _handler: GetCoreSchemaHandler
    ) -> CoreSchema:
        return core_schema.no_info_plain_validator_function(
            lambda v: cls(v) if not isinstance(v, cls) else v,
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda v: v.value
            ),
        )


def wrap_mpi_pi(angle_rad: Rad | float) -> Rad:
    """Wrap angle in radians to [-π, π]."""
    result = float(angle_rad) % TWO_PI
    if result > PI:
        result -= TWO_PI
    return Rad(result)


def wrap_180(angle_deg: Deg | float) -> Deg:
    """Wrap angle in degrees to [-180, 180]."""
    v = float(angle_deg) if isinstance(angle_deg, (int, float)) else angle_deg.value
    v = v % 360.0
    if v > 180.0:
        v -= 360.0
    return Deg(v)


def wrap_360(angle_deg: Deg | float) -> Deg:
    """Wrap angle in degrees to [0, 360)."""
    v = float(angle_deg) if isinstance(angle_deg, (int, float)) else angle_deg.value
    return Deg(v % 360.0)


def ros_quaternion_from_euler(roll, pitch, yaw) -> ros.Quaternion:
    """Create from roll, pitch, yaw angles."""
    q = quaternion_from_euler(roll, pitch, yaw)
    return ros.Quaternion(x=q[0], y=q[1], z=q[2], w=q[3])


def euler_from_ros_quaternion(q: ros.Quaternion) -> tuple[float, float, float]:
    """Extract roll, pitch, yaw angles from a ROS Quaternion."""
    return euler_from_quaternion([q.x, q.y, q.z, q.w])
