#!/usr/bin/env bash
# Messbank A5 (RM-592): kalt.py im Wechsel zweier Bäume, je Modell und Runde ein Prozess.
#
#   bash kalt_wechsel.sh <runden> <ausgabe.jsonl> <baum-a> <baum-b> <liste.txt>
#
# Je Runde und Modell erst a, dann b; in geraden Runden umgekehrt.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="F:/3D Druck/.venv/Scripts/python.exe"
ROUNDS="$1"; OUT="$2"; A="$3"; B="$4"; LIST="$5"
for round in $(seq 1 "$ROUNDS"); do
  while IFS= read -r model; do
    [ -z "$model" ] && continue
    if [ $((round % 2)) -eq 1 ]; then order=("$A" "$B"); else order=("$B" "$A"); fi
    for tree in "${order[@]}"; do
      "$PY" "$HERE/kalt.py" "$tree" "$OUT" "$model" > /dev/null 2>&1
      echo "Runde $round $(basename "$tree") $model: Exit $?"
    done
  done < "$LIST"
done
