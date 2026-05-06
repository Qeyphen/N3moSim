"""
waypoint_publisher.py
=====================
Publishes target waypoints for physics-based vessel navigation.

Given a target position, the boat uses PhysicsController.cs
to move there using real Unity physics — arrive behaviour,
smooth deceleration, stops on arrival. No oscillation.

Modes:
  point    — send boat to one specific world coordinate then stop
  straight — keep sending points ahead, boat cruises indefinitely
  circle   — pre-calculated circle of waypoints
  eight    — figure-8 path
  square   — square path

Subscribes:
  /{object_id}/actual_pose  ← real position from PhysicsController.cs

Publishes:
  /{object_id}/waypoint     → PhysicsController.cs

Usage:
  # send to a specific point and stop
  ros2 run n3mo_control waypoint_publisher --ros-args \
    -p scenario:=point \
    -p target_x:=50.0 \
    -p target_z:=200.0 \
    -p object_id:=sailboat_01

  # cruise in a straight line
  ros2 run n3mo_control waypoint_publisher --ros-args \
    -p scenario:=straight \
    -p object_id:=sailboat_01

  # circle
  ros2 run n3mo_control waypoint_publisher --ros-args \
    -p scenario:=circle \
    -p radius:=50.0 \
    -p object_id:=sailboat_01
"""

import math
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PointStamped, PoseStamped


