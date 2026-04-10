"""
trajectory_publisher.py
=======================
Publishes predefined trajectory commands for N3moSim demo scenarios.
Reads a scenario JSON file and publishes Twist commands to each vessel
via the mission planner topics.

Scenarios supported:
  - circle: constant forward + constant turn
  - eight:  constant forward + sinusoidal turn (figure-8)

Usage:
  ros2 run n3mo_control trajectory_publisher --ros-args \
    -p scenario_file:=scenario_mixed.json

Topics published:
  /mission/{object_id}/cmd_vel → n3mo_controller
"""

import math
import os
import time
import json

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class TrajectoryPublisher(Node):
    def __init__(self):
        super().__init__('trajectory_publisher')

        self.declare_parameter('scenario_file', 'scenario_mixed.json')
        scenario_file = self.get_parameter(
            'scenario_file').get_parameter_value().string_value

        self.scenario = self.load_scenario(scenario_file)
        if self.scenario is None:
            self.get_logger().error('Failed to load scenario! Shutting down.')
            return

        self.publishers = {}
        self.start_time = time.time()
        self.speed = 0.4  # how fast the trajectory cycles

        # Create one publisher per object
        for obj in self.scenario.get('objects', []):
            object_id = obj['id']
            topic = f'/mission/{object_id}/cmd_vel'
            self.publishers[object_id] = self.create_publisher(
                Twist, topic, 10)
            self.get_logger().info(
                f'Trajectory [{obj["trajectory"]}] → {topic}')

        # Publish at 10Hz
        self.timer = self.create_timer(0.1, self.publish_trajectories)

        self.get_logger().info(
            f'TrajectoryPublisher ready! '
            f'Scenario: {self.scenario.get("scenario")} — '
            f'{self.scenario.get("description")}'
        )

    def load_scenario(self, filename):
        search_paths = [
            f'/n3mosim/config/{filename}',
            os.path.join(os.path.dirname(__file__),
                         '..', '..', '..', '..', 'config', filename),
        ]
        for path in search_paths:
            path = os.path.normpath(path)
            if os.path.exists(path):
                try:
                    with open(path, 'r') as f:
                        scenario = json.load(f)
                    self.get_logger().info(f'Scenario loaded: {path}')
                    return scenario
                except json.JSONDecodeError as e:
                    self.get_logger().error(f'Scenario JSON error: {e}')
                    return None
        self.get_logger().error(
            f'Scenario file not found: {filename}\n'
            f'Searched: {search_paths}'
        )
        return None

    def publish_trajectories(self):
        t = (time.time() - self.start_time) * self.speed

        for obj in self.scenario.get('objects', []):
            object_id = obj['id']
            if object_id not in self.publishers:
                continue

            trajectory = obj.get('trajectory', 'circle')
            phase = obj.get('phase_offset', 0.0)
            msg = Twist()

            if trajectory == 'circle':
                # Constant forward speed + constant angular = perfect circle
                msg.linear.x = float(obj.get('linear_x', 2.0))
                msg.angular.z = float(obj.get('angular_z', 0.3))

            elif trajectory == 'eight':
                # Constant forward + sinusoidal turn = figure-8
                amplitude = float(obj.get('angular_z_amplitude', 0.5))
                msg.linear.x = float(obj.get('linear_x', 2.0))
                msg.angular.z = amplitude * math.sin(t + phase)

            self.publishers[object_id].publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = TrajectoryPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()