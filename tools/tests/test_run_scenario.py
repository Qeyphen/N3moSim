"""Tests for SOLO frame harvest. Filesystem only, no Docker/ROS/Unity."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import run_scenario


def make_solo(root, name="solo"):
    """A session SOLO dir with schema definitions and an empty sequence.0,
    laid out under the real Unity data-folder path the globber scans."""
    base = Path(root) / "Library" / "Application Support" / "Co" / "Proj" / name
    (base / "sequence.0").mkdir(parents=True)
    for f in ("annotation_definitions.json", "metadata.json"):
        (base / f).write_text("{}")
    return base


def append_steps(solo, start, count):
    """Append frames as Perception does: stepN.<cam>.png + stepN.frame_data.json."""
    seq = solo / "sequence.0"
    for s in range(start, start + count):
        for cam in ("camera_left", "camera_right"):
            (seq / f"step{s}.{cam}.png").write_text("img")
        (seq / f"step{s}.frame_data.json").write_text("{}")


class TestHarvest(unittest.TestCase):
    def test_harvest_moves_frames_keeps_sequence_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            solo = make_solo(tmp)
            before = run_scenario.snapshot_step_files(home=tmp)
            append_steps(solo, 0, 3)
            new = run_scenario.snapshot_step_files(home=tmp) - before

            out = Path(tmp) / "out"
            run_scenario.harvest_step_files(out, new, home=tmp)

            # frames moved out, both cameras preserved, definitions copied
            self.assertEqual(len(list(out.rglob("*.frame_data.json"))), 3)
            self.assertEqual(len(list(out.rglob("*.png"))), 6)
            self.assertTrue((out / "annotation_definitions.json").exists())
            # the live sequence dir survives, emptied of harvested frames
            self.assertTrue((solo / "sequence.0").is_dir())
            self.assertEqual(list((solo / "sequence.0").glob("step*")), [])

    def test_two_scenarios_split_by_new_steps(self):
        with tempfile.TemporaryDirectory() as tmp:
            solo = make_solo(tmp)
            # scenario 1 appends steps 0..2, scenario 2 appends 3..5 (same seq.0)
            b1 = run_scenario.snapshot_step_files(home=tmp)
            append_steps(solo, 0, 3)
            run_scenario.harvest_step_files(
                Path(tmp) / "s1", run_scenario.snapshot_step_files(home=tmp) - b1, home=tmp)
            b2 = run_scenario.snapshot_step_files(home=tmp)
            append_steps(solo, 3, 3)
            run_scenario.harvest_step_files(
                Path(tmp) / "s2", run_scenario.snapshot_step_files(home=tmp) - b2, home=tmp)

            self.assertEqual(len(list((Path(tmp) / "s1").rglob("*.frame_data.json"))), 3)
            self.assertEqual(len(list((Path(tmp) / "s2").rglob("*.frame_data.json"))), 3)

    def test_ignores_pre_existing_residue(self):
        with tempfile.TemporaryDirectory() as tmp:
            solo = make_solo(tmp)
            append_steps(solo, 0, 2)  # stale residue from an earlier session
            before = run_scenario.snapshot_step_files(home=tmp)
            append_steps(solo, 2, 3)  # this run's frames
            new = run_scenario.snapshot_step_files(home=tmp) - before
            run_scenario.harvest_step_files(Path(tmp) / "out", new, home=tmp)
            # only the run's own 3 frames are harvested, not the 2 residue
            self.assertEqual(len(list((Path(tmp) / "out").rglob("*.frame_data.json"))), 3)

    def test_empty_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "No new SOLO frames"):
                run_scenario.harvest_step_files(Path(tmp) / "out", set())


if __name__ == "__main__":
    unittest.main()
