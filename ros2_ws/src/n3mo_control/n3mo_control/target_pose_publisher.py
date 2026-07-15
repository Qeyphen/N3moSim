#!/usr/bin/env python3
"""Publishes a target pose on /<agent>/target_pose for Unity's AutonomousBoatController, then exits.

The target is a 2D point on the water in Unity convention: x (right), z (forward), y = 0.
Unity only subscribes while the boat is in AUTO mode, and the relayed subscription can appear a
moment late, so this republishes until a subscriber has been present for `hold_time` (then exits),
or warns and exits after `wait_timeout`.
"""

import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from geometry_msgs.msg import PoseStamped


class TargetPosePublisher(Node):
    def __init__(self):
        super().__init__('target_pose_publisher')

        self.declare_parameter('topic', '/agent_01/target_pose')
        self.declare_parameter('frame_id', 'map')
        self.declare_parameter('x', 0.0)               # Unity right
        self.declare_parameter('z', 0.0)               # Unity forward
        self.declare_parameter('wait_timeout', 15.0)   # s — give up if no subscriber
        self.declare_parameter('hold_time', 2.0)       # s — keep publishing after a subscriber appears
        self.declare_parameter('period', 0.25)         # s — republish interval

        self.topic = self.get_parameter('topic').value

        qos = QoSProfile(
            depth=1,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
            reliability=QoSReliabilityPolicy.RELIABLE,
        )
        self.publisher = self.create_publisher(PoseStamped, self.topic, qos)

    def _make_msg(self) -> PoseStamped:
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self.get_parameter('frame_id').value
        msg.pose.position.x = float(self.get_parameter('x').value)
        msg.pose.position.y = 0.0
        msg.pose.position.z = float(self.get_parameter('z').value)
        msg.pose.orientation.w = 1.0  # heading derived on the Unity side
        return msg

    def run(self):
        wait_timeout = float(self.get_parameter('wait_timeout').value)
        hold_time = float(self.get_parameter('hold_time').value)
        period = float(self.get_parameter('period').value)
        x = float(self.get_parameter('x').value)
        z = float(self.get_parameter('z').value)

        start = time.monotonic()
        first_sub: float | None = None
        published = 0

        while rclpy.ok():
            now = time.monotonic()
            subs = self.count_subscribers(self.topic)
            if subs > 0 and first_sub is None:
                first_sub = now
                self.get_logger().info(f"Subscriber detected on '{self.topic}'.")

            self.publisher.publish(self._make_msg())
            published += 1

            if first_sub is not None and (now - first_sub) >= hold_time:
                self.get_logger().info(
                    f"Published target on '{self.topic}': x={x}, z={z} "
                    f"(subscribers={subs}, sent={published})."
                )
                return

            if first_sub is None and (now - start) >= wait_timeout:
                self.get_logger().warn(
                    f"No subscriber on '{self.topic}' after {wait_timeout:.0f}s — "
                    f"published {published}x anyway. Is Unity in Play and the boat in AUTO mode?"
                )
                return

            time.sleep(period)


def main(args=None):
    rclpy.init(args=args)
    node = TargetPosePublisher()
    try:
        node.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
