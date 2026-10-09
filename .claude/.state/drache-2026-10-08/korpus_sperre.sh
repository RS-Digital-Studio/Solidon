#!/usr/bin/env bash
# Korpusfälle, deren Sperre mit dem neuen Stand entfällt, obwohl Stützen nötig
# sind: alter und neuer Stand durch ElegooSlicer (CC2), dann Stützbahn im
# Sperrkörper des alten Stands. Aufruf aus dem Prüfordner.
set -u
PY="/f/3D Druck/.venv/Scripts/python.exe"
export PYTHONUTF8=1 GESAMT_BEHALTEN=1 GESAMT_KERNE=FFF0FF
BASE="$PWD/korpus-sperre"
mkdir -p "$BASE"
for model in \
  "F:/3D Dateien/countercleaner.3mf" \
  "F:/3D Dateien/Modern++Cutlery+Organizer+with+Divider.3mf" \
  "F:/3D Dateien/parametric-laptop-riser.stl" \
  "F:/3D Dateien/kumiko_elongated-hexagon_shell_w150.stl" \
  "F:/3D Dateien/spiderman+voronoi+bambu+10cm_stls/obj_1_spiderman.stl"; do
  name=$(basename "$model"); name="${name%.*}"; name=$(echo "$name" | tr -c 'A-Za-z0-9._\n-' '_')
  out="$BASE/$name"; mkdir -p "$out"
  for stand in vorher nachher; do
    root="F:/sl-drache"; [ "$stand" = vorher ] && root="F:/sl-drache-vorher"
    "$PY" "F:/sl-drache/tools/matrix_unit.py" "$root" "$model" "$out/$stand" "elegoo:centauri-carbon-2" > "$out/$stand.log" 2>&1
    echo "$name $stand Exit: $?"
  done
  old=$(find "$out/vorher/arbeit" -path "*vorschlaege*" -name "*.3mf" | head -1)
  (cd "$out" && "$PY" "$BASE/../extract.py" "$old" > extract.log 2>&1)
  ls "$out"/obj*.stl
  mapfile -t gcodes < <(find "$out/nachher/arbeit" "$out/vorher/arbeit" -name "*.gcode" | sort)
  # extract.log: „<id> <name> …“ je Teil; die Sperre heißt „Stützsperre“.
  region="$out/obj$(grep "Stützsperre" "$out/extract.log" | head -1 | cut -d' ' -f1).stl"
  body="$out/obj$(grep -v "Stützsperre" "$out/extract.log" | head -1 | cut -d' ' -f1).stl"
  echo "Körper $body, Bereich $region" > "$out/im_kanal.log"
  "$PY" "$BASE/../gcode_im_kanal.py" "$body" "$region" "${gcodes[@]}" >> "$out/im_kanal.log" 2>&1
  echo "$name im Kanal Exit: $?"
done
