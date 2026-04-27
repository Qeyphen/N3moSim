"""
pose_publisher.py
=================
Publishes exact boat positions for circle and figure-8 trajectories.
Unity PoseController moves boat directly to each position.
No physics drift, no backwards movement issues.

Usage:
  ros2 run n3mo_control pose_publisher --ros-args -p scenario:=circle
  ros2 run n3mo_control pose_publisher --ros-args -p scenario:=eight
"""

import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped


class PosePublisher(Node):
    def __init__(self):
        super().__init__('pose_publisher')

        self.declare_parameter('scenario', 'circle')
        self.scenario = self.get_parameter('scenario').value

        self.declare_parameter('radius', 50.0)
        self.radius = self.get_parameter('radius').value

        self.declare_parameter('speed', 0.3)
        self.speed = self.get_parameter('speed').value

        # Match the scene_config.json sailboat position
        self.center_x = 0.0
        self.center_z = -300.0
        self.water_y  = 1.0

        self.pub = self.create_publisher(
            PoseStamped, '/sailboat_01/pose', 10)

        self.t = 0.0
        self.timer = self.create_timer(0.1, self.publish_pose)

        self.get_logger().info(
            f'PosePublisher ready! '
            f'scenario={self.scenario} '
            f'radius={self.radius} '
            f'speed={self.speed}'
        )

    def publish_pose(self):
        self.t -= 0.1 * self.speed

        if self.scenario == 'circle':
            x   = self.center_x + self.radius * math.cos(self.t)
            z   = self.center_z + self.radius * math.sin(self.t)
            yaw = self.t + math.pi / 2

        elif self.scenario == 'eight':
            x   = self.center_x + self.radius * math.sin(self.t)
            z   = self.center_z + self.radius * math.sin(self.t * 2)
            yaw = math.atan2(
                self.radius * 2 * math.cos(self.t * 2),
                self.radius * math.cos(self.t)
            )
        else:
            return

        msg                    = PoseStamped()
        msg.header.stamp       = self.get_clock().now().to_msg()
        msg.header.frame_id    = 'world'
        msg.pose.position.x    = x
        msg.pose.position.y    = self.water_y
        msg.pose.position.z    = z
        msg.pose.orientation.x = 0.0
        msg.pose.orientation.y = math.sin(yaw / 2)
        msg.pose.orientation.z = 0.0
        msg.pose.orientation.w = math.cos(yaw / 2)

        self.pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = PosePublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()