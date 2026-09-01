"""Tests for the plan orchestrator. No Docker/ROS/Unity needed."""

import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plan_loader import build_plan
from run_dataset_plan import (
    RUN_SCENARIO,
    build_command,
    build_manifest,
    format_arg_value,
    main,
    read_run_summary,
    run_plan,
    scenario_output_dir,
)


def two_scenario_plan():
    return build_plan({
        "name": "test-plan",
        "defaults": {"duration": 25, "capture_hz": 5, "track_count": 18},
        "scenarios": [
            {
                "name": "lake-clear",
                "area_type": "lake",
                "weather": "clear",
                "time_of_day": 11.0,
                "scene_seed": 1,
                "fog": 0.3,
                "type_counts": {"sailboat": 6, "kayak": 2},
            },
            {
                "name": "harbor-stormy",
                "area_type": "harbor",
                "weather": "stormy",
                "time_of_day": 18.0,
                "scene_seed": 2,
            },
        ],
    })


class TestCommandBuilding(unittest.TestCase):
    def test_format_arg_value(self):
        self.assertEqual(format_arg_value(25.0), "25")
        self.assertEqual(format_arg_value(0.8), "0.8")
        self.assertEqual(format_arg_value(18), "18")
        self.assertEqual(format_arg_value("clear"), "clear")

    def test_build_command_kebab_case_and_order(self):
        plan = two_scenario_plan()
        cmd = build_command(plan.scenarios[0], "/tmp/out", python="python3")
        self.assertEqual(cmd[:2], ["python3", str(RUN_SCENARIO)])
        self.assertEqual(cmd[2:4], ["--output", "/tmp/out"])
        self.assertIn("--capture-hz", cmd)
        self.assertIn("--time-of-day", cmd)
        self.assertNotIn("--capture_hz", cmd)
        # arguments appear after --output in ARG_ORDER order
        self.assertLess(cmd.index("--duration"), cmd.index("--scene-seed"))
        self.assertLess(cmd.index("--scene-seed"), cmd.index("--weather"))

    def test_build_command_only_provided_args(self):
        plan = two_scenario_plan()
        cmd = build_command(plan.scenarios[1], "/tmp/out")
        self.assertNotIn("--fog", cmd)
        self.assertNotIn("--type-counts-json", cmd)
        self.assertNotIn("--occupied-fraction", cmd)

    def test_build_command_type_counts_as_json(self):
        plan = two_scenario_plan()
        cmd = build_command(plan.scenarios[0], "/tmp/out")
        payload = cmd[cmd.index("--type-counts-json") + 1]
        self.assertEqual(json.loads(payload), {"sailboat": 6, "kayak": 2})

    def test_scenario_output_dir(self):
        plan = two_scenario_plan()
        out = scenario_output_dir("/data/root", 0, plan.scenarios[0])
        self.assertEqual(out, Path("/data/root/001-lake-clear"))
        out = scenario_output_dir("/data/root", 1, plan.scenarios[1])
        self.assertEqual(out, Path("/data/root/002-harbor-stormy"))


class TestManifest(unittest.TestCase):
    def test_read_run_summary_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(read_run_summary(tmp))

    def test_read_run_summary_corrupt(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "run_summary.json").write_text("not json")
            self.assertIsNone(read_run_summary(tmp))

    def test_build_manifest_totals(self):
        plan = two_scenario_plan()
        entries = [
            {"name": "lake-clear", "status": "ok", "frames": 120},
            {"name": "harbor-stormy", "status": "failed", "frames": None},
        ]
        manifest = build_manifest(
            plan, "plan.yaml", "/data/root", entries, "T0", finished_at="T1")
        self.assertEqual(manifest["plan"], "test-plan")
        self.assertEqual(manifest["totals"], {
            "scenarios": 2, "completed": 1, "failed": 1, "frames": 120,
        })
        self.assertEqual(manifest["finished_at"], "T1")


