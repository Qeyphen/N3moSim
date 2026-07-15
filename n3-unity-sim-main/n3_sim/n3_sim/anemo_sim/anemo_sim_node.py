"""
Simulated anemometer node — design notes.

Wind variation model
--------------------
Each wind component (direction and speed) is modulated around its mean by an
additive variation chosen among three modes: "none", "sinusoidal" or
"turbulent".

Ornstein-Uhlenbeck process (_WindVariation.step_ou)
---------------------------------------------------
    dx = -theta * x * dt + sigma * dW,
    theta = 1 / time_constant,
    sigma = std * sqrt(2 * theta)

Properties:
- Stationary, zero-mean with standard deviation `turb_std` (no drift).
- Exponential autocorrelation with time constant `turb_time_constant_s`.
- Smooth — no discrete jumps like a piecewise-linear random walk.

Cross-channel correlation (_draw_correlated_noise)
--------------------------------------------------
One shared noise source plus one independent noise per channel:

    dir_noise   = rho * shared + sqrt(1 - rho**2) * indep_dir
    speed_noise = rho * shared + sqrt(1 - rho**2) * indep_speed

Both channel noises remain N(0, 1) but with an exact linear correlation
coefficient `rho`. Effect: when the wind picks up on a gust, the direction
tends to shift as well — realistic coupling.

Reproducibility — `random_seed` (_make_rng)
-------------------------------------------
- random_seed = 0 → time-based `random.Random()`, non-reproducible.
- random_seed > 0 → `random.Random(seed)`, deterministic; ideal for
  integration tests and replays.
- The RNG is owned by the node (never the global `random.*`) so the sim
  does not pollute other libraries' RNG state.

Live param updates (on_params_changed)
--------------------------------------
Rebuilds both variation helpers on any param change, but only reseeds the
RNG when `random_seed` itself changed — otherwise editing an unrelated
parameter would restart the whole random sequence.

Real time step
--------------
dt is measured as `now - last_tick` instead of `1 / publish_rate_hz`, so
the OU integration remains correct even if a tick is late.

Reasonable defaults
-------------------
- Turbulent direction: sigma = 8 deg, tau = 30 s (slow credible drift for
  a mean wind).
- Turbulent speed: sigma = 1.2 m/s, tau = 15 s (faster gusts).
- Correlation: rho = 0.3 (moderate, visible but not locked).
"""

from __future__ import annotations

import math
import random

import n3_common.ros as ros
import rclpy
from n3_common.math_utils.angles import Deg
from n3_common.models import ApparentWind, BoatVelocity, Direction, TrueWind
from n3_common.topics.n3mo_topics import ANEMO_DATA, BOAT_POSE, BOAT_VELOCITY
from rclpy.node import Node

from .anemo_sim_params import AnemoSimModel, AnemoSimParams, VariationMode

TRUE_WIND_TOPIC = "/sim/true_wind"


class _WindVariation:
    """Time-varying additive offset for a wind component (direction or speed).

    Three modes:
    - "none": always 0.
    - "sinusoidal": amplitude * sin(2π t / period) — fully deterministic.
    - "turbulent": Ornstein-Uhlenbeck process

        dx = -theta * x * dt + sigma * dW

      with theta = 1 / time_constant and sigma = std * sqrt(2 * theta).
      This yields a stationary zero-mean Gaussian signal with the target
      std and correlation time — a good physical model for atmospheric
      turbulence at fixed height.

    The OU state is advanced externally via step_ou(dt, noise) so the
    caller can share a noise source across several channels (cross-channel
    correlation).
    """

    def __init__(
        self,
        mode: VariationMode,
        *,
        sinus_period_s: float,
        sinus_amplitude: float,
        turb_std: float,
        turb_time_constant_s: float,
    ) -> None:
        self.mode = mode
        self.sinus_period_s = sinus_period_s
        self.sinus_amplitude = sinus_amplitude
        self.turb_std = turb_std
        self.turb_theta = 1.0 / max(turb_time_constant_s, 1e-3)
        self.turb_sigma = turb_std * math.sqrt(2.0 * self.turb_theta)
        self._ou_value = 0.0

    def step_ou(self, dt: float, noise: float) -> None:
        """Advance the OU state. noise must be a standard normal sample."""
        if self.mode != "turbulent" or dt <= 0.0:
            return
        self._ou_value += (
            -self.turb_theta * self._ou_value * dt
            + self.turb_sigma * math.sqrt(dt) * noise
        )

    def value(self, t: float) -> float:
        if self.mode == "sinusoidal":
            return self.sinus_amplitude * math.sin(
                2 * math.pi * t / self.sinus_period_s
            )
        if self.mode == "turbulent":
            return self._ou_value
        return 0.0


def _build_direction_variation(p: AnemoSimModel) -> _WindVariation:
    return _WindVariation(
        p.twd_variation_mode,
        sinus_period_s=p.twd_sinus_period_s,
        sinus_amplitude=p.twd_sinus_amplitude_deg,
        turb_std=p.twd_turb_std_deg,
        turb_time_constant_s=p.twd_turb_time_constant_s,
    )


