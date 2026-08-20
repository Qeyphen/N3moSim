#!/usr/bin/env python3
"""Generate a scenario manifest for short, isolated dataset runs.

Each manifest entry represents one scenario-sized recording with an explicit
environment policy:
- fixed weather for the scenario
- fixed or slowly progressing time of day
- fixed duration
- fixed capture rate
- one traffic seed

Usage:
  python3 tools/generate_scenarios.py --count 20 --out scenarios.json
  python3 tools/generate_scenarios.py --count 20 --time-mode linear --time-drift-hours 0.4
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone


DEFAULT_WEATHERS = ["clear", "cloudy", "overcast", "foggy", "stormy"]
AREA_PRESETS = {
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
        ("fishing_boat", 3.0),
        ("ferry", 1.0),
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

SAFE_TIME_MIN = 6.5
SAFE_TIME_MAX = 17.0

TIME_WINDOWS = {
    "day": [(8.0, SAFE_TIME_MAX)],
    "twilight": [(SAFE_TIME_MIN, 7.0), (16.0, SAFE_TIME_MAX)],
    "night": [(SAFE_TIME_MIN, 7.0), (16.0, SAFE_TIME_MAX)],
}


@dataclass
class ScenarioSpec:
    id: str
    duration_s: float
    capture_hz: float
    waypoint_period_s: float
    track_count: int
    area_type: str
    type_counts: dict[str, int]
    weather: str
    weather_mode: str
    time_bucket: str
    time_mode: str
    time_start_of_day: float
    time_end_of_day: float
    time_update_period_s: float
    scenario_seed: int
    min_static_clearance_m: float
    min_dynamic_clearance_m: float
    record_start_delay_s: float = 2.0


def parse_weathers(raw: str) -> list[str]:
    weathers = [part.strip() for part in raw.split(",") if part.strip()]
    if not weathers:
        raise SystemExit("at least one weather preset must be enabled")
    return weathers


def build_time_buckets(count: int, day_frac: float, twilight_frac: float, night_frac: float) -> list[str]:
    if count <= 0:
        return []
    buckets = []
    day_n = int(round(count * day_frac))
    twilight_n = int(round(count * twilight_frac))
    night_n = max(0, count - day_n - twilight_n)
    buckets.extend(["day"] * day_n)
    buckets.extend(["twilight"] * twilight_n)
    buckets.extend(["night"] * night_n)
    while len(buckets) < count:
        buckets.append("day")
    return buckets[:count]


def build_weather_sequence(count: int, weathers: list[str], rng: random.Random) -> list[str]:
    if count <= 0:
        return []
    base = count // len(weathers)
    extra = count % len(weathers)
    items: list[str] = []
    for idx, weather in enumerate(weathers):
        n = base + (1 if idx < extra else 0)
        items.extend([weather] * n)
    rng.shuffle(items)
    return items


def choose_time_schedule(
    bucket: str,
    mode: str,
    drift_hours: float,
    rng: random.Random,
) -> tuple[float, float]:
    windows = TIME_WINDOWS[bucket]
    start_lo, start_hi = rng.choice(windows)
    if mode == "fixed":
        value = round(rng.uniform(start_lo, start_hi), 2)
        value = max(SAFE_TIME_MIN, min(SAFE_TIME_MAX, value))
        return value, value

    candidate_windows = []
    for lo, hi in windows:
        max_drift = min(drift_hours, max(0.0, hi - lo))
        if max_drift <= 0.01:
            continue
        candidate_windows.append((lo, hi, max_drift))

    if not candidate_windows:
        value = round(rng.uniform(start_lo, start_hi), 2)
        value = max(SAFE_TIME_MIN, min(SAFE_TIME_MAX, value))
        return value, value

    lo, hi, max_drift = rng.choice(candidate_windows)
    start = rng.uniform(lo, hi - max_drift)
    drift = rng.uniform(min(0.1, max_drift), max_drift)
    end = min(hi, start + drift)
    start = max(SAFE_TIME_MIN, min(SAFE_TIME_MAX, start))
    end = max(SAFE_TIME_MIN, min(SAFE_TIME_MAX, end))
    return round(start, 2), round(end, 2)


def count_values(items: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


def parse_area_type(raw: str) -> str:
    if raw not in AREA_PRESETS:
        raise SystemExit(
            f"--area-type must be one of: {', '.join(sorted(AREA_PRESETS))}"
        )
    return raw


def build_type_counts(
    *,
    area_type: str,
    track_count: int,
    rng: random.Random,
    minimum_per_type: int,
) -> dict[str, int]:
    preset = AREA_PRESETS[area_type]
    type_names = [name for name, _weight in preset]
    weights = [weight for _name, weight in preset]
    if not type_names:
        return {}

    if track_count < len(type_names) * minimum_per_type:
        minimum_per_type = max(0, track_count // max(len(type_names), 1))

    counts = {name: minimum_per_type for name in type_names}
    assigned = sum(counts.values())
    remaining = max(0, track_count - assigned)
    if remaining == 0:
        return {name: count for name, count in counts.items() if count > 0}

    weighted_pool = rng.choices(type_names, weights=weights, k=remaining)
    for name in weighted_pool:
        counts[name] += 1
    return {name: count for name, count in counts.items() if count > 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=20, help="number of scenarios")
    ap.add_argument("--out", default="scenarios.json", help="output manifest path")
    ap.add_argument("--seed", type=int, default=0, help="RNG seed (0 = non-deterministic)")
    ap.add_argument("--duration", type=float, default=20.0, help="scenario duration in seconds")
    ap.add_argument("--capture-hz", type=float, default=10.0, help="capture rate in Hz")
    ap.add_argument("--waypoint-period", type=float, default=12.0, help="seconds between target updates")
    ap.add_argument("--track-count", type=int, default=16, help="generated traffic tracks per scenario")
    ap.add_argument("--area-type", default="coastal", help="traffic preset: lake, coastal, harbor, open_sea")
    ap.add_argument("--min-instances-per-type", type=int, default=1, help="minimum count per preset type, when possible")
    ap.add_argument("--min-static-clearance", type=float, default=6.0, help="static obstacle clearance in meters")
    ap.add_argument("--min-dynamic-clearance", type=float, default=8.0, help="dynamic obstacle clearance in meters")
    ap.add_argument("--record-start-delay", type=float, default=2.0, help="delay before recording starts once traffic is ready")
    ap.add_argument("--day-frac", type=float, default=0.8, help="fraction of daytime scenarios")
    ap.add_argument("--twilight-frac", type=float, default=0.2, help="fraction of dawn/dusk scenarios")
    ap.add_argument("--night-frac", type=float, default=0.0, help="fraction of night scenarios")
    ap.add_argument("--weathers", default=",".join(DEFAULT_WEATHERS), help="comma-separated enabled weather presets")
    ap.add_argument(
        "--time-mode",
        choices=["fixed", "linear"],
        default="fixed",
        help="time policy within each scenario",
    )
    ap.add_argument(
        "--time-drift-hours",
        type=float,
        default=0.4,
        help="maximum forward time drift across one scenario when --time-mode=linear",
    )
    ap.add_argument(
        "--time-update-period",
        type=float,
        default=2.0,
        help="seconds between time-of-day updates when --time-mode=linear",
    )
    args = ap.parse_args()

    if args.count <= 0:
        raise SystemExit("--count must be > 0")
    if args.duration <= 0.0:
        raise SystemExit("--duration must be > 0")
    if args.capture_hz <= 0.0:
        raise SystemExit("--capture-hz must be > 0")
    if args.track_count <= 0:
        raise SystemExit("--track-count must be > 0")
    if args.min_instances_per_type < 0:
        raise SystemExit("--min-instances-per-type must be >= 0")
    if args.time_drift_hours < 0.0:
        raise SystemExit("--time-drift-hours must be >= 0")
    if args.time_update_period <= 0.0:
        raise SystemExit("--time-update-period must be > 0")

    total_frac = args.day_frac + args.twilight_frac + args.night_frac
    if total_frac <= 0.0:
        raise SystemExit("day/twilight/night fractions must sum to > 0")

    day_frac = args.day_frac / total_frac
    twilight_frac = args.twilight_frac / total_frac
    night_frac = args.night_frac / total_frac

    enabled_weathers = parse_weathers(args.weathers)
    area_type = parse_area_type(args.area_type)
    rng = random.Random(args.seed) if args.seed > 0 else random.Random()
    buckets = build_time_buckets(args.count, day_frac, twilight_frac, night_frac)
    rng.shuffle(buckets)
    weather_sequence = build_weather_sequence(args.count, enabled_weathers, rng)

    scenarios: list[ScenarioSpec] = []
    for idx in range(args.count):
        bucket = buckets[idx]
        start_tod, end_tod = choose_time_schedule(
            bucket=bucket,
            mode=args.time_mode,
            drift_hours=args.time_drift_hours,
            rng=rng,
        )
        scenario_seed = rng.randint(1, 2_147_483_647)
        type_counts = build_type_counts(
            area_type=area_type,
            track_count=args.track_count,
            rng=rng,
            minimum_per_type=args.min_instances_per_type,
        )
        scenarios.append(
            ScenarioSpec(
                id=f"scenario_{idx + 1:04d}",
                duration_s=args.duration,
                capture_hz=args.capture_hz,
                waypoint_period_s=args.waypoint_period,
                track_count=args.track_count,
                area_type=area_type,
                type_counts=type_counts,
                weather=weather_sequence[idx],
                weather_mode="fixed",
                time_bucket=bucket,
                time_mode=args.time_mode,
                time_start_of_day=start_tod,
                time_end_of_day=end_tod,
                time_update_period_s=args.time_update_period,
                scenario_seed=scenario_seed,
                min_static_clearance_m=args.min_static_clearance,
                min_dynamic_clearance_m=args.min_dynamic_clearance,
                record_start_delay_s=args.record_start_delay,
            )
        )

    manifest = {
        "version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(scenarios),
        "defaults": {
            "duration_s": args.duration,
            "capture_hz": args.capture_hz,
            "waypoint_period_s": args.waypoint_period,
            "track_count": args.track_count,
            "area_type": area_type,
            "min_instances_per_type": args.min_instances_per_type,
            "min_static_clearance_m": args.min_static_clearance,
            "min_dynamic_clearance_m": args.min_dynamic_clearance,
            "record_start_delay_s": args.record_start_delay,
            "environment_policy": {
                "weather_mode": "fixed",
                "enabled_weathers": enabled_weathers,
                "time_mode": args.time_mode,
                "time_drift_hours": args.time_drift_hours,
                "time_update_period_s": args.time_update_period,
                "distribution": {
                    "day_frac": day_frac,
                    "twilight_frac": twilight_frac,
                    "night_frac": night_frac,
                },
            },
        },
        "distribution_summary": {
            "weather_counts": count_values([s.weather for s in scenarios]),
            "time_bucket_counts": count_values([s.time_bucket for s in scenarios]),
            "type_totals": {
                type_name: sum(s.type_counts.get(type_name, 0) for s in scenarios)
                for type_name, _weight in AREA_PRESETS[area_type]
            },
        },
        "scenarios": [asdict(s) for s in scenarios],
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    print(f"wrote {args.out}: {len(scenarios)} scenarios")
    print("weather counts:", manifest["distribution_summary"]["weather_counts"])
    print("time buckets:", manifest["distribution_summary"]["time_bucket_counts"])
    print("type totals:", manifest["distribution_summary"]["type_totals"])


if __name__ == "__main__":
    main()
