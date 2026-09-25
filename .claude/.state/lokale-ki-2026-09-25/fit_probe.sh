#!/bin/bash
# Je Modell: Grundlast zählen (neuer Baum), dann mit Fenster laden und die Lage lesen, dann entladen.
SP="C:/Users/rober/AppData/Local/Temp/claude/F--3D-Druck/c532d8f7-8f49-4adc-93d0-1ed2d7f07f4e/scratchpad/ki"
PY="/f/3D Druck/.venv/Scripts/python.exe"
for m in "$@"; do
  for ctx in 32768 65536; do
    echo "=== $m num_ctx=$ctx  vorher: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
    PYTHONUTF8=1 "$PY" "$SP/wt-new/tools/measure_local_model.py" --count-tokens --model "$m" --context $ctx 2>&1 | tail -2
    curl -s http://localhost:11434/api/generate -d "{\"model\":\"$m\",\"prompt\":\"Hallo\",\"stream\":false,\"keep_alive\":\"2m\",\"options\":{\"num_ctx\":$ctx,\"num_predict\":1}}" > /dev/null
    ollama ps | tail -n +2
    echo "    nachher: $(nvidia-smi --query-gpu=memory.used --format=csv,noheader)"
    curl -s http://localhost:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0}" > /dev/null
    sleep 3
  done
done
