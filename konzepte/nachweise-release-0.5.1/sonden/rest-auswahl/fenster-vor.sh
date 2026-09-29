#!/bin/bash
export PYTHONUTF8=1
export NUR="Maße bleiben beim Langlochzug (zuerst)"
PY="/f/3D Druck/.venv/Scripts/python.exe"
HERE="/f/3D Druck.review-051/sonden/rest-auswahl"
cd "$HERE/wt-vor" && timeout 300 "$PY" "$HERE/fenstertests.py" . vor > "$HERE/out/fenster-vor-konsole.txt" 2>&1; echo "vor Exit: $?"
