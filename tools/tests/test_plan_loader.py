"""Tests for the YAML-subset parser and plan validation. No Docker/ROS needed."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from plan_loader import (
    PlanError,
    build_plan,
    load_plan,
    load_yaml_subset,
)

PLANS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "plans")


def minimal_plan(**overrides):
    """A valid plan document as a dict, with optional top-level overrides."""
    doc = {
        "name": "test",
        "scenarios": [
            {
                "name": "s1",
                "duration": 25,
                "time_of_day": 11.0,
                "weather": "clear",
                "scene_seed": 1,
            }
        ],
    }
    doc.update(overrides)
    return doc


class TestYamlSubsetParser(unittest.TestCase):
    def test_scalars(self):
        doc = load_yaml_subset(
            "a: 1\nb: 2.5\nc: true\nd: false\ne: hello\nf: 'quoted'\n"
            'g: "double"\nh: ~\n'
        )
        self.assertEqual(doc, {
            "a": 1, "b": 2.5, "c": True, "d": False,
            "e": "hello", "f": "quoted", "g": "double", "h": None,
        })
        self.assertIsInstance(doc["a"], int)
        self.assertIsInstance(doc["b"], float)

    def test_nested_mapping(self):
        doc = load_yaml_subset("outer:\n  inner: 3\n  other: x\ntop: 1\n")
        self.assertEqual(doc, {"outer": {"inner": 3, "other": "x"}, "top": 1})

    def test_list_of_mappings(self):
        doc = load_yaml_subset(
            "items:\n"
            "  - name: a\n"
            "    value: 1\n"
            "  - name: b\n"
            "    value: 2\n"
        )
        self.assertEqual(doc["items"], [
            {"name": "a", "value": 1},
            {"name": "b", "value": 2},
        ])

    def test_list_of_scalars(self):
        doc = load_yaml_subset("xs:\n  - 1\n  - two\n")
        self.assertEqual(doc["xs"], [1, "two"])

    def test_comments_stripped(self):
        doc = load_yaml_subset(
            "# full line comment\n"
            "a: 1  # trailing comment\n"
            "b: 'kept # inside quotes'\n"
        )
        self.assertEqual(doc, {"a": 1, "b": "kept # inside quotes"})

    def test_empty_document(self):
        self.assertEqual(load_yaml_subset("# only comments\n\n"), {})

    def test_tab_indent_rejected(self):
        with self.assertRaises(PlanError):
            load_yaml_subset("a:\n\tb: 1\n")

    def test_duplicate_key_rejected(self):
        with self.assertRaises(PlanError):
            load_yaml_subset("a: 1\na: 2\n")

    def test_bad_line_rejected(self):
        with self.assertRaises(PlanError):
            load_yaml_subset("just some words\n")


class TestPlanValidation(unittest.TestCase):
    def test_minimal_plan_ok(self):
        plan = build_plan(minimal_plan())
        self.assertEqual(plan.name, "test")
        self.assertEqual(len(plan.scenarios), 1)
        self.assertEqual(plan.scenarios[0].args["scene_seed"], 1)

    def test_defaults_applied_and_overridable(self):
        doc = minimal_plan(defaults={"track_count": 20, "capture_hz": 5})
        doc["scenarios"][0]["capture_hz"] = 10
        plan = build_plan(doc)
        self.assertEqual(plan.scenarios[0].args["track_count"], 20)
        self.assertEqual(plan.scenarios[0].args["capture_hz"], 10.0)

    def test_required_keys_resolved_via_defaults(self):
        doc = minimal_plan(defaults={"duration": 30, "weather": "cloudy",
                                     "time_of_day": 9.0})
        doc["scenarios"] = [{"name": "s1", "scene_seed": 1}]
        plan = build_plan(doc)
        self.assertEqual(plan.scenarios[0].args["duration"], 30.0)
        self.assertEqual(plan.scenarios[0].args["weather"], "cloudy")

    def test_missing_required_key(self):
        doc = minimal_plan()
        del doc["scenarios"][0]["weather"]
        with self.assertRaisesRegex(PlanError, "missing 'weather'"):
            build_plan(doc)

    def test_unknown_key_rejected(self):
        doc = minimal_plan()
        doc["scenarios"][0]["target_images"] = 100
        with self.assertRaisesRegex(PlanError, "unknown key 'target_images'"):
            build_plan(doc)

    def test_scene_seed_forbidden_in_defaults(self):
        doc = minimal_plan(defaults={"scene_seed": 7})
        with self.assertRaisesRegex(PlanError, "scene_seed"):
            build_plan(doc)

    def test_scene_seed_required_and_positive(self):
        doc = minimal_plan()
        doc["scenarios"][0]["scene_seed"] = 0
        with self.assertRaisesRegex(PlanError, "scene_seed"):
            build_plan(doc)
        del doc["scenarios"][0]["scene_seed"]
        with self.assertRaisesRegex(PlanError, "scene_seed"):
            build_plan(doc)

    def test_bad_area_type(self):
        doc = minimal_plan()
        doc["scenarios"][0]["area_type"] = "ocean"
        with self.assertRaisesRegex(PlanError, "area_type"):
            build_plan(doc)

    def test_bad_weather(self):
        doc = minimal_plan()
        doc["scenarios"][0]["weather"] = "sunny"
        with self.assertRaisesRegex(PlanError, "weather"):
            build_plan(doc)

    def test_time_of_day_range(self):
        doc = minimal_plan()
        doc["scenarios"][0]["time_of_day"] = 25
        with self.assertRaisesRegex(PlanError, "time_of_day"):
            build_plan(doc)

    def test_env_override_range(self):
        doc = minimal_plan()
        doc["scenarios"][0]["fog"] = 1.5
        with self.assertRaisesRegex(PlanError, "fog"):
            build_plan(doc)
        doc["scenarios"][0]["fog"] = 0.7
        plan = build_plan(doc)
        self.assertEqual(plan.scenarios[0].args["fog"], 0.7)

    def test_type_counts_validated(self):
        doc = minimal_plan()
        doc["scenarios"][0]["type_counts"] = {"sailboat": 6, "kayak": 2}
        plan = build_plan(doc)
        self.assertEqual(plan.scenarios[0].args["type_counts"],
                         {"sailboat": 6, "kayak": 2})
        doc["scenarios"][0]["type_counts"] = {"sailboat": -1}
        with self.assertRaisesRegex(PlanError, "type_counts"):
            build_plan(doc)

    def test_duration_must_be_positive(self):
        doc = minimal_plan()
        doc["scenarios"][0]["duration"] = 0
        with self.assertRaisesRegex(PlanError, "duration"):
            build_plan(doc)

    def test_duplicate_scenario_names(self):
        doc = minimal_plan()
        doc["scenarios"] = [
            doc["scenarios"][0],
            dict(doc["scenarios"][0], scene_seed=2),
        ]
        with self.assertRaisesRegex(PlanError, "duplicate scenario names"):
            build_plan(doc)

    def test_duplicate_seeds(self):
        doc = minimal_plan()
        doc["scenarios"] = [
            doc["scenarios"][0],
            dict(doc["scenarios"][0], name="s2"),
        ]
        with self.assertRaisesRegex(PlanError, "scene_seed values must be unique"):
            build_plan(doc)

    def test_type_counts_force_track_count(self):
        doc = minimal_plan(defaults={"track_count": 18})
        doc["scenarios"][0]["type_counts"] = {"kayak": 3, "swimmer": 2}
        plan = build_plan(doc)
        self.assertEqual(plan.scenarios[0].args["track_count"], 5)

    def test_estimated_frames(self):
        doc = minimal_plan(defaults={"capture_hz": 5})
        plan = build_plan(doc)
        # 25 s at 5 Hz -> 125 frames
        self.assertEqual(plan.scenarios[0].estimated_frames, 125)
        self.assertEqual(plan.total_estimated_frames, 125)

    def test_missing_file(self):
        with self.assertRaisesRegex(PlanError, "not found"):
            load_plan("/nonexistent/plan.yaml")


class TestDataset1kPlan(unittest.TestCase):
    """The shipped reference plan must itself be valid and hit its targets."""

    def setUp(self):
        self.plan = load_plan(os.path.join(PLANS_DIR, "dataset-1k.yaml"))

    def test_totals(self):
        self.assertEqual(self.plan.total_estimated_frames, 1000)
        self.assertAlmostEqual(self.plan.total_capture_s, 200.0)

    def test_covers_all_area_types(self):
        areas = {s.args["area_type"] for s in self.plan.scenarios}
        self.assertEqual(areas, {"lake", "coastal", "harbor", "open_sea"})

    def test_covers_all_weather_presets(self):
        weathers = {s.args["weather"] for s in self.plan.scenarios}
        self.assertEqual(
            weathers, {"clear", "cloudy", "overcast", "foggy", "stormy"})

    def test_day_and_dusk(self):
        times = [s.args["time_of_day"] for s in self.plan.scenarios]
        self.assertTrue(any(t < 15 for t in times), "no daytime scenario")
        self.assertTrue(any(t >= 18 for t in times), "no dusk scenario")

    def test_all_scenarios_seeded(self):
        seeds = [s.args["scene_seed"] for s in self.plan.scenarios]
        self.assertTrue(all(s >= 1 for s in seeds))
        self.assertEqual(len(seeds), len(set(seeds)))


if __name__ == "__main__":
    unittest.main()
