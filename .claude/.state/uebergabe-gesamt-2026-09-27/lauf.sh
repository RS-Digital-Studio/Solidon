#!/usr/bin/env bash
# Gezielter Testlauf, gebunden auf die Kerne 0-7:
#   cmd //c "start /b /wait /affinity FF bash lauf.sh <name>"
# Liest den Baum aus der ersten Zeile von laeufe/<name>.args, die
# pytest-Argumente aus den übrigen Zeilen (je Zeile eines — so kommen
# Leerzeichen heil durch cmd). Ergebnis nur aus
# output/review/gesamt-2026-09-27/<name>.txt lesen.
here="$(cd "$(dirname "$0")" && pwd)"
name="$1"
mapfile -t lines < <(tr -d '\r' < "$here/laeufe/$name.args")
tree="${lines[0]}"
cd "$tree" || exit 9
out="/f/3D Druck/output/review/gesamt-2026-09-27/${name}.txt"
py="/f/3D Druck/.venv/Scripts/python.exe"
export PYTHONUTF8=1
"$py" -m pytest -q -p no:cacheprovider "${lines[@]:1}" > "$out" 2>&1
echo "PYTEST-EXIT=$?" >> "$out"
echo "ENDE $(date +%H:%M:%S)" >> "$out"
