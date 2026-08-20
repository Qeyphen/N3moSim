#!/usr/bin/env python3
"""Run a scenario manifest against the Dockerized ROS side and Unity.

This script executes one short, isolated recording per manifest entry:
- sets a fixed capture rate
- sets fixed weather values for the scenario
- sets fixed or slowly progressing time-of-day values for the scenario
- sets the scenario generator seed
- runs dataset_sweep in scenario mode

Usage:
  python3 tools/run_scenario_batch.py scenarios.json
  python3 tools/run_scenario_batch.py scenarios.json --limit 1
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROS_ENV = (
    "source /opt/ros/humble/setup.bash && "
    "source /root/ros2_ws/install/setup.bash && "
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run(cmd: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True)


def ros_exec(shell_command: str) -> None:
    run(["docker", "compose", "exec", "ros_bridge", "bash", "-lc", ROS_ENV + shell_command])


def start_ros_exec(shell_command: str) -> subprocess.Popen[str]:
    return subprocess.Popen(
        ["docker", "compose", "exec", "ros_bridge", "bash", "-lc", ROS_ENV + shell_command],
        text=True,
    )


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
        "weather_mode": scenario.get("weather_mode", "fixed"),
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

    if track_count > 0:
        ros_exec(f"ros2 param set /scenario_generator_node gen_track_count {track_count}")
    ros_exec(f"ros2 param set /scenario_generator_node gen_area_type {area_type}")

    payload = json.dumps(type_counts, separators=(",", ":"))
    # ros2 param set parses the value as YAML first; wrap the JSON blob as a YAML string literal
    # so the target parameter receives a plain string instead of a parsed mapping.
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

    # Backward compatibility with v1 manifests.
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
) -> None:
    if mode != "linear" or abs(end_hour - start_hour) < 1e-6:
        proc.wait()
        return

    next_update_at = time.monotonic() + update_period_s
    start_monotonic = time.monotonic()
    deadline = start_monotonic + duration_s + max(update_period_s, 2.0)
    while proc.poll() is None:
        now = time.monotonic()
        if now >= deadline:
            break
        if now >= next_update_at:
            elapsed = now - start_monotonic
            frac = min(1.0, elapsed / max(duration_s, 1e-6))
            hour = start_hour + (end_hour - start_hour) * frac
            set_time_of_day(round(hour, 2))
            next_update_at = now + update_period_s
        time.sleep(0.25)
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("manifest", help="scenario manifest JSON")
    ap.add_argument("--sleep-between", type=float, default=3.0, help="seconds between scenarios")
    ap.add_argument("--limit", type=int, default=0, help="run only the first N scenarios")
    ap.add_argument("--dry-run", action="store_true", help="print the commands without running them")
    args = ap.parse_args()

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

        started_at = utc_now()
        proc = start_ros_exec(cmd)
        try:
            drive_time_policy(
                proc,
                mode=time_mode,
                start_hour=time_start,
                end_hour=time_end,
                duration_s=duration_s,
                update_period_s=time_update_period,
            )
        except Exception:
            proc.terminate()
            proc.wait(timeout=10)
            raise

        return_code = int(proc.returncode or 0)
        if return_code != 0:
            raise subprocess.CalledProcessError(return_code, cmd)

        if i != len(scenarios):
            time.sleep(args.sleep_between)

    print("\nScenario batch complete.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print(exc, file=sys.stderr)
        sys.exit(exc.returncode)
