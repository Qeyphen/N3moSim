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

import math
import random
from collections import deque
from dataclasses import dataclass

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, QoSDurabilityPolicy, QoSReliabilityPolicy
from std_msgs.msg import Bool, Int32
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import OccupancyGrid
from std_srvs.srv import Trigger
from n3_new_msgs.msg import TrackArray


@dataclass
class DynamicTrack:
    x: float
    z: float
    radius_m: float


class DatasetSweep(Node):
    def __init__(self):
        super().__init__("dataset_sweep")
        self.declare_parameter("frames", 10000)       # stop after this many captured frames
        self.declare_parameter("hz", 10.0)            # assumed capture rate (for the safety timeout)
        self.declare_parameter("waypoint_period", 25.0)
        self.declare_parameter("env_period", 60.0)
        self.declare_parameter("regen_period", 250.0)  # < scenario duration so traffic never dries up
        self.declare_parameter("duration_s", 0.0)      # >0 => stop after this wall-clock duration instead of frame target
        self.declare_parameter("wp_range", 180.0)      # random waypoint half-range (Unity metres)
        self.declare_parameter("obstacle_bias", 0.6)   # target fraction of waypoints aimed at an obstacle
        self.declare_parameter("min_obstacle_frac", 0.5)  # hard floor: never let obstacle waypoints fall below this
        self.declare_parameter("randomize_env_on_start", False)
        self.declare_parameter("randomize_env_during_run", True)
        self.declare_parameter("regenerate_on_start", True)
        self.declare_parameter("regenerate_during_run", True)
        self.declare_parameter("record_start_delay_s", 2.0)
        self.declare_parameter("min_static_clearance_m", 6.0)
        self.declare_parameter("min_dynamic_clearance_m", 8.0)
        self.declare_parameter("arrival_clearance_m", 3.0)
        self.declare_parameter("path_sample_step_m", 2.0)
        self.declare_parameter("obstacle_target_jitter_m", 8.0)
        self.declare_parameter("recovery_wp_range", 90.0)
        self.declare_parameter("stuck_timeout_s", 18.0)
        self.declare_parameter("stuck_speed_mps", 0.35)
        self.declare_parameter("progress_timeout_s", 14.0)
        self.declare_parameter("min_progress_m", 4.0)
        self.declare_parameter("max_target_samples", 90)

        self.target = int(self.get_parameter("frames").value)
        self.duration_s = float(self.get_parameter("duration_s").value)
        self.range = float(self.get_parameter("wp_range").value)
        self.bias = float(self.get_parameter("obstacle_bias").value)
        self.min_obs = float(self.get_parameter("min_obstacle_frac").value)
        self.randomize_env_on_start = bool(self.get_parameter("randomize_env_on_start").value)
        self.randomize_env_during_run = bool(self.get_parameter("randomize_env_during_run").value)
        self.regenerate_on_start = bool(self.get_parameter("regenerate_on_start").value)
        self.regenerate_during_run = bool(self.get_parameter("regenerate_during_run").value)
        self.record_start_delay_s = max(0.0, float(self.get_parameter("record_start_delay_s").value))
        self.min_static_clearance = float(self.get_parameter("min_static_clearance_m").value)
        self.min_dynamic_clearance = float(self.get_parameter("min_dynamic_clearance_m").value)
        self.arrival_clearance = float(self.get_parameter("arrival_clearance_m").value)
        self.path_sample_step = max(0.5, float(self.get_parameter("path_sample_step_m").value))
        self.obstacle_target_jitter = float(self.get_parameter("obstacle_target_jitter_m").value)
        self.recovery_range = float(self.get_parameter("recovery_wp_range").value)
        self.stuck_timeout = float(self.get_parameter("stuck_timeout_s").value)
        self.stuck_speed = float(self.get_parameter("stuck_speed_mps").value)
        self.progress_timeout = float(self.get_parameter("progress_timeout_s").value)
        self.min_progress = float(self.get_parameter("min_progress_m").value)
        self.max_target_samples = int(self.get_parameter("max_target_samples").value)
        self.n_wp = 0      # waypoints issued
        self.n_obs = 0     # of those, aimed at an obstacle
        self.frames = 0
        self.seed = 0
        self.rng = random.Random()
        self.tracks = []   # latest obstacle positions as Unity (x, z), from /sim/tracks
        self.map = None    # (data, cols, rows, res, origin_x, origin_z) from /map — keeps waypoints on water
        self.ego_pose = None
        self.current_target = None
        self.current_target_kind = None
        self.current_target_sent_time = None
        self.target_start_pose = None
        self.last_progress_log_time = None
        self.pose_history = deque()

        latched = QoSProfile(depth=1, durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
                             reliability=QoSReliabilityPolicy.RELIABLE)
        self.pub_ctrl = self.create_publisher(Bool, "/dataset/control", latched)
        self.pub_wp = self.create_publisher(PoseStamped, "/ego_boat/target_pose", latched)
        self.pub_rand = self.create_publisher(Int32, "/env/randomize", latched)
        self.regen = self.create_client(Trigger, "/sim/generate_scenario")
        self.create_subscription(Int32, "/dataset/frames", self.on_frames, 10)
        self.create_subscription(TrackArray, "/sim/tracks", self.on_tracks, 10)
        self.create_subscription(OccupancyGrid, "/map/costmap_static", self.on_map, latched)
        self.create_subscription(PoseStamped, "/sim/boat/pose", self.on_ego_pose, 10)

        self.get_logger().info(f"sweep starting — target {self.target} frames. Waiting for traffic...")
        # Recording is deferred until a fresh scenario is up (see startup), so the first frames
        # aren't empty water when the previous scenario has expired.
        self.recording = False
        self.kicked = False
        self.startup_ticks = 0
        self.stopped = False
        self.last_frames = -1
        self.stall_ticks = 0
        self.recording_started_at = None
        self.delayed_start_timer = None
        self.startup_timer = self.create_timer(2.0, self.startup)

        self.create_timer(float(self.get_parameter("waypoint_period").value), self.send_waypoint)
        if self.randomize_env_during_run and float(self.get_parameter("env_period").value) > 0.0:
            self.create_timer(float(self.get_parameter("env_period").value), self.randomise_env)
        if self.regenerate_during_run and float(self.get_parameter("regen_period").value) > 0.0:
            self.create_timer(float(self.get_parameter("regen_period").value), self.regenerate)
        self.create_timer(2.0, self.check_done)
        # safety timeout: 1.6x the ideal time so a low rate can't run forever
        safety_timeout = self.target / max(1.0, float(self.get_parameter("hz").value)) * 1.6
        if self.duration_s > 0.0:
            safety_timeout = max(safety_timeout, self.duration_s * 2.0)
        self.create_timer(safety_timeout, self.stop_once)

    def startup(self):
        # Kick a fresh scenario, then start recording once traffic is live (or after ~30s).
        if self.recording:
            return
        self.startup_ticks += 1
        if self.randomize_env_on_start and self.seed == 0:
            self.randomise_env()
        if self.regenerate_on_start and not self.kicked and self.regen.service_is_ready():
            self.regen.call_async(Trigger.Request())
            self.kicked = True
            self.get_logger().info("kicked a fresh scenario at startup")
        ready_for_record = self.startup_ticks >= 15
        if self.regenerate_on_start:
            ready_for_record = (self.kicked and self.tracks) or self.startup_ticks >= 15
        if ready_for_record:
            self.recording = True
            if self.record_start_delay_s > 0.0:
                self.get_logger().info(f"waiting {self.record_start_delay_s:.1f}s before recording start")
                self.delayed_start_timer = self.create_timer(
                    self.record_start_delay_s, self.start_recording_once
                )
            else:
                self.start_recording_once()
            self.startup_timer.cancel()

    def start_recording_once(self):
        if not self.recording or self.recording_started_at is not None:
            return
        if self.delayed_start_timer is not None:
            self.delayed_start_timer.cancel()
            self.delayed_start_timer = None
        self.recording_started_at = self.now_sec()
        self.pub_ctrl.publish(Bool(data=True))   # start recording
        scenario_desc = (
            f"{self.duration_s:.1f}s"
            if self.duration_s > 0.0
            else f"{self.target} frames"
        )
        self.get_logger().info(
            f"traffic ready ({len(self.tracks)} tracks) — recording ON for {scenario_desc}."
        )
        self.send_waypoint()

    def on_frames(self, msg):
        self.frames = msg.data

    def on_tracks(self, msg):
        # Same mapping TrackSpawner uses to place them: Unity (x, z) = ROS (x, y).
        self.tracks = [
            DynamicTrack(
                x=float(t.pose.position.x),
                z=float(t.pose.position.y),
                radius_m=self.track_clearance_radius(t.type),
            )
            for t in msg.tracks
        ]

    def on_map(self, msg):
        self.map = (msg.data, msg.info.width, msg.info.height, msg.info.resolution,
                    msg.info.origin.position.x, msg.info.origin.position.y)
        free = sum(1 for v in msg.data if v == 0)
        self.get_logger().info(f"map {msg.info.width}x{msg.info.height} @ {msg.info.resolution}m, {free} water cells")

    def on_ego_pose(self, msg):
        x = float(msg.pose.position.x)
        z = float(msg.pose.position.y)
        now = self.now_sec()
        self.ego_pose = (x, z)
        self.pose_history.append((now, x, z))
        cutoff = now - max(self.stuck_timeout, self.progress_timeout) - 2.0
        while self.pose_history and self.pose_history[0][0] < cutoff:
            self.pose_history.popleft()

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

    def now_sec(self):
        return self.get_clock().now().nanoseconds * 1e-9

    @staticmethod
    def dist(a, b):
        return math.hypot(a[0] - b[0], a[1] - b[1])

    def track_clearance_radius(self, track_type):
        # Approximate half-extents based on the visual marker sizes in n3_sim.
        radii = {
            1: 6.0,   # sailboat
            2: 4.0,   # motorboat
            3: 2.0,   # jetski
            4: 2.5,   # kayak
            5: 2.0,   # paddleboard
            6: 1.0,   # swimmer
            7: 3.0,   # dinghy
            8: 5.0,   # fishing boat
            9: 10.0,  # ferry
            10: 20.0, # cargo
            11: 1.5,  # buoy
            12: 1.5,  # debris
            13: 2.0,  # windsurf
            14: 2.0,  # kitesurf
            15: 2.0,  # pedalo
        }
        return radii.get(int(track_type), 2.0)

    def nearest_dynamic_gap(self, x, z):
        if not self.tracks:
            return float("inf")
        return min(math.hypot(x - t.x, z - t.z) - t.radius_m for t in self.tracks)

    def static_clearance_ok(self, x, z, clearance_m):
        if self.map is None:
            return True
        _, _, _, res, _, _ = self.map
        radius_cells = max(0, int(math.ceil(clearance_m / max(res, 1e-6))))
        data, cols, rows, _, ox, oz = self.map
        col = int((x - ox) / res)
        row = int((z - oz) / res)
        if col < 0 or row < 0 or col >= cols or row >= rows:
            return False
        for dc in range(-radius_cells, radius_cells + 1):
            for dr in range(-radius_cells, radius_cells + 1):
                nc = col + dc
                nr = row + dr
                if nc < 0 or nr < 0 or nc >= cols or nr >= rows:
                    return False
                if data[nr * cols + nc] != 0:
                    wx = ox + (nc + 0.5) * res
                    wz = oz + (nr + 0.5) * res
                    if math.hypot(x - wx, z - wz) <= clearance_m:
                        return False
        return True

    def dynamic_clearance_ok(self, x, z, clearance_m):
        if not self.tracks:
            return True
        for track in self.tracks:
            if math.hypot(x - track.x, z - track.z) < clearance_m + track.radius_m:
                return False
        return True

    def target_is_safe(self, x, z, static_clearance=None, dynamic_clearance=None):
        static_clearance = self.min_static_clearance if static_clearance is None else static_clearance
        dynamic_clearance = self.min_dynamic_clearance if dynamic_clearance is None else dynamic_clearance
        return (
            self.is_water(x, z)
            and self.static_clearance_ok(x, z, static_clearance)
            and self.dynamic_clearance_ok(x, z, dynamic_clearance)
        )

    def path_is_clear(self, start, goal, static_clearance=None, dynamic_clearance=None):
        static_clearance = self.min_static_clearance if static_clearance is None else static_clearance
        dynamic_clearance = self.min_dynamic_clearance if dynamic_clearance is None else dynamic_clearance
        distance = self.dist(start, goal)
        steps = max(1, int(math.ceil(distance / self.path_sample_step)))
        for i in range(steps + 1):
            alpha = i / steps
            x = start[0] + (goal[0] - start[0]) * alpha
            z = start[1] + (goal[1] - start[1]) * alpha
            if not self.target_is_safe(x, z, static_clearance, dynamic_clearance):
                return False
        return True

    def sample_safe_water(self, sample_range=None, static_clearance=None, dynamic_clearance=None):
        sample_range = self.range if sample_range is None else sample_range
        static_clearance = self.min_static_clearance if static_clearance is None else static_clearance
        dynamic_clearance = self.min_dynamic_clearance if dynamic_clearance is None else dynamic_clearance
        start = self.ego_pose
        last_candidate = None
        for _ in range(self.max_target_samples):
            x = self.rng.uniform(-sample_range, sample_range)
            z = self.rng.uniform(-sample_range, sample_range)
            last_candidate = (x, z)
            if not self.target_is_safe(x, z, static_clearance, dynamic_clearance):
                continue
            if start is not None and not self.path_is_clear(start, (x, z), static_clearance, dynamic_clearance):
                continue
            return x, z
        return last_candidate

    def sample_safe_obstacle_target(self):
        if not self.tracks:
            return None
        start = self.ego_pose
        for _ in range(self.max_target_samples):
            track = self.rng.choice(self.tracks)
            angle = self.rng.uniform(0.0, 2.0 * math.pi)
            radius = self.rng.uniform(
                self.arrival_clearance + track.radius_m + 1.0,
                self.arrival_clearance + track.radius_m + self.obstacle_target_jitter,
            )
            x = track.x + math.cos(angle) * radius
            z = track.z + math.sin(angle) * radius
            if not self.target_is_safe(x, z):
                continue
            if start is not None and not self.path_is_clear(start, (x, z)):
                continue
            return x, z
        return None

    def should_issue_new_waypoint(self):
        if self.current_target is None or self.ego_pose is None:
            return True, "no_active_target"
        dist_to_target = self.dist(self.ego_pose, self.current_target)
        if dist_to_target <= self.arrival_clearance:
            return True, "target_reached"
        if not self.target_is_safe(*self.current_target):
            return True, "target_invalidated"
        if self.is_stuck():
            return True, "stuck_recovery"
        return False, None

    def is_stuck(self):
        if self.ego_pose is None or self.current_target is None or not self.pose_history:
            return False
        now = self.now_sec()
        recent = [p for p in self.pose_history if p[0] >= now - self.stuck_timeout]
        if len(recent) >= 2:
            moved = math.hypot(recent[-1][1] - recent[0][1], recent[-1][2] - recent[0][2])
            avg_speed = moved / max(recent[-1][0] - recent[0][0], 1e-6)
            if avg_speed < self.stuck_speed:
                return True
        if self.target_start_pose is not None and self.current_target_sent_time is not None:
            age = now - self.current_target_sent_time
            if age >= self.progress_timeout:
                progress = self.dist(self.target_start_pose, self.ego_pose)
                if progress < self.min_progress:
                    return True
        return False

    def issue_waypoint(self, x, z, kind, reason):
        p = PoseStamped()
        p.header.frame_id = "map"
        p.pose.position.x = float(x)   # Unity x
        p.pose.position.z = float(z)   # Unity z
        p.pose.orientation.w = 1.0
        self.pub_wp.publish(p)
        self.current_target = (x, z)
        self.current_target_kind = kind
        self.current_target_sent_time = self.now_sec()
        self.target_start_pose = self.ego_pose
        if kind == "obstacle":
            self.n_obs += 1
        self.get_logger().info(
            f"[{self.frames}/{self.target}] -> {kind} ({x:.0f}, {z:.0f}) reason={reason}, "
            f"tracks={len(self.tracks)}, obstacle={self.n_obs}/{self.n_wp} "
            f"({self.n_obs / max(self.n_wp, 1):.0%})"
        )

    def send_waypoint(self):
        # Aim at a real obstacle for `bias` of waypoints so the bow camera faces traffic on the
        # approach; the rest are open water for viewpoint variety. Both are now filtered by static
        # and dynamic clearance, and straight-line path validity from the ego pose.
        if not self.recording:
            return
        should_send, reason = self.should_issue_new_waypoint()
        if not should_send:
            return

        frac = self.n_obs / self.n_wp if self.n_wp else 0.0
        want_obstacle = self.rng.random() < self.bias or frac < self.min_obs
        self.n_wp += 1

        if reason == "stuck_recovery":
            candidate = self.sample_safe_water(
                sample_range=self.recovery_range,
                static_clearance=self.min_static_clearance + 1.0,
                dynamic_clearance=self.min_dynamic_clearance + 1.0,
            )
            kind = "recovery"
        elif self.tracks and want_obstacle:
            candidate = self.sample_safe_obstacle_target()
            kind = "obstacle"
        else:
            candidate = self.sample_safe_water()
            kind = "water"

        if candidate is None or not self.target_is_safe(*candidate):
            fallback = self.sample_safe_water(
                sample_range=self.recovery_range if reason == "stuck_recovery" else self.range
            )
            candidate = fallback
            kind = "recovery" if reason == "stuck_recovery" else "water"

        if candidate is None or not self.target_is_safe(*candidate):
            self.get_logger().warn(
                f"[{self.frames}/{self.target}] no safe waypoint found for reason={reason}; "
                "keeping current target."
            )
            return

        x, z = candidate
        self.issue_waypoint(x, z, kind, reason)

    def randomise_env(self):
        self.seed += 1
        self.pub_rand.publish(Int32(data=self.seed))

    def regenerate(self):
        if self.regen.service_is_ready():
            self.regen.call_async(Trigger.Request())
            self.get_logger().info("regenerated scenario (fresh traffic)")

    def check_done(self):
        if self.duration_s > 0.0 and self.recording_started_at is not None:
            if self.now_sec() - self.recording_started_at >= self.duration_s:
                self.stop_once()
                return
        elif self.frames >= self.target:
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
            if self.recording:
                self.send_waypoint()

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
