from __future__ import annotations

import numpy as np

from n3_common.math_utils.angles import Deg, Rad
from n3_common.models.angle_models import Angle, Direction


class CircularMeanFilter:
    """
    Sliding-window circular mean for angular data.

    Uses complex-exponential averaging to correctly handle angle wrap-around
    (e.g. averaging 359° and 1° gives 0°, not 180°).

    Input/output are in radians, degrees, Direction, or Angle.
    """

    def __init__(self, window: int) -> None:
        if window < 1:
            raise ValueError(f"window must be >= 1, got {window}")
        self._window = window
        self._buffer: np.ndarray = np.empty(0)

    def update_from_rad(self, angle_rad: Rad) -> Rad:
        """Add a sample, return current circular mean in radians [-π, π]."""
        self._buffer = np.append(self._buffer, float(angle_rad))
        if len(self._buffer) > self._window:
            self._buffer = self._buffer[-self._window :]
        return Rad(float(np.angle(np.mean(np.exp(1j * self._buffer)))))

    def update_from_deg(self, angle_deg: Deg) -> Deg:
        """Add a sample, return current circular mean in degrees [0, 360)."""
        return self.update_from_rad(angle_deg.to_rad()).to_deg()

    def update_from_direction(self, angle: Direction) -> Direction:
        return Direction(deg=self.update_from_deg(angle.deg))

    def update_from_angle(self, angle: Angle) -> Angle:
        return Angle(rad=self.update_from_rad(angle.rad))

    def reset(self) -> None:
        self._buffer = np.empty(0)

    @property
    def is_ready(self) -> bool:
        """True once the window is full."""
        return len(self._buffer) >= self._window


class ScalarEmaFilter:
    """
    Exponential moving average (EMA) for scalar data.

    y[n] = alpha * x[n] + (1 - alpha) * y[n-1]

    alpha = 1.0 → no smoothing (pass-through)
    alpha = 0.1 → heavy smoothing (slow response)

    Prefer EMA over sliding mean for physical signals: it weights recent
    samples more and has no hard window-edge artifact.
    """

    def __init__(self, alpha: float) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError(f"alpha must be in (0, 1], got {alpha}")
        self._alpha = alpha
        self._value: float | None = None

    def update(self, value: float) -> float:
        """Add a sample, return current EMA."""
        if self._value is None:
            self._value = value
        else:
            self._value = self._alpha * value + (1.0 - self._alpha) * self._value
        return self._value

    def reset(self) -> None:
        self._value = None

    @property
    def is_ready(self) -> bool:
        return self._value is not None

    @property
    def value(self) -> float | None:
        return self._value


class CircularEmaFilter:
    """
    Exponential moving average for angular data.

    Internally filters the unit complex representation:
        z = exp(1j * angle)

    This correctly handles wrap-around.
    Input/output are in radians.
    """

    def __init__(self, alpha: float) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError(f"alpha must be in (0, 1], got {alpha}")
        self._alpha = alpha
        self._z: complex | None = None
        self._confidence = (
            0.0  # tracks confidence in the estimate (0 to 1) based on recent updates
        )

    def update_from_rad(self, angle_rad: Rad) -> Rad:
        """Add a sample, return current circular EMA in radians [-π, π]."""
        z_new = np.exp(1j * float(angle_rad))

        if self._z is None:
            self._z = z_new
            self._confidence = 1.0
        else:
            self._z = self._alpha * z_new + (1.0 - self._alpha) * self._z
            # norm of z represents confidence in the estimate
            norm = abs(self._z)
            self._confidence = norm
            # renormalize to avoid amplitude drift
            if norm > 1e-12:
                self._z /= norm

        return Rad(float(np.angle(self._z)))

    def update_from_deg(self, angle_deg: Deg) -> Deg:
        """Add a sample, return current circular EMA in degrees [0, 360)."""
        return self.update_from_rad(angle_deg.to_rad()).to_deg()

    def update_from_direction(self, angle: Direction) -> Direction:
        """Add a sample, return current circular EMA in a Direction class."""
        return Direction(deg=self.update_from_deg(angle.deg))

    def update_from_angle(self, angle: Angle) -> Angle:
        """Add a sample, return current circular EMA in an Angle class."""
        return Angle(rad=self.update_from_rad(angle.rad))

    def reset(self) -> None:
        self._z = None
        self._confidence = 0.0

    @property
    def confidence(self) -> float:
        return self._confidence

    @property
    def is_ready(self) -> bool:
        return self._z is not None

    @property
    def value(self) -> Rad | None:
        if self._z is None:
            return None
        return Rad(float(np.angle(self._z)))
