#!/usr/bin/env bash
# Wie lauf.sh, aber mit Frist — für Fenstertests, die an einem Dialog hängen
# können (Hinweis der Release-Sitzung, 28.09.2026). Gebunden aufrufen:
#   cmd //c "start /b /wait /affinity FF bash lauf_frist.sh <name> [frist-s]"
# laeufe/<name>.args: erste Zeile der Baum, dann je Zeile ein pytest-Argument.
# Nach 240 s ohne Fortschritt schreibt pytest die Stapel (faulthandler).
here="$(cd "$(dirname "$0")" && pwd)"
name="$1"
frist="${2:-1500}"
mapfile -t lines < <(tr -d '\r' < "$here/laeufe/$name.args")
tree="${lines[0]}"
cd "$tree" || exit 9
out="/f/3D Druck/output/review/gesamt-2026-09-27/${name}.txt"
py="/f/3D Druck/.venv/Scripts/python.exe"
export PYTHONUTF8=1
timeout "$frist" "$py" -u -m pytest -q -p no:cacheprovider -o faulthandler_timeout=240 "${lines[@]:1}" > "$out" 2>&1
echo "PYTEST-EXIT=$? (124 = Frist)" >> "$out"
echo "ENDE $(date +%H:%M:%S)" >> "$out"
