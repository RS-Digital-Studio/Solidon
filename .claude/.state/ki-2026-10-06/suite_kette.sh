#!/bin/bash
# Suiteläufe nacheinander, jeder erst auf freier Karte: unter 3 GB belegt, kein
# Modell geladen und kein anderer Suitelauf (suite_timed.py, run_agent_suite.py)
# auf dem Rechner. Ein fremder Lauf entlädt das Modell zwischen zwei Fällen —
# deshalb zweimal im Abstand von 90 Sekunden prüfen (am 06.10. lief sonst ein
# Lauf 13 Minuten neben einem fremden, mit CUDA out of memory).
# Aufruf: bash suite_kette.sh <baum>=<name> [<baum>=<name> ...]   (Modell: qwen3:14b)
HERE="/f/3D Druck/.claude/.state/ki-2026-10-06"
PY="/f/3D Druck/.venv/Scripts/python.exe"
MODEL="${MODEL:-qwen3:14b}"

frei() {
  [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | tr -d ' \r')" -lt 3000 ] || return 1
  curl -s http://localhost:11434/api/ps | grep -q '"models":\[\]' || return 1
  local laeufe
  laeufe=$(powershell -NoProfile -c "@(Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | Where-Object { \$_.CommandLine -match 'suite_timed|run_agent_suite' }).Count" | tr -d ' \r')
  [ "$laeufe" = "0" ]
}

for item in "$@"; do
  tree="${item%%=*}"; name="${item##*=}"
  until frei && sleep 90 && frei; do sleep 30; done
  echo "=== $(date +%H:%M:%S) $name ($MODEL, $tree, $(git -C "$tree" rev-parse --short HEAD)) GPU vorher: $(nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader)"
  ( cd "$tree" && PYTHONUTF8=1 "$PY" -u "$HERE/suite_timed.py" "$tree" "$MODEL" "$HERE/messung/suite_$name.json" > "$HERE/messung/suite_$name.log" 2>&1 )
  echo "    Exit $?  $(tail -1 "$HERE/messung/suite_$name.log")"
  curl -s http://localhost:11434/api/generate -d "{\"model\":\"$MODEL\",\"keep_alive\":0}" > /dev/null
  sleep 5
done
echo "=== $(date +%H:%M:%S) Kette fertig"
