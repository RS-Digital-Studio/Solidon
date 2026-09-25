#!/bin/bash
# Suiteläufe nacheinander: Baum, Modell, Name. Jeder Lauf schreibt JSON und Protokoll.
SP="C:/Users/rober/AppData/Local/Temp/claude/F--3D-Druck/c532d8f7-8f49-4adc-93d0-1ed2d7f07f4e/scratchpad/ki"
PY="/f/3D Druck/.venv/Scripts/python.exe"
while [ $# -ge 3 ]; do
  tree="$1"; model="$2"; name="$3"; shift 3
  echo "=== $(date +%H:%M:%S) $name ($model, $tree) GPU vorher: $(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader)"
  ( cd "$SP/$tree" && PYTHONUTF8=1 "$PY" -u "$SP/suite_timed.py" "$SP/$tree" "$model" "$SP/suite_$name.json" > "$SP/suite_$name.log" 2>&1 )
  echo "    Exit $?  $(tail -1 "$SP/suite_$name.log")"
  curl -s http://localhost:11434/api/generate -d "{\"model\":\"$model\",\"keep_alive\":0}" > /dev/null
  sleep 5
done
echo "=== $(date +%H:%M:%S) fertig"
