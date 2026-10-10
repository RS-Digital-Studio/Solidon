#!/usr/bin/env bash
# Messbank RM-637: kalt.py an einem Baum im Wechsel ohne und mit Arbeitern, je Lauf ein Prozess.
#
#   bash arbeiter_wechsel.sh <runden> <ausgabe.jsonl> <baum> <liste.txt>
#
# Je Runde und Modell erst ohne, dann mit Arbeitern; in geraden Runden umgekehrt. Die
# Arbeiter starten in jedem Prozess neu — gemessen wird das erste Laden nach dem Start.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="F:/3D Druck/.venv/Scripts/python.exe"
ROUNDS="$1"; OUT="$2"; TREE="$3"; LIST="$4"
for round in $(seq 1 "$ROUNDS"); do
  while IFS= read -r model; do
    [ -z "$model" ] && continue
    if [ $((round % 2)) -eq 1 ]; then order=(0 1); else order=(1 0); fi
    for workers in "${order[@]}"; do
      MESSBANK_ARBEITER="$workers" "$PY" "$HERE/kalt.py" "$TREE" "$OUT" "$model" > /dev/null 2>&1
      echo "Runde $round Arbeiter $workers $model: Exit $?"
    done
  done < "$LIST"
done
