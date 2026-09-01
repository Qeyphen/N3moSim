#!/usr/bin/env python3
"""Load and validate dataset generation plans for run_dataset_plan.py.

A plan is a YAML file restricted to a small subset (parsed here with the
stdlib only, no PyYAML dependency): nested mappings, lists of mappings,
scalars (int, float, bool, null, strings), full-line and trailing comments.
Indentation is 2 spaces per level.

Each scenario maps directly onto the CLI arguments of tools/run_scenario.py
(underscores instead of dashes). `defaults` holds values shared by every
scenario; a scenario overrides them freely. `--output` is not part of the
plan: the orchestrator derives one output folder per scenario.

Plan schema:

    name: dataset-1k             # plan name (used in the manifest)
    defaults:                    # any scenario key except name/scene_seed
      duration: 25               # seconds of capture per run
      capture_hz: 5              # DatasetCaptureScheduler rate in Unity
      track_count: 18
      area_type: coastal         # lake | coastal | harbor | open_sea
      occupied_fraction: 0.8
    scenarios:
      - name: lake-clear-day     # unique scenario name
        scene_seed: 101          # required, >= 1 for reproducibility
        area_type: lake
        weather: clear           # clear | cloudy | overcast | foggy | stormy
        time_of_day: 11.0        # hour 0-24
        fog: 0.3                 # optional 0-1 overrides: fog, wave, wind,
        rain: 0.1                # cloudiness, rain
        type_counts:             # optional exact object mix
          sailboat: 6
          kayak: 2
"""

from __future__ import annotations

import os

AREA_TYPES = ("lake", "coastal", "harbor", "open_sea")
WEATHER_PRESETS = ("clear", "cloudy", "overcast", "foggy", "stormy")
ENV_OVERRIDES = ("fog", "wave", "wind", "cloudiness", "rain")

# run_scenario.py's own default, used only to estimate plan totals when a
# scenario does not pin capture_hz explicitly.
FALLBACK_CAPTURE_HZ = 8.0

# Scenario keys -> validation rule. Mirrors tools/run_scenario.py arguments.
_FLOAT_MIN_EXCL = "float>0"
_FLOAT_UNIT = "float0..1"
_FLOAT_POS = "float>=0"
_INT_MIN_1 = "int>=1"

SCENARIO_KEYS = {
    "duration": _FLOAT_MIN_EXCL,
    "capture_hz": _FLOAT_MIN_EXCL,
    "waypoint_period": _FLOAT_MIN_EXCL,
    "track_count": _INT_MIN_1,
    "area_type": "area_type",
    "occupied_fraction": _FLOAT_UNIT,
    "scene_seed": _INT_MIN_1,
    "min_static_clearance": _FLOAT_POS,
    "min_dynamic_clearance": _FLOAT_POS,
    "record_start_delay": _FLOAT_POS,
    "time_of_day": "time_of_day",
    "weather": "weather",
    "fog": _FLOAT_UNIT,
    "wave": _FLOAT_UNIT,
    "wind": _FLOAT_UNIT,
    "cloudiness": _FLOAT_UNIT,
    "rain": _FLOAT_UNIT,
    "type_counts": "type_counts",
}

# Keys run_scenario.py requires; every scenario must resolve them, either
# directly or through `defaults` (scene_seed must be per-scenario).
REQUIRED_KEYS = ("duration", "time_of_day", "weather", "scene_seed")


class PlanError(Exception):
    """Invalid plan file (syntax or content)."""


# ---------------------------------------------------------------------------
# Minimal YAML-subset parser (stdlib only)
# ---------------------------------------------------------------------------

def _strip_comment(line):
    """Remove a trailing comment, respecting single/double quoted strings."""
    in_single = in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            if i == 0 or line[i - 1] in " \t":
                return line[:i]
    return line


def _parse_scalar(text):
    text = text.strip()
    if text in ("", "~", "null"):
        return None
    if (text.startswith('"') and text.endswith('"') and len(text) >= 2) or (
        text.startswith("'") and text.endswith("'") and len(text) >= 2
    ):
        return text[1:-1]
    low = text.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def _tokenize(text):
    """Return a list of (indent, content, lineno) for meaningful lines."""
    tokens = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise PlanError(f"line {lineno}: tabs are not allowed in indentation")
        line = _strip_comment(raw).rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        tokens.append((indent, line.strip(), lineno))
    return tokens


