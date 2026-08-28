#!/usr/bin/env python3
"""Run dataset scenarios against the Dockerized ROS side and Unity.

Two modes are supported:

1. Legacy manifest mode:
   python3 tools/run_scenario_batch.py scenarios.json

2. Orchestrator mode:
   python3 tools/run_scenario_batch.py \
     --output-root solo/new_run \
     --total-frames 1000 \
     --duration 20 \
     --capture-hz 8 \
     --track-count 18 \
     --area-type coastal

Orchestrator mode defines one deterministic scene template, generates that
scene once, then replays the exact same trajectories repeatedly while varying
environment per run. Each run is archived under a UUID folder inside the
requested output root.
"""

from __future__ import annotations

import argparse
import glob
import json
import random
import re
import shlex
import shutil
import subprocess
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROS_ENV = (
    "source /opt/ros/humble/setup.bash && "
    "source /root/ros2_ws/install/setup.bash && "
)

DEFAULT_WEATHERS = ["clear", "cloudy", "overcast", "foggy", "stormy"]
SAFE_TIME_MIN = 6.5
SAFE_TIME_MAX = 17.0
TIME_WINDOWS = {
    "day": [(8.0, SAFE_TIME_MAX)],
    "twilight": [(SAFE_TIME_MIN, 7.0), (16.0, SAFE_TIME_MAX)],
    "night": [(SAFE_TIME_MIN, 7.0), (16.0, SAFE_TIME_MAX)],
}
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


@dataclass
class SceneTemplate:
    id: str
    duration_s: float
    capture_hz: float
    waypoint_period_s: float
    track_count: int
    area_type: str
    type_counts: dict[str, int]
    scenario_seed: int
    min_static_clearance_m: float
    min_dynamic_clearance_m: float
    record_start_delay_s: float
    occupied_fraction: float
    weather_options: list[str]
    day_fraction: float
    twilight_fraction: float
    night_fraction: float
    time_mode: str
    time_drift_hours: float
    time_update_period_s: float
    generated_scenario_path: str = ""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(
    cmd: list[str],
    *,
    check: bool = True,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        check=check,
        text=True,
        capture_output=capture_output,
    )


def ros_exec(shell_command: str, *, capture_output: bool = False) -> str:
    result = run(
        ["docker", "compose", "exec", "ros_bridge", "bash", "-lc", ROS_ENV + shell_command],
        capture_output=capture_output,
    )
    return result.stdout if capture_output else ""


def start_ros_exec(shell_command: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["docker", "compose", "exec", "ros_bridge", "bash", "-lc", ROS_ENV + shell_command],
        text=True,
    )


def parse_weathers(raw: str) -> list[str]:
    items = [part.strip() for part in raw.split(",") if part.strip()]
    if not items:
        raise SystemExit("at least one weather preset must be enabled")
    return items


def parse_area_type(raw: str) -> str:
    if raw not in AREA_PRESETS:
        raise SystemExit(f"--area-type must be one of: {', '.join(sorted(AREA_PRESETS))}")
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


def choose_time_bucket(
    rng: random.Random,
    *,
    day_frac: float,
    twilight_frac: float,
    night_frac: float,
) -> str:
    total = max(1e-6, day_frac + twilight_frac + night_frac)
    pick = rng.random() * total
    if pick < day_frac:
        return "day"
    if pick < day_frac + twilight_frac:
        return "twilight"
    return "night"


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


def set_time_of_day(hour: float) -> None:
    ros_exec(f"ros2 run n3mo_control env_control --ros-args -p time:={hour}")


def set_environment(weather: str, hour: float) -> None:
    ros_exec(
        f"ros2 run n3mo_control env_control --ros-args -p time:={hour} -p weather:={weather}"
    )


def publish_capture_rate(capture_hz: float) -> None:
    ros_exec(
        "ros2 topic pub -w 0 --once /dataset/capture_hz std_msgs/msg/Float32 "
        f"\"{{data: {capture_hz}}}\""
    )


