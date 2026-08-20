# Dataset Generation V2

This is the current dataset-generation workflow.

## Goals

- many short scenarios instead of one long sweep
- fixed weather inside a scenario
- fixed or slowly progressing time of day inside a scenario
- explicit traffic density and class mix per scenario
- scenario-preserving raw outputs
- metadata at Unity startup, scenario start/end, and recording end

## Main pieces

- `tools/generate_scenarios.py`
  - builds a scenario manifest
  - assigns environment policy per scenario
  - assigns traffic policy per scenario (`track_count`, `area_type`, `type_counts`)
- `tools/run_scenario_batch.py`
  - applies one manifest entry at a time
  - sets weather/time policy
  - sets capture rate
  - sets scenario-generator traffic policy
  - publishes scenario metadata to Unity on `/dataset/scenario_info`
- `ros2 run n3mo_control dataset_sweep`
  - low-level runner used by the batch script
- Unity capture side
  - `DatasetCaptureScheduler.cs`
  - `RunMetadata.cs`
  - `ScenarioMetadataContext.cs`
  - `UnityDefaultsDump.cs`

## Files produced

- Unity startup/default dump:
  - `solo_x/unity_defaults_<timestamp>.json`
- Unity scenario start/end records:
  - `solo*/scenario_start_<scenario_id>_<timestamp>.json`
  - `solo*/scenario_end_<scenario_id>_<timestamp>.json`
- Unity run-level capture metadata:
  - `solo*/run_metadata_<timestamp>.json`

## Recommended commands

### Smoke run

```bash
python3 tools/generate_scenarios.py \
  --count 3 \
  --duration 20 \
  --capture-hz 8 \
  --track-count 12 \
  --area-type coastal \
  --time-mode fixed \
  --out scenarios_smoke.json

python3 tools/run_scenario_batch.py scenarios_smoke.json --limit 1
```

### Scenario split export

```bash
python3 tools/solo_to_yolo.py /path/to/solo_a /path/to/solo_b --split scenario --val-frac 0.2 --out yolo_split
```

### Raw export without split

```bash
python3 tools/solo_to_yolo.py /path/to/solo --out yolo_raw
```

This writes `images/all` and `labels/all`, plus `dataset_manifest.json`. No train/val split is created by default.
