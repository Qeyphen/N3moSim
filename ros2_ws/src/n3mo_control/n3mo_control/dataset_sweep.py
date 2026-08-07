#!/usr/bin/env python3
"""Unattended dataset generation: record while driving the boat + randomising weather/traffic,
then stop at a target frame count.

Starts recording, then on timers: sends the boat new random waypoints (so it meets traffic from
many angles), randomises weather/time, and regenerates the scenario (fresh traffic) for variety.
Stops when Unity reports >= --frames (via /dataset/frames), or after a safety timeout.

Prereqs: Unity in Play (or the headless player) connected to the bridge; the boat in AUTO mode
(Scene.json control_mode: "auto") so it follows the waypoints.

  ros2 run n3mo_control dataset_sweep --ros-args -p frames:=10000
"""

import random

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from std_msgs.msg import Bool, Int32
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from std_srvs.srv import Trigger
from n3_new_msgs.msg import TrackArray


class DatasetSweep(Node):
    def __init__(self):
        super().__init__("dataset_sweep")
        self.declare_parameter("frames", 10000)       # stop after this many captured frames
        self.declare_parameter("hz", 10.0)            # assumed capture rate (for the safety timeout)
        self.declare_parameter("waypoint_period", 25.0)
        self.declare_parameter("env_period", 60.0)
        self.declare_parameter("regen_period", 250.0)  # < scenario duration so traffic never dries up
        self.declare_parameter("wp_range", 180.0)      # random waypoint half-range (Unity metres)
        self.declare_parameter("obstacle_bias", 0.6)   # target fraction of waypoints aimed at an obstacle
        self.declare_parameter("min_obstacle_frac", 0.5)  # hard floor: never let obstacle waypoints fall below this

        self.target = int(self.get_parameter("frames").value)
        self.range = float(self.get_parameter("wp_range").value)
        self.bias = float(self.get_parameter("obstacle_bias").value)
        self.min_obs = float(self.get_parameter("min_obstacle_frac").value)
        self.n_wp = 0      # waypoints issued
        self.n_obs = 0     # of those, aimed at an obstacle
        self.frames = 0
        self.seed = 0
        self.rng = random.Random()
        self.tracks = []   # latest obstacle positions as Unity (x, z), from /sim/tracks
        self.map = None    # (data, cols, rows, res, origin_x, origin_z) from /map — keeps waypoints on water

        latched = QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=QoSReliabilityPolicy.RELIABLE)
        self.pub_ctrl = self.create_publisher(Bool, "/dataset/control", latched)
        self.pub_wp = self.create_publisher(PoseStamped, "/agent_01/target_pose", latched)
        self.pub_rand = self.create_publisher(Int32, "/env/randomize", latched)
        self.regen = self.create_client(Trigger, "/sim/generate_scenario")
        self.create_subscription(Int32, "/dataset/frames", self.on_frames, 10)
        self.create_subscription(TrackArray, "/sim/tracks", self.on_tracks, 10)
        self.create_subscription(OccupancyGrid, "/map", self.on_map, latched)

        self.get_logger().info(f"sweep starting — target {self.target} frames. Waiting for traffic...")
        # Recording is deferred until a fresh scenario is up (see startup), so the first frames
        # aren't empty water when the previous scenario has expired.
        self.recording = False
        self.kicked = False
        self.startup_ticks = 0
        self.stopped = False
        self.last_frames = -1
        self.stall_ticks = 0
        self.startup_timer = self.create_timer(2.0, self.startup)

        self.create_timer(float(self.get_parameter("waypoint_period").value), self.send_waypoint)
        self.create_timer(float(self.get_parameter("env_period").value), self.randomise_env)
        self.create_timer(float(self.get_parameter("regen_period").value), self.regenerate)
        self.create_timer(2.0, self.check_done)
        # safety timeout: 1.6x the ideal time so a low rate can't run forever
        self.create_timer(self.target / max(1.0, float(self.get_parameter("hz").value)) * 1.6,
                          self.stop_once)

    def startup(self):
        # Kick a fresh scenario, then start recording once traffic is live (or after ~30s).
        if self.recording:
            return
        self.startup_ticks += 1
        if not self.kicked and self.regen.service_is_ready():
            self.regen.call_async(Trigger.Request())
            self.kicked = True
            self.get_logger().info("kicked a fresh scenario at startup")
        if (self.kicked and self.tracks) or self.startup_ticks >= 15:
            self.recording = True
            self.pub_ctrl.publish(Bool(data=True))   # start recording
            self.get_logger().info(f"traffic ready ({len(self.tracks)} tracks) — recording ON.")
            self.send_waypoint()
            self.startup_timer.cancel()

    def on_frames(self, msg):
        self.frames = msg.data

    def on_tracks(self, msg):
        # Same mapping TrackSpawner uses to place them: Unity (x, z) = ROS (x, y).
        self.tracks = [(t.pose.position.x, t.pose.position.y) for t in msg.tracks]

    def on_map(self, msg):
        self.map = (msg.data, msg.info.width, msg.info.height, msg.info.resolution,
                    msg.info.origin.position.x, msg.info.origin.position.y)
        free = sum(1 for v in msg.data if v == 0)
        self.get_logger().info(f"map {msg.info.width}x{msg.info.height} @ {msg.info.resolution}m, {free} water cells")

    def is_water(self, x, z):
        # 0 = free (water), 100 = occupied (island/obstacle). No map yet -> don't block.
        if self.map is None:
            return True
        data, cols, rows, res, ox, oz = self.map
        col = int((x - ox) / res)
        row = int((z - oz) / res)
        if col < 0 or row < 0 or col >= cols or row >= rows:
            return False   # outside the grid -> not navigable
        return data[row * cols + col] == 0

    def sample_water(self):
        # Rejection-sample a point within range that sits on a water cell (off the island).
        x = z = 0.0
        for _ in range(60):
            x = self.rng.uniform(-self.range, self.range)
            z = self.rng.uniform(-self.range, self.range)
            if self.is_water(x, z):
                return x, z
        return x, z   # give up after 60 tries -> last sample

    def send_waypoint(self):
        # Aim at a real obstacle for `bias` of waypoints so the bow camera faces traffic on the
        # approach; the rest are open water for viewpoint variety. Both are kept on water so the
        # boat never drives onto the island. A running floor (min_obstacle_frac) forces an obstacle
        # whenever the ratio dips, so >= that fraction of the run always drives at objects.
        frac = self.n_obs / self.n_wp if self.n_wp else 0.0
        want_obstacle = self.rng.random() < self.bias or frac < self.min_obs
        self.n_wp += 1

        if self.tracks and want_obstacle:
            tx, tz = self.rng.choice(self.tracks)
            x = tx + self.rng.uniform(-8.0, 8.0)   # small jitter -> obstacle isn't always dead-centre
            z = tz + self.rng.uniform(-8.0, 8.0)
            if not self.is_water(x, z):
                x, z = tx, tz   # jitter hit land -> aim at the track itself (always on water)
            kind = "obstacle"
            self.n_obs += 1
        else:
            x, z = self.sample_water()
            kind = "water"

        p = PoseStamped()
        p.header.frame_id = "map"
        p.pose.position.x = float(x)   # Unity x
        p.pose.position.z = float(z)   # Unity z
        p.pose.orientation.w = 1.0
        self.pub_wp.publish(p)
        self.get_logger().info(
            f"[{self.frames}/{self.target}] -> {kind} ({x:.0f}, {z:.0f}), "
            f"tracks={len(self.tracks)}, obstacle={self.n_obs}/{self.n_wp} ({self.n_obs/self.n_wp:.0%})")

    def randomise_env(self):
        self.seed += 1
        self.pub_rand.publish(Int32(data=self.seed))

    def regenerate(self):
        if self.regen.service_is_ready():
            self.regen.call_async(Trigger.Request())
            self.get_logger().info("regenerated scenario (fresh traffic)")

    def check_done(self):
        if self.frames >= self.target:
            self.stop_once()
            return
        # Stall watchdog: if recording has started but the frame count stops advancing, Unity has
        # probably crashed/closed — don't spin until the safety timeout, stop now.
        if self.recording:
            if self.frames == self.last_frames:
                self.stall_ticks += 1
                if self.stall_ticks >= 20:   # ~40s with no new frames (2s check)
                    self.get_logger().warn(
                        f"no new frames for ~40s at {self.frames} — Unity stopped/crashed. Ending.")
                    self.stop_once()
            else:
                self.stall_ticks = 0
                self.last_frames = self.frames

    def stop_once(self):
        if self.stopped:
            return
        self.stopped = True
        self.pub_ctrl.publish(Bool(data=False))         # stop recording
        self.get_logger().info(f"DONE — {self.frames} frames. Recording OFF. Now run filter_boxes + solo_to_yolo.")
        # let the stop message flush, then exit
        self.create_timer(1.0, lambda: rclpy.shutdown())


def main():
    rclpy.init()
    node = DatasetSweep()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, rclpy.executors.ExternalShutdownException):
        pass
    finally:
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