def publish_scenario_info(scenario: dict, manifest_path: str) -> None:
    payload = {
        "id": scenario["id"],
        "manifest_path": manifest_path,
        "weather": scenario["weather"],
        "weather_mode": scenario.get("weather_mode", "sampled"),
        "time_mode": scenario.get("time_mode", "fixed"),
        "time_bucket": scenario.get("time_bucket", "unknown"),
        "time_start_of_day": scenario.get("time_start_of_day", scenario.get("time_of_day", 0.0)),
        "time_end_of_day": scenario.get("time_end_of_day", scenario.get("time_of_day", 0.0)),
        "time_update_period_s": scenario.get("time_update_period_s", 2.0),
        "duration_s": scenario["duration_s"],
        "capture_hz": scenario["capture_hz"],
        "track_count": scenario.get("track_count", 0),
        "area_type": scenario.get("area_type", ""),
        "type_counts_json": json.dumps(scenario.get("type_counts", {}), separators=(",", ":")),
        "scenario_seed": scenario["scenario_seed"],
    }
    raw = json.dumps(payload, separators=(",", ":"))
    yaml_payload = "{data: " + json.dumps(raw) + "}"
    ros_exec(
        "ros2 topic pub -w 0 --once /dataset/scenario_info std_msgs/msg/String "
        + shlex.quote(yaml_payload)
    )


def configure_traffic(scenario: dict) -> None:
    track_count = int(scenario.get("track_count", 0))
    area_type = str(scenario.get("area_type", "coastal"))
    type_counts = scenario.get("type_counts", {})
    occupied_fraction = float(scenario.get("occupied_fraction", 0.7))

    if track_count > 0:
        ros_exec(f"ros2 param set /scenario_generator_node gen_track_count {track_count}")
    ros_exec(f"ros2 param set /scenario_generator_node gen_area_type {area_type}")
    ros_exec(
        f"ros2 param set /scenario_generator_node gen_ego_view_fraction {max(0.0, min(1.0, occupied_fraction))}"
    )
    ros_exec(
        "ros2 param set /scenario_generator_node gen_bias_to_ego_view "
        + ("true" if occupied_fraction > 0.0 else "false")
    )

    payload = json.dumps(type_counts, separators=(",", ":"))
    payload_literal = json.dumps(payload)
    ros_exec(
        "ros2 param set /scenario_generator_node gen_type_counts_json "
        f"'{payload_literal}'"
    )


def read_time_policy(scenario: dict) -> tuple[str, float, float, float]:
    if "time_start_of_day" in scenario:
        start = float(scenario["time_start_of_day"])
        end = float(scenario.get("time_end_of_day", start))
        mode = str(scenario.get("time_mode", "fixed"))
        update_period = float(scenario.get("time_update_period_s", 2.0))
        return mode, start, end, update_period

    start = float(scenario["time_of_day"])
    return "fixed", start, start, 2.0


def drive_time_policy(
    proc: subprocess.Popen[str],
    *,
    mode: str,
    start_hour: float,
    end_hour: float,
    duration_s: float,
    update_period_s: float,
    startup_grace_s: float = 40.0,
) -> bool:
    hit_deadline = False
    start_monotonic = time.monotonic()
    deadline = start_monotonic + startup_grace_s + duration_s + max(update_period_s, 2.0)
    if mode == "linear" and abs(end_hour - start_hour) >= 1e-6:
        next_update_at = time.monotonic() + update_period_s
    else:
        next_update_at = None

    while proc.poll() is None:
        now = time.monotonic()
        if now >= deadline:
            hit_deadline = True
            break
        if next_update_at is not None and now >= next_update_at:
            elapsed = now - start_monotonic
            frac = min(1.0, elapsed / max(duration_s, 1e-6))
            hour = start_hour + (end_hour - start_hour) * frac
            set_time_of_day(round(hour, 2))
            next_update_at = now + update_period_s
        time.sleep(0.25)
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)
    return hit_deadline


def find_solo_dirs() -> dict[Path, float]:
    home = str(Path.home())
    patterns = [
        Path(p)
        for pat in (
            f"{home}/.config/unity3d/*/*/solo*",
            f"{home}/Library/Application Support/*/*/solo*",
        )
        for p in glob.glob(pat)
    ]
    result: dict[Path, float] = {}
    for path in patterns:
        if path.is_dir():
            result[path.resolve()] = path.stat().st_mtime
    return result


def detect_updated_solo_dir(before: dict[Path, float], *, timeout_s: float = 20.0) -> Path:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        after = find_solo_dirs()
        changed = [
            path
            for path, mtime in after.items()
            if path not in before or mtime > before.get(path, 0.0) + 1e-6
        ]
        if changed:
            changed.sort(key=lambda p: after[p], reverse=True)
            return changed[0]
        time.sleep(0.5)
    raise RuntimeError("No updated SOLO dataset directory detected after run")


