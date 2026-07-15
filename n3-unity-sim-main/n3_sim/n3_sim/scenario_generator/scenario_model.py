"""Scenario model — track interpolation and procedural generation.

Pure Python, no ROS dependency. Easily testable outside the container.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from n3_common.n3_const import DEG2RAD, KTS_TO_MS

# Track type name → (enum value, default speed range kts, heading sigma deg)
TRACK_TYPE_TABLE: dict[str, tuple[int, float, float, float]] = {
    # name: (enum_value, min_speed_kts, max_speed_kts, heading_sigma_deg)
    "unknown": (0, 0.0, 0.0, 0.0),
    "sailboat": (1, 3.0, 8.0, 15.0),
    "motorboat": (2, 10.0, 30.0, 25.0),
    "jetski": (3, 20.0, 45.0, 45.0),
    "kayak": (4, 2.0, 5.0, 20.0),
    "paddleboard": (5, 1.0, 3.0, 10.0),
    "swimmer": (6, 0.5, 1.5, 30.0),
    "dinghy": (7, 1.0, 5.0, 20.0),
    "fishing_boat": (8, 5.0, 15.0, 15.0),
    "ferry": (9, 8.0, 20.0, 5.0),
    "cargo": (10, 8.0, 15.0, 3.0),
    "buoy": (11, 0.0, 0.0, 0.0),
    "debris": (12, 0.0, 0.5, 0.0),
    "windsurf": (13, 5.0, 25.0, 20.0),
    "kitesurf": (14, 10.0, 30.0, 25.0),
    "pedalo": (15, 1.0, 3.0, 15.0),
}

AREA_PRESETS: dict[str, list[tuple[str, float]]] = {
    "lake": [
        ("sailboat", 5.0),
        ("kayak", 3.0),
        ("paddleboard", 2.0),
        ("swimmer", 2.0),
        ("pedalo", 2.0),
    ],
    "coastal": [
        ("sailboat", 5.0),
        ("motorboat", 3.0),
        ("jetski", 2.0),
        ("fishing_boat", 2.0),
        ("windsurf", 1.0),
    ],
    "harbor": [
        ("motorboat", 4.0),
        ("dinghy", 3.0),
        ("ferry", 2.0),
        ("cargo", 1.0),
    ],
    "open_sea": [
        ("sailboat", 4.0),
        ("cargo", 3.0),
        ("ferry", 2.0),
        ("fishing_boat", 2.0),
    ],
}


@dataclass
class TrackWaypoint:
    x: float  # ENU meters
    y: float  # ENU meters
    speed_kts: float


@dataclass
class TrackDef:
    id: int
    type_name: str
    type_value: int
    spawn_time_s: float
    despawn_time_s: float
    waypoints: list[TrackWaypoint]
    heading_mode: str = "tangent"  # tangent | fixed | cog


@dataclass
class TrackState:
    """Interpolated state of a track at a given time."""

    id: int
    type_value: int
    x: float
    y: float
    z: float
    heading_rad: float  # ENU yaw, radians
    vx: float  # m/s
    vy: float  # m/s


@dataclass
class Scenario:
    name: str
    duration_s: float
    tracks: list[TrackDef] = field(default_factory=list)


def load_scenario(path: str | Path) -> Scenario:
    """Load a scenario from a YAML file."""
    data = yaml.safe_load(Path(path).read_text())
    sc = data["scenario"]
    tracks: list[TrackDef] = []
    for t in sc.get("tracks", []):
        type_name = t["type"]
        type_info = TRACK_TYPE_TABLE.get(type_name, TRACK_TYPE_TABLE["unknown"])
        wps = [
            TrackWaypoint(
                x=float(w["x"]), y=float(w["y"]), speed_kts=float(w.get("speed_kts", 3.0))
            )
            for w in t["waypoints"]
        ]
        tracks.append(
            TrackDef(
                id=t["id"],
                type_name=type_name,
                type_value=type_info[0],
                spawn_time_s=t.get("spawn_time_s", 0.0),
                despawn_time_s=t.get("despawn_time_s", sc["duration_s"]),
                waypoints=wps,
                heading_mode=t.get("heading_mode", "tangent"),
            )
        )
    return Scenario(
        name=sc.get("name", "unnamed"), duration_s=sc["duration_s"], tracks=tracks
    )


def _segment_distances(wps: list[TrackWaypoint]) -> list[float]:
    """Cumulative distances along waypoint segments."""
    dists = [0.0]
    for i in range(1, len(wps)):
        dx = wps[i].x - wps[i - 1].x
        dy = wps[i].y - wps[i - 1].y
        dists.append(dists[-1] + math.hypot(dx, dy))
    return dists


def _segment_times(wps: list[TrackWaypoint], cum_dists: list[float]) -> list[float]:
    """Cumulative times along waypoints, computed from segment distance and speed."""
    times = [0.0]
    for i in range(1, len(wps)):
        seg_dist = cum_dists[i] - cum_dists[i - 1]
        speed_ms = max(wps[i - 1].speed_kts * KTS_TO_MS, 0.01)
        times.append(times[-1] + seg_dist / speed_ms)
    return times


def interpolate_track(track: TrackDef, t: float) -> TrackState | None:
    """Interpolate a track at time t (relative to spawn). Returns None if outside lifespan."""
    local_t = t - track.spawn_time_s
    if local_t < 0 or t > track.despawn_time_s:
        return None

    wps = track.waypoints
    if not wps:
        return None

    if len(wps) == 1:
        return TrackState(
            id=track.id,
            type_value=track.type_value,
            x=wps[0].x,
            y=wps[0].y,
            z=0.0,
            heading_rad=0.0,
            vx=0.0,
            vy=0.0,
        )

    cum_dists = _segment_distances(wps)
    cum_times = _segment_times(wps, cum_dists)
    total_time = cum_times[-1]

    if total_time <= 0:
        return TrackState(
            id=track.id,
            type_value=track.type_value,
            x=wps[0].x,
            y=wps[0].y,
            z=0.0,
            heading_rad=0.0,
            vx=0.0,
            vy=0.0,
        )

    # Clamp to end of path
    local_t = min(local_t, total_time)

    # Find segment
    seg_idx = 0
    for i in range(1, len(cum_times)):
        if cum_times[i] >= local_t:
            seg_idx = i - 1
            break
    else:
        seg_idx = len(wps) - 2

    seg_duration = cum_times[seg_idx + 1] - cum_times[seg_idx]
    alpha = (local_t - cum_times[seg_idx]) / max(seg_duration, 1e-6)
    alpha = max(0.0, min(1.0, alpha))

    x = wps[seg_idx].x + alpha * (wps[seg_idx + 1].x - wps[seg_idx].x)
    y = wps[seg_idx].y + alpha * (wps[seg_idx + 1].y - wps[seg_idx].y)

    dx = wps[seg_idx + 1].x - wps[seg_idx].x
    dy = wps[seg_idx + 1].y - wps[seg_idx].y

    if track.heading_mode == "tangent":
        heading_rad = math.atan2(dy, dx)
    elif track.heading_mode == "fixed":
        heading_rad = math.atan2(wps[0].y - 0, wps[0].x - 0)
    else:  # cog
        heading_rad = math.atan2(dy, dx)

    speed_ms = wps[seg_idx].speed_kts * KTS_TO_MS
    seg_len = math.hypot(dx, dy)
    if seg_len > 0:
        vx = speed_ms * dx / seg_len
        vy = speed_ms * dy / seg_len
    else:
        vx, vy = 0.0, 0.0

    return TrackState(
        id=track.id,
        type_value=track.type_value,
        x=x,
        y=y,
        z=0.0,
        heading_rad=heading_rad,
        vx=vx,
        vy=vy,
    )


# ---------------------------------------------------------------------------
# Procedural scenario generation
# ---------------------------------------------------------------------------


@dataclass
class NavigableArea:
    """Binary mask of navigable cells from an OccupancyGrid."""

    mask: list[list[bool]]  # [row][col], True = navigable
    resolution: float  # m/cell
    origin_x: float  # meters
    origin_y: float  # meters
    width: int  # cells
    height: int  # cells

    def is_navigable(self, x: float, y: float) -> bool:
        col = int((x - self.origin_x) / self.resolution)
        row = int((y - self.origin_y) / self.resolution)
        if 0 <= row < self.height and 0 <= col < self.width:
            return self.mask[row][col]
        return False

    def area_m2(self) -> float:
        count = sum(sum(row) for row in self.mask)
        return count * self.resolution * self.resolution

    def sample_point(self, rng: random.Random) -> tuple[float, float]:
        """Sample a random navigable point."""
        for _ in range(1000):
            x = self.origin_x + rng.uniform(0, self.width * self.resolution)
            y = self.origin_y + rng.uniform(0, self.height * self.resolution)
            if self.is_navigable(x, y):
                return x, y
        # Fallback: center of the map
        return (
            self.origin_x + self.width * self.resolution / 2,
            self.origin_y + self.height * self.resolution / 2,
        )


def extract_navigable_area(
    data: list[int],
    width: int,
    height: int,
    resolution: float,
    origin_x: float,
    origin_y: float,
    margin_m: float,
) -> NavigableArea:
    """Build NavigableArea from OccupancyGrid data. Free cells have value 0."""
    margin_cells = max(1, int(margin_m / resolution))
    # Build raw mask
    raw = [
        [data[row * width + col] == 0 for col in range(width)] for row in range(height)
    ]
    # Erode by margin_cells (simple box erosion)
    eroded = [[False] * width for _ in range(height)]
    for r in range(height):
        for c in range(width):
            if not raw[r][c]:
                continue
            navigable = True
            for dr in range(-margin_cells, margin_cells + 1):
                for dc in range(-margin_cells, margin_cells + 1):
                    nr, nc = r + dr, c + dc
                    if (
                        nr < 0
                        or nr >= height
                        or nc < 0
                        or nc >= width
                        or not raw[nr][nc]
                    ):
                        navigable = False
                        break
                if not navigable:
                    break
            eroded[r][c] = navigable

    return NavigableArea(
        mask=eroded,
        resolution=resolution,
        origin_x=origin_x,
        origin_y=origin_y,
        width=width,
        height=height,
    )


def generate_scenario(
    nav_area: NavigableArea,
    *,
    duration_s: float,
    track_count: int,
    density: float,
    area_type: str,
    type_names: list[str],
    type_weights: list[float],
    min_speed_kts: float,
    max_speed_kts: float,
    min_waypoints: int,
    max_waypoints: int,
    spawn_spread_s: float,
    seed: int,
) -> Scenario:
    """Generate a random scenario within the navigable area."""
    rng = random.Random(seed) if seed > 0 else random.Random()

    # Resolve type distribution
    if type_names and type_weights and len(type_names) == len(type_weights):
        type_dist = list(zip(type_names, type_weights))
    else:
        type_dist = AREA_PRESETS.get(area_type, AREA_PRESETS["lake"])

    dist_names = [t[0] for t in type_dist]
    dist_weights = [t[1] for t in type_dist]

    # Determine count
    if track_count <= 0:
        area_km2 = nav_area.area_m2() / 1e6
        track_count = max(1, min(200, int(density * area_km2)))

    tracks: list[TrackDef] = []
    for i in range(track_count):
        type_name = rng.choices(dist_names, weights=dist_weights, k=1)[0]
        type_info = TRACK_TYPE_TABLE.get(type_name, TRACK_TYPE_TABLE["unknown"])
        type_value, default_min_spd, default_max_spd, heading_sigma = type_info

        lo_spd = min_speed_kts if min_speed_kts > 0 else default_min_spd
        hi_spd = max_speed_kts if max_speed_kts > 0 else default_max_spd
        if hi_spd < lo_spd:
            hi_spd = lo_spd
        speed_kts = rng.uniform(lo_spd, hi_spd)

        n_wps = rng.randint(min_waypoints, max_waypoints)
        wps: list[TrackWaypoint] = []

        # First waypoint
        x, y = nav_area.sample_point(rng)
        wps.append(TrackWaypoint(x=x, y=y, speed_kts=speed_kts))

        heading_rad = rng.uniform(0, 2 * math.pi)
        sigma_rad = heading_sigma * DEG2RAD

        for _ in range(n_wps - 1):
            # Random heading change
            heading_rad += rng.gauss(0, sigma_rad)
            seg_time = rng.uniform(20.0, duration_s / max(n_wps, 1))
            dist = speed_kts * KTS_TO_MS * seg_time

            # Candidate point
            nx = x + dist * math.cos(heading_rad)
            ny = y + dist * math.sin(heading_rad)

            # Boundary reflection: try up to 5 times
            for attempt in range(5):
                if nav_area.is_navigable(nx, ny):
                    break
                heading_rad += math.pi * (0.5 + rng.random() * 0.5)
                nx = x + dist * math.cos(heading_rad)
                ny = y + dist * math.sin(heading_rad)
            else:
                # Fallback: resample
                nx, ny = nav_area.sample_point(rng)

            x, y = nx, ny
            wps.append(TrackWaypoint(x=x, y=y, speed_kts=speed_kts))

        spawn_t = rng.uniform(0, spawn_spread_s)
        # Compute total path time
        cum_dists = _segment_distances(wps)
        cum_times = _segment_times(wps, cum_dists)
        despawn_t = min(spawn_t + cum_times[-1], duration_s)

        tracks.append(
            TrackDef(
                id=i + 1,
                type_name=type_name,
                type_value=type_value,
                spawn_time_s=spawn_t,
                despawn_time_s=despawn_t,
                waypoints=wps,
                heading_mode="tangent",
            )
        )

    return Scenario(name=f"generated_{area_type}", duration_s=duration_s, tracks=tracks)


def scenario_to_yaml(scenario: Scenario) -> dict[str, Any]:
    """Convert a Scenario to a dict suitable for YAML dump."""
    tracks_data = []
    for t in scenario.tracks:
        tracks_data.append(
            {
                "id": t.id,
                "type": t.type_name,
                "spawn_time_s": round(t.spawn_time_s, 1),
                "despawn_time_s": round(t.despawn_time_s, 1),
                "heading_mode": t.heading_mode,
                "waypoints": [
                    {
                        "x": round(w.x, 1),
                        "y": round(w.y, 1),
                        "speed_kts": round(w.speed_kts, 1),
                    }
                    for w in t.waypoints
                ],
            }
        )
    return {
        "scenario": {
            "name": scenario.name,
            "duration_s": scenario.duration_s,
            "tracks": tracks_data,
        }
    }


def save_scenario(scenario: Scenario, path: str | Path) -> None:
    """Write scenario to a YAML file."""
    data = scenario_to_yaml(scenario)
    Path(path).write_text(yaml.dump(data, default_flow_style=False, sort_keys=False))
