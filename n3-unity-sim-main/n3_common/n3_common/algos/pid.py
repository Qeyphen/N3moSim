from __future__ import annotations

from pydantic import BaseModel, Field

from n3_common.math_utils.angles import wrap_180


class PIDParams(BaseModel):
    """Pydantic model for PID gains + output limits. Embeddable in ROS param models."""

    kp: float = Field(default=0.0)
    ki: float = Field(default=0.0)
    kd: float = Field(default=0.0)
    output_min: float = Field(default=-1.0)
    output_max: float = Field(default=1.0)
    angle_mode: bool = Field(default=False)

    def build(self) -> PID:
        return PID(
            kp=self.kp,
            ki=self.ki,
            kd=self.kd,
            output_min=self.output_min,
            output_max=self.output_max,
            angle_mode=self.angle_mode,
        )


class PID:
    """
    Discrete PID controller.

    y = Kp*e + Ki*∫e dt + Kd*(de/dt)

    Output is clamped to [output_min, output_max].
    Integral is clamped to the same range to prevent windup.

    angle_mode=True: wraps error to [-180, 180] before each update,
    correct for heading control where 350° error == -10° error.
    """

    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        output_min: float,
        output_max: float,
        *,
        angle_mode: bool = False,
    ) -> None:
        if output_min >= output_max:
            raise ValueError(
                f"output_min must be < output_max, got [{output_min}, {output_max}]"
            )
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.output_min = output_min
        self.output_max = output_max
        self.angle_mode = angle_mode

        self._integral: float = 0.0
        self._prev_error: float | None = None

    def update(self, error: float, dt: float) -> float:
        """Compute PID output for a given error and time delta."""
        if self.angle_mode:
            error = wrap_180(error).value

        self._integral += error * dt
        self._integral = _clamp(self._integral, self.output_min, self.output_max)

        derivative = 0.0
        if self._prev_error is not None and dt > 0.0:
            d_err = error - self._prev_error
            if self.angle_mode:
                d_err = wrap_180(d_err).value
            derivative = d_err / dt
        self._prev_error = error

        output = self.kp * error + self.ki * self._integral + self.kd * derivative
        return _clamp(output, self.output_min, self.output_max)

    def reset(self) -> None:
        """Zero integrator and previous error."""
        self._integral = 0.0
        self._prev_error = None

    @property
    def integral(self) -> float:
        return self._integral


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