def count_frame_jsons(solo_dir: Path) -> int:
    return len(list(solo_dir.rglob("*.frame_data.json")))


def hoist_unity_defaults(run_dir: Path, output_root: Path) -> None:
    defaults = sorted(run_dir.glob("unity_defaults_*.json"))
    if not defaults:
        return

    root_defaults = sorted(output_root.glob("unity_defaults_*.json"))
    if not root_defaults:
        target = output_root / defaults[0].name
        shutil.move(str(defaults[0]), str(target))
        defaults = defaults[1:]

    for path in defaults:
        path.unlink(missing_ok=True)


def parse_trigger_message(output: str) -> str:
    match = re.search(r"message='([^']*)'", output, re.DOTALL)
    if not match:
        raise RuntimeError(f"Could not parse Trigger response:\n{output}")
    return match.group(1)


def scenario_command(payload: dict) -> dict:
    raw = json.dumps(payload, separators=(",", ":"))
    request = "{json_request: " + json.dumps(raw) + "}"
    output = ros_exec(
        "ros2 service call /sim/scenario/command n3_new_msgs/srv/ScenarioCommand "
        + shlex.quote(request),
        capture_output=True,
    )
    success_match = re.search(r"success=(True|False)", output)
    json_match = re.search(r"json_response='(.*)'", output, re.DOTALL)
    success = success_match is not None and success_match.group(1) == "True"
    response = {}
    if json_match is not None:
        response = json.loads(json_match.group(1))
    if not success:
        raise RuntimeError(f"Scenario command failed for {payload!r}: {response or output}")
    return response


def generate_scene_once(template: SceneTemplate) -> str:
    ros_exec(f"ros2 param set /scenario_generator_node gen_random_seed {template.scenario_seed}")
    ros_exec(f"ros2 param set /scenario_generator_node gen_duration_s {template.duration_s}")
    configure_traffic(asdict(template))
    output = ros_exec(
        "ros2 service call /sim/generate_scenario std_srvs/srv/Trigger '{}'",
        capture_output=True,
    )
    path = parse_trigger_message(output).strip()
    if not path:
        raise RuntimeError(f"Scenario generator returned empty path:\n{output}")
    return path


def build_scene_template(args: argparse.Namespace) -> SceneTemplate:
    if args.total_frames <= 0:
        raise SystemExit("--total-frames must be > 0")
    if args.duration <= 0.0:
        raise SystemExit("--duration must be > 0")
    if args.capture_hz <= 0.0:
        raise SystemExit("--capture-hz must be > 0")
    if args.track_count <= 0:
        raise SystemExit("--track-count must be > 0")
    if not 0.0 <= args.occupied_fraction <= 1.0:
        raise SystemExit("--occupied-fraction must be within [0, 1]")

    area_type = parse_area_type(args.area_type)
    weather_options = parse_weathers(args.weathers)
    build_rng = random.Random(args.scene_seed) if args.scene_seed > 0 else random.Random(12345)
    if args.type_counts_json:
        type_counts = json.loads(args.type_counts_json)
        if not isinstance(type_counts, dict):
            raise SystemExit("--type-counts-json must decode to an object")
        type_counts = {str(k): int(v) for k, v in type_counts.items() if int(v) > 0}
    else:
        type_counts = build_type_counts(
            area_type=area_type,
            track_count=args.track_count,
            rng=build_rng,
            minimum_per_type=args.min_instances_per_type,
        )

    return SceneTemplate(
        id=f"scene_{uuid.uuid4()}",
        duration_s=args.duration,
        capture_hz=args.capture_hz,
        waypoint_period_s=args.waypoint_period,
        track_count=args.track_count,
        area_type=area_type,
        type_counts=type_counts,
        scenario_seed=args.scene_seed if args.scene_seed > 0 else build_rng.randint(1, 2_147_483_647),
        min_static_clearance_m=args.min_static_clearance,
        min_dynamic_clearance_m=args.min_dynamic_clearance,
        record_start_delay_s=args.record_start_delay,
        occupied_fraction=args.occupied_fraction,
        weather_options=weather_options,
        day_fraction=args.day_frac,
        twilight_fraction=args.twilight_frac,
        night_fraction=args.night_frac,
        time_mode=args.time_mode,
        time_drift_hours=args.time_drift_hours,
        time_update_period_s=args.time_update_period,
    )


