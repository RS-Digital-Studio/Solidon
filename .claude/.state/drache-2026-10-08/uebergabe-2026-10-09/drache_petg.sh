#!/usr/bin/env bash
# Drache mit PETG nach den Fixes der Nachprüfung (RM-583), aus F:/sl-stuetzen.
set -u
PY="/f/3D Druck/.venv/Scripts/python.exe"
export PYTHONUTF8=1 GESAMT_MATERIAL=petg GESAMT_BEHALTEN=1
OUT="/f/3D Druck/output/drache-2026-10-08/kontakt-drache-petg"
LOG="/f/3D Druck/output/drache-2026-10-08/kontakt-drache-petg.log"
rm -rf "$OUT"
"$PY" /f/sl-stuetzen/tools/matrix_unit.py /f/sl-stuetzen "/f/3D Druck/output/drache-2026-10-08/Drache.3mf" "$OUT" \
  "elegoo:slicer-orca-af8733f715e1dfb0606b,orca:anycubic-kobra-2,bambu:bambu-p1s,prusa:prusa-mk4s,cura:sovol-sv06" > "$LOG" 2>&1
echo "EXIT=$?" >> "$LOG"
