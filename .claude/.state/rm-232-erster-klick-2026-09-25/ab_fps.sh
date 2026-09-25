# Bildtakt 30 (Vorgabe von rendercanvas) gegen den Takt des Bildschirms, abwechselnd.
model="$1"; rounds="${2:-2}"
for round in $(seq 1 "$rounds"); do
  for fps in 30 screen; do
    PROBE_FPS="$fps" PROBE_ROOT="F:/3D Druck" timeout 600 "F:/3D Druck/.venv/Scripts/python.exe" slot_probe.py clicktime "$model" > probe-clicktime.stdout 2>&1
    echo "$round fps=$fps $(grep ERGEBNIS probe-out/clicktime/log.txt)"
  done
done