def sample_run_environment(template: SceneTemplate, rng: random.Random) -> dict:
    bucket = choose_time_bucket(
        rng,
        day_frac=template.day_fraction,
        twilight_frac=template.twilight_fraction,
        night_frac=template.night_fraction,
    )
    start_tod, end_tod = choose_time_schedule(
        bucket=bucket,
        mode=template.time_mode,
        drift_hours=template.time_drift_hours,
        rng=rng,
    )
    return {
        "weather": rng.choice(template.weather_options),
        "time_bucket": bucket,
        "time_start_of_day": start_tod,
        "time_end_of_day": end_tod,
        "time_mode": template.time_mode,
        "time_update_period_s": template.time_update_period_s,
    }


def run_legacy_manifest_mode(args: argparse.Namespace) -> None:
    manifest_path = Path(args.manifest)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    scenarios = manifest.get("scenarios", [])
    if args.limit > 0:
        scenarios = scenarios[:args.limit]
    if not scenarios:
        raise SystemExit("manifest contains no scenarios")

    if args.dry_run:
        for s in scenarios:
            print(json.dumps(s, indent=2))
        return

    print("Ensuring ros_bridge and scenario services are up...")
    run(["docker", "compose", "up", "-d", "ros_bridge", "scenario"])

    for i, scenario in enumerate(scenarios, start=1):
        sid = scenario["id"]
        print(f"\n[{i}/{len(scenarios)}] {sid}")

        seed = int(scenario["scenario_seed"])
        capture_hz = float(scenario["capture_hz"])
        duration_s = float(scenario["duration_s"])
        waypoint_period = float(scenario["waypoint_period_s"])
        weather = str(scenario["weather"])
        track_count = int(scenario.get("track_count", 0))
        area_type = str(scenario.get("area_type", "coastal"))
        type_counts = scenario.get("type_counts", {})
        min_static = float(scenario["min_static_clearance_m"])
        min_dynamic = float(scenario["min_dynamic_clearance_m"])
        record_start_delay = float(scenario.get("record_start_delay_s", 2.0))
        time_mode, time_start, time_end, time_update_period = read_time_policy(scenario)

        print(
            "  "
            f"seed={seed} weather={weather} time={time_start}"
            f"->{time_end} ({time_mode}) duration={duration_s}s capture={capture_hz}Hz "
            f"tracks={track_count} area={area_type} mix={type_counts}"
        )

        ros_exec(f"ros2 param set /scenario_generator_node gen_random_seed {seed}")
        configure_traffic(scenario)
        set_environment(weather, time_start)
        publish_capture_rate(capture_hz)
        publish_scenario_info(scenario, str(manifest_path.resolve()))

        cmd = (
            "ros2 run n3mo_control dataset_sweep --ros-args "
            f"-p duration_s:={duration_s} "
            f"-p hz:={capture_hz} "
            f"-p waypoint_period:={waypoint_period} "
            f"-p min_static_clearance_m:={min_static} "
            f"-p min_dynamic_clearance_m:={min_dynamic} "
            f"-p randomize_env_on_start:=false "
            f"-p randomize_env_during_run:=false "
            f"-p regenerate_on_start:=true "
            f"-p regenerate_during_run:=false "
            f"-p record_start_delay_s:={record_start_delay}"
        )

        proc = start_ros_exec(cmd)
        try:
            hit_deadline = drive_time_policy(
                proc,
                mode=time_mode,
                start_hour=time_start,
                end_hour=time_end,
                duration_s=duration_s,
                update_period_s=time_update_period,
                startup_grace_s=max(40.0, record_start_delay + 32.0),
            )
        except Exception:
            proc.terminate()
            proc.wait(timeout=10)
            raise

        return_code = int(proc.returncode or 0)
        if return_code != 0 and not hit_deadline:
            raise subprocess.CalledProcessError(return_code, cmd)

        if i != len(scenarios):
            time.sleep(args.sleep_between)

    print("\nScenario batch complete.")