def _parse_block(tokens, pos, indent):
    """Parse tokens starting at pos, all at exactly `indent`. Returns (value, pos)."""
    if pos >= len(tokens):
        return None, pos
    if tokens[pos][1].startswith("- ") or tokens[pos][1] == "-":
        return _parse_list(tokens, pos, indent)
    return _parse_mapping(tokens, pos, indent)


def _parse_list(tokens, pos, indent):
    items = []
    while pos < len(tokens):
        tok_indent, content, lineno = tokens[pos]
        if tok_indent < indent:
            break
        if tok_indent > indent:
            raise PlanError(f"line {lineno}: unexpected indentation")
        if not (content.startswith("- ") or content == "-"):
            break
        inner = content[2:].strip() if content.startswith("- ") else ""
        if inner and ":" in inner:
            # Mapping item: inline first key, then deeper-indented keys.
            # The inline key virtually sits at indent + 2.
            virtual = (indent + 2, inner, lineno)
            sub_tokens = [virtual]
            pos += 1
            while pos < len(tokens) and tokens[pos][0] > indent:
                sub_tokens.append(tokens[pos])
                pos += 1
            value, consumed = _parse_mapping(sub_tokens, 0, indent + 2)
            if consumed != len(sub_tokens):
                bad = sub_tokens[consumed]
                raise PlanError(f"line {bad[2]}: unexpected indentation")
            items.append(value)
        elif inner:
            items.append(_parse_scalar(inner))
            pos += 1
        else:
            raise PlanError(f"line {lineno}: empty list items are not supported")
    return items, pos


def _parse_mapping(tokens, pos, indent):
    mapping = {}
    while pos < len(tokens):
        tok_indent, content, lineno = tokens[pos]
        if tok_indent < indent:
            break
        if tok_indent > indent:
            raise PlanError(f"line {lineno}: unexpected indentation")
        if content.startswith("- "):
            break
        if ":" not in content:
            raise PlanError(f"line {lineno}: expected 'key: value', got '{content}'")
        key, _, rest = content.partition(":")
        key = key.strip()
        rest = rest.strip()
        if key in mapping:
            raise PlanError(f"line {lineno}: duplicate key '{key}'")
        if rest:
            mapping[key] = _parse_scalar(rest)
            pos += 1
        else:
            pos += 1
            if pos < len(tokens) and tokens[pos][0] > indent:
                value, pos = _parse_block(tokens, pos, tokens[pos][0])
            else:
                value = None
            mapping[key] = value
    return mapping, pos


def load_yaml_subset(text):
    """Parse a YAML-subset document into Python dicts/lists/scalars."""
    tokens = _tokenize(text)
    if not tokens:
        return {}
    value, pos = _parse_block(tokens, 0, tokens[0][0])
    if pos != len(tokens):
        raise PlanError(f"line {tokens[pos][2]}: trailing content not parsed")
    return value


# ---------------------------------------------------------------------------
# Plan model + validation
# ---------------------------------------------------------------------------

class Scenario:
    """One run of tools/run_scenario.py: name + resolved CLI arguments."""

    def __init__(self, name, args):
        self.name = name
        self.args = args

    @property
    def estimated_frames(self):
        hz = self.args.get("capture_hz", FALLBACK_CAPTURE_HZ)
        return int(round(self.args["duration"] * hz))


