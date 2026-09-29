#!/bin/bash
# Vorher/nachher im Wechsel, je Lauf ein Prozess: Stand aa82afdff (headbaum)
# gegen den Arbeitsbaum wt-3mf. Aufruf gebunden:
#   cmd //c "start /b /wait /affinity FFFFF0FF bash sonden/3mf/reihe_ab.sh <name> <runden> [modell]"
export PYTHONUTF8=1
PY="F:/3D Druck/.venv/Scripts/python.exe"
cd "/f/3D Druck.review-051/wt-3mf" || exit 9
name="$1"; rounds="$2"; model="$3"
dir="/f/3D Druck.review-051/sonden/3mf/out"
out="$dir/ab_${name}.txt"
load() { powershell -NoProfile -Command "(Get-CimInstance Win32_Processor).LoadPercentage" | tr -d '\r'; }
echo "START $(date +%H:%M:%S) Last $(load) %" > "$out"
for n in $(seq 1 "$rounds"); do
  for side in head neu; do
    tag="${name}_${side}${n}"
    if [ "$side" = head ]; then tree="F:/3D Druck.review-051/sonden/3mf/headbaum"; else tree="F:/3D Druck.review-051/wt-3mf"; fi
    before=$(load)
    if [ -n "$model" ]; then
      SONDE_OHNE_DUMP=1 SONDE_GRIFFE=${SONDE_GRIFFE:-} SONDE_TAG="$tag" SONDE_TREE="$tree" timeout 600 "$PY" ../sonden/3mf/p01_nativ.py "$model" > "$dir/p01_${tag}.stderr.txt" 2>&1
    else
      SONDE_OHNE_DUMP=1 SONDE_GRIFFE=${SONDE_GRIFFE:-} SONDE_TAG="$tag" SONDE_TREE="$tree" timeout 600 "$PY" ../sonden/3mf/p01_nativ.py > "$dir/p01_${tag}.stderr.txt" 2>&1
    fi
    code=$?
    echo "$tag exit $code Last vorher ${before} % nachher $(load) % | $(grep -h 'fertig nach' "$dir/p01_${tag}.txt" | cut -c11-) | $(grep -h ERGEBNIS "$dir/p01_${tag}.txt" | cut -c11-)" >> "$out"
  done
done
echo "ENDE $(date +%H:%M:%S)" >> "$out"
