#!/usr/bin/env bash
# Filter + convert one or more SOLO recordings into a single merged YOLO dataset.
#
# Each SOLO folder is filtered (tiny/submerged boxes dropped), then ALL are converted together in
# one solo_to_yolo pass so they share ONE class list (chunks can have different classes present —
# converting separately would misalign class ids). Also builds one merged data card.
#
# Usage: ./scripts/merge_to_yolo.sh <solo_dir> [<solo_dir> ...] [-o OUT]
#   ./scripts/merge_to_yolo.sh ~/.config/unity3d/DefaultCompany/N3moSim/solo_3 \
#                              ~/.config/unity3d/DefaultCompany/N3moSim/solo_4
set -euo pipefail

OUT="yolo"
DIRS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -o) OUT="$2"; shift 2 ;;
    *)  DIRS+=("$1"); shift ;;
  esac
done

if [ ${#DIRS[@]} -eq 0 ]; then
  echo "usage: $0 <solo_dir> [<solo_dir> ...] [-o OUT]"; exit 1
fi

CARDS=()
for D in "${DIRS[@]}"; do
  if [ ! -d "$D" ]; then echo "not a directory: $D"; exit 1; fi
  echo "=== filtering $D ==="
  card=$(ls -t "$D"/run_metadata_*.json 2>/dev/null | head -1 || true)
  [ -n "$card" ] && CARDS+=("$card")
  python3 tools/filter_boxes.py "$D" --apply
done

# Convert ALL dirs in one pass -> shared class list, consistent ids, filenames prefixed per dir.
echo "=== converting to YOLO (shared class list) ==="
python3 tools/solo_to_yolo.py "${DIRS[@]}" --out "$OUT"

# One merged data card for the whole dataset (sums frames, keeps shared config, lists sources).
if [ ${#CARDS[@]} -gt 0 ]; then
  python3 tools/merge_metadata.py "$OUT/dataset_metadata.json" "${CARDS[@]}"
fi

echo
echo "=== merged into $OUT/ ==="
echo "train images: $(ls "$OUT/images/train" 2>/dev/null | wc -l)"
echo "val images:   $(ls "$OUT/images/val"   2>/dev/null | wc -l)"
echo "train labels: $(ls "$OUT/labels/train" 2>/dev/null | wc -l)"
echo "val labels:   $(ls "$OUT/labels/val"   2>/dev/null | wc -l)"
echo "classes:"; grep '^names' "$OUT/data.yaml" 2>/dev/null || cat "$OUT/data.yaml"