class Plan:
    def __init__(self, name, scenarios):
        self.name = name
        self.scenarios = scenarios

    @property
    def total_estimated_frames(self):
        return sum(s.estimated_frames for s in self.scenarios)

    @property
    def total_capture_s(self):
        return sum(s.args["duration"] for s in self.scenarios)


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_value(key, rule, value, ctx):
    if rule == _FLOAT_MIN_EXCL:
        if not _is_number(value) or value <= 0:
            raise PlanError(f"{ctx}: '{key}' must be a number > 0, got {value!r}")
        return float(value)
    if rule == _FLOAT_POS:
        if not _is_number(value) or value < 0:
            raise PlanError(f"{ctx}: '{key}' must be a number >= 0, got {value!r}")
        return float(value)
    if rule == _FLOAT_UNIT:
        if not _is_number(value) or not 0 <= value <= 1:
            raise PlanError(f"{ctx}: '{key}' must be within [0, 1], got {value!r}")
        return float(value)
    if rule == _INT_MIN_1:
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise PlanError(f"{ctx}: '{key}' must be an integer >= 1, got {value!r}")
        return value
    if rule == "area_type":
        if value not in AREA_TYPES:
            raise PlanError(
                f"{ctx}: 'area_type' must be one of {', '.join(AREA_TYPES)}, "
                f"got {value!r}"
            )
        return value
    if rule == "weather":
        if value not in WEATHER_PRESETS:
            raise PlanError(
                f"{ctx}: 'weather' must be one of {', '.join(WEATHER_PRESETS)}, "
                f"got {value!r}"
            )
        return value
    if rule == "time_of_day":
        if not _is_number(value) or not 0 <= value <= 24:
            raise PlanError(f"{ctx}: 'time_of_day' must be within [0, 24], got {value!r}")
        return float(value)
    if rule == "type_counts":
        if not isinstance(value, dict) or not value:
            raise PlanError(f"{ctx}: 'type_counts' must be a non-empty mapping")
        for track_type, count in value.items():
            if not isinstance(count, int) or isinstance(count, bool) or count < 0:
                raise PlanError(
                    f"{ctx}: 'type_counts.{track_type}' must be an integer >= 0, "
                    f"got {count!r}"
                )
        return dict(value)
    raise AssertionError(f"unknown rule {rule}")  # pragma: no cover


def _validate_mapping(raw, ctx, forbidden=()):
    """Validate a defaults/scenario mapping against SCENARIO_KEYS."""
    args = {}
    for key, value in raw.items():
        if key in ("name",):
            continue
        if key in forbidden:
            raise PlanError(f"{ctx}: '{key}' is not allowed here")
        if key not in SCENARIO_KEYS:
            known = ", ".join(sorted(SCENARIO_KEYS))
            raise PlanError(f"{ctx}: unknown key '{key}' (known keys: {known})")
        if value is None:
            continue
        args[key] = _validate_value(key, SCENARIO_KEYS[key], value, ctx)
    return args


def _build_scenario(raw, index, defaults):
    if not isinstance(raw, dict):
        raise PlanError(f"scenario {index}: must be a mapping")
    ctx = f"scenario {index} ({raw.get('name', 'unnamed')})"

    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise PlanError(f"scenario {index}: missing 'name'")

    args = dict(defaults)
    args.update(_validate_mapping(raw, ctx))

    for key in REQUIRED_KEYS:
        if key not in args:
            raise PlanError(f"{ctx}: missing '{key}' (set it here or in 'defaults')")

    return Scenario(name=name, args=args)


def build_plan(data):
    """Validate a parsed plan document and return a Plan."""
    if not isinstance(data, dict):
        raise PlanError("plan root must be a mapping")

    name = data.get("name")
    if not isinstance(name, str) or not name:
        raise PlanError("plan: missing 'name'")

    defaults_raw = data.get("defaults") or {}
    if not isinstance(defaults_raw, dict):
        raise PlanError("plan: 'defaults' must be a mapping")
    defaults = _validate_mapping(defaults_raw, "defaults", forbidden=("scene_seed",))

    raw_scenarios = data.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise PlanError("plan: 'scenarios' must be a non-empty list")

    scenarios = [
        _build_scenario(raw, i, defaults)
        for i, raw in enumerate(raw_scenarios)
    ]

    names = [s.name for s in scenarios]
    if len(names) != len(set(names)):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise PlanError(f"plan: duplicate scenario names: {', '.join(dupes)}")
    seeds = [s.args["scene_seed"] for s in scenarios]
    if len(seeds) != len(set(seeds)):
        raise PlanError("plan: scene_seed values must be unique for traceability")

    return Plan(name=name, scenarios=scenarios)


def load_plan(path):
    """Load, parse and validate a plan file."""
    if not os.path.isfile(path):
        raise PlanError(f"plan file not found: {path}")
    with open(path) as f:
        text = f.read()
    return build_plan(load_yaml_subset(text))
