#!/usr/bin/env python3
"""Run one deterministic scenario with an explicit environment and output folder.

Example:
  python3 tools/run_scenario.py \
    --output /home/user/simulators/UnityMarineSim/defense_run \
    --duration 60 \
    --capture-hz 8 \
    --track-count 24 \
    --area-type coastal \
    --occupied-fraction 0.8 \
    --scene-seed 12345 \
    --time-of-day 8.0 \
    --weather foggy \
    --fog 0.45 \
    --wave 0.9 \
    --wind 0.6 \
    --cloudiness 0.6
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import shlex
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


ROS_ENV = (
    "source /opt/ros/humble/setup.bash && "
    "source /root/ros2_ws/install/setup.bash && "
)

AREA_PRESETS = {"lake", "coastal", "harbor", "open_sea"}
WEATHER_PRESETS = {"clear", "cloudy", "overcast", "foggy", "stormy"}


@dataclass
class ScenarioRunSpec:
    duration_s: float
    capture_hz: float
    waypoint_period_s: float
    track_count: int
    area_type: str
    occupied_fraction: float
    scene_seed: int
    min_static_clearance_m: float
    min_dynamic_clearance_m: float
    record_start_delay_s: float
    time_of_day: float
    weather: str
    fog: float | None
    wave: float | None
    wind: float | None
    cloudiness: float | None
    rain: float | None
    type_counts: dict[str, int]
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


def parse_area_type(raw: str) -> str:
    if raw not in AREA_PRESETS:
        raise SystemExit(f"--area-type must be one of: {', '.join(sorted(AREA_PRESETS))}")
    return raw


def parse_weather(raw: str) -> str:
    value = raw.strip().lower()
    if value not in WEATHER_PRESETS:
        raise SystemExit(f"--weather must be one of: {', '.join(sorted(WEATHER_PRESETS))}")
    return value


def parse_optional_unit_float(value: str | None, *, name: str) -> float | None:
    if value is None or value == "":
        return None
    parsed = float(value)
    if not 0.0 <= parsed <= 1.0:
        raise SystemExit(f"--{name} must be within [0, 1]")
    return parsed


def parse_type_counts_json(raw: str) -> dict[str, int]:
    if not raw.strip():
        return {}
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise SystemExit("--type-counts-json must decode to an object")
    return {str(k): int(v) for k, v in data.items() if int(v) > 0}


def configure_traffic(spec: ScenarioRunSpec) -> None:
    ros_exec(f"ros2 param set /scenario_generator_node gen_random_seed {spec.scene_seed}")
    ros_exec(f"ros2 param set /scenario_generator_node gen_duration_s {spec.duration_s}")
    ros_exec(f"ros2 param set /scenario_generator_node gen_track_count {spec.track_count}")
    ros_exec(f"ros2 param set /scenario_generator_node gen_area_type {spec.area_type}")
    ros_exec(
        f"ros2 param set /scenario_generator_node gen_ego_view_fraction {spec.occupied_fraction}"
    )
    ros_exec(
        "ros2 param set /scenario_generator_node gen_bias_to_ego_view "
        + ("true" if spec.occupied_fraction > 0.0 else "false")
    )
    payload = json.dumps(spec.type_counts, separators=(",", ":"))
    payload_literal = json.dumps(payload)
    ros_exec(
        "ros2 param set /scenario_generator_node gen_type_counts_json "
        f"'{payload_literal}'"
    )


def parse_trigger_message(output: str) -> str:
    marker = "message='"
    start = output.find(marker)
    if start < 0:
        raise RuntimeError(f"Could not parse Trigger response:\n{output}")
    start += len(marker)
    end = output.find("'", start)
    if end < 0:
        raise RuntimeError(f"Could not parse Trigger response:\n{output}")
    return output[start:end]


def generate_scene_once(spec: ScenarioRunSpec) -> str:
    configure_traffic(spec)
    output = ros_exec(
        "ros2 service call /sim/generate_scenario std_srvs/srv/Trigger '{}'",
        capture_output=True,
    )
    if "success=True" not in output:
        raise RuntimeError(f"Scenario generation failed:\n{output}")
    path = parse_trigger_message(output).strip()
    if not path.startswith("/"):
        raise RuntimeError(f"Scenario generator returned no file path:\n{output}")
    return path


def publish_capture_rate(capture_hz: float) -> None:
    ros_exec(
        "ros2 topic pub -w 0 --once /dataset/capture_hz std_msgs/msg/Float32 "
        f"\"{{data: {capture_hz}}}\""
    )


def apply_environment(spec: ScenarioRunSpec) -> None:
    ros_exec(
        f"ros2 run n3mo_control env_control --ros-args "
        f"-p time:={spec.time_of_day} -p weather:={spec.weather}"
    )
    parts = []
    if spec.fog is not None:
        parts.append(f"-p fog:={spec.fog}")
    if spec.wave is not None:
        parts.append(f"-p wave:={spec.wave}")
    if spec.wind is not None:
        parts.append(f"-p wind:={spec.wind}")
    if spec.cloudiness is not None:
        parts.append(f"-p cloudiness:={spec.cloudiness}")
    if spec.rain is not None:
        parts.append(f"-p rain:={spec.rain}")
    if parts:
        ros_exec(
            "ros2 run n3mo_control env_control --ros-args " + " ".join(parts)
        )


def publish_scenario_info(spec: ScenarioRunSpec, output_dir: Path) -> None:
    payload = {
        "id": output_dir.name,
        "manifest_path": str(output_dir / "scene_spec.json"),
        "weather": spec.weather,
        "weather_mode": "fixed",
        "time_mode": "fixed",
        "time_bucket": "explicit",
        "time_start_of_day": spec.time_of_day,
        "time_end_of_day": spec.time_of_day,
        "time_update_period_s": 0.0,
        "duration_s": spec.duration_s,
        "capture_hz": spec.capture_hz,
        "track_count": spec.track_count,
        "area_type": spec.area_type,
        "type_counts_json": json.dumps(spec.type_counts, separators=(",", ":")),
        "scenario_seed": spec.scene_seed,
    }
    raw = json.dumps(payload, separators=(",", ":"))
    yaml_payload = "{data: " + json.dumps(raw) + "}"
    ros_exec(
        "ros2 topic pub -w 0 --once /dataset/scenario_info std_msgs/msg/String "
        + shlex.quote(yaml_payload)
    )


# SOLO root files that define the dataset schema (both stereo cameras share
# one SOLO dir). They are copied into each scenario folder so it is a valid
# standalone dataset, and left in place for the ongoing Play session.
SOLO_DEFINITION_FILES = frozenset({
    "annotation_definitions.json",
    "metadata.json",
    "metric_definitions.json",
    "sensor_definitions.json",
})


def find_solo_dirs(home: str | None = None) -> list[Path]:
    home = home or str(Path.home())
    dirs: list[Path] = []
    for pat in (
        f"{home}/.config/unity3d/*/*/solo*",
        f"{home}/Library/Application Support/*/*/solo*",
    ):
        for p in glob.glob(pat):
            path = Path(p)
            if path.is_dir():
                dirs.append(path.resolve())
    return sorted(set(dirs))


def snapshot_sequences(home: str | None = None) -> set[Path]:
    """All sequence.N dirs currently under the SOLO dirs. Perception keeps one
    SOLO dir for the whole Play session (both stereo cameras write into it) and
    appends a new sequence per recording, so a run's own output is exactly the
    sequences that appear after it started. We must never delete the SOLO dir
    itself, only lift out the sequences this run produced."""
    seqs: set[Path] = set()
    for solo in find_solo_dirs(home):
        for child in solo.iterdir():
            if child.is_dir() and child.name.startswith("sequence."):
                seqs.add(child.resolve())
    return seqs


def wait_for_new_sequences(
    before: set[Path], *, timeout_s: float = 45.0, settle_s: float = 3.0
) -> list[Path]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if snapshot_sequences() - before:
            time.sleep(settle_s)  # let both cameras' frames finish flushing
            return sorted(snapshot_sequences() - before)
        time.sleep(0.5)
    raise RuntimeError("No new SOLO sequence appeared after the run")


def harvest_sequences(output_dir: Path, new_sequences: list[Path]) -> int:
    """Move the run's new sequences into output_dir and copy the SOLO schema
    definitions alongside, leaving the SOLO dir intact for the session. The
    frame data (the only thing that grows) never stays in the Unity folder."""
    if not new_sequences:
        raise RuntimeError("No new SOLO sequence to harvest")
    output_dir.mkdir(parents=True, exist_ok=True)
    for seq in new_sequences:
        for name in SOLO_DEFINITION_FILES:
            src = seq.parent / name
            dst = output_dir / name
            if src.exists() and not dst.exists():
                shutil.copy2(str(src), str(dst))
    for i, seq in enumerate(sorted(new_sequences)):
        shutil.move(str(seq), str(output_dir / f"sequence.{i}"))
    return len(new_sequences)


def drive_until_done(
    proc: subprocess.Popen[str],
    *,
    duration_s: float,
    startup_grace_s: float,
) -> bool:
    hit_deadline = False
    deadline = time.monotonic() + startup_grace_s + duration_s + 2.0
    while proc.poll() is None:
        if time.monotonic() >= deadline:
            hit_deadline = True
            break
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


def count_frame_jsons(path: Path) -> int:
    return len(list(path.rglob("*.frame_data.json")))


def write_scene_spec(spec: ScenarioRunSpec, output_dir: Path) -> None:
    payload = {
        "version": 1,
        "mode": "single_run",
        "generated_at": utc_now(),
        "scene": asdict(spec),
    }
    (output_dir / "scene_spec.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def write_run_summary(spec: ScenarioRunSpec, output_dir: Path, frame_count: int) -> None:
    payload = {
        "version": 1,
        "mode": "single_run",
        "finished_at": utc_now(),
        "output_dir": str(output_dir),
        "frames": frame_count,
        "scene": asdict(spec),
    }
    (output_dir / "run_summary.json").write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )


def ensure_output_dir(path: Path) -> None:
    if path.exists():
        if not path.is_dir():
            raise SystemExit(f"--output must be a directory path: {path}")
        if any(path.iterdir()):
            raise SystemExit(f"--output directory must be empty: {path}")
    else:
        path.mkdir(parents=True, exist_ok=True)


def build_spec(args: argparse.Namespace) -> ScenarioRunSpec:
    if args.duration <= 0.0:
        raise SystemExit("--duration must be > 0")
    if args.capture_hz <= 0.0:
        raise SystemExit("--capture-hz must be > 0")
    if args.track_count <= 0:
        raise SystemExit("--track-count must be > 0")
    if not 0.0 <= args.occupied_fraction <= 1.0:
        raise SystemExit("--occupied-fraction must be within [0, 1]")

    scene_seed = int(args.scene_seed)
    if scene_seed <= 0:
        scene_seed = int(time.time())

    return ScenarioRunSpec(
        duration_s=float(args.duration),
        capture_hz=float(args.capture_hz),
        waypoint_period_s=float(args.waypoint_period),
        track_count=int(args.track_count),
        area_type=parse_area_type(args.area_type),
        occupied_fraction=float(args.occupied_fraction),
        scene_seed=scene_seed,
        min_static_clearance_m=float(args.min_static_clearance),
        min_dynamic_clearance_m=float(args.min_dynamic_clearance),
        record_start_delay_s=float(args.record_start_delay),
        time_of_day=float(args.time_of_day),
        weather=parse_weather(args.weather),
        fog=parse_optional_unit_float(args.fog, name="fog"),
        wave=parse_optional_unit_float(args.wave, name="wave"),
        wind=parse_optional_unit_float(args.wind, name="wind"),
        cloudiness=parse_optional_unit_float(args.cloudiness, name="cloudiness"),
        rain=parse_optional_unit_float(args.rain, name="rain"),
        type_counts=parse_type_counts_json(args.type_counts_json),
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, help="directory that will receive this single run")
    ap.add_argument("--duration", type=float, required=True, help="run duration in seconds")
    ap.add_argument("--capture-hz", type=float, default=8.0, help="capture rate in Hz")
    ap.add_argument("--waypoint-period", type=float, default=12.0, help="seconds between target updates")
    ap.add_argument("--track-count", type=int, default=18, help="generated traffic tracks")
    ap.add_argument("--area-type", default="coastal", help="traffic preset: lake, coastal, harbor, open_sea")
    ap.add_argument("--occupied-fraction", type=float, default=0.8, help="share of traffic biased into the ego forward view")
    ap.add_argument("--scene-seed", type=int, default=0, help="deterministic scene seed (0 = use current timestamp)")
    ap.add_argument("--min-static-clearance", type=float, default=6.0, help="static obstacle clearance in meters")
    ap.add_argument("--min-dynamic-clearance", type=float, default=8.0, help="dynamic obstacle clearance in meters")
    ap.add_argument("--record-start-delay", type=float, default=2.0, help="delay before recording starts once traffic is ready")
    ap.add_argument("--time-of-day", type=float, required=True, help="time of day in hours")
    ap.add_argument("--weather", required=True, help="weather preset")
    ap.add_argument("--fog", default=None, help="explicit fog override 0..1")
    ap.add_argument("--wave", default=None, help="explicit wave override 0..1")
    ap.add_argument("--wind", default=None, help="explicit wind override 0..1")
    ap.add_argument("--cloudiness", default=None, help="explicit cloudiness override 0..1")
    ap.add_argument("--rain", default=None, help="explicit rain override 0..1")
    ap.add_argument("--type-counts-json", default="", help='exact object mix as JSON, for example \'{"sailboat":6,"ferry":1}\'')
    args = ap.parse_args()

    output_dir = Path(args.output).expanduser().resolve()
    ensure_output_dir(output_dir)
    spec = build_spec(args)

    print("Ensuring ros_bridge and scenario services are up...")
    run(["docker", "compose", "up", "-d", "ros_bridge", "scenario"])

    sequences_before = snapshot_sequences()

    spec.generated_scenario_path = generate_scene_once(spec)
    print(f"Scene template generated once: {spec.generated_scenario_path}")

    write_scene_spec(spec, output_dir)
    apply_environment(spec)
    publish_capture_rate(spec.capture_hz)
    publish_scenario_info(spec, output_dir)

    cmd = (
        "ros2 run n3mo_control dataset_sweep --ros-args "
        f"-p duration_s:={spec.duration_s} "
        f"-p hz:={spec.capture_hz} "
        f"-p waypoint_period:={spec.waypoint_period_s} "
        f"-p min_static_clearance_m:={spec.min_static_clearance_m} "
        f"-p min_dynamic_clearance_m:={spec.min_dynamic_clearance_m} "
        f"-p randomize_env_on_start:=false "
        f"-p randomize_env_during_run:=false "
        f"-p regenerate_on_start:=false "
        f"-p regenerate_during_run:=false "
        f"-p record_start_delay_s:={spec.record_start_delay_s}"
    )

    proc = start_ros_exec(cmd)
    hit_deadline = drive_until_done(
        proc,
        duration_s=spec.duration_s,
        startup_grace_s=max(40.0, spec.record_start_delay_s + 32.0),
    )
    return_code = int(proc.returncode or 0)
    if return_code != 0 and not hit_deadline:
        raise subprocess.CalledProcessError(return_code, cmd)

    harvest_sequences(output_dir, wait_for_new_sequences(sequences_before))
    frame_count = count_frame_jsons(output_dir)
    write_run_summary(spec, output_dir, frame_count)

    print(f"Saved run -> {output_dir}")
    print(f"Frames captured: {frame_count}")


if __name__ == "__main__":
    main()
