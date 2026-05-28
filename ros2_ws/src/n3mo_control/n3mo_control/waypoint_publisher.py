#!/usr/bin/env python3
"""
waypoint_publisher.py
---------------------
Publishes a single PointStamped waypoint on /{object_id}/waypoint.

Usage
-----
# One-shot: send a single waypoint
ros2 run n3mo_control waypoint_publisher --ros-args \
  -p object_id:=sailboat_01 \
  -p x:=50.0 \
  -p z:=100.0

# Interactive: keep node alive, re-publish on a timer (useful for debugging)
ros2 run n3mo_control waypoint_publisher --ros-args \
  -p object_id:=sailboat_01 \
  -p x:=50.0 \
  -p z:=100.0 \
  -p mode:=repeat \
  -p repeat_hz:=1.0

Parameters
----------
object_id   str    sailboat_01   Which vessel to command
x           float  50.0          World X coordinate
z           float  100.0         World Z coordinate (forward in Unity)
mode        str    once          "once" | "repeat"
repeat_hz   float  1.0           Publish rate when mode=repeat
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped
from builtin_interfaces.msg import Time
import time


class WaypointPublisher(Node):

    def __init__(self):
        super().__init__('waypoint_publisher')

        self.declare_parameter('object_id',  'sailboat_01')
        self.declare_parameter('x',          50.0)
        self.declare_parameter('z',          100.0)
        self.declare_parameter('mode',       'once') 
        self.declare_parameter('repeat_hz',  1.0)

        self.object_id  = self.get_parameter('object_id').value
        self.x          = float(self.get_parameter('x').value)
        self.z          = float(self.get_parameter('z').value)
        self.mode       = self.get_parameter('mode').value
        self.repeat_hz  = float(self.get_parameter('repeat_hz').value)

        topic = f'/{self.object_id}/waypoint'
        self.pub = self.create_publisher(PointStamped, topic, 10)

        self.get_logger().info(
            f'WaypointPublisher ready → {topic}  '
            f'target=({self.x}, {self.z})  mode={self.mode}'
        )

        if self.mode == 'once':
            # Small delay so Unity subscriber is ready
            time.sleep(0.5)
            self._publish()
            self.get_logger().info('Waypoint sent (once). Shutting down.')
        else:
            period = 1.0 / self.repeat_hz
            self.timer = self.create_timer(period, self._publish)

    # ────────────────────────────────────────────────────────────────────────

    def _publish(self):
        msg = PointStamped()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = 'world'
        msg.point.x         = self.x
        msg.point.y         = 0.0   # Y ignored by SimpleController
        msg.point.z         = self.z
        self.pub.publish(msg)
        self.get_logger().info(
            f'  → waypoint ({self.x:.1f}, {self.z:.1f}) published'
        )


# ────────────────────────────────────────────────────────────────────────────

def main(args=None):
    rclpy.init(args=args)
    node = WaypointPublisher()

    if node.mode == 'once':
        node.destroy_node()
        rclpy.shutdown()
    else:
        try:
            rclpy.spin(node)
        except KeyboardInterrupt:
            pass
        finally:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()