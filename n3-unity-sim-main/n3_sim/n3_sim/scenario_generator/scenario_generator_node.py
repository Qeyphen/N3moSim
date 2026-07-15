"""Scenario generator node — publishes simulated TrackArray from a YAML scenario."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path

import n3_common.ros as ros
import rclpy
from n3_common.topics.sim_topics import COSTMAP_STATIC, SIM_TRACKS
from rclpy.node import Node
from std_srvs.srv import Trigger

from .scenario_generator_params import ScenarioGeneratorParams
from .scenario_model import (
    TRACK_TYPE_TABLE,
    Scenario,
    TrackDef,
    TrackState,
    TrackWaypoint,
    extract_navigable_area,
    generate_scenario,
    interpolate_track,
    load_scenario,
    save_scenario,
)


def _track_state_to_ros(state: TrackState) -> ros.Track:
    """Convert internal TrackState to a ROS Track message."""
    q_z = math.sin(state.heading_rad / 2.0)
    q_w = math.cos(state.heading_rad / 2.0)
    return ros.Track(
        id=state.id,
        pose=ros.Pose(
            position=ros.Point(x=float(state.x), y=float(state.y), z=float(state.z)),
            orientation=ros.Quaternion(x=0.0, y=0.0, z=q_z, w=q_w),
        ),
        twist=ros.Twist(
            linear=ros.Vector3(x=float(state.vx), y=float(state.vy), z=0.0),
        ),
        type=state.type_value,
    )


class ScenarioGeneratorNode(Node):
    def __init__(self) -> None:
        super().__init__("scenario_generator_node", enable_logger_service=True)

        self.params = ScenarioGeneratorParams(self)
        p = self.params.p

        self.scenario: Scenario | None = None
        self.start_time = self.get_clock().now()
        self.costmap_msg: ros.OccupancyGrid | None = None

        # Injected tracks (added at runtime via MCP bridge)
        self.injected_tracks: list[TrackDef] = []
        self.next_injected_id = 1000

        # Publishers
        self.tracks_pub = self.create_publisher(
            ros.TrackArray,
            SIM_TRACKS.name,
            SIM_TRACKS.qos,
        )

        # Subscriptions
        self.create_subscription(
            ros.OccupancyGrid,
            COSTMAP_STATIC.name,
            self.on_costmap,
            COSTMAP_STATIC.qos,
        )

        # Services
        self.create_service(
            Trigger, "/sim/generate_scenario", self.on_generate_scenario
        )
        self.create_service(
            ros.ScenarioCommand, "/sim/scenario/command", self.on_scenario_command
        )

        # Timer
        self.timer = self.create_timer(1.0 / p.publish_rate_hz, self.on_timer)

        # Load scenario if path provided
        self.log = self.get_logger()
        if p.scenario_file:
            self._load_scenario(p.scenario_file)

        self.log.info("ScenarioGeneratorNode ready")

    def _load_scenario(self, path: str) -> bool:
        try:
            self.scenario = load_scenario(path)
            self.start_time = self.get_clock().now()
            self.log.info(
                f"Loaded scenario '{self.scenario.name}' — "
                f"{len(self.scenario.tracks)} tracks, {self.scenario.duration_s}s"
            )
            return True
        except Exception as e:
            self.log.error(f"Failed to load scenario '{path}': {e}")
            return False

    def on_costmap(self, msg: ros.OccupancyGrid) -> None:
        self.costmap_msg = msg
        self.log.info(
            f"Received costmap: {msg.info.width}x{msg.info.height}, "
            f"resolution={msg.info.resolution}m"
        )

    def on_generate_scenario(
        self,
        _request: Trigger.Request,
        response: Trigger.Response,
    ) -> Trigger.Response:
        p = self.params.p

        if self.costmap_msg is None:
            response.success = False
            response.message = "No costmap received yet on " + COSTMAP_STATIC.name
            return response

        base_path = Path(p.gen_output_file)
        suffix = datetime.now().strftime("_%Y_%m_%d__%H:%M")
        output_path = base_path.with_name(
            base_path.stem + suffix + base_path.suffix
        )

        info = self.costmap_msg.info
        nav_area = extract_navigable_area(
            data=list(self.costmap_msg.data),
            width=info.width,
            height=info.height,
            resolution=info.resolution,
            origin_x=info.origin.position.x,
            origin_y=info.origin.position.y,
            margin_m=p.gen_margin_m,
        )

        scenario = generate_scenario(
            nav_area,
            duration_s=p.gen_duration_s,
            track_count=p.gen_track_count,
            density=p.gen_density,
            area_type=p.gen_area_type,
            type_names=[],  # TODO: expose as string[] param if needed
            type_weights=[],
            min_speed_kts=p.gen_min_speed_kts,
            max_speed_kts=p.gen_max_speed_kts,
            min_waypoints=p.gen_min_waypoints,
            max_waypoints=p.gen_max_waypoints,
            spawn_spread_s=p.gen_spawn_spread_s,
            seed=p.gen_random_seed,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        save_scenario(scenario, output_path)
        self.log.info(
            f"Generated scenario '{scenario.name}' — "
            f"{len(scenario.tracks)} tracks → {output_path}"
        )

        if p.gen_autostart:
            self._load_scenario(str(output_path))

        response.success = True
        response.message = str(output_path)
        return response

    def on_timer(self) -> None:
        now = self.get_clock().now()
        elapsed = (now - self.start_time).nanoseconds * 1e-9

        active_tracks: list[ros.Track] = []

        # Scenario tracks (from YAML)
        if self.scenario is not None:
            if elapsed > self.scenario.duration_s:
                if self.params.p.loop:
                    self.start_time = now
                    elapsed = 0.0
                else:
                    elapsed = self.scenario.duration_s

            for track_def in self.scenario.tracks:
                state = interpolate_track(track_def, elapsed)
                if state is not None:
                    active_tracks.append(_track_state_to_ros(state))

        # Injected tracks (from MCP bridge)
        for track_def in self.injected_tracks:
            state = interpolate_track(track_def, elapsed)
            if state is not None:
                active_tracks.append(_track_state_to_ros(state))

        if not active_tracks and self.scenario is None:
            return

        msg = ros.TrackArray(
            header=ros.Header(stamp=now.to_msg(), frame_id="map"),
            tracks=active_tracks,
        )
        self.tracks_pub.publish(msg)

    # ------------------------------------------------------------------
    # Scenario command service (JSON-based, used by MCP bridge)
    # ------------------------------------------------------------------

    def on_scenario_command(
        self,
        request: ros.ScenarioCommand.Request,
        response: ros.ScenarioCommand.Response,
    ) -> ros.ScenarioCommand.Response:
        try:
            req = json.loads(request.json_request)
        except json.JSONDecodeError as e:
            response.success = False
            response.json_response = json.dumps({"error": f"Invalid JSON: {e}"})
            return response

        cmd = req.get("cmd")
        if cmd == "add_track":
            return self._cmd_add_track(req, response)
        if cmd == "remove_track":
            return self._cmd_remove_track(req, response)
        if cmd == "list_tracks":
            return self._cmd_list_tracks(response)
        if cmd == "clear_tracks":
            return self._cmd_clear_tracks(response)

        response.success = False
        response.json_response = json.dumps({"error": f"Unknown command: {cmd}"})
        return response

    def _cmd_add_track(
        self,
        req: dict,
        response: ros.ScenarioCommand.Response,
    ) -> ros.ScenarioCommand.Response:
        type_name = req.get("type_name", "unknown")
        type_info = TRACK_TYPE_TABLE.get(type_name, TRACK_TYPE_TABLE["unknown"])

        waypoints_raw = req.get("waypoints", [])
        if not waypoints_raw:
            response.success = False
            response.json_response = json.dumps({"error": "No waypoints provided"})
            return response

        waypoints = [
            TrackWaypoint(x=w["x"], y=w["y"], speed_kts=w.get("speed_kts", 3.0))
            for w in waypoints_raw
        ]

        elapsed = (self.get_clock().now() - self.start_time).nanoseconds * 1e-9
        track_id = self.next_injected_id
        self.next_injected_id += 1

        track = TrackDef(
            id=track_id,
            type_name=type_name,
            type_value=type_info[0],
            spawn_time_s=elapsed,
            despawn_time_s=elapsed + req.get("duration_s", 600.0),
            waypoints=waypoints,
            heading_mode=req.get("heading_mode", "tangent"),
        )
        self.injected_tracks.append(track)
        self.log.info(f"Injected track {track_id} ({type_name})")

        response.success = True
        response.json_response = json.dumps({"id": track_id, "type": type_name})
        return response

    def _cmd_remove_track(
        self,
        req: dict,
        response: ros.ScenarioCommand.Response,
    ) -> ros.ScenarioCommand.Response:
        track_id = req.get("id")
        before = len(self.injected_tracks)
        self.injected_tracks = [t for t in self.injected_tracks if t.id != track_id]
        removed = before - len(self.injected_tracks)

        response.success = removed > 0
        response.json_response = json.dumps({"removed": removed, "id": track_id})
        if removed:
            self.log.info(f"Removed injected track {track_id}")
        return response

    def _cmd_list_tracks(
        self,
        response: ros.ScenarioCommand.Response,
    ) -> ros.ScenarioCommand.Response:
        tracks = [
            {
                "id": t.id,
                "type": t.type_name,
                "waypoints": [
                    {"x": w.x, "y": w.y, "speed_kts": w.speed_kts} for w in t.waypoints
                ],
                "spawn_time_s": t.spawn_time_s,
                "despawn_time_s": t.despawn_time_s,
            }
            for t in self.injected_tracks
        ]
        response.success = True
        response.json_response = json.dumps({"tracks": tracks})
        return response

    def _cmd_clear_tracks(
        self,
        response: ros.ScenarioCommand.Response,
    ) -> ros.ScenarioCommand.Response:
        count = len(self.injected_tracks)
        self.injected_tracks.clear()
        self.log.info(f"Cleared {count} injected tracks")
        response.success = True
        response.json_response = json.dumps({"cleared": count})
        return response


def main() -> None:
    rclpy.init()
    node = ScenarioGeneratorNode()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
