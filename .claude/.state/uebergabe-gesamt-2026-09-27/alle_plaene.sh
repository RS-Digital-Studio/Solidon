#!/bin/bash
# Die Gesamtprüfung: erst jeder Drucker an drei Modellen, dann jedes Modell an den
# Heimdruckern der sechs Slicer. Ein Aufruf, damit die Nacht durchläuft.
cd "$(dirname "$0")" || exit 1
PY="/f/3D Druck/.venv/Scripts/python.exe"
CODE="F:/3D Druck.gesamt"
OUT="F:/3D Druck/output/review/gesamt-2026-09-27"
export PYTHONUTF8=1
"$PY" -u treiber.py "$CODE" "$OUT/drucker" drucker --arbeiter 3 > "$OUT/drucker.out" 2>&1
echo "drucker: $?" >> "$OUT/plaene-status.txt"
"$PY" -u treiber.py "$CODE" "$OUT/modelle" modelle --arbeiter 3 > "$OUT/modelle.out" 2>&1
echo "modelle: $?" >> "$OUT/plaene-status.txt"
echo fertig >> "$OUT/plaene-status.txt"
