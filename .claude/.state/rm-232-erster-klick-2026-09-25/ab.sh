# Drei Varianten abwechselnd, je Lauf der Median der Klicks nach dem ersten.
model="$1"; rounds="${2:-2}"
for round in $(seq 1 "$rounds"); do
  for variant in alt neu alien; do
    PROBE_VARIANT="$variant" PROBE_ROOT="F:/3D Druck" timeout 600 "F:/3D Druck/.venv/Scripts/python.exe" slot_probe.py clicktime "$model" > probe-clicktime.stdout 2>&1
    echo "$round $variant $(grep ERGEBNIS probe-out/clicktime/log.txt)"
  done
done
