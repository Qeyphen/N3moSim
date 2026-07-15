from __future__ import annotations

import n3_common.ros as ros
import rclpy
from n3_common.topics.n3mo_topics import PILOT_COMMAND, PILOT_STATUS
from rclpy.node import Node

from n3_sim.naveol_syd_sim.syd_model import SydCommandFrame
from n3_sim.naveol_syd_sim.syd_params import SydInterface, SydParams


class SydNode(Node):
    """
    SYD simulator driver.

    Replaces the Naveol serial driver with a ZMQ/TCP connection to the SYD
    physics simulator.  Publishes to PILOT_STATUS and subscribes to
    PILOT_COMMAND, identical to NaveolNode from the rest of the system's
    perspective.
    """

    def __init__(self) -> None:
        super().__init__("syd_node")

        self.params = SydParams(self)
        self.syd_interface = SydInterface(self.params)

        self.status_pub = self.create_publisher(
            ros.PilotStatus,
            PILOT_STATUS.name,
            PILOT_STATUS.qos,
        )

        self.create_subscription(
            ros.PilotCommand,
            PILOT_COMMAND.name,
            self.on_pilot_command,
            PILOT_COMMAND.qos,
        )

        self.create_timer(1.0 / self.params.p.poll_rate_hz, self.on_poll_timer)

        self.get_logger().info("SydNode ready")

    def on_poll_timer(self) -> None:
        status_frame = self.syd_interface.read()
        if status_frame is None or status_frame.Run == 0:
            return
        self.get_logger().debug(f"syd status: {status_frame}")
        self.status_pub.publish(status_frame.to_pilot_status())

    def on_pilot_command(self, msg: ros.PilotCommand) -> None:
        command = SydCommandFrame.from_pilot_command(msg)
        self.get_logger().debug(
            f"syd command: engine={command.engine_speed_pct:.2f} "
            f"rudder={command.rudder_position_pct:.2f} mast={command.mast_speed_pct:.2f}"
        )
        self.syd_interface.write(command)


def main() -> None:
    rclpy.init()
    node = SydNode()
    try:
        rclpy.spin(node)
    finally:
        node.syd_interface.disconnect()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
