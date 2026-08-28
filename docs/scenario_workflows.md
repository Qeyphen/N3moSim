# Scenario Workflows

## Recommended Entry Points

Use one of these:

- `tools/run_scenario.py`
  - one explicit scene run
- `tools/run_scenario_batch.py`
  - one deterministic scene reused across repeated runs until a target frame count is reached

`tools/generate_scenarios.py` remains available for legacy manifest-based operation, but it is no longer the main recommended workflow.

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

## `tools/run_scenario_batch.py`

## Purpose

Runs one deterministic scene template across multiple captures until a total frame target is reached.

This is the current orchestrator.

It:

1. generates one scene template from the supplied scene-generation arguments
2. reuses the same generated scene layout across runs
3. samples different allowed environments per run
4. archives each run under a UUID folder below `--output-root`
5. stops when accumulated frames reach `--total-frames`

Use this when you want:

- many runs of the same base scene
- changing weather/time conditions across runs
- one parent output directory with multiple run subfolders

## Command

```bash
python3 tools/run_scenario_batch.py \
  --output-root /absolute/path/to/batch_root \
  --total-frames 300 \
  --duration 20 \
  --capture-hz 8 \
  --track-count 18 \
  --area-type coastal \
  --occupied-fraction 0.8 \
  --time-mode fixed
```

## Core Arguments

- `--output-root`
  - parent directory for UUID run folders
- `--total-frames`
  - stop once accumulated archived frames reach this target
- `--scene-seed`
  - deterministic scene layout seed
- `--env-seed`
  - deterministic environment sampling seed
- `--duration`
  - per-run duration
- `--capture-hz`
  - per-run capture rate
- `--track-count`
  - generated tracks in the reused scene
- `--area-type`
  - traffic preset
- `--type-counts-json`
  - exact object mix override
- `--occupied-fraction`
  - ego-view bias fraction

## Time arguments

- `--time-mode fixed`
  - one time-of-day per run
- `--time-mode linear`
  - time-of-day drifts forward smoothly during a run
- `--time-drift-hours`
  - maximum forward drift when `linear`
- `--time-update-period`
  - seconds between applied time updates when `linear`

## Weather/time distribution arguments

- `--weathers`
  - comma-separated preset list to sample from
- `--day-frac`
- `--twilight-frac`
- `--night-frac`

Important current policy:

- visible-hour use is intentionally favored
- previous work restricted most runs away from pitch-black conditions

## Batch Output Structure

Inside `--output-root`:

- `scene_spec.json`
  - describes the fixed scene template for the batch
- `batch_summary.json`
  - global summary across all runs
- `unity_defaults_<timestamp>.json`
  - hoisted once to batch root
- `<uuid>/`
  - one directory per archived run
  - contains raw SOLO data and Unity metadata for that run
  - contains `orchestrator_run.json`

## Legacy Manifest Mode

`run_scenario_batch.py` also still supports the older manifest flow.

If the first positional argument is a real JSON file, it is treated as a scenario manifest:

```bash
python3 tools/run_scenario_batch.py scenarios_full_test.json --limit 1
```

In that mode:

- the file already contains multiple scenario definitions
- the runner iterates through them
- environment and timing come from the manifest rather than the new orchestrator logic

## `tools/generate_scenarios.py`

## Purpose

Generates a JSON manifest of many scenarios for the legacy manifest flow.

Example:

```bash
python3 tools/generate_scenarios.py \
  --count 3 \
  --duration 20 \
  --capture-hz 8 \
  --out scenarios_test.json
```

This writes a manifest file. It does not run Unity, ROS, or capture by itself.

You would then pass that manifest to:

```bash
python3 tools/run_scenario_batch.py scenarios_test.json
```

## `--time-mode fixed` vs `--time-mode linear`

### `fixed`

- time of day does not change within the run

### `linear`

- time of day starts at one hour
- ends at a later hour
- the runner publishes updates periodically during the run
- this creates slow, coherent progression rather than abrupt jumps

Example:

- `12.8 -> 13.1 (linear)`
  - the run starts around 12:48
  - it ends around 13:06
  - the change is gradual

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
