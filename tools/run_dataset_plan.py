#!/usr/bin/env python3
"""Generate a full dataset by running tools/run_scenario.py once per scenario.

The plan file (see plan_loader.py) declares every scenario as the exact CLI
arguments of run_scenario.py, plus shared defaults. This orchestrator loops
over the scenarios sequentially, gives each run its own sub-folder under
--output-root, and aggregates the per-run run_summary.json files into a
global manifest.json so the resulting dataset is fully traceable.

A failing scenario does not stop the plan: the failure is recorded in the
manifest and the next scenario starts. The manifest is rewritten after every
scenario, so a crash or Ctrl-C leaves a usable partial manifest behind.

Usage (from the repo root, Unity in Play mode as for run_scenario.py):

    python3 tools/run_dataset_plan.py tools/plans/dataset-1k.yaml \
        --output-root recordings/dataset-1k
    python3 tools/run_dataset_plan.py PLAN --output-root DIR --dry-run
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from plan_loader import PlanError, load_plan  # noqa: E402

RUN_SCENARIO = Path(__file__).resolve().parent / "run_scenario.py"

# Emission order of run_scenario.py arguments, for stable commands and diffs.
ARG_ORDER = (
    "duration",
    "capture_hz",
    "waypoint_period",
    "track_count",
    "area_type",
    "occupied_fraction",
    "scene_seed",
    "min_static_clearance",
    "min_dynamic_clearance",
    "record_start_delay",
    "time_of_day",
    "weather",
    "fog",
    "wave",
    "wind",
    "cloudiness",
    "rain",
    "type_counts",
)


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without Docker, ROS or Unity)
# ---------------------------------------------------------------------------

def format_arg_value(value):
    """Render one plan value as a CLI argument string."""
    if isinstance(value, float):
        return f"{value:g}"
    return str(value)


def build_command(scenario, output_dir, python=None):
    """Build the run_scenario.py command line for one scenario."""
    python = python or sys.executable
    cmd = [python, str(RUN_SCENARIO), "--output", str(output_dir)]
    for key in ARG_ORDER:
        if key not in scenario.args:
            continue
        value = scenario.args[key]
        if key == "type_counts":
            cmd += ["--type-counts-json", json.dumps(value, sort_keys=True)]
        else:
            cmd += ["--" + key.replace("_", "-"), format_arg_value(value)]
    return cmd


def scenario_output_dir(output_root, index, scenario):
    """One sub-folder per scenario: 001-lake-clear-day, 002-..."""
    return Path(output_root) / f"{index + 1:03d}-{scenario.name}"


def read_run_summary(output_dir):
    """Return the parsed run_summary.json of a finished run, or None."""
    path = Path(output_dir) / "run_summary.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def build_manifest(plan, plan_path, output_root, entries, started_at, finished_at=None):
    """Aggregate per-scenario entries into the global manifest payload."""
    ok = [e for e in entries if e["status"] == "ok"]
    failed = [e for e in entries if e["status"] == "failed"]
    return {
        "version": 1,
        "plan": plan.name,
        "plan_file": str(plan_path),
        "output_root": str(output_root),
        "started_at": started_at,
        "finished_at": finished_at,
        "totals": {
            "scenarios": len(plan.scenarios),
            "completed": len(ok),
            "failed": len(failed),
            "frames": sum(e.get("frames") or 0 for e in entries),
        },
        "scenarios": entries,
    }


def write_manifest(manifest, output_root):
    path = Path(output_root) / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Execution
# ---------------------------------------------------------------------------

def run_plan(plan, plan_path, output_root, dry_run=False, runner=subprocess.run):
    """Run every scenario of the plan. Returns the final manifest."""
    output_root = Path(output_root).expanduser().resolve()

    if dry_run:
        for index, scenario in enumerate(plan.scenarios):
            out_dir = scenario_output_dir(output_root, index, scenario)
            print(shlex.join(build_command(scenario, out_dir)))
        print(
            f"# {len(plan.scenarios)} scenarios, "
            f"~{plan.total_estimated_frames} frames, "
            f"{plan.total_capture_s:g}s of capture"
        )
        return None

    output_root.mkdir(parents=True, exist_ok=True)
    started_at = utc_now()
    entries = []

    for index, scenario in enumerate(plan.scenarios):
        out_dir = scenario_output_dir(output_root, index, scenario)
        cmd = build_command(scenario, out_dir)
        entry = {
            "index": index,
            "name": scenario.name,
            "output_dir": str(out_dir),
            "command": shlex.join(cmd),
            "scene_seed": scenario.args["scene_seed"],
            "status": "running",
            "started_at": utc_now(),
            "finished_at": None,
            "return_code": None,
            "frames": None,
        }
        entries.append(entry)
        write_manifest(
            build_manifest(plan, plan_path, output_root, entries, started_at),
            output_root,
        )

        print(f"[{index + 1}/{len(plan.scenarios)}] {scenario.name}")
        print(f"  $ {entry['command']}")
        result = runner(cmd)
        entry["return_code"] = int(result.returncode or 0)
        entry["finished_at"] = utc_now()

        summary = read_run_summary(out_dir)
        if entry["return_code"] == 0 and summary is not None:
            entry["status"] = "ok"
            entry["frames"] = summary.get("frames")
        else:
            entry["status"] = "failed"
            print(
                f"  FAILED (return code {entry['return_code']}, "
                f"run_summary {'present' if summary else 'missing'}), continuing",
                file=sys.stderr,
            )

        write_manifest(
            build_manifest(plan, plan_path, output_root, entries, started_at),
            output_root,
        )

    manifest = build_manifest(
        plan, plan_path, output_root, entries, started_at, finished_at=utc_now()
    )
    write_manifest(manifest, output_root)

    totals = manifest["totals"]
    print(
        f"Plan '{plan.name}' finished: {totals['completed']} ok, "
        f"{totals['failed']} failed, {totals['frames']} frames -> {output_root}"
    )
    return manifest


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("plan", help="plan YAML file (see tools/plan_loader.py)")
    ap.add_argument(
        "--output-root",
        required=True,
        help="directory receiving one sub-folder per scenario plus manifest.json",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print the run_scenario.py commands without executing anything",
    )
    args = ap.parse_args(argv)

    try:
        plan = load_plan(args.plan)
    except PlanError as exc:
        print(f"Invalid plan: {exc}", file=sys.stderr)
        return 2

    manifest = run_plan(plan, args.plan, args.output_root, dry_run=args.dry_run)
    if manifest is not None and manifest["totals"]["failed"] > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
