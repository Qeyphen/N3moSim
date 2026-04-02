"""
mission_planner.py
==================
High level mission brain for N3moSim.
Decides what each dynamic object should do and when.
Publishes individual commands per object to n3mo_controller.

Topics published (one per dynamic object):
  /mission/{object_id}/cmd_vel  → n3mo_controller

Topics subscribed:
  /sailboat/gps    ← sensor_publisher (boat position)
  /obstacles       ← obstacle_detector (nearby obstacles)
"""

import json
import os
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from sensor_msgs.msg import NavSatFix
from std_msgs.msg import String
from n3mo_control.config_loader import load_config


class MissionPlanner(Node):
    def __init__(self):
        super().__init__('mission_planner')

        self.config = load_config(self.get_logger())

        # Create one publisher per dynamic object
        # { object_id: Publisher }
        self.cmd_publishers = {}

        # { object_id: mission_state }
        self.mission_states = {}

        for obj in self.config.get('objects', []):
            if not obj.get('dynamic', False):
                continue

            object_id = obj['id']
            mission_topic = f'/mission/{object_id}/cmd_vel'

            self.cmd_publishers[object_id] = self.create_publisher(
                Twist, mission_topic, 10)

            # Default state for each object
            self.mission_states[object_id] = 'idle'

            self.get_logger().info(
                f'MissionPlanner controlling: {object_id} → {mission_topic}')

        # GPS from sailboat
        self.create_subscription(
            NavSatFix, '/sailboat/gps', self.on_gps, 10)

        # Obstacle data
        self.create_subscription(
            String, '/obstacles', self.on_obstacles, 10)

        self.current_lat = 0.0
        self.current_lon = 0.0
        self.obstacles   = []

        # Mission loop at 10Hz
        self.timer = self.create_timer(0.1, self.mission_loop)
        self.get_logger().info('MissionPlanner ready!')

    def load_config(self, path):
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.get_logger().error(f'Config error: {e}')
            return {'objects': []}

    # Sensor callbacks
    def on_gps(self, msg):
        self.current_lat = msg.latitude
        self.current_lon = msg.longitude

    def on_obstacles(self, msg):
        self.obstacles = msg.data

    def mission_loop(self):
        for object_id, state in self.mission_states.items():
            cmd = self.compute_command(object_id, state)
            if object_id in self.cmd_publishers:
                self.cmd_publishers[object_id].publish(cmd)

    # Compute command based on state
    def compute_command(self, object_id, state):
        msg = Twist()

        if state == 'idle':
            # Do nothing — stay still
            msg.linear.x  = 0.0
            msg.angular.z = 0.0

        elif state == 'forward':
            # Move straight ahead
            msg.linear.x  = 1.0
            msg.angular.z = 0.0

        elif state == 'reverse':
            # Move backwards
            msg.linear.x  = -1.0
            msg.angular.z = 0.0

        elif state == 'turn_left':
            # Turn left while moving
            msg.linear.x  = 0.5
            msg.angular.z = -1.0

        elif state == 'turn_right':
            # Turn right while moving
            msg.linear.x  = 0.5
            msg.angular.z = 1.0

        elif state == 'patrol':
            # Simple patrol — go forward slowly
            msg.linear.x  = 0.3
            msg.angular.z = 0.0

        elif state == 'stop':
            msg.linear.x  = 0.0
            msg.angular.z = 0.0

        return msg

    # Public: set mission state for any object
    def set_mission(self, object_id, state):
        if object_id in self.mission_states:
            self.mission_states[object_id] = state
            self.get_logger().info(
                f'{object_id} mission → {state}')
        else:
            self.get_logger().warn(
                f'Unknown object: {object_id}')

    # Public: set all objects to same state
    def set_all_missions(self, state):
        for object_id in self.mission_states:
            self.set_mission(object_id, state)


def main(args=None):
    rclpy.init(args=args)
    node = MissionPlanner()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()