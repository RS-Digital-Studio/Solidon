#!/usr/bin/env bash
# Misst einen Kandidatenordner: Stützabdeckung am Drachen (100 und 130 %),
# Stütze im Kanal der Schüssel je Slicer, Stütze in der Kehle des
# Countercleaners. Aufruf aus dem Prüfordner: bash messe_kandidat.sh <ordner>
set -u
PY="/f/3D Druck/.venv/Scripts/python.exe"
export PYTHONUTF8=1
K="$1"
mapfile -t d100 < <(find "$K/drache100/arbeit" -name "*.gcode" 2>/dev/null | grep -v standard | sort)
mapfile -t d130 < <(find "$K/drache130/arbeit" -name "*.gcode" 2>/dev/null | grep -v standard | sort)
mapfile -t sch < <(find "$K/schuessel/arbeit" -name "*.gcode" 2>/dev/null | grep -v standard | sort)
mapfile -t cc < <(find "$K/countercleaner/arbeit" -name "*.gcode" 2>/dev/null | grep -v standard | sort)
[ ${#d100[@]} -gt 0 ] && "$PY" gcode_stuetzen.py "F:/sl-drache" obj3.stl "$K/stuetzen-100.json" "${d100[@]}" > "$K/stuetzen-100.log" 2>&1 &
[ ${#d130[@]} -gt 0 ] && "$PY" gcode_stuetzen.py "F:/sl-drache" sx130/obj3.stl "$K/stuetzen-130.json" "${d130[@]}" > "$K/stuetzen-130.log" 2>&1 &
[ ${#sch[@]} -gt 0 ] && "$PY" gcode_im_kanal.py schuessel-end/obj3.stl schuessel-end/obj4.stl "${sch[@]}" > "$K/schuessel-kanal.log" 2>&1 &
[ ${#sch[@]} -gt 0 ] && "$PY" gcode_stuetzen.py "F:/sl-drache" schuessel-end/obj3.stl "$K/stuetzen-schuessel.json" "${sch[@]}" > "$K/stuetzen-schuessel.log" 2>&1 &
[ ${#cc[@]} -gt 0 ] && "$PY" gcode_im_kanal.py korpus-sperre/countercleaner/obj3.stl korpus-sperre/countercleaner/obj4.stl "${cc[@]}" > "$K/countercleaner-kanal.log" 2>&1 &
wait
for f in "$K"/stuetzen-*.json; do "$PY" zeige_lauf.py "$f"; done
cut -c1-200 "$K/schuessel-kanal.log" "$K/countercleaner-kanal.log" 2>/dev/null
