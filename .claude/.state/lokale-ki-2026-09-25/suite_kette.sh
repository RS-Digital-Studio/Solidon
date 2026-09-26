#!/bin/bash
# Dritte Kette: je Lauf erst auf eine freie Karte warten (unter 3 GB belegt, kein Modell geladen).
SP="C:/Users/rober/AppData/Local/Temp/claude/F--3D-Druck/c532d8f7-8f49-4adc-93d0-1ed2d7f07f4e/scratchpad/ki"
PY="/f/3D Druck/.venv/Scripts/python.exe"
run() {
  tree="$1"; model="$2"; name="$3"; shift 3
  until [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' \r')" -lt 3000 ] && curl -s http://localhost:11434/api/ps | grep -q '"models":\[\]'; do sleep 30; done
  echo "=== $(date +%H:%M:%S) $name ($model, $tree $*) GPU vorher: $(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader)"
  ( cd "$SP/$tree" && PYTHONUTF8=1 "$PY" -u "$SP/suite_timed.py" "$SP/$tree" "$model" "$SP/suite_$name.json" "$@" > "$SP/suite_$name.log" 2>&1 )
  echo "    Exit $?  $(tail -1 "$SP/suite_$name.log")"
  curl -s http://localhost:11434/api/generate -d "{\"model\":\"$model\",\"keep_alive\":0}" > /dev/null
  sleep 5
}
run stand qwen3:14b stand_qwen3_14b
run base qwen3:14b base_qwen3_14b
run stand gpt-oss:20b stand_gpt_oss_20b
echo "=== $(date +%H:%M:%S) Kette 3 fertig"
