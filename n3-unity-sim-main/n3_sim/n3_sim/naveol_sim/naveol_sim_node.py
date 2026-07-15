from __future__ import annotations

import n3_common.ros as ros
import rclpy
from n3_common.geo.local_cartesian_projector import LocalCartesianProjector
from n3_common.models import BoatVelocity, Pose2D
from n3_common.topics.n3mo_topics import PILOT_COMMAND, PILOT_STATUS
from n3_common.topics.sim_topics import (
    SIM_CMD_ENGINE,
    SIM_CMD_RUDDER_ANGLE,
    SIM_CMD_SAIL_ANGLE,
    SIM_POSE,
    SIM_SAIL_ANGLE_STATE,
    SIM_VELOCITY,
)
from n3_common.utils.logger_helper import logt
from n3_common.utils.topic_checker import all_ready
from rclpy.node import Node

from .naveol_sim_params import NaveolSimParams


class NaveolSimNode(Node):
    """
    Simulated Naveol autopilot.

    Bridges PILOT_COMMAND to sim command topics and sim state back to
    PILOT_STATUS, replacing the real Naveol serial driver.

    PILOT_COMMAND fields:
        engine_speed_pct      -> /sim/cmd/engine         (Float32, %)
        rudder_position_pct   -> /sim/cmd/rudder_angle  (Float32, deg)
        bow_thruster_pct      -> ignored
        mast_speed_pct        -> integrated into sail angle -> /sim/cmd/sail_angle (SailAngle)

    Sim state -> PILOT_STATUS:
        /sim/boat/pose        -> psi_deg (heading), gps lat/lon (via projector)
        /sim/boat/velocity    -> gps north/east speed
        /sim/boat/sail_angle  -> mast_position_pts
        Radio fields          -> zeroed
    """

    def __init__(self) -> None:
        super().__init__("naveol_sim_node", enable_logger_service=True)

        self.params = NaveolSimParams(self)
        p = self.params.p

        self.projector = LocalCartesianProjector(
            origin_lat_deg=p.origin_lat_deg,
            origin_lon_deg=p.origin_lon_deg,
            origin_alt=p.origin_alt_m,
        )

        # --- publishers ---
        self.status_pub = self.create_publisher(
            ros.PilotStatus,
            PILOT_STATUS.name,
            PILOT_STATUS.qos,
        )
        self.sim_cmd_rudder_pub = self.create_publisher(
            ros.Float,
            SIM_CMD_RUDDER_ANGLE.name,
            SIM_CMD_RUDDER_ANGLE.qos,
        )
        self.sim_cmd_sail_pub = self.create_publisher(
            ros.SailAngle,
            SIM_CMD_SAIL_ANGLE.name,
            SIM_CMD_SAIL_ANGLE.qos,
        )
        self.sim_cmd_engine_pub = self.create_publisher(
            ros.Float,
            SIM_CMD_ENGINE.name,
            SIM_CMD_ENGINE.qos,
        )

        # --- subscriptions ---
        self.create_subscription(
            ros.PilotCommand,
            PILOT_COMMAND.name,
            self.on_pilot_command,
            PILOT_COMMAND.qos,
        )
        self.create_subscription(
            ros.PoseStamped,
            SIM_POSE.name,
            self.on_sim_pose,
            SIM_POSE.qos,
        )
        self.create_subscription(
            ros.Velocity,
            SIM_VELOCITY.name,
            self.on_sim_velocity,
            SIM_VELOCITY.qos,
        )
        self.create_subscription(
            ros.SailAngle,
            SIM_SAIL_ANGLE_STATE.name,
            self.on_sim_sail_angle,
            SIM_SAIL_ANGLE_STATE.qos,
        )

        # --- internal state ---
        self.sail_angle_deg: float = 0.0
        self.pose: Pose2D | None = None
        self.velocity: BoatVelocity | None = None
        self.mast_position_pts: int = 0

        dt = 1.0 / p.publish_rate_hz
        self.create_timer(dt, self.on_publish_timer)

        self.get_logger().info(
            f"NaveolSimNode ready — origin=({p.origin_lat_deg}, {p.origin_lon_deg})"
        )

    # --- PILOT_COMMAND -> sim commands ---

    def on_pilot_command(self, msg: ros.PilotCommand) -> None:
        # Engine: pct [-100, 100] -> forward to sim
        engine_msg = ros.Float()
        engine_msg.data = float(msg.engine_speed_pct)
        self.sim_cmd_engine_pub.publish(engine_msg)

        # Rudder: pct [-100, 100] -> angle [-max, max] deg
        rudder_deg = (
            msg.rudder_position_pct / 100.0 * self.params.p.rudder_max_angle_deg
        )
        rudder_msg = ros.Float()
        rudder_msg.data = float(rudder_deg)
        self.sim_cmd_rudder_pub.publish(rudder_msg)

        # Mast: speed pct [-100, 100] -> integrate sail angle
        dt = 1.0 / self.params.p.publish_rate_hz
        mast_speed_deg = msg.mast_speed_pct / 100.0 * self.params.p.mast_max_speed_deg_s
        self.sail_angle_deg += mast_speed_deg * dt

        sail_msg = ros.SailAngle()
        sail_msg.angle_deg = float(self.sail_angle_deg)
        sail_msg.reference = ros.SailAngle.BOAT_REF
        self.sim_cmd_sail_pub.publish(sail_msg)

    # --- sim state callbacks ---

    def on_sim_pose(self, msg: ros.PoseStamped) -> None:
        self.pose = Pose2D.from_ros_pose(msg.pose)

    def on_sim_velocity(self, msg: ros.Velocity) -> None:
        self.velocity = BoatVelocity.from_ros_velocity(msg)

    def on_sim_sail_angle(self, msg: ros.SailAngle) -> None:
        # Inverse of fake_actuator_node: angle_deg -> pts
        # pts = angle_deg * 8192 / 360 + 3000
        self.mast_position_pts = int(msg.angle_deg * 8192 / 360 + 3000)

    # --- publish PilotStatus ---

    def on_publish_timer(self) -> None:
        if not all_ready(
            self,
            pose=self.pose,
            velocity=self.velocity,
            mast_position_pts=self.mast_position_pts,
        ):
            return

        geopose = self.projector.pose2d_to_geopose2d(self.pose)
        enu_vel = self.velocity.to_enu_vector()
        heading_deg = self.pose.yaw.to_direction().deg

        status = ros.PilotStatus()

        # Position angles
        status.position_angle_phi_deg = 0.0
        status.position_angle_theta_deg = 0.0
        status.position_angle_psi_deg = heading_deg.value
        status.position_angle_mast_position_pts = self.mast_position_pts

        # GPS
        status.gps_north_speed_m_s = float(enu_vel[1])
        status.gps_east_speed_m_s = float(enu_vel[0])
        status.gps_down_speed_m_s = 0.0
        status.gps_latitude_deg = float(geopose.lat_deg)
        status.gps_longitude_deg = float(geopose.lon_deg)
        status.gps_altitude_m = 0.0

        # Radio (null data)
        status.radio_tx_mode = 0
        status.radio_tx_1 = 0.0
        status.radio_tx_2 = 0.0
        status.radio_tx_3 = 0.0
        status.radio_tx_4 = 0.0
        status.radio_tx_5 = 0.0
        status.radio_tx_6 = 0.0
        status.radio_tx_7 = 0.0
        status.radio_tx_8 = 0.0

        self.status_pub.publish(status)
        logt(self).debug(
            f"Publish PilotStatus: pos=({geopose.lat_deg:.6f}, {geopose.lon_deg:.6f}), mast={self.mast_position_pts}, heading={heading_deg}, speed=({enu_vel[0]:.2f}, {enu_vel[1]:.2f}) m/s"
        )


def main() -> None:
    rclpy.init()
    node = NaveolSimNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
