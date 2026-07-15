from __future__ import annotations

import n3_common.ros as ros
import rclpy
from n3_common.math_utils.angles import Deg, Rad
from n3_common.models import BoatVelocity, Direction, EnuAngle, Pose2D, TrueWind
from n3_common.params import ParamChange
from n3_common.ros.time import now_stamp
from n3_common.topics.n3mo_topics import WIND_TRUE
from n3_common.topics.sim_topics import (
    SIM_CMD_ENGINE,
    SIM_CMD_RUDDER_ANGLE,
    SIM_CMD_SAIL_ANGLE,
    SIM_POSE,
    SIM_SAIL_ANGLE_STATE,
    SIM_VELOCITY,
)
from n3_common.utils.logger_helper import logt
from rclpy.node import Node

from .simple_sim_dynamics import SimParams, SimState, step
from .simple_sim_params import SimpleSimParams


class SimpleSimNode(Node):
    """
    Simplified sailing dynamics simulator (3-DOF: surge + yaw).

    Subscriptions:
        /wind/true             (Wind)       — true wind for aero forces
        /sim/cmd/rudder_angle  (Float32)    — rudder deflection (deg)
        /sim/cmd/sail_angle    (SailAngle)  — sail angle command
        /sim/cmd/engine        (Float32)    — engine throttle (% [-100, 100])

    Publications:
        /sim/boat/pose         (PoseStamped) — ENU pose
        /sim/boat/velocity     (Velocity)    — COG + SOG
        /sim/boat/sail_angle   (SailAngle)   — current sail angle
    """

    def __init__(self) -> None:
        super().__init__("simple_sim_node")

        self.params = SimpleSimParams(self, on_change=self.on_params_changed)
        p = self.params.p

        # --- publishers (in /sim/ namespace) ---
        self.pose_pub = self.create_publisher(
            ros.PoseStamped,
            SIM_POSE.name,
            SIM_POSE.qos,
        )
        self.velocity_pub = self.create_publisher(
            ros.Velocity,
            SIM_VELOCITY.name,
            SIM_VELOCITY.qos,
        )
        self.sail_angle_pub = self.create_publisher(
            ros.SailAngle,
            SIM_SAIL_ANGLE_STATE.name,
            SIM_SAIL_ANGLE_STATE.qos,
        )

        # --- subscriptions ---
        self.create_subscription(
            ros.Wind,
            WIND_TRUE.name,
            self.on_wind_true,
            WIND_TRUE.qos,
        )
        self.create_subscription(
            ros.Float,
            SIM_CMD_RUDDER_ANGLE.name,
            self.on_rudder_angle,
            SIM_CMD_RUDDER_ANGLE.qos,
        )
        self.create_subscription(
            ros.SailAngle,
            SIM_CMD_SAIL_ANGLE.name,
            self.on_sail_angle,
            SIM_CMD_SAIL_ANGLE.qos,
        )
        self.create_subscription(
            ros.Float,
            SIM_CMD_ENGINE.name,
            self.on_engine,
            SIM_CMD_ENGINE.qos,
        )

        # --- sim state ---
        init_heading_enu_rad = Deg(90.0 - p.init_heading_deg).to_rad()
        self.sim_state = SimState(heading_rad=init_heading_enu_rad)
        self.sim_params = self.build_sim_params()

        self.true_wind: TrueWind = TrueWind(direction=Direction(deg=Deg(0)), speed_ms=0)
        self.rudder_angle: Rad = Rad(0.0)
        self.sail_angle: Rad = Rad(0.0)
        self.engine_pct: float = 0.0

        dt = 1.0 / p.sim_rate_hz
        self.create_timer(dt, self.on_sim_step)

        self.get_logger().info(
            f"SimpleSimNode ready — dt={dt:.4f}s, mass={p.mass_kg}kg"
        )

    def on_params_changed(self, changes: list[ParamChange]) -> None:
        self.sim_params = self.build_sim_params()

    def build_sim_params(self) -> SimParams:
        p = self.params.p
        return SimParams(
            mass_kg=p.mass_kg,
            inertia_z=p.inertia_z_kg_m2,
            hull_drag_coeff=p.hull_drag_coeff,
            yaw_damping=p.yaw_damping,
            sail_area=p.sail_area_m2,
            sail_cl=p.sail_lift_coeff,
            sail_cd=p.sail_drag_coeff,
            rudder_area=p.rudder_area_m2,
            rudder_cl=p.rudder_lift_coeff,
            rudder_arm=p.rudder_arm_m,
            engine_max_thrust=p.engine_max_thrust_n,
        )

    # --- callbacks ---

    def on_wind_true(self, msg: ros.Wind) -> None:
        self.true_wind = TrueWind.from_ros(msg)

    def on_rudder_angle(self, msg: ros.Float) -> None:
        # TODO en vrai je pense que l'actionneur n'est pas instantané. Il faudrait ici un limiteur de vitesse d'angle, voir une acceleration.
        #  Voir sur le vrai systeme la dynamique et le type d'actionneur
        self.rudder_angle = Deg(msg.data).to_rad()

    def on_sail_angle(self, msg: ros.SailAngle) -> None:
        self.sail_angle = Deg(msg.angle_deg).to_rad()

    def on_engine(self, msg: ros.Float) -> None:
        self.engine_pct = msg.data

    def on_sim_step(self) -> None:
        # True wind direction: Direction (CW from North) -> ENU angle (CCW from East)
        twd_enu_rad: Rad = self.true_wind.direction.to_enu_angle().rad
        tws = self.true_wind.speed_ms

        dt = 1.0 / self.params.p.sim_rate_hz
        self.sim_state, _ = step(
            state=self.sim_state,
            params=self.sim_params,
            sail_angle=self.sail_angle,
            rudder_angle=self.rudder_angle,
            twd_rad=twd_enu_rad,
            tws=tws,
            dt=dt,
            engine_pct=self.engine_pct,
        )

        self.publish_state()

    def publish_state(self) -> None:
        stamp = now_stamp(self)

        # --- pose ---
        pose = Pose2D(
            x=self.sim_state.x,
            y=self.sim_state.y,
            yaw=EnuAngle(rad=self.sim_state.heading_rad),
        )
        pose_msg = ros.PoseStamped()
        pose_msg.header.stamp = stamp
        pose_msg.header.frame_id = "map"
        pose_msg.pose = pose.to_ros_pose()
        self.pose_pub.publish(pose_msg)
        logt(self).debug(f"Publish sim : {pose!r}")

        # --- velocity ---
        # COG = heading when moving forward (u > 0), opposite when moving backward
        heading_dir = pose.yaw.to_direction()
        if self.sim_state.u >= 0:
            cog = heading_dir
        else:
            cog = heading_dir.opposite()
        velocity = BoatVelocity(cog=cog, sog_ms=abs(self.sim_state.u))
        self.velocity_pub.publish(velocity.to_ros_velocity())
        logt(self).debug(f"Publish sim : {velocity!r}")

        # --- sail angle ---
        sail_msg = ros.SailAngle()
        sail_msg.angle_deg = self.sail_angle.to_deg().value
        sail_msg.reference = ros.SailAngle.BOAT_REF
        self.sail_angle_pub.publish(sail_msg)
        logt(self).debug(f"Publish sim : {sail_msg!r}")


def main() -> None:
    rclpy.init()
    node = SimpleSimNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