class WaypointPublisher(Node):
    def __init__(self):
        super().__init__('waypoint_publisher')

        # ── parameters ────────────────────────────────────────
        self.declare_parameter('scenario',       'point')
        self.declare_parameter('object_id',      'sailboat_01')
        self.declare_parameter('water_y',        1.0)
        self.declare_parameter('arrival_radius', 6.0)
        self.declare_parameter('lookahead_dist', 25.0)
        self.declare_parameter('radius',         50.0)
        self.declare_parameter('center_x',       0.0)
        self.declare_parameter('center_z',       0.0)
        self.declare_parameter('num_points',     36)

        # point mode — specific target coordinates
        self.declare_parameter('target_x', 0.0)
        self.declare_parameter('target_z', 200.0)

        self.scenario       = self.get_parameter('scenario').value
        self.object_id      = self.get_parameter('object_id').value
        self.water_y        = self.get_parameter('water_y').value
        self.arrival_radius = self.get_parameter('arrival_radius').value
        self.lookahead_dist = self.get_parameter('lookahead_dist').value
        self.radius         = self.get_parameter('radius').value
        self.center_x       = self.get_parameter('center_x').value
        self.center_z       = self.get_parameter('center_z').value
        self.num_points     = self.get_parameter('num_points').value
        self.target_x       = self.get_parameter('target_x').value
        self.target_z       = self.get_parameter('target_z').value

        # ── vessel state ──────────────────────────────────────
        self.vessel_x       = 0.0
        self.vessel_z       = 0.0
        self.vessel_heading = 0.0
        self.has_position   = False
        self.arrived        = False

        # ── straight line state ───────────────────────────────
        self.waypoint_x = 0.0
        self.waypoint_z = self.lookahead_dist

        # ── indexed waypoints for circle/eight/square ─────────
        self.waypoints   = []
        self.current_idx = 0
        if self.scenario not in ('straight', 'point'):
            self.waypoints = self._build_waypoints()

        # ── ROS2 ─────────────────────────────────────────────
        waypoint_topic = f'/{self.object_id}/waypoint'
        pose_topic     = f'/{self.object_id}/actual_pose'

        self.wp_pub = self.create_publisher(
            PointStamped, waypoint_topic, 10)

        self.create_subscription(
            PoseStamped, pose_topic, self._on_pose, 10)

        self.create_timer(0.1, self._publish_waypoint)

        self.get_logger().info(
            f'WaypointPublisher ready\n'
            f'  scenario       : {self.scenario}\n'
            f'  object         : {self.object_id}\n'
            f'  arrival_radius : {self.arrival_radius}m\n'
            f'  waypoint topic : {waypoint_topic}\n'
            f'  pose topic     : {pose_topic}'
        )

        if self.scenario == 'point':
            self.get_logger().info(
                f'  target         : ({self.target_x}, {self.target_z})'
            )

    # ── receive actual position from Unity ───────────────────────────────────
    def _on_pose(self, msg: PoseStamped):
        self.vessel_x    = msg.pose.position.x
        self.vessel_z    = msg.pose.position.z
        self.has_position = True

        qy = msg.pose.orientation.y
        qw = msg.pose.orientation.w
        self.vessel_heading = 2.0 * math.atan2(qy, qw)

        if self.scenario == 'straight':
            self._advance_straight()
        elif self.scenario not in ('point',):
            self._advance_indexed()
        elif self.scenario == 'point':
            self._check_arrived_at_point()

    # ── point mode: check if arrived ─────────────────────────────────────────
    def _check_arrived_at_point(self):
        dist = math.sqrt(
            (self.vessel_x - self.target_x) ** 2 +
            (self.vessel_z - self.target_z) ** 2
        )
        if dist < self.arrival_radius and not self.arrived:
            self.arrived = True
            self.get_logger().info(
                f'Arrived at target ({self.target_x:.1f}, {self.target_z:.1f}) '
                f'dist={dist:.1f}m'
            )

    # ── straight: keep waypoint ahead of vessel ───────────────────────────────
    def _advance_straight(self):
        dist = math.sqrt(
            (self.vessel_x - self.waypoint_x) ** 2 +
            (self.vessel_z - self.waypoint_z) ** 2
        )
        if dist < self.arrival_radius:
            fwd_x = math.sin(self.vessel_heading)
            fwd_z = math.cos(self.vessel_heading)
            self.waypoint_x = self.vessel_x + fwd_x * self.lookahead_dist
            self.waypoint_z = self.vessel_z + fwd_z * self.lookahead_dist
            self.get_logger().info(
                f'Waypoint advanced → '
                f'({self.waypoint_x:.1f}, {self.waypoint_z:.1f})'
            )

    # ── indexed: advance through pre-built list ───────────────────────────────
    def _advance_indexed(self):
        if not self.waypoints:
            return
        tx, _, tz = self.waypoints[self.current_idx]
        dist = math.sqrt(
            (self.vessel_x - tx) ** 2 +
            (self.vessel_z - tz) ** 2
        )
        if dist < self.arrival_radius:
            prev             = self.current_idx
            self.current_idx = (self.current_idx + 1) % len(self.waypoints)
            self.get_logger().info(
                f'Waypoint {prev} reached (dist={dist:.1f}m) '
                f'→ advancing to {self.current_idx}'
            )

    # ── build waypoints for circle/eight/square ───────────────────────────────
    def _build_waypoints(self):
        points = []

        if self.scenario == 'circle':
            for i in range(self.num_points):
                a = (2 * math.pi * i) / self.num_points
                points.append((
                    self.center_x + self.radius * math.cos(a),
                    self.water_y,
                    self.center_z + self.radius * math.sin(a)
                ))

        elif self.scenario == 'eight':
            for i in range(self.num_points * 2):
                t = (2 * math.pi * i) / (self.num_points * 2)
                points.append((
                    self.center_x + self.radius * math.sin(t),
                    self.water_y,
                    self.center_z + self.radius * math.sin(t) * math.cos(t)
                ))

        elif self.scenario == 'square':
            half = self.radius
            for cx, cz in [
                ( half, -half),
                ( half,  half),
                (-half,  half),
                (-half, -half),
            ]:
                points.append((
                    self.center_x + cx,
                    self.water_y,
                    self.center_z + cz
                ))

        self.get_logger().info(
            f'Built {len(points)} waypoints for {self.scenario}')
        return points

    # ── publish current waypoint at 10Hz ─────────────────────────────────────
    def _publish_waypoint(self):

        if self.scenario == 'point':
            # always publish the fixed target
            # PhysicsController arrive behaviour handles the stop
            wx, wz = self.target_x, self.target_z

        elif self.scenario == 'straight':
            if self.has_position:
                # recalculate every cycle based on actual vessel position
                # waypoint always stays lookahead_dist ahead of the vessel
                fwd_x = math.sin(self.vessel_heading)
                fwd_z = math.cos(self.vessel_heading)
                wx    = self.vessel_x + fwd_x * self.lookahead_dist
                wz    = self.vessel_z + fwd_z * self.lookahead_dist
            else:
                wx, wz = self.waypoint_x, self.waypoint_z

        else:
            if not self.waypoints:
                return
            wx, _, wz = self.waypoints[self.current_idx]

        msg                 = PointStamped()
        msg.header.stamp    = self.get_clock().now().to_msg()
        msg.header.frame_id = 'world'
        msg.point.x         = float(wx)
        msg.point.y         = float(self.water_y)
        msg.point.z         = float(wz)
        self.wp_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = WaypointPublisher()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()