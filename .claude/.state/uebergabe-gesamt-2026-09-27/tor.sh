#!/usr/bin/env bash
# Entwicklungstor im Arbeitsbaum der Gesamtprüfung. Aufruf gebunden:
#   cmd //c "start /b /wait /affinity FF bash <dieses skript> <name>"
# Ergebnis nur aus output/review/gesamt-2026-09-27/tor-<name>.txt lesen.
cd "/f/3D Druck.gesamtfix" || exit 9
out="/f/3D Druck/output/review/gesamt-2026-09-27/tor-${1:-lauf}.txt"
py="/f/3D Druck/.venv/Scripts/python.exe"
export PYTHONUTF8=1
bash .claude/scripts/suite-getrennt.sh > "$out" 2>&1
echo "TOR-EXIT=$?" >> "$out"
"$py" -m ruff check . >> "$out" 2>&1
echo "RUFF-EXIT=$?" >> "$out"
"$py" -m ruff format --check . >> "$out" 2>&1
echo "FORMAT-EXIT=$?" >> "$out"
"$py" -m mypy >> "$out" 2>&1
echo "MYPY-EXIT=$?" >> "$out"
echo "ENDE $(date +%H:%M:%S)" >> "$out"