def run_orchestrator_mode(args: argparse.Namespace) -> None:
    output_root = Path(args.output_root)
    try:
        output_root.mkdir(parents=True, exist_ok=True)
    except PermissionError as exc:
        raise SystemExit(
            "Cannot create --output-root at "
            f"'{output_root}'. This host path is not writable by the current user. "
            "Use a writable absolute path, for example "
            "'--output-root /home/user/simulators/UnityMarineSim/new_run', "
            "or fix the ownership/permissions of the target directory."
        ) from exc

    print("Ensuring ros_bridge and scenario services are up...")
    run(["docker", "compose", "up", "-d", "ros_bridge", "scenario"])

    template = build_scene_template(args)
    template.generated_scenario_path = generate_scene_once(template)
    scenario_command({"cmd": "load_scenario", "path": template.generated_scenario_path})

    scene_spec_path = output_root / "scene_spec.json"
    scene_spec_path.write_text(
        json.dumps(
            {
                "version": 3,
                "mode": "single_scene_orchestrator",
                "generated_at": utc_now(),
                "target_total_frames": args.total_frames,
                "scene_template": asdict(template),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Scene template generated once: {template.generated_scenario_path}")
    print(f"Scene spec written: {scene_spec_path}")

    total_frames = 0
    run_index = 0
    env_rng = random.Random(args.env_seed) if args.env_seed > 0 else random.Random()
    summaries: list[dict] = []

    while total_frames < args.total_frames:
        run_index += 1
        run_uuid = str(uuid.uuid4())
        run_dir = output_root / run_uuid
        before_solo = find_solo_dirs()
        env = sample_run_environment(template, env_rng)

        scenario = {
            "id": run_uuid,
            "duration_s": template.duration_s,
            "capture_hz": template.capture_hz,
            "waypoint_period_s": template.waypoint_period_s,
            "track_count": template.track_count,
            "area_type": template.area_type,
            "type_counts": template.type_counts,
            "weather": env["weather"],
            "weather_mode": "sampled",
            "time_bucket": env["time_bucket"],
            "time_mode": env["time_mode"],
            "time_start_of_day": env["time_start_of_day"],
            "time_end_of_day": env["time_end_of_day"],
            "time_update_period_s": env["time_update_period_s"],
            "scenario_seed": template.scenario_seed,
            "min_static_clearance_m": template.min_static_clearance_m,
            "min_dynamic_clearance_m": template.min_dynamic_clearance_m,
            "record_start_delay_s": template.record_start_delay_s,
            "occupied_fraction": template.occupied_fraction,
        }

        print(
            f"\n[{run_index}] {run_uuid}\n"
            f"  weather={scenario['weather']} time={scenario['time_start_of_day']}"
            f"->{scenario['time_end_of_day']} ({scenario['time_mode']}) "
            f"duration={template.duration_s}s capture={template.capture_hz}Hz "
            f"tracks={template.track_count} area={template.area_type} "
            f"occupied_fraction={template.occupied_fraction:.2f}"
        )

        scenario_command({"cmd": "load_scenario", "path": template.generated_scenario_path})
        set_environment(scenario["weather"], scenario["time_start_of_day"])
        publish_capture_rate(template.capture_hz)
        publish_scenario_info(scenario, str(scene_spec_path.resolve()))

        cmd = (
            "ros2 run n3mo_control dataset_sweep --ros-args "
            f"-p duration_s:={template.duration_s} "
            f"-p hz:={template.capture_hz} "
            f"-p waypoint_period:={template.waypoint_period_s} "
            f"-p min_static_clearance_m:={template.min_static_clearance_m} "
            f"-p min_dynamic_clearance_m:={template.min_dynamic_clearance_m} "
            f"-p randomize_env_on_start:=false "
            f"-p randomize_env_during_run:=false "
            f"-p regenerate_on_start:=false "
            f"-p regenerate_during_run:=false "
            f"-p record_start_delay_s:={template.record_start_delay_s}"
        )

        proc = start_ros_exec(cmd)
        try:
            hit_deadline = drive_time_policy(
                proc,
                mode=scenario["time_mode"],
                start_hour=scenario["time_start_of_day"],
                end_hour=scenario["time_end_of_day"],
                duration_s=template.duration_s,
                update_period_s=scenario["time_update_period_s"],
                startup_grace_s=max(40.0, template.record_start_delay_s + 32.0),
            )
        except Exception:
            proc.terminate()
            proc.wait(timeout=10)
            raise

        return_code = int(proc.returncode or 0)
        if return_code != 0 and not hit_deadline:
            raise subprocess.CalledProcessError(return_code, cmd)

        solo_dir = detect_updated_solo_dir(before_solo)
        shutil.move(str(solo_dir), str(run_dir))
        hoist_unity_defaults(run_dir, output_root)
        frame_count = count_frame_jsons(run_dir)
        total_frames += frame_count

        run_summary = {
            "run_index": run_index,
            "run_uuid": run_uuid,
            "solo_dir": str(run_dir),
            "frames": frame_count,
            "accumulated_frames": total_frames,
            "environment": env,
            "scene_seed": template.scenario_seed,
            "generated_scenario_path": template.generated_scenario_path,
            "moved_from": str(solo_dir),
            "finished_at": utc_now(),
        }
        (run_dir / "orchestrator_run.json").write_text(
            json.dumps(run_summary, indent=2) + "\n",
            encoding="utf-8",
        )
        summaries.append(run_summary)

        print(
            f"  archived -> {run_dir}\n"
            f"  frames this run={frame_count}, accumulated={total_frames}/{args.total_frames}"
        )

        time.sleep(args.sleep_between)

    (output_root / "batch_summary.json").write_text(
        json.dumps(
            {
                "version": 3,
                "mode": "single_scene_orchestrator",
                "completed_at": utc_now(),
                "target_total_frames": args.total_frames,
                "actual_total_frames": total_frames,
                "scene_template": asdict(template),
                "runs": summaries,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print("\nOrchestrated batch complete.")


def build_arg_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", nargs="?", help="legacy scenario manifest JSON")
    ap.add_argument("--sleep-between", type=float, default=3.0, help="seconds between runs")
    ap.add_argument("--limit", type=int, default=0, help="legacy mode: run only the first N scenarios")
    ap.add_argument("--dry-run", action="store_true", help="legacy mode: print scenarios without running them")

    ap.add_argument("--output-root", default="", help="orchestrator mode: parent directory for UUID run folders")
    ap.add_argument("--total-frames", "--count", dest="total_frames", type=int, default=0, help="orchestrator mode: stop when this many total frames have been archived")
    ap.add_argument("--scene-seed", type=int, default=0, help="orchestrator mode: deterministic scene seed (0 = auto)")
    ap.add_argument("--env-seed", type=int, default=0, help="orchestrator mode: environment RNG seed (0 = auto)")
    ap.add_argument("--duration", type=float, default=20.0, help="scene duration in seconds")
    ap.add_argument("--capture-hz", type=float, default=10.0, help="capture rate in Hz")
    ap.add_argument("--waypoint-period", type=float, default=12.0, help="seconds between target updates")
    ap.add_argument("--track-count", type=int, default=16, help="generated traffic tracks in the fixed scene")
    ap.add_argument("--area-type", default="coastal", help="traffic preset: lake, coastal, harbor, open_sea")
    ap.add_argument("--type-counts-json", default="", help='exact object mix as JSON, for example \'{"sailboat":4,"ferry":1}\'')
    ap.add_argument("--min-instances-per-type", type=int, default=1, help="when --type-counts-json is absent, minimum count per preset type when possible")
    ap.add_argument("--occupied-fraction", type=float, default=0.8, help="fraction of generated traffic forced into the ego forward view cone")
    ap.add_argument("--min-static-clearance", type=float, default=6.0, help="static obstacle clearance in meters")
    ap.add_argument("--min-dynamic-clearance", type=float, default=8.0, help="dynamic obstacle clearance in meters")
    ap.add_argument("--record-start-delay", type=float, default=2.0, help="delay before recording starts once traffic is ready")
    ap.add_argument("--weathers", default=",".join(DEFAULT_WEATHERS), help="comma-separated enabled weather presets")
    ap.add_argument("--day-frac", type=float, default=0.8, help="fraction of daytime runs")
    ap.add_argument("--twilight-frac", type=float, default=0.2, help="fraction of dawn/dusk runs")
    ap.add_argument("--night-frac", type=float, default=0.0, help="fraction of visible-edge runs reserved for night bucket")
    ap.add_argument("--time-mode", choices=["fixed", "linear"], default="fixed", help="time policy inside each run")
    ap.add_argument("--time-drift-hours", type=float, default=0.4, help="maximum forward time drift across one run when --time-mode=linear")
    ap.add_argument("--time-update-period", type=float, default=2.0, help="seconds between time-of-day updates when --time-mode=linear")
    return ap


def main() -> None:
    args = build_arg_parser().parse_args()
    if args.manifest and Path(args.manifest).exists():
        run_legacy_manifest_mode(args)
        return
    if not args.output_root:
        raise SystemExit("orchestrator mode requires --output-root (or pass a legacy manifest path)")
    run_orchestrator_mode(args)


if __name__ == "__main__":
    main()
