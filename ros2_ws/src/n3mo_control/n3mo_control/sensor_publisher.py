"""
sensor_publisher.py
===================
Publishes simulated sensor data from Unity to ROS2.
Receives object positions and state from Unity via ROS TCP Bridge.
Publishes standard ROS2 sensor messages for use by mission planner.

Topics published:
  /sailboat/gps          → sensor_msgs/NavSatFix
  /sailboat/imu          → sensor_msgs/Imu
  /environment/wind      → geometry_msgs/Vector3
  /unity/object_positions → geometry_msgs/PoseArray

Topics subscribed (from Unity via ROS TCP Bridge):
  /unity/sailboat_pose   ← Unity boat position
  /unity/wind_data       ← Unity wind data
"""

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import NavSatFix, Imu
from geometry_msgs.msg import Vector3, PoseArray, Pose
from std_msgs.msg import Float32


class SensorPublisher(Node):
    def __init__(self):
        super().__init__('sensor_publisher')

        # Publishers → ROS2 network
        self.gps_pub  = self.create_publisher(
            NavSatFix, '/sailboat/gps', 10)

        self.imu_pub  = self.create_publisher(
            Imu, '/sailboat/imu', 10)

        self.wind_pub = self.create_publisher(
            Vector3, '/environment/wind', 10)

        self.objects_pub = self.create_publisher(
            PoseArray, '/unity/object_positions', 10)

        # Subscribers ← Unity via ROS TCP Bridge
        # These will be populated once Unity starts sending data
        self.create_subscription(
            Pose, '/unity/sailboat_pose',
            self.on_sailboat_pose, 10)

        self.create_subscription(
            Vector3, '/unity/wind_data',
            self.on_wind_data, 10)

        self.sailboat_x   = 0.0
        self.sailboat_y   = 0.0
        self.sailboat_z   = 0.0
        self.wind_speed   = 0.0
        self.wind_dir_x   = 0.0
        self.wind_dir_z   = 0.0

        # Publish at 10Hz
        self.timer = self.create_timer(0.1, self.publish_all)
        self.get_logger().info('SensorPublisher ready!')

    def on_sailboat_pose(self, msg):
        self.sailboat_x = msg.position.x
        self.sailboat_y = msg.position.y
        self.sailboat_z = msg.position.z

    def on_wind_data(self, msg):
        self.wind_speed = msg.y
        self.wind_dir_x = msg.x
        self.wind_dir_z = msg.z

    def publish_all(self):
        self.publish_gps()
        self.publish_imu()
        self.publish_wind()

    def publish_gps(self):
        msg             = NavSatFix()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'sailboat'

        # Convert Unity world position to GPS coordinates
        # Origin: 48.3833° N, 4.4833° W (Brest, France)
        origin_lat = 48.3833
        origin_lon = -4.4833
        scale      = 0.00001  # meters to degrees

        msg.latitude  = origin_lat + (self.sailboat_z * scale)
        msg.longitude = origin_lon + (self.sailboat_x * scale)
        msg.altitude  = self.sailboat_y

        msg.status.status = 0  # GPS fix
        self.gps_pub.publish(msg)

    def publish_imu(self):
        msg = Imu()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = 'sailboat'
        # Will be populated with real orientation from Unity
        self.imu_pub.publish(msg)

    def publish_wind(self):
        msg   = Vector3()
        msg.x = self.wind_dir_x
        msg.y = self.wind_speed
        msg.z = self.wind_dir_z
        self.wind_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = SensorPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()