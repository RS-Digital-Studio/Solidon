#!/usr/bin/env bash
# mypy für Windows im Arbeitsbaum der Gesamtprüfung. Gebunden aufrufen:
#   cmd //c "start /b /wait /affinity FFFFF000 bash mypy_win.sh"
out="/f/3D Druck/output/review/gesamt-2026-09-27/mypy-win.txt"
cd "/f/3D Druck.gesamtfix" || exit 9
export PYTHONUTF8=1
"/f/3D Druck/.venv/Scripts/python.exe" -m mypy > "$out" 2>&1
echo "MYPY-WIN-EXIT=$?" >> "$out"
