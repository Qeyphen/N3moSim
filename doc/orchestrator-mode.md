# Single-Scene Orchestrator

The new batch flow defines one deterministic scene template, generates that
scene once, and then replays the exact same trajectories across many runs while
sampling a new environment per run.

## Command

```bash
python3 tools/run_scenario_batch.py \
  --output-root recordings/new_run \
  --total-frames 1000 \
  --duration 20 \
  --capture-hz 8 \
  --track-count 18 \
  --area-type coastal \
  --occupied-fraction 0.8 \
  --time-mode linear
```

## What Stays Fixed

- track count
- type mix
- generated trajectories
- scenario duration
- capture rate
- waypoint / clearance policy

## What Changes Per Run

- weather preset
- time of day

Weather is randomly sampled from the enabled presets. Time of day is sampled
from the configured day/twilight fractions and can stay fixed or drift slowly
within a run depending on `--time-mode`.

## Output Layout

The `--output-root` directory receives:

- `scene_spec.json`
- `batch_summary.json`
- one UUID folder per run

Example:

```text
recordings/new_run/
  scene_spec.json
  batch_summary.json
  52f6b482-0f3a-4a13-bd0d-7cc8db3e93b7/
  c86f3164-3da7-42d7-8d87-069a8db80d54/
```

Each UUID folder contains the raw SOLO dataset moved from Unity after that run,
plus `orchestrator_run.json`.

## Visibility Constraint

`--occupied-fraction` controls how much generated traffic is forced into the
ego boat's forward view cone during scenario generation.

Example:

- `0.8` means 80% of tracks are biased to spawn in front of the boat
- `0.2` means only 20% are biased in-view and more of the scene stays empty

This is how the orchestrator enforces the requested occupied vs empty scene
ratio while still using one deterministic scene template.
