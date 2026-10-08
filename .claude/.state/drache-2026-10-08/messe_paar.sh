#!/usr/bin/env bash
# Stütze im Sperrkörper des alten Stands, alt gegen neu: <vorher-ordner> <nachher-ordner> <name>
# Körper und Sperre aus der Vorschlags-Übergabe des alten Stands; gemessen
# werden die Vorschlags-Druckdateien beider Stände. Aus dem Prüfordner.
set -u
PY="/f/3D Druck/.venv/Scripts/python.exe"
export PYTHONUTF8=1
old="$1"; new="$2"; name="$3"
out="paar-$name"; mkdir -p "$out"
threemf="$PWD/$(find "$old/arbeit" -path "*vorschlaege*" -name "*.3mf" | head -1)"
(cd "$out" && "$PY" ../extract.py "$threemf" > extract.log 2>&1)
region="$out/obj$(grep "Stützsperre" "$out/extract.log" | head -1 | cut -d' ' -f1).stl"
body="$out/obj$(grep -v "Stützsperre" "$out/extract.log" | head -1 | cut -d' ' -f1).stl"
mapfile -t g < <(find "$old/arbeit" "$new/arbeit" -path "*vorschlaege*" -name "*.gcode" | sort)
"$PY" gcode_im_kanal.py "$body" "$region" "${g[@]}" 2>&1 | cut -c1-220