class FakeRunner:
    """Stands in for subprocess.run; optionally fails some scenarios."""

    def __init__(self, fail_names=(), frames=125):
        self.fail_names = fail_names
        self.frames = frames
        self.commands = []

    def __call__(self, cmd):
        self.commands.append(cmd)
        out_dir = Path(cmd[cmd.index("--output") + 1])
        name = out_dir.name.split("-", 1)[1]
        if name in self.fail_names:
            return SimpleNamespace(returncode=1)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "run_summary.json").write_text(
            json.dumps({"version": 1, "frames": self.frames}))
        return SimpleNamespace(returncode=0)


class TestRunPlan(unittest.TestCase):
    def test_dry_run_executes_nothing(self):
        plan = two_scenario_plan()
        runner = FakeRunner()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "root"
            buf = io.StringIO()
            with redirect_stdout(buf):
                manifest = run_plan(plan, "p.yaml", root, dry_run=True,
                                    runner=runner)
            self.assertIsNone(manifest)
            self.assertEqual(runner.commands, [])
            self.assertFalse(root.exists())
            printed = buf.getvalue()
            self.assertIn("001-lake-clear", printed)
            self.assertIn("--scene-seed 1", printed)
            self.assertIn("~250 frames", printed)

    def test_all_scenarios_ok(self):
        plan = two_scenario_plan()
        runner = FakeRunner()
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()):
                manifest = run_plan(plan, "p.yaml", tmp, runner=runner)
            self.assertEqual(len(runner.commands), 2)
            self.assertEqual(manifest["totals"],
                             {"scenarios": 2, "completed": 2, "failed": 0,
                              "frames": 250})
            on_disk = json.loads(
                (Path(tmp) / "manifest.json").read_text())
            self.assertEqual(on_disk["totals"], manifest["totals"])
            self.assertIsNotNone(on_disk["finished_at"])
            for entry in on_disk["scenarios"]:
                self.assertEqual(entry["status"], "ok")
                self.assertEqual(entry["frames"], 125)

    def test_failure_recorded_and_plan_continues(self):
        plan = two_scenario_plan()
        runner = FakeRunner(fail_names=("lake-clear",))
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                manifest = run_plan(plan, "p.yaml", tmp, runner=runner)
            # the second scenario still ran
            self.assertEqual(len(runner.commands), 2)
            statuses = {e["name"]: e["status"] for e in manifest["scenarios"]}
            self.assertEqual(statuses,
                             {"lake-clear": "failed", "harbor-stormy": "ok"})
            self.assertEqual(manifest["totals"]["failed"], 1)
            self.assertEqual(manifest["totals"]["frames"], 125)

    def test_missing_run_summary_is_a_failure(self):
        plan = two_scenario_plan()

        def runner(cmd):
            # exits 0 but never writes run_summary.json
            return SimpleNamespace(returncode=0)

        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                manifest = run_plan(plan, "p.yaml", tmp, runner=runner)
            self.assertEqual(manifest["totals"]["failed"], 2)


class TestMain(unittest.TestCase):
    def test_invalid_plan_exit_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yaml"
            bad.write_text("name: x\nscenarios:\n  - name: s1\n")
            with redirect_stderr(io.StringIO()) as buf:
                code = main([str(bad), "--output-root", tmp])
            self.assertEqual(code, 2)
            self.assertIn("Invalid plan", buf.getvalue())

    def test_dry_run_with_shipped_plan(self):
        plans = Path(__file__).resolve().parent.parent / "plans"
        with tempfile.TemporaryDirectory() as tmp:
            with redirect_stdout(io.StringIO()) as buf:
                code = main([str(plans / "dataset-1k.yaml"),
                             "--output-root", tmp, "--dry-run"])
            self.assertEqual(code, 0)
            lines = [l for l in buf.getvalue().splitlines()
                     if l and not l.startswith("#")]
            self.assertEqual(len(lines), 8)
            self.assertIn("~1000 frames", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
