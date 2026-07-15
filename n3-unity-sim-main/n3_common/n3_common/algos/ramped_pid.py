from __future__ import annotations

import math

from pydantic import BaseModel, Field

from n3_common.math_utils.angles import wrap_mpi_pi


class RampedPIDParams(BaseModel):
    """Pydantic model for RampedPID parameters. Embeddable in ROS param models."""

    kp: float = Field(default=0.0)
    ki: float = Field(default=0.0)
    kd: float = Field(default=0.0)
    ramp_accel: float = Field(default=1.0, description="Setpoint ramp-up rate (unit/s)")
    ramp_decel: float = Field(
        default=1.0, description="Setpoint ramp-down rate (unit/s)"
    )
    output_accel_max: float = Field(
        default=1.0, description="Max output rate of change (unit/s)"
    )
    output_max: float = Field(default=1.0, description="Output saturation (symmetric)")
    output_dead_zone: float = Field(
        default=0.0, description="Output forced to 0 below this threshold"
    )
    integral_max: float | None = Field(
        default=None, description="Integral saturation (defaults to output_max)"
    )
    error_threshold: float = Field(
        default=0.0, description="Error flag raised above this value"
    )
    error_reset_threshold: float = Field(
        default=0.0, description="Error flag cleared below this value (hysteresis)"
    )
    dt: float = Field(default=0.1, description="Expected period between updates (s)")
    angle_mode: bool = Field(
        default=False, description="Wrap setpoint ramp and error to [-pi, pi]"
    )

    def build(self) -> RampedPID:
        return RampedPID(
            kp=self.kp,
            ki=self.ki,
            kd=self.kd,
            ramp_accel=self.ramp_accel,
            ramp_decel=self.ramp_decel,
            output_accel_max=self.output_accel_max,
            output_max=self.output_max,
            output_dead_zone=self.output_dead_zone,
            integral_max=self.integral_max
            if self.integral_max is not None
            else self.output_max,
            error_threshold=self.error_threshold,
            error_reset_threshold=self.error_reset_threshold,
            dt=self.dt,
            angle_mode=self.angle_mode,
        )