def _build_speed_variation(p: AnemoSimModel) -> _WindVariation:
    return _WindVariation(
        p.tws_variation_mode,
        sinus_period_s=p.tws_sinus_period_s,
        sinus_amplitude=p.tws_sinus_amplitude_ms,
        turb_std=p.tws_turb_std_ms,
        turb_time_constant_s=p.tws_turb_time_constant_s,
    )


def _make_rng(seed: int) -> random.Random:
    """seed=0 means non-reproducible (time-based)."""
    return random.Random(seed) if seed > 0 else random.Random()


class AnemoSimNode(Node):
    """
    Simulated anemometer node.

    Reads a true wind profile from parameters (twd_deg, tws_ms), subscribes
    to BOAT_POSE for heading and BOAT_VELOCITY for speed, and publishes
    simulated ANEMO_DATA.

    Apparent wind = true wind vector - boat velocity vector.
    The anemometer angle (AWA) is the apparent wind direction relative
    to the boat heading.

    The true wind direction and speed can each be modulated around their
    mean by an additive variation (sinusoidal or turbulent Ornstein-Uhlenbeck).
    In turbulent mode both channels are driven by jointly correlated Gaussian
    noise controlled by wind_turb_correlation.
    """

    def __init__(self) -> None:
        super().__init__("anemo_sim_node", enable_logger_service=True)

        self.params = AnemoSimParams(self, on_change=self.on_params_changed)
        p = self.params.p

        self.direction_variation = _build_direction_variation(p)
        self.speed_variation = _build_speed_variation(p)
        self.rng = _make_rng(p.random_seed)
        self.start_time = self.get_clock().now()
        self.last_tick = self.start_time

        self.anemo_pub = self.create_publisher(
            ros.Anemometer,
            ANEMO_DATA.name,
            ANEMO_DATA.qos,
        )
        self.true_wind_pub = self.create_publisher(
            ros.Wind,
            TRUE_WIND_TOPIC,
            ANEMO_DATA.qos,
        )

        self.create_subscription(
            ros.PoseStamped,
            BOAT_POSE.name,
            self.on_boat_pose,
            BOAT_POSE.qos,
        )
        self.create_subscription(
            ros.Velocity,
            BOAT_VELOCITY.name,
            self.on_boat_velocity,
            BOAT_VELOCITY.qos,
        )

        self.heading: Direction = Direction(deg=Deg(0))
        self.boat_velocity: BoatVelocity = BoatVelocity(
            cog=Direction(deg=Deg(0)), sog_ms=0
        )

        self.create_timer(1.0 / p.publish_rate_hz, self.on_publish_timer)

        self.log = self.get_logger()
        self.log.info(
            f"AnemoSimNode ready — TWD={p.twd_deg}° TWS={p.tws_ms} m/s "
            f"(dir_mode={p.twd_variation_mode}, speed_mode={p.tws_variation_mode}, "
            f"rho={p.wind_turb_correlation}, seed={p.random_seed})"
        )

    def on_params_changed(self, _changes) -> None:
        p = self.params.p
        self.direction_variation = _build_direction_variation(p)
        self.speed_variation = _build_speed_variation(p)
        # Reset RNG only if the seed changed — rebuilding a time-seeded RNG
        # would reroll history on every unrelated param edit.
        changed = {c.name for c in _changes}
        if "random_seed" in changed:
            self.rng = _make_rng(p.random_seed)

    def on_boat_pose(self, msg: ros.PoseStamped) -> None:
        self.heading = Direction.from_pose_stamped(msg)

    def on_boat_velocity(self, msg: ros.Velocity) -> None:
        self.boat_velocity = BoatVelocity.from_ros_velocity(msg)

    def _draw_correlated_noise(self, rho: float) -> tuple[float, float]:
        """Return (dir_noise, speed_noise) — two standard-normal samples with
        linear correlation coefficient rho in [-1, 1]."""
        shared = self.rng.gauss(0.0, 1.0)
        indep_dir = self.rng.gauss(0.0, 1.0)
        indep_speed = self.rng.gauss(0.0, 1.0)
        rho = max(-1.0, min(1.0, rho))
        orthogonal = math.sqrt(max(0.0, 1.0 - rho * rho))
        dir_noise = rho * shared + orthogonal * indep_dir
        speed_noise = rho * shared + orthogonal * indep_speed
        return dir_noise, speed_noise

    def on_publish_timer(self) -> None:
        p = self.params.p
        now = self.get_clock().now()
        dt = (now - self.last_tick).nanoseconds * 1e-9
        t = (now - self.start_time).nanoseconds * 1e-9
        self.last_tick = now

        dir_noise, speed_noise = self._draw_correlated_noise(p.wind_turb_correlation)
        self.direction_variation.step_ou(dt, dir_noise)
        self.speed_variation.step_ou(dt, speed_noise)

        twd_deg = p.twd_deg + self.direction_variation.value(t)
        tws_ms = max(0.0, p.tws_ms + self.speed_variation.value(t))

        true_wind = TrueWind(
            direction=Direction(deg=Deg(twd_deg)),
            speed_ms=tws_ms,
        )
        self.true_wind_pub.publish(true_wind.to_ros())
        apparent_wind = ApparentWind.from_true_wind(true_wind, self.boat_velocity)
        self.anemo_pub.publish(apparent_wind.to_ros_anemometer(self.heading))


def main() -> None:
    rclpy.init()
    node = AnemoSimNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
