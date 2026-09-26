# HEAD-Arbeitsbaum gegen Hauptbaum, abwechselnd, CPU-Zeit des Hauptfadens je Klick.
head="$1"; rounds="${2:-3}"; model="${3:-}"
for round in $(seq 1 "$rounds"); do
  for root in "$head" "F:/3D Druck"; do
    PROBE_ROOT="$root" timeout 600 "F:/3D Druck/.venv/Scripts/python.exe" slot_probe.py cpuzeit $model > probe-cpuzeit.stdout 2>&1
    name=$([ "$root" = "$head" ] && echo HEAD || echo neu)
    echo "$round $name $(grep ERGEBNIS probe-out/cpuzeit/log.txt)"
  done
done
