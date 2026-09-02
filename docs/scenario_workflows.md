# Scenario Workflows

## Recommended Entry Points

Use one of these:

- `tools/run_scenario.py`
  - one explicit scene run
- `tools/run_dataset_plan.py`
  - a full dataset: one `run_scenario.py` run per scenario listed in a YAML plan

## `tools/run_scenario.py`

## Purpose

Runs one deterministic scene once.

It:

1. starts `ros_bridge` and `scenario`
2. configures the scenario generator
3. generates one scenario YAML from the chosen scene seed
4. applies one explicit environment
5. publishes capture rate and scenario metadata
6. runs `dataset_sweep` for the requested duration
7. moves the produced SOLO contents into the requested output directory
8. writes `scene_spec.json` and `run_summary.json`

Use this when you want:

- exact weather
- exact time of day
- exact duration
- exact output folder
- no repeated runs

## Command

```bash
python3 tools/run_scenario.py \
  --output /absolute/path/to/output_dir \
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
```

## Arguments

### Required

- `--output`
  - directory that will receive the run output
  - must be empty, or the script exits
- `--duration`
  - requested run duration in seconds
- `--time-of-day`
  - hour in Unity time, `0..24`
- `--weather`
  - preset weather name
  - allowed: `clear`, `cloudy`, `overcast`, `foggy`, `stormy`

### Scenario layout and traffic

- `--scene-seed`
  - deterministic seed for procedural scene generation
  - same seed + same generation args => same spawned trajectories/layout
  - `0` means use the current timestamp
- `--track-count`
  - number of generated tracks
- `--area-type`
  - traffic preset
  - allowed: `lake`, `coastal`, `harbor`, `open_sea`
- `--type-counts-json`
  - exact object mix override
  - example:

```bash
--type-counts-json '{"sailboat":7,"motorboat":4,"fishing_boat":2,"ferry":1}'
```

### Capture and sweep

- `--capture-hz`
  - requested capture frequency in Hz
- `--waypoint-period`
  - seconds between ego target changes during the sweep
- `--record-start-delay`
  - wait after traffic is ready before recording starts

### Safety and density bias

- `--occupied-fraction`
  - fraction of generated tracks biased into the ego forward view cone
  - this improves the probability of visible traffic
  - this is not a hard guarantee that the same fraction of frames contain objects
- `--min-static-clearance`
  - minimum clearance from static obstacles and land
- `--min-dynamic-clearance`
  - minimum clearance from dynamic obstacles

### Optional explicit environment overrides

These are all `0..1`:

- `--fog`
- `--wave`
- `--wind`
- `--cloudiness`
- `--rain`

How these work:

- the weather preset is applied first
- explicit overrides then replace individual channels

Example:

- `--weather foggy --fog 0.45 --wave 0.9`
  - start from the `foggy` preset
  - then force fog to `0.45`
  - then force wave height to `0.9`

## Output Structure

The run output directory will contain:

- raw SOLO capture files
- `scene_spec.json`
- `run_summary.json`
- Unity metadata files such as:
  - `run_metadata_<camera>_<timestamp>.json`
  - `scenario_start_<camera>_<timestamp>.json`
  - `scenario_end_<camera>_<timestamp>.json`
  - `unity_defaults_<timestamp>.json`

## `tools/run_dataset_plan.py`

## Purpose

Runs a full dataset plan: one `run_scenario.py` run per scenario declared in a single YAML plan file.

It:

1. loads and validates the plan (`tools/plan_loader.py`, stdlib-only YAML subset)
2. resolves each scenario as explicit `run_scenario.py` arguments (plan `defaults` plus per-scenario overrides)
3. runs the scenarios sequentially, each into its own numbered folder under `--output-root`
4. aggregates every `run_summary.json` into a global `manifest.json`
5. records failures in the manifest and keeps going with the next scenario

Use this when you want:

- a complete dataset with controlled variety: lighting, weather, times of day, area types, seeds
- every run deterministic and reproducible (`scene_seed` is mandatory per scenario)
- one traceable manifest for downstream QC

## Command

```bash
python3 tools/run_dataset_plan.py tools/plans/dataset-1k.yaml \
  --output-root recordings/dataset-1k

# preview the exact run_scenario.py commands without running anything
python3 tools/run_dataset_plan.py tools/plans/dataset-1k.yaml \
  --output-root recordings/dataset-1k --dry-run
```

Unity must be in Play mode, exactly as for a single `run_scenario.py` run.

## Plan File

```yaml
name: dataset-1k
defaults:            # shared run_scenario.py arguments
  duration: 25
  capture_hz: 5
  track_count: 18
scenarios:
  - name: lake-clear-day
    area_type: lake
    weather: clear
    time_of_day: 11.0
    scene_seed: 101
  - name: harbor-stormy-dusk
    area_type: harbor
    weather: stormy
    time_of_day: 18.0
    wave: 0.9
    scene_seed: 302
```

Scenario keys are the `run_scenario.py` arguments with underscores (`capture_hz` for `--capture-hz`, a `type_counts` mapping for `--type-counts-json`). `duration`, `time_of_day`, `weather` and `scene_seed` are required, directly or through `defaults` (`scene_seed` is per-scenario only and must be unique). Unknown keys are rejected. The full schema is documented in `tools/plan_loader.py`.

The reference plan `tools/plans/dataset-1k.yaml` produces ~1000 frames at 5 Hz across the four area types, all weather presets, and day/dusk lighting.

## Plan Output Structure

Inside `--output-root`:

- `manifest.json`
  - plan name, per-scenario status, frames, commands, and totals
  - rewritten after every scenario, so an interrupted run leaves a usable partial manifest
- `001-<scenario-name>/`, `002-<scenario-name>/`, ...
  - one folder per scenario, containing the standard single-run output (`scene_spec.json`, `run_summary.json`, SOLO data, Unity metadata)
  - Perception keeps one SOLO dir for the whole Play session (both stereo
    cameras write into each `sequence.N`) and appends a sequence per run. Each
    run lifts out only its own new sequence into the scenario folder and copies
    the SOLO schema definitions alongside, never touching the live SOLO dir. The
    frame data (the only thing that grows) therefore never accumulates in the
    Unity data folder; the lightweight SOLO shell is recreated each session and
    can be cleared with `rm -rf "<data folder>/solo"*` while Unity is NOT in Play

## `tools/run_defense_scene.sh`

Convenience wrapper for one demo/defense capture.

It is a shell wrapper around the same ideas:

- set a deterministic scene seed
- set track count and view bias
- set environment values
- run one `dataset_sweep`

Example:

```bash
TIME_OF_DAY=8.0 FOG=0.45 WAVE=0.9 TRACK_COUNT=24 RUN_DURATION_S=60 ./tools/run_defense_scene.sh
```

Use `tools/run_scenario.py` if you want the cleaner and more explicit modern version with an output directory under your control.
