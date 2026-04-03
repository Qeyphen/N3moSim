"""
n3mo_controller.py
==================
Master controller for N3moSim.
Reads scene_config.json and creates a publisher for EACH dynamic object.
Each object gets its own unique ROS2 topic so they can be controlled independently.

Topics published (per dynamic object):
  /sailboat_01/cmd_vel    → geometry_msgs/Twist
  /catamaran_01/cmd_vel   → geometry_msgs/Twist
  /catamaran_02/cmd_vel   → geometry_msgs/Twist
  /buoy_03/cmd_vel        → geometry_msgs/Twist
  ... (one per dynamic object in config)

Topics subscribed:
  /mission/{object_id}/cmd_vel  ← from mission planner (per object)
"""

import json
import os
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from n3mo_control.config_loader import load_config


class N3moController(Node):
    def __init__(self):
        super().__init__('n3mo_controller')

        self.config = load_config(self.get_logger())
        if self.config is None:
            self.get_logger().error('Failed to load config! Shutting down.')
            return

        # { object_id: { 'publisher': Publisher, 'topic': str, 'type': str } }
        self.dynamic_objects = {}

        # Create publishers and subscribers for each dynamic object
        for obj in self.config.get('objects', []):
            if not obj.get('dynamic', False):
                self.get_logger().info(
                    f"[STATIC]  {obj['id']} — no ROS2 control needed")
                continue

            object_id = obj['id']
            ros2_topic = obj.get('ros2_topic', f'/{object_id}/cmd_vel')
            object_type = obj.get('type', 'unknown')

            publisher = self.create_publisher(Twist, ros2_topic, 10)

            # Subscriber ← mission planner (per object commands)
            mission_topic = f'/mission/{object_id}/cmd_vel'
            self.create_subscription(
                Twist,
                mission_topic,
                lambda msg, oid=object_id: self.on_mission_command(msg, oid),
                10
            )

            self.dynamic_objects[object_id] = {
                'publisher':  publisher,
                'topic':      ros2_topic,
                'type':       object_type,
                'current_cmd': Twist()
            }

            self.get_logger().info(
                f"[DYNAMIC] {object_id} ({object_type}) "
                f"→ Unity: {ros2_topic} "
                f"← Mission: {mission_topic}"
            )

        self.timer = self.create_timer(0.1, self.publish_all_commands)

        self.get_logger().info(
            f'N3moController ready! '
            f'Controlling {len(self.dynamic_objects)} dynamic objects.'
        )

    def load_config(self, path):
        try:
            with open(path, 'r') as f:
                config = json.load(f)
            self.get_logger().info(f'Config loaded from: {path}')
            return config
        except FileNotFoundError:
            self.get_logger().error(f'Config not found: {path}')
            return None
        except json.JSONDecodeError as e:
            self.get_logger().error(f'Config JSON error: {e}')
            return None

    # Receive command from mission planner for a specific object
    def on_mission_command(self, msg, object_id):
        if object_id in self.dynamic_objects:
            self.dynamic_objects[object_id]['current_cmd'] = msg

    # Publish current command for each dynamic object to Unity
    def publish_all_commands(self):
        for object_id, obj in self.dynamic_objects.items():
            obj['publisher'].publish(obj['current_cmd'])

    # Public: set velocity directly (for testing or ML)
    def set_velocity(self, object_id, linear_x, angular_z):
        if object_id not in self.dynamic_objects:
            self.get_logger().warn(f'Unknown object: {object_id}')
            return

        msg = Twist()
        msg.linear.x  = float(linear_x)
        msg.angular.z = float(angular_z)
        self.dynamic_objects[object_id]['current_cmd'] = msg

    # stop a specific object
    def stop_object(self, object_id):
        self.set_velocity(object_id, 0.0, 0.0)

    # Public: stop all objects
    def stop_all(self):
        for object_id in self.dynamic_objects:
            self.stop_object(object_id)
        self.get_logger().info('All objects stopped.')


def main(args=None):
    rclpy.init(args=args)
    node = N3moController()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()