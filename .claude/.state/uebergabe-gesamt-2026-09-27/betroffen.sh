#!/usr/bin/env bash
# Die betroffenen Tests im Arbeitsbaum der Gesamtprüfung, gebunden:
#   cmd //c "start /b /wait /affinity FF bash betroffen.sh <name>"
# laeufe/<name>.files: je Zeile eine geänderte Datei (relativ zum Baum).
# Ergebnis nur aus output/review/gesamt-2026-09-27/<name>.txt lesen.
here="$(cd "$(dirname "$0")" && pwd)"
mapfile -t files < <(tr -d '\r' < "$here/laeufe/$1.files")
cd "/f/3D Druck.gesamtfix" || exit 9
out="/f/3D Druck/output/review/gesamt-2026-09-27/$1.txt"
export PYTHONUTF8=1
"/f/3D Druck/.venv/Scripts/python.exe" tools/affected_tests.py "${files[@]}" --run > "$out" 2>&1
echo "AFFECTED-EXIT=$?" >> "$out"
echo "ENDE $(date +%H:%M:%S)" >> "$out"
