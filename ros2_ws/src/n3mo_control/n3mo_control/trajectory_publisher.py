"""
trajectory_publisher.py
=======================
Publishes predefined trajectory commands for N3moSim demo scenarios.

Reads dynamic objects from scene_config.json (same config Unity uses),
then applies movement patterns from the chosen scenario file.

This ensures trajectory publisher always stays in sync with what
Unity has actually spawned — no duplicate config needed.

Scenarios supported:
  - circle: constant forward + constant turn = circular path
  - eight:  constant forward + sinusoidal turn = figure-8 path

Usage:
  ros2 run n3mo_control trajectory_publisher --ros-args \
    -p scenario_file:=scenario_mixed.json

Topics published:
  /mission/{object_id}/cmd_vel → n3mo_controller → Unity
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

        # ROS2 parameter: which scenario file to use
        self.declare_parameter('scenario_file', 'scenario_mixed.json')
        scenario_file = self.get_parameter(
            'scenario_file').get_parameter_value().string_value

        # Load scenario — cross-references scene_config.json automatically
        self.scenario = self.load_scenario(scenario_file)
        if self.scenario is None:
            self.get_logger().error('Failed to load scenario! Shutting down.')
            return

        self.vessel_publishers = {}
        self.start_time = time.time()
        self.speed = 0.4  # trajectory cycle speed multiplier

        # Create one publisher per active object
        for obj in self.scenario.get('objects', []):
            object_id = obj['id']
            topic = f'/mission/{object_id}/cmd_vel'
            self.vessel_publishers[object_id] = self.create_publisher(
                Twist, topic, 10)
            self.get_logger().info(
                f'[{obj["trajectory"].upper()}] {object_id} → {topic}')

        # Publish at 10Hz
        self.timer = self.create_timer(0.1, self.publish_trajectories)

        self.get_logger().info(
            f'TrajectoryPublisher ready! '
            f'Scenario: {self.scenario.get("scenario")} — '
            f'{self.scenario.get("description")} | '
            f'{len(self.vessel_publishers)} vessels active'
        )

    def _read_json(self, path):
        """Read and parse a JSON file. Returns dict or None."""
        path = os.path.normpath(path)
        if not os.path.exists(path):
            self.get_logger().error(f'File not found: {path}')
            return None
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            self.get_logger().error(f'JSON parse error in {path}: {e}')
            return None

    def load_scenario(self, scenario_filename):
        """
        Load scenario file and cross-reference with scene_config.json.

        Only publishes to objects that are:
          1. Present in scene_config.json as dynamic=true
             (i.e. actually spawned in Unity)
          2. Listed in the scenario file with a trajectory

        This keeps trajectory_publisher in sync with Unity automatically.
        """

        # Search paths for scenario file
        scenario_search = [
            f'/n3mosim/config/{scenario_filename}',
            os.path.normpath(os.path.join(
                os.path.dirname(__file__),
                '..', '..', '..', '..', 'config', scenario_filename
            )),
        ]

        # Search paths for scene_config
        scene_search = [
            '/n3mosim/config/scene_config.json',
            os.path.normpath(os.path.join(
                os.path.dirname(__file__),
                '..', '..', '..', '..', 'config', 'scene_config.json'
            )),
        ]

        # Load scenario file
        scenario = None
        for path in scenario_search:
            scenario = self._read_json(path)
            if scenario:
                self.get_logger().info(f'Scenario loaded: {path}')
                break

        if not scenario:
            self.get_logger().error(
                f'Scenario file not found: {scenario_filename}\n'
                f'Searched: {scenario_search}'
            )
            return None

        # Load scene_config to know what Unity has spawned
        scene = None
        for path in scene_search:
            scene = self._read_json(path)
            if scene:
                self.get_logger().info(f'Scene config loaded: {path}')
                break

        if not scene:
            self.get_logger().warn(
                'scene_config.json not found — '
                'using all objects from scenario file without filtering. '
                'Make sure object IDs match what Unity has spawned.'
            )
            return scenario

        # Get IDs of dynamic objects actually spawned in Unity
        unity_dynamic_ids = {
            obj['id']
            for obj in scene.get('objects', [])
            if obj.get('dynamic', False)
        }

        self.get_logger().info(
            f'Unity dynamic objects: {sorted(unity_dynamic_ids)}'
        )

        # Filter scenario to only include objects Unity has spawned
        all_scenario_ids = {obj['id'] for obj in scenario.get('objects', [])}
        skipped = all_scenario_ids - unity_dynamic_ids
        if skipped:
            self.get_logger().warn(
                f'Skipping objects not in scene_config (or not dynamic): '
                f'{sorted(skipped)}'
            )

        active_objects = [
            obj for obj in scenario.get('objects', [])
            if obj['id'] in unity_dynamic_ids
        ]

        if not active_objects:
            self.get_logger().error(
                'No matching dynamic objects found between scenario and '
                'scene_config! Check that object IDs match.'
            )
            return None

        scenario['objects'] = active_objects
        self.get_logger().info(
            f'Active vessels: {[o["id"] for o in active_objects]}'
        )
        return scenario

    def publish_trajectories(self):
        """Compute and publish Twist command for each vessel."""
        t = (time.time() - self.start_time) * self.speed

        for obj in self.scenario.get('objects', []):
            object_id = obj['id']
            if object_id not in self.vessel_publishers:
                continue

            trajectory = obj.get('trajectory', 'circle')
            phase = obj.get('phase_offset', 0.0)
            msg = Twist()

            if trajectory == 'circle':
                # Constant forward + constant turn = perfect circle
                msg.linear.x  = float(obj.get('linear_x', 2.0))
                msg.angular.z = float(obj.get('angular_z', 0.3))

            elif trajectory == 'eight':
                # Constant forward + sinusoidal turn = figure-8
                amplitude     = float(obj.get('angular_z_amplitude', 0.5))
                msg.linear.x  = float(obj.get('linear_x', 2.0))
                msg.angular.z = amplitude * math.sin(t + phase)

            elif trajectory == 'idle':
                # Stay still
                msg.linear.x  = 0.0
                msg.angular.z = 0.0

            self.vessel_publishers[object_id].publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = TrajectoryPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()