#!/bin/bash
export PYTHONUTF8=1
PY="/f/3D Druck/.venv/Scripts/python.exe"
MODEL="/f/3D Dateien/large-screwdriver-holder-with-honeycomb-pattern.stl"
HERE="/f/3D Druck.review-051/sonden/rest-auswahl"
true
cd "/f/3D Druck.review-051/wt-rest-auswahl" && timeout 260 "$PY" "$HERE/probe.py" . langloch "$MODEL" neu > "$HERE/out/langloch-neu-konsole.txt" 2>&1; echo "neu Exit: $?"
