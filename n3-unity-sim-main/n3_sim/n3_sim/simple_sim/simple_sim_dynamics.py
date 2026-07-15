"""
Simplified 3-DOF sailing dynamics (surge, sway ignored, yaw).

State:  x, y (ENU meters), heading (rad, ENU yaw), u (surge speed m/s), r (yaw rate rad/s)
Inputs: sail_angle (rad, relative to centerline), rudder_angle (rad), true wind (dir + speed)

Physics:
  1. Apparent wind from true wind minus boat velocity
  2. Sail force: lift/drag from angle of attack on a flat plate
  3. Rudder force: lateral force from water flow, creates yaw moment
  4. Hull drag: quadratic resistance opposing surge
  5. Euler integration
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from n3_common.math_utils.angles import Rad

RHO_AIR = 1.225  # kg/m³
RHO_WATER = 1025.0  # kg/m³


@dataclass
class SimState:
    x: float = 0.0  # East (m)
    y: float = 0.0  # North (m)
    heading_rad: Rad = Rad(0.0)  # ENU yaw, CCW from East
    u: float = 0.0  # surge speed along heading (m/s)
    r: float = 0.0  # yaw rate (rad/s, CCW positive)


@dataclass
class SimParams:
    mass_kg: float = 80.0
    inertia_z: float = 60.0
    hull_drag_coeff: float = 20.0
    yaw_damping: float = 200.0
    sail_area: float = 6.0
    sail_cl: float = 1.2
    sail_cd: float = 0.1
    rudder_area: float = 0.05
    rudder_cl: float = 1.0
    rudder_arm: float = 1.5
    engine_max_thrust: float = 50.0  # N at 100% throttle


@dataclass
class SimForces:
    """Debug output of force components."""

    sail_forward: float = 0.0
    sail_lateral: float = 0.0
    rudder_lateral: float = 0.0
    hull_drag: float = 0.0
    engine_thrust: float = 0.0
    yaw_moment: float = 0.0


def step(
    state: SimState,
    params: SimParams,
    sail_angle: Rad,
    rudder_angle: Rad,
    twd_rad: Rad,
    tws: float,
    dt: float,
    engine_pct: float = 0.0,
) -> tuple[SimState, SimForces]:
    """
    Advance the simulation by dt seconds.

    Args:
        state: current state
        params: boat physical parameters
        sail_angle: sail angle relative to boat centerline (rad, CCW positive)
        rudder_angle: rudder deflection (rad, CCW positive = turn to port)
        twd_rad: true wind direction in ENU frame (rad, angle the wind comes FROM)
        tws: true wind speed (m/s)
        dt: timestep (s)
        engine_pct: engine throttle in [-100, 100] %

    Returns:
        (new_state, forces) tuple
    """
    h = state.heading_rad

    # --- apparent wind in boat frame ---
    # True wind vector (where it blows TO = opposite of coming-from)
    tw_to_x = -tws * math.cos(twd_rad)
    tw_to_y = -tws * math.sin(twd_rad)

    # Boat velocity in world frame
    boat_vx = state.u * math.cos(h)
    boat_vy = state.u * math.sin(h)

    # Apparent wind = true wind (blows-to) - boat velocity, in world frame
    aw_x = tw_to_x - boat_vx
    aw_y = tw_to_y - boat_vy
    aw_speed = math.hypot(aw_x, aw_y)

    # Apparent wind angle in boat frame (from heading)
    aw_world_angle = math.atan2(aw_y, aw_x)
    aw_boat = aw_world_angle - h  # angle relative to boat heading

    # --- sail forces ---
    # Angle of attack on sail
    aoa = aw_boat - sail_angle
    # Wrap to [-pi, pi]
    aoa = math.atan2(math.sin(aoa), math.cos(aoa))

    q_air = 0.5 * RHO_AIR * aw_speed**2 * params.sail_area

    # Flat plate model: lift ~ sin(aoa)*cos(aoa), drag ~ sin²(aoa) + parasitic
    lift = params.sail_cl * q_air * math.sin(aoa) * math.cos(aoa)
    drag = params.sail_cd * q_air + q_air * math.sin(aoa) ** 2

    # Lift is perpendicular to apparent wind (90° CCW), drag is along it
    # Project into boat frame (forward = x, lateral = y)
    sail_forward = -lift * math.sin(aw_boat) + drag * math.cos(aw_boat)
    sail_lateral = lift * math.cos(aw_boat) + drag * math.sin(aw_boat)

    # --- rudder forces ---
    q_water = 0.5 * RHO_WATER * state.u**2 * params.rudder_area
    rudder_lateral = params.rudder_cl * q_water * math.sin(rudder_angle)
    yaw_moment_rudder = -rudder_lateral * params.rudder_arm

    # --- hull drag ---
    hull_drag = params.hull_drag_coeff * state.u * abs(state.u)

    # --- engine thrust ---
    engine_thrust = params.engine_max_thrust * (engine_pct / 100.0)

    # --- equations of motion ---
    # Surge: sail forward + engine thrust - hull drag
    f_surge = sail_forward + engine_thrust - hull_drag
    u_dot = f_surge / params.mass_kg

    # Yaw: rudder moment + sail lateral (small arm, ignored) - damping
    m_yaw = yaw_moment_rudder - params.yaw_damping * state.r
    r_dot = m_yaw / params.inertia_z

    # --- Euler integration ---
    u_new = state.u + u_dot * dt
    r_new = state.r + r_dot * dt
    heading_new = h + state.r * dt
    # Wrap heading
    heading_new = Rad(math.atan2(math.sin(heading_new), math.cos(heading_new)))

    x_new = state.x + state.u * math.cos(h) * dt
    y_new = state.y + state.u * math.sin(h) * dt

    new_state = SimState(
        x=x_new,
        y=y_new,
        heading_rad=heading_new,
        u=u_new,
        r=r_new,
    )
    forces = SimForces(
        sail_forward=sail_forward,
        sail_lateral=sail_lateral,
        rudder_lateral=rudder_lateral,
        hull_drag=hull_drag,
        engine_thrust=engine_thrust,
        yaw_moment=yaw_moment_rudder,
    )
    return new_state, forces
