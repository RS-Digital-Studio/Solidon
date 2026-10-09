#!/usr/bin/env bash
# Messbank A4/A5 (RM-592): tempo.py im Wechsel zweier Bäume, je Lauf ein Prozess.
#
#   bash tempo_wechsel.sh <runden> <ausgabe.jsonl> <baum-a> <baum-b> <fall> [<fall> ...]
#
# Je Runde und Fall erst a, dann b; in geraden Runden umgekehrt — sonst misst die
# Reihenfolge die Uhrzeit mit. Das Ergebnis steht in <ausgabe.jsonl> (Spalte "baum").
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="F:/3D Druck/.venv/Scripts/python.exe"
ROUNDS="$1"; OUT="$2"; A="$3"; B="$4"; shift 4
for round in $(seq 1 "$ROUNDS"); do
  for case in "$@"; do
    if [ $((round % 2)) -eq 1 ]; then order=("$A" "$B"); else order=("$B" "$A"); fi
    for tree in "${order[@]}"; do
      "$PY" "$HERE/tempo.py" "$tree" "$OUT" "$case" > /dev/null 2>&1
      echo "Runde $round $case $(basename "$tree"): Exit $?"
    done
  done
done
