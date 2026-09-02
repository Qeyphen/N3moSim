"""Tests for SOLO capture harvest + data-folder restore. No Docker/ROS/Unity."""

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
    """A Unity data folder with the editor-telemetry subdir and an empty solo."""
    data = root / "Library" / "Application Support" / "DefaultCompany" / "N3moSim"
    (data / "Unity" / "analytics").mkdir(parents=True)
    (data / "solo").mkdir(parents=True)
    return data


def append_capture(data, start, count, extra_root_json=True):
    """Simulate a Perception recording: frames as stepN.* in solo/sequence.0
    plus per-run root metadata, as the real rig writes them."""
    seq = data / "solo" / "sequence.0"
    seq.mkdir(parents=True, exist_ok=True)
    for name in ("annotation_definitions.json", "metadata.json"):
        (data / "solo" / name).write_text("{}")
    for s in range(start, start + count):
        for cam in ("camera_left", "camera_right"):
            (seq / f"step{s}.{cam}.png").write_text("img")
        (seq / f"step{s}.frame_data.json").write_text("{}")
    if extra_root_json:
        (data / f"run_metadata_{start}.json").write_text("{}")


class TestDataFolder(unittest.TestCase):
    def test_derives_path_from_project_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = write_project(Path(tmp) / "repo", company="Foo", product="Bar")
            got = run_scenario.unity_data_folder(project_root=root, home=Path(tmp))
            self.assertEqual(got.name, "Bar")
            self.assertEqual(got.parent.name, "Foo")

    def test_snapshot_excludes_telemetry(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_folder(Path(tmp))
            (data / "run_metadata_x.json").write_text("{}")
            snap = run_scenario.snapshot_capture_state(data)
            names = {p.name for p in snap}
            self.assertIn("solo", names)
            self.assertIn("run_metadata_x.json", names)
            self.assertNotIn("Unity", names)
            self.assertNotIn("analytics", names)


class TestHarvestRestore(unittest.TestCase):
    def test_harvest_moves_frames_and_restores_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_folder(Path(tmp))
            before = run_scenario.snapshot_capture_state(data)
            append_capture(data, 0, 3)  # the run writes 3 frames + metadata

            run_scenario.wait_for_capture(data, before, timeout_s=2, settle_s=0)
            out = Path(tmp) / "out"
            frames = run_scenario.harvest_and_restore(out, data, before)

            self.assertEqual(frames, 3)
            self.assertEqual(len(list(out.rglob("*.frame_data.json"))), 3)
            self.assertEqual(len(list(out.rglob("*.png"))), 6)  # both cameras
            self.assertTrue((out / "annotation_definitions.json").exists())
            # data folder is byte-for-byte back to before
            self.assertEqual(run_scenario.snapshot_capture_state(data), before)

    def test_second_run_independent_and_restores(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_folder(Path(tmp))
            # run 1
            b1 = run_scenario.snapshot_capture_state(data)
            append_capture(data, 0, 3)
            run_scenario.harvest_and_restore(Path(tmp) / "s1", data, b1)
            self.assertEqual(run_scenario.snapshot_capture_state(data), b1)
            # run 2 appends more steps to the same solo (Perception behaviour)
            b2 = run_scenario.snapshot_capture_state(data)
            append_capture(data, 3, 4)
            f2 = run_scenario.harvest_and_restore(Path(tmp) / "s2", data, b2)
            self.assertEqual(f2, 4)
            self.assertEqual(run_scenario.snapshot_capture_state(data), b2)

    def test_wait_raises_when_perception_wrote_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            data = make_data_folder(Path(tmp))
            before = run_scenario.snapshot_capture_state(data)
            with self.assertRaisesRegex(RuntimeError, "no frames"):
                run_scenario.wait_for_capture(data, before, timeout_s=1, settle_s=0)


if __name__ == "__main__":
    unittest.main()
