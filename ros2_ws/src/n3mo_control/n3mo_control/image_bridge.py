"""
image_bridge.py
===============
Subscribes to /unity/camera/compressed from Unity via ROS TCP bridge.
Republishes as standard ROS2 sensor_msgs/CompressedImage so any
ROS2 node or ros2 bag can consume it.

Also saves latest frame to /recordings/latest_frame.jpg for
quick visual verification.

Topics:
  Subscribes:  /unity/camera/compressed  ← from Unity
  Publishes:   /camera/compressed        → ROS2 network + bag
"""

import os
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage


class ImageBridge(Node):
    def __init__(self):
        super().__init__('image_bridge')

        self.frame_count = 0
        self.save_every  = 30  # save a preview frame every 30 frames

        self.create_subscription(
            CompressedImage,
            '/unity/camera/compressed',
            self.on_image,
            10
        )

        self.pub = self.create_publisher(
            CompressedImage, '/camera/compressed', 10)

        self.get_logger().info(
            'ImageBridge ready — '
            '/unity/camera/compressed → /camera/compressed'
        )

    def on_image(self, msg):
        # republish to ROS network
        self.pub.publish(msg)

        self.frame_count += 1

        # save preview frame periodically for verification
        if self.frame_count % self.save_every == 0:
            try:
                path = '/recordings/latest_frame.jpg'
                os.makedirs('/recordings', exist_ok=True)
                with open(path, 'wb') as f:
                    f.write(bytes(msg.data))
                self.get_logger().info(
                    f'Frame {self.frame_count} saved → {path}'
                )
            except Exception as e:
                self.get_logger().warn(f'Could not save frame: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = ImageBridge()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
