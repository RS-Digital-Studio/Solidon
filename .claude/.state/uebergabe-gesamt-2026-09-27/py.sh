#!/usr/bin/env bash
# Python der .venv, gebunden ausführbar:
#   cmd //c "start /b /wait /affinity <maske> bash py.sh <name>"
# laeufe/<name>.pyargs: erste Zeile die Ausgabedatei, dann je Zeile ein
# Argument für python (Skript zuerst) — so kommen Leerzeichen heil durch cmd.
here="$(cd "$(dirname "$0")" && pwd)"
mapfile -t lines < <(tr -d '\r' < "$here/laeufe/$1.pyargs")
out="${lines[0]}"
cd "$here" || exit 9
export PYTHONUTF8=1
"/f/3D Druck/.venv/Scripts/python.exe" "${lines[@]:1}" > "$out" 2>&1
echo "PY-EXIT=$?" >> "$out"
