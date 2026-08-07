#!/usr/bin/env python3
"""Merge per-chunk run_metadata JSON data cards into one card for a merged dataset.

Config sections (image/camera/labels/scene/system) are identical across chunks recorded from the
same Unity setup, so they're taken from the first card. Capture stats are summed (frames, duration)
and actual_hz recomputed. The environment snapshot differs per chunk (weather is randomised), so all
snapshots are kept under environment_samples with a note.

Usage: python3 tools/merge_metadata.py <out.json> <run_metadata_a.json> <run_metadata_b.json> ...
"""

import json
import sys


def main():
    if len(sys.argv) < 3:
        print("usage: merge_metadata.py <out.json> <card.json> [<card.json> ...]")
        sys.exit(1)

    out_path = sys.argv[1]
    cards = []
    for p in sys.argv[2:]:
        with open(p) as f:
            cards.append(json.load(f))

    first = cards[0]
    total_frames = sum(c.get("capture", {}).get("frames", 0) for c in cards)
    total_dur = sum(c.get("capture", {}).get("duration_s", 0.0) for c in cards)
    actual_hz = round(total_frames / total_dur, 3) if total_dur > 0 else 0.0

    merged = {
        "dataset": "merged",
        "sources": [c.get("run_id", "?") for c in cards],
        "recorded_at": [c.get("recorded_at", "?") for c in cards],
        "capture": {
            "target_hz": first.get("capture", {}).get("target_hz"),
            "actual_hz": actual_hz,
            "frames": total_frames,
            "duration_s": round(total_dur, 2),
            "chunks": [c.get("capture", {}).get("frames", 0) for c in cards],
        },
        # identical across chunks -> taken from the first card
        "image": first.get("image"),
        "camera": first.get("camera"),
        "labels": first.get("labels"),
        "scene": first.get("scene"),
        "system": first.get("system"),
        # differs per chunk (weather randomised, no rain) -> keep them all
        "environment_note": "randomised per run (no rain); fog/cloud/wind/wave/time-of-day varied across frames",
        "environment_samples": [c.get("environment") for c in cards],
    }

    with open(out_path, "w") as f:
        json.dump(merged, f, indent=2)
    print(f"wrote {out_path}: {total_frames} frames from {len(cards)} chunks, actual_hz={actual_hz}")


if __name__ == "__main__":
    main()
