"""
obstacle_detector.py
====================
Detects and tracks obstacles in N3moSim.
Receives all object positions from Unity.
Filters and publishes obstacle data to mission planner.

Topics subscribed:
  /unity/object_positions ← Unity (all object poses)

Topics published:
  /obstacles              → mission_planner
  /obstacles/nearby       → mission_planner (within threshold)
"""

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseArray, Pose
from std_msgs.msg import String
import math

class ObstacleDetector(Node):
    def __init__(self):
        super().__init__('obstacle_detector')

        self.detection_radius = 50.0  # meters — detect obstacles within 50m
        self.sailboat_x       = 0.0
        self.sailboat_z       = 0.0

        self.obstacle_pub = self.create_publisher(
            PoseArray, '/obstacles', 10)

        self.nearby_pub = self.create_publisher(
            PoseArray, '/obstacles/nearby', 10)

        self.create_subscription(
            PoseArray, '/unity/object_positions',
            self.on_objects, 10)

        self.create_subscription(
            Pose, '/unity/sailboat_pose',
            self.on_sailboat_pose, 10)

        self.get_logger().info(
            f'ObstacleDetector ready! '
            f'Detection radius: {self.detection_radius}m')

    def on_sailboat_pose(self, msg):
        self.sailboat_x = msg.position.x
        self.sailboat_z = msg.position.z

    def on_objects(self, msg):
        all_obstacles  = PoseArray()
        near_obstacles = PoseArray()

        all_obstacles.header  = msg.header
        near_obstacles.header = msg.header

        for pose in msg.poses:
            # All objects are potential obstacles
            all_obstacles.poses.append(pose)

            # Check if within detection radius
            distance = self.calculate_distance(
                pose.position.x,
                pose.position.z
            )

            if distance < self.detection_radius:
                near_obstacles.poses.append(pose)
                self.get_logger().debug(
                    f'Obstacle detected at distance: {distance:.1f}m')

        self.obstacle_pub.publish(all_obstacles)
        self.nearby_pub.publish(near_obstacles)

    def calculate_distance(self, obs_x, obs_z):
        dx = obs_x - self.sailboat_x
        dz = obs_z - self.sailboat_z
        return math.sqrt(dx*dx + dz*dz)


def main(args=None):
    rclpy.init(args=args)
    node = ObstacleDetector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()