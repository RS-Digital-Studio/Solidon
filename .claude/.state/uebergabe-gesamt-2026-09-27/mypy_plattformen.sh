#!/usr/bin/env bash
# mypy für die Zielplattformen, die das lokale Tor nicht fährt (Hinweis der
# Release-Sitzung, 28.09.2026). Gebunden aufrufen:
#   cmd //c "start /b /wait /affinity FF bash mypy_plattformen.sh <name>"
# laeufe/<name>.baum: eine Zeile, der Pfad des Arbeitsbaums (Leerzeichen
# kommen so heil durch cmd).
here="$(cd "$(dirname "$0")" && pwd)"
name="$1"
tree="$(tr -d '\r' < "$here/laeufe/$name.baum" | head -1)"
out="/f/3D Druck/output/review/gesamt-2026-09-27/mypy-${name}.txt"
cd "$tree" || { echo "Baum fehlt: $tree" > "$out"; exit 9; }
py="/f/3D Druck/.venv/Scripts/python.exe"
export PYTHONUTF8=1
"$py" -m mypy --platform linux > "$out" 2>&1
echo "MYPY-LINUX-EXIT=$?" >> "$out"
"$py" -m mypy --platform darwin >> "$out" 2>&1
echo "MYPY-DARWIN-EXIT=$?" >> "$out"
echo "ENDE $(date +%H:%M:%S)" >> "$out"