class RampedPID:
    """PID controller with setpoint ramping, output rate limiting, dead zone,
    back-calculated anti-windup, smoothed derivative, and error flag with hysteresis.

    Setpoint ramping:
        Instead of jumping to the target setpoint instantly, the effective setpoint
        moves toward the target at configurable accel/decel rates. This avoids
        integrating a large step error.

    Output rate limiting:
        The output change between steps is capped by output_accel_max.

    Dead zone:
        When |output| < output_dead_zone, output is forced to 0 and the integral
        is reset to avoid chattering at rest.

    Anti-windup (back-calculation):
        When output saturates, the integral term is back-calculated so it stays
        consistent with the clamped output.

    Smoothed derivative:
        Uses (error - error[-2]) / (2*dt) for a smoother derivative estimate.

    Error flag with hysteresis:
        A boolean flag is raised when |error| > error_threshold and cleared
        when |error| < error_reset_threshold.

    angle_mode:
        When True, setpoint ramping and error computation wrap to [-pi, pi].
    """

    def __init__(
        self,
        kp: float,
        ki: float,
        kd: float,
        ramp_accel: float,
        ramp_decel: float,
        output_accel_max: float,
        output_max: float,
        output_dead_zone: float,
        integral_max: float,
        error_threshold: float,
        error_reset_threshold: float,
        dt: float,
        *,
        angle_mode: bool = False,
    ) -> None:
        if dt <= 0.0:
            raise ValueError(f"dt must be > 0, got {dt}")

        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.ramp_accel = ramp_accel
        self.ramp_decel = ramp_decel
        self.output_accel_max = output_accel_max
        self.output_max = output_max
        self.output_dead_zone = output_dead_zone
        self.integral_max = integral_max
        self.error_threshold = error_threshold
        self.error_reset_threshold = error_reset_threshold
        self.dt = dt
        self.angle_mode = angle_mode

        self._setpoint: float = 0.0
        self._effective_setpoint: float = 0.0
        self._output: float = 0.0
        self._prev_output: float = 0.0
        self._error: float = 0.0
        self._prev_error: float = 0.0
        self._prev_prev_error: float = 0.0
        self._integral: float = 0.0
        self._error_flag: bool = False

    # -- Public API -----------------------------------------------------------

    def set_setpoint(self, setpoint: float) -> None:
        self._setpoint = setpoint

    def calc(self, measurement: float) -> float:
        """Compute output from a measurement. Applies setpoint ramping first."""
        if self.angle_mode:
            measurement = float(wrap_mpi_pi(measurement))
            self._ramp_angle()
            error = float(wrap_mpi_pi(self._effective_setpoint - measurement))
        else:
            self._ramp()
            error = self._effective_setpoint - measurement

        return self._calc_from_error(error)

    def calc_from_error(self, error: float) -> float:
        """Compute output directly from an error value (no setpoint ramping)."""
        return self._calc_from_error(error)

    def reset(self, measurement: float = 0.0) -> None:
        """Reset internal state without changing gains/limits."""
        self._setpoint = 0.0
        self._effective_setpoint = measurement
        self._output = 0.0
        self._prev_output = 0.0
        self._error = 0.0
        self._prev_error = 0.0
        self._prev_prev_error = 0.0
        self._integral = 0.0
        self._error_flag = False

    @property
    def setpoint(self) -> float:
        return self._setpoint

    @property
    def effective_setpoint(self) -> float:
        return self._effective_setpoint

    @property
    def output(self) -> float:
        return self._output

    @property
    def error(self) -> float:
        return self._setpoint - self._effective_setpoint + self._error

    @property
    def integral(self) -> float:
        return self._integral

    @property
    def error_flag(self) -> bool:
        return self._error_flag

    # -- Internals ------------------------------------------------------------

    def _calc_from_error(self, error: float) -> float:
        self._error = error

        # Integral accumulation
        self._integral += error * self.dt

        # [Feature 5] Smoothed derivative
        # Uses (err - err[-2]) / (2*dt) instead of single-step (err - err[-1]) / dt.
        # This two-sample averaging reduces high-frequency noise in the derivative term,
        # producing smoother output at the cost of a tiny phase delay.
        derivative = (error - self._prev_prev_error) / (2.0 * self.dt)
        self._prev_prev_error = self._prev_error
        self._prev_error = error

        # [Feature 7] Error flag with hysteresis
        # Raised when |error| exceeds error_threshold, cleared only when |error| drops
        # below error_reset_threshold. The gap between the two thresholds prevents the
        # flag from toggling rapidly when error oscillates near a single threshold.
        # Useful for supervisory logic (e.g. "is the heading loop converged?").
        if math.fabs(error) > self.error_threshold > 0.0:
            self._error_flag = True
        elif math.fabs(error) < self.error_reset_threshold:
            self._error_flag = False

        # [Feature 4] Integral saturation (anti-windup, part 1)
        # Hard-clamps the integral to [-integral_max, integral_max] to prevent unbounded
        # growth when the system is saturated or far from setpoint.
        self._integral = _clamp(self._integral, -self.integral_max, self.integral_max)

        # PID output
        output = self.kp * error + self.ki * self._integral + self.kd * derivative

        # [Feature 4] Anti-windup with back-calculation (part 2)
        # When the PID output exceeds output_max, the integral is back-calculated so that
        # kp*error + ki*integral = output_max. This keeps the integral consistent with the
        # clamped output and allows immediate response when the error reverses, instead of
        # waiting for the integral to "unwind" naturally.
        if output > self.output_max:
            output = self.output_max
            if self.ki != 0.0:
                self._integral = (self.output_max - self.kp * error) / self.ki
        elif output < -self.output_max:
            output = -self.output_max
            if self.ki != 0.0:
                self._integral = (-self.output_max - self.kp * error) / self.ki

        # [Feature 3] Dead zone
        # Forces output to zero when |output| is below output_dead_zone. This prevents
        # small residual commands from causing actuator "chattering" at rest (e.g. a motor
        # buzzing without actually moving). The integral is also zeroed to avoid accumulating
        # error while the output is suppressed.
        if math.fabs(output) < self.output_dead_zone:
            output = 0.0
            self._integral = 0.0

        # [Feature 2] Output rate limiting
        # Caps the rate of change of the output to output_accel_max (unit/s). This protects
        # actuators from sudden command jumps (e.g. limiting motor acceleration) even when
        # the PID itself would command a large step.
        acc = (output - self._prev_output) / self.dt
        if acc > 0.0 and acc > self.output_accel_max:
            output = self._prev_output + self.output_accel_max * self.dt
        elif acc < 0.0 and math.fabs(acc) > self.output_accel_max:
            output = self._prev_output - self.output_accel_max * self.dt

        self._prev_output = output
        self._output = output
        return output

    # [Feature 1] Setpoint ramping
    # Instead of applying the target setpoint instantly (which would create a large step
    # error and cause the integral to spike), the effective setpoint moves toward the
    # target at configurable rates: ramp_accel (unit/s) when increasing, ramp_decel
    # (unit/s) when decreasing. The PID only ever sees the smoothly-moving effective
    # setpoint, producing gentler transients.

    def _ramp(self) -> None:
        """Linear ramp toward setpoint."""
        gap = self._setpoint - self._effective_setpoint

        if gap >= 0.0:
            step = min(self.ramp_accel * self.dt, gap)
        else:
            step = max(-self.ramp_decel * self.dt, gap)

        self._effective_setpoint += step

    # [Feature 6] Angle-mode wrapping
    # When angle_mode is True, setpoint ramping and error computation wrap through
    # [-pi, pi]. This ensures the controller always takes the shortest rotational path
    # (e.g. going from 170 deg to -170 deg is a 20 deg move, not 340 deg).

    def _ramp_angle(self) -> None:
        """Linear ramp toward setpoint, wrapping through [-pi, pi]."""
        gap = float(wrap_mpi_pi(self._setpoint - self._effective_setpoint))

        if gap >= 0.0:
            step = min(self.ramp_accel * self.dt, gap)
        else:
            step = max(-self.ramp_decel * self.dt, gap)

        self._effective_setpoint = float(wrap_mpi_pi(self._effective_setpoint + step))


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
