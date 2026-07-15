"""
Test harness for simple_sim_node.
Allow to test simple sim alone to check how the boat behaves with given wind, sail angle and rudder angle.

Publishes fixed commands (wind, sail, rudder) and subscribes to sim outputs.
Also broadcasts TF (map → boat_link) and joint_states so the boat is visible
in Foxglove 3D.
"""

from __future__ import annotations

import n3_common.models as pyd
import n3_common.ros as ros
import rclpy
from n3_common.geo.frame_ids import FrameIds
from n3_common.geo.tf_helper import TfHelper
from n3_common.math_utils.angles import Rad
from n3_common.models import EnuAngle, Pose2D
from n3_common.n3_const import DEG2RAD
from n3_common.params.pydantic_params_base import PydanticParamsBase
from n3_common.topics.n3mo_topics import BOAT_POSE, BOAT_VELOCITY, WIND_TRUE
from n3_common.topics.sim_topics import (
    SIM_CMD_RUDDER_ANGLE,
    SIM_CMD_SAIL_ANGLE,
    SIM_POSE,
    SIM_SAIL_ANGLE_STATE,
    SIM_VELOCITY,
)
from n3_common.utils.logger_helper import logt
from pydantic import BaseModel, Field
from rclpy.node import Node


class TestHarnessModel(BaseModel):
    wind_direction_deg: float = Field(
        default=0.0, description="True wind direction in degrees CW from North."
    )
    wind_speed_kts: float = Field(
        default=10.0, ge=0.0, description="True wind speed in knots."
    )
    sail_angle_deg: float = Field(
        default=-20.0, description="Sail angle in degrees CCW (+ = starboard)."
    )
    rudder_angle_deg: float = Field(
        default=0.0, description="Rudder angle in degrees (+ = turn to port)."
    )
    publish_rate_hz: float = Field(
        default=10.0, ge=1.0, le=50.0, description="Command publish rate in Hz."
    )


class TestHarnessParams(PydanticParamsBase[TestHarnessModel]):
    model_class = TestHarnessModel

    def __init__(self, node: Node, *, on_change=None):
        super().__init__(node, on_change=on_change)


class TestHarnessNode(Node):
    """Publishes fixed test inputs and relays sim pose to TF for Foxglove."""

    def __init__(self) -> None:
        super().__init__("test_harness", enable_logger_service=True)

        self.params = TestHarnessParams(self, on_change=self.on_params_change)
        p = self.params.p

        # --- publishers ---
        self.wind_pub = self.create_publisher(ros.Wind, WIND_TRUE.name, WIND_TRUE.qos)
        self.sail_pub = self.create_publisher(
            ros.SailAngle, SIM_CMD_SAIL_ANGLE.name, SIM_CMD_SAIL_ANGLE.qos
        )
        self.rudder_pub = self.create_publisher(
            ros.Float, SIM_CMD_RUDDER_ANGLE.name, SIM_CMD_RUDDER_ANGLE.qos
        )
        self.joint_state_pub = self.create_publisher(
            ros.JointState, "/joint_states", 10
        )
        self.boat_pose_pub = self.create_publisher(
            ros.PoseStamped, BOAT_POSE.name, BOAT_POSE.qos
        )
        self.boat_velocity_pub = self.create_publisher(
            ros.Velocity, BOAT_VELOCITY.name, BOAT_VELOCITY.qos
        )
        # --- subscribers (log sim outputs) ---
        self.create_subscription(
            ros.PoseStamped, SIM_POSE.name, self.on_sim_pose, SIM_POSE.qos
        )
        self.create_subscription(
            ros.Velocity, SIM_VELOCITY.name, self.on_sim_velocity, SIM_VELOCITY.qos
        )
        self.create_subscription(
            ros.SailAngle,
            SIM_SAIL_ANGLE_STATE.name,
            self.on_sim_sail_angle,
            SIM_SAIL_ANGLE_STATE.qos,
        )

        # --- TF broadcaster ---
        self.tf_helper = TfHelper(self)

        # --- timers ---
        self.create_timer(1.0 / p.publish_rate_hz, self.on_publish_commands)

        self.get_logger().info(
            f"TestHarness ready — "
            f"wind={p.wind_direction_deg}° @ {p.wind_speed_kts} kts, "
            f"sail={p.sail_angle_deg}°, rudder={p.rudder_angle_deg}°"
        )

    def on_params_change(self, _changes: list) -> None:
        p = self.params.p
        self.get_logger().info(
            f"Params changed — "
            f"wind={p.wind_direction_deg}° @ {p.wind_speed_kts} kts, "
            f"sail={p.sail_angle_deg}°, rudder={p.rudder_angle_deg}°"
        )

    def on_publish_commands(self) -> None:
        p = self.params.p
        # Wind
        wind_msg = ros.Wind()
        wind_msg.direction_deg = float(p.wind_direction_deg)
        wind_msg.speed_kts = float(p.wind_speed_kts)
        self.wind_pub.publish(wind_msg)

        # Sail angle
        sail_msg = ros.SailAngle()
        sail_msg.angle_deg = float(p.sail_angle_deg)
        sail_msg.reference = ros.SailAngle.BOAT_REF
        self.sail_pub.publish(sail_msg)

        # Rudder angle
        rudder_msg = ros.Float()
        rudder_msg.data = float(p.rudder_angle_deg)
        self.rudder_pub.publish(rudder_msg)

    def on_sim_pose(self, msg: ros.PoseStamped) -> None:
        pose2d = Pose2D.from_ros_pose(msg.pose)

        # Republish on /boat/pose for foxglove_converter
        self.boat_pose_pub.publish(msg)

        # Broadcast TF for Foxglove 3D: map → benu → boat_link
        self.tf_helper.publish_tf_from_yaw_xyz(
            parent_frame=FrameIds.MAP,
            child_frame=FrameIds.BENU,
            yaw=EnuAngle(rad=Rad(0.0)),
            x=pose2d.x,
            y=pose2d.y,
            z=0.0,
        )
        self.tf_helper.publish_tf_from_yaw(
            parent_frame=FrameIds.BENU,
            child_frame=FrameIds.BOAT,
            yaw=pose2d.yaw,
        )

        # Publish joint states for sail/rudder visualization
        js = ros.JointState()
        js.header.stamp = msg.header.stamp
        js.name = ["sail_joint", "rudder_joint"]
        js.position = [
            self.params.p.sail_angle_deg * DEG2RAD,
            self.params.p.rudder_angle_deg * DEG2RAD,
        ]
        js.velocity = [0.0, 0.0]
        js.effort = [0.0, 0.0]
        self.joint_state_pub.publish(js)

        logt(self, dt_sec=5.0).info(f"pose: {pose2d}")

    def on_sim_velocity(self, msg: ros.Velocity) -> None:
        logt(self, dt_sec=5.0).info(f"vel: {pyd.BoatVelocity.from_ros_velocity(msg)}")
        # Republish on /boat/velocity for foxglove_converter
        self.boat_velocity_pub.publish(msg)

    def on_sim_sail_angle(self, msg: ros.SailAngle) -> None:
        logt(self, dt_sec=5.0).info(f"sail Angle: {pyd.SailAngle.from_ros(msg)}")


def main() -> None:
    rclpy.init()
    node = TestHarnessNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
