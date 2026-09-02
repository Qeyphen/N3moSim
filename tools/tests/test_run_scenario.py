"""Tests for SOLO harvest/purge. Filesystem only, no Docker/ROS/Unity."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import run_scenario


def make_solo(root, name, camera_key, steps):
    """Create a one-camera SOLO dir with root definitions + a sequence.0."""
    solo = Path(root) / name
    (solo / "sequence.0").mkdir(parents=True)
    for f in ("annotation_definitions.json", "metadata.json"):
        (solo / f).write_text("{}")
    (solo / f"run_metadata_{camera_key}.json").write_text("{}")
    for s in range(steps):
        (solo / "sequence.0" / f"step{s}.{camera_key}.png").write_text("img")
        (solo / "sequence.0" / f"step{s}.frame_data.json").write_text("{}")
    return solo


class TestHarvest(unittest.TestCase):
    def test_merges_two_cameras_into_separate_sequences(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            left = make_solo(tmp, "solo", "povcamera_left", 3)
            right = make_solo(tmp, "solo_1", "povcamera_right", 3)

            n = run_scenario.harvest_solo_dirs(out, [left, right])

            self.assertEqual(n, 2)
            self.assertTrue((out / "sequence.0").is_dir())
            self.assertTrue((out / "sequence.1").is_dir())
            # both cameras' frames survive
            self.assertEqual(len(list(out.rglob("*.frame_data.json"))), 6)
            self.assertEqual(len(list(out.rglob("*.png"))), 6)
            # duplicate definition kept once, per-camera metadata both kept
            self.assertTrue((out / "annotation_definitions.json").exists())
            self.assertTrue((out / "run_metadata_povcamera_left.json").exists())
            self.assertTrue((out / "run_metadata_povcamera_right.json").exists())
            # source dirs are gone
            self.assertFalse(left.exists())
            self.assertFalse(right.exists())

    def test_empty_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(RuntimeError, "No SOLO"):
                run_scenario.harvest_solo_dirs(Path(tmp) / "out", [])

    def test_name_collision_is_namespaced_not_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out"
            a = make_solo(tmp, "solo", "cam", 1)
            b = make_solo(tmp, "solo_1", "cam", 1)  # identical camera key
            run_scenario.harvest_solo_dirs(out, [a, b])
            # same-named per-step files land in distinct sequences, none lost
            self.assertEqual(len(list(out.rglob("step0.cam.png"))), 2)


class TestDiscovery(unittest.TestCase):
    def test_find_solo_dirs_scopes_to_home(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp) / "Library" / "Application Support" / "Co" / "Proj"
            base.mkdir(parents=True)
            (base / "solo").mkdir()
            (base / "solo_1").mkdir()
            (base / "other").mkdir()
            found = {p.name for p in run_scenario.find_solo_dirs(home=tmp)}
            self.assertEqual(found, {"solo", "solo_1"})


if __name__ == "__main__":
    unittest.main()
