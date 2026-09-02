"""Tests for SOLO sequence harvest. Filesystem only, no Docker/ROS/Unity."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import run_scenario


def make_solo(root, name="solo"):
    """A session SOLO dir with schema definitions and no sequences yet."""
    solo = Path(root) / name
    solo.mkdir(parents=True)
    for f in ("annotation_definitions.json", "metadata.json"):
        (solo / f).write_text("{}")
    return solo


def add_sequence(solo, index, frames=3):
    """Append a sequence.N with both stereo cameras, as Perception would."""
    seq = solo / f"sequence.{index}"
    seq.mkdir()
    for s in range(frames):
        for cam in ("camera_left", "camera_right"):
            (seq / f"step{s}.{cam}.png").write_text("img")
        (seq / f"step{s}.frame_data.json").write_text("{}")
    return seq


class TestHarvest(unittest.TestCase):
    def test_moves_new_sequence_keeps_solo_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            solo = make_solo(tmp)
            new = add_sequence(solo, 0)

            run_scenario.harvest_sequences(out, [new])

            # sequence moved out, both cameras preserved
            self.assertTrue((out / "sequence.0").is_dir())
            self.assertEqual(len(list(out.rglob("*.frame_data.json"))), 3)
            self.assertEqual(len(list(out.rglob("*.png"))), 6)
            # definitions copied, not moved
            self.assertTrue((out / "annotation_definitions.json").exists())
            self.assertTrue((solo / "annotation_definitions.json").exists())
            # the SOLO dir survives for the ongoing session
            self.assertTrue(solo.is_dir())
            self.assertFalse(new.exists())

    def test_second_scenario_only_takes_its_own_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            # snapshot_sequences globs the real Unity data-folder layout
            solo = make_solo(Path(tmp) / "Library" / "Application Support" / "Co" / "Proj")
            # scenario 1
            before1 = run_scenario.snapshot_sequences(home=tmp)
            add_sequence(solo, 0)
            got1 = sorted(run_scenario.snapshot_sequences(home=tmp) - before1)
            run_scenario.harvest_sequences(Path(tmp) / "s1", got1)
            # scenario 2: Perception appends sequence.1 to the SAME solo dir
            before2 = run_scenario.snapshot_sequences(home=tmp)
            add_sequence(solo, 1)
            got2 = sorted(run_scenario.snapshot_sequences(home=tmp) - before2)
            run_scenario.harvest_sequences(Path(tmp) / "s2", got2)

            self.assertEqual(len(list((Path(tmp) / "s1").rglob("*.frame_data.json"))), 3)
            self.assertEqual(len(list((Path(tmp) / "s2").rglob("*.frame_data.json"))), 3)

    def test_empty_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "No new SOLO sequence"):
                run_scenario.harvest_sequences(Path(tmp) / "out", [])


class TestDiscovery(unittest.TestCase):
    def test_snapshot_sequences_scopes_to_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Library" / "Application Support" / "Co" / "Proj"
            solo = base / "solo"
            solo.mkdir(parents=True)
            add_sequence(solo, 0)
            add_sequence(solo, 1)
            found = {p.name for p in run_scenario.snapshot_sequences(home=tmp)}
            self.assertEqual(found, {"sequence.0", "sequence.1"})


if __name__ == "__main__":
    unittest.main()
