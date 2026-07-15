from __future__ import annotations

import time

import n3_common.ros as ros
import rclpy
from n3_common.math_utils.angles import Deg, wrap_180, wrap_360
from n3_common.models import MissionState
from n3_common.topics.n3mo_topics import (
    MISSION_STATE,
    PILOT_COMMAND,
    TARGET_SAIL_ANGLE,
    TARGET_VELOCITY,
)
from rclpy.node import Node
from sensor_msgs.msg import Joy

from .joystick_params import JoystickParams


class JoystickNode(Node):
    """Map gamepad axes to guidance targets or direct pilot commands.

    Subscribes to /joy (sensor_msgs/Joy) and publishes:
      - guidance mode: /guidance/target/velocity + /guidance/target/sail_angle
      - direct mode:   /drivers/naveol/pilot_command
    """

    def __init__(self) -> None:
        super().__init__("joystick_node", enable_logger_service=True)

        self.params = JoystickParams(self, on_change=lambda _: None)

        # Subscribers
        self.create_subscription(Joy, "/joy", self.on_joy, 10)

        # Guidance publishers
        self.velocity_pub = self.create_publisher(
            ros.Velocity, TARGET_VELOCITY.name, TARGET_VELOCITY.qos
        )
        self.sail_pub = self.create_publisher(
            ros.SailAngle, TARGET_SAIL_ANGLE.name, TARGET_SAIL_ANGLE.qos
        )

        # Direct publisher
        self.command_pub = self.create_publisher(
            ros.PilotCommand, PILOT_COMMAND.name, PILOT_COMMAND.qos
        )

        # Mission state publisher (guidance mode only)
        self.mission_state_pub = self.create_publisher(
            ros.MissionState, MISSION_STATE.name, MISSION_STATE.qos
        )

        self.latest_axes: list[float] = []
        self.latest_buttons: list[int] = []
        self.prev_buttons: list[int] = []
        self.btn_last_trigger: dict[int, float] = {}

        # Guidance accumulated state
        self.target_cog_deg = Deg(0.0)
        self.target_sog_kts = 0.0
        self.target_sail_deg = Deg(0.0)

        # Mutable runtime state (initialised from params)
        self.mode = self.params.p.mode
        self.sail_reference = self.params.p.sail_reference

        self.dt = 1.0 / self.params.p.publish_hz
        self.create_timer(self.dt, self.on_publish_timer)

        self.get_logger().info(f"JoystickNode ready — mode={self.mode}")

    # ---- subscription ----

    def on_joy(self, msg: Joy) -> None:
        self.prev_buttons = self.latest_buttons
        self.latest_axes = list(msg.axes)
        self.latest_buttons = list(msg.buttons)

    # ---- publish loop ----

    def on_publish_timer(self) -> None:
        if not self.latest_axes:
            return

        self._handle_mode_buttons()

        if self.mode == "guidance":
            self._publish_guidance()
        elif self.mode == "direct":
            self._publish_direct()

    def _handle_mode_buttons(self) -> None:
        p = self.params.p

        if self._btn_pressed(p.sail_boat_ref_btn) and self.sail_reference != 0:
            self.sail_reference = 0
            self.get_logger().info("Sail reference → BOAT")

        if self._btn_pressed(p.sail_wind_ref_btn) and self.sail_reference != 1:
            self.sail_reference = 1
            self.get_logger().info("Sail reference → WIND")

        if self._btn_pressed(p.guidance_mode_btn) and self.mode != "guidance":
            self.mode = "guidance"
            self.get_logger().info("Switched to guidance mode")

        if self._btn_pressed(p.direct_mode_btn) and self.mode != "direct":
            self.mode = "direct"
            self.get_logger().info("Switched to direct mode")

    def _publish_guidance(self) -> None:
        p = self.params.p

        # Axis rate-of-change
        cog_raw = Deg(self._axis(p.cog_axis))
        sail_raw = Deg(self._axis(p.sail_axis))
        sog_raw = self._axis(p.sog_axis)

        self.target_cog_deg += cog_raw * p.cog_rate_deg_s * self.dt
        self.target_sog_kts += sog_raw * p.sog_rate_kts_s * self.dt
        self.target_sail_deg += sail_raw * p.sail_rate_deg_s * self.dt

        # Button steps (edge-detected)
        self.target_cog_deg += Deg(self._btn_step(p.cog_plus_btn, p.cog_step_deg))
        self.target_cog_deg += Deg(self._btn_step(p.cog_minus_btn, -p.cog_step_deg))
        self.target_sog_kts += self._btn_step(p.sog_plus_btn, p.sog_step_kts)
        self.target_sog_kts += self._btn_step(p.sog_minus_btn, -p.sog_step_kts)
        self.target_sail_deg += Deg(self._btn_step(p.sail_plus_btn, p.sail_step_deg))
        self.target_sail_deg += Deg(self._btn_step(p.sail_minus_btn, -p.sail_step_deg))

        # Clamp / normalize
        self.target_cog_deg = wrap_360(self.target_cog_deg)
        self.target_sog_kts = max(0.0, min(self.target_sog_kts, p.sog_max_kts))
        self.target_sail_deg = wrap_180(self.target_sail_deg)

        vel = ros.Velocity()
        vel.cog_deg = self.target_cog_deg.value
        vel.sog_kts = float(self.target_sog_kts)
        self.velocity_pub.publish(vel)

        sail = ros.SailAngle()
        sail.angle_deg = self.target_sail_deg.value
        sail.reference = int(self.sail_reference)
        self.sail_pub.publish(sail)

        mission = ros.MissionState()
        mission.state = int(MissionState.NAVIGATING)
        mission.goal_index = 0
        self.mission_state_pub.publish(mission)

    def _publish_direct(self) -> None:
        p = self.params.p

        engine_raw = self._axis(p.engine_axis)
        rudder_raw = self._axis(p.rudder_axis)
        mast_raw = self._axis(p.mast_axis)

        cmd = ros.PilotCommand()
        cmd.rudder_position_pct = float(rudder_raw * p.rudder_scale_pct)
        cmd.engine_speed_pct = float(max(0.0, engine_raw) * p.engine_scale_pct)
        cmd.mast_speed_pct = float(mast_raw * p.mast_scale_pct)
        self.command_pub.publish(cmd)

        mission = ros.MissionState()
        mission.state = int(MissionState.IDLE)
        mission.goal_index = 0
        self.mission_state_pub.publish(mission)

    # ---- helpers ----

    def _axis(self, index: int) -> float:
        """Read axis value with deadzone applied."""
        if index >= len(self.latest_axes):
            return 0.0
        value = self.latest_axes[index]
        if abs(value) < self.params.p.deadzone:
            return 0.0
        return value

    def _btn_pressed(self, btn_index: int) -> bool:
        """Return True on debounced rising edge of button."""
        return self._btn_step(btn_index, 1.0) != 0.0

    def _btn_step(self, btn_index: int, step: float) -> float:
        """Return *step* on debounced rising edge of button, else 0."""
        if btn_index < 0:
            return 0.0
        now = (
            self.latest_buttons[btn_index]
            if btn_index < len(self.latest_buttons)
            else 0
        )
        prev = self.prev_buttons[btn_index] if btn_index < len(self.prev_buttons) else 0
        if now and not prev:
            t = time.monotonic()
            if (
                t - self.btn_last_trigger.get(btn_index, 0.0)
                < self.params.p.btn_debounce_s
            ):
                return 0.0
            self.btn_last_trigger[btn_index] = t
            return step
        return 0.0


def main() -> None:
    rclpy.init()
    node = JoystickNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
