"""Tests for SOLO capture copy + data-folder cleanup. No Docker/ROS/Unity."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import run_scenario


def write_project(root, company="DefaultCompany", product="N3moSim"):
    ps = root / "ProjectSettings"
    ps.mkdir(parents=True)
    (ps / "ProjectSettings.asset").write_text(
        f"PlayerSettings:\n  companyName: {company}\n  productName: {product}\n"
    )
    return root


def make_data_folder(root):
    data = root / "Library" / "Application Support" / "DefaultCompany" / "N3moSim"
    (data / "Unity" / "analytics").mkdir(parents=True)
    (data / "solo" / "sequence.0").mkdir(parents=True)
    for f in ("annotation_definitions.json", "metadata.json"):
        (data / "solo" / f).write_text("{}")
    return data


def append_capture(data, start, count):
    """Perception appends frames as stepN.* to the shared solo/sequence.0,
    plus per-run root metadata."""
    seq = data / "solo" / "sequence.0"
    for s in range(start, start + count):
        for cam in ("camera_left", "camera_right"):
            (seq / f"step{s}.{cam}.png").write_text("img")
        (seq / f"step{s}.frame_data.json").write_text("{}")
    (data / f"run_metadata_{start}.json").write_text("{}")


class TestDataFolder(unittest.TestCase):
    def test_derives_path_from_project_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_project(Path(tmp) / "repo", company="Foo", product="Bar")
            got = run_scenario.unity_data_folder(project_root=root, home=Path(tmp))
            self.assertEqual((got.parent.name, got.name), ("Foo", "Bar"))


class TestCopyFrames(unittest.TestCase):
    def test_copies_frames_and_leaves_solo_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_folder(Path(tmp))
            before = run_scenario.snapshot_capture_state(data)
            append_capture(data, 0, 3)
            added = run_scenario.snapshot_capture_state(data) - before

            out = Path(tmp) / "out"
            frames = run_scenario.copy_new_frames(out, added, data)

            self.assertEqual(frames, 3)
            self.assertEqual(len(list(out.rglob("*.frame_data.json"))), 3)
            self.assertEqual(len(list(out.rglob("*.png"))), 6)  # both cameras
            self.assertTrue((out / "annotation_definitions.json").exists())
            # the live SOLO dir is untouched: frames still there for Perception
            self.assertEqual(
                len(list((data / "solo" / "sequence.0").glob("*.frame_data.json"))), 3)

    def test_two_scenarios_each_copy_only_their_own_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_folder(Path(tmp))
            # scenario 1
            b1 = run_scenario.snapshot_capture_state(data)
            append_capture(data, 0, 3)
            f1 = run_scenario.copy_new_frames(
                Path(tmp) / "s1", run_scenario.snapshot_capture_state(data) - b1, data)
            # scenario 2 appends to the SAME solo (solo never touched between runs)
            b2 = run_scenario.snapshot_capture_state(data)
            append_capture(data, 3, 4)
            f2 = run_scenario.copy_new_frames(
                Path(tmp) / "s2", run_scenario.snapshot_capture_state(data) - b2, data)
            self.assertEqual((f1, f2), (3, 4))
            self.assertEqual(len(list((Path(tmp) / "s1").rglob("*.frame_data.json"))), 3)
            self.assertEqual(len(list((Path(tmp) / "s2").rglob("*.frame_data.json"))), 4)

    def test_wait_raises_when_perception_wrote_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_folder(Path(tmp))
            before = run_scenario.snapshot_capture_state(data)
            with self.assertRaisesRegex(RuntimeError, "no frames"):
                run_scenario.wait_for_capture(data, before, timeout_s=1, settle_s=0)


class TestCleanup(unittest.TestCase):
    def test_cleanup_removes_capture_leaves_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_folder(Path(tmp))
            append_capture(data, 0, 5)
            (data / "solo_1").mkdir()  # a second solo, if Perception incremented

            removed = run_scenario.cleanup_data_folder(data)

            self.assertGreaterEqual(removed, 2)  # solo, solo_1, run_metadata json
            self.assertFalse((data / "solo").exists())
            self.assertFalse((data / "solo_1").exists())
            self.assertEqual(list(data.glob("*.json")), [])
            # editor telemetry is left alone
            self.assertTrue((data / "Unity").exists())


if __name__ == "__main__":
    unittest.main()
