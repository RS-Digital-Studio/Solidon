# Stand HEAD (eigener Arbeitsbaum) gegen den Arbeitsbaum, abwechselnd, Zeitleiste je Lauf.
# Aufruf: bash ab_head.sh <head-baum> [<runden>] [<modell>]
head="$1"; rounds="${2:-2}"; model="${3:-}"
for round in $(seq 1 "$rounds"); do
  for root in "$head" "F:/3D Druck"; do
    PROBE_ROOT="$root" timeout 600 "F:/3D Druck/.venv/Scripts/python.exe" slot_probe.py zeitleiste $model > probe-zeitleiste.stdout 2>&1
    name=$([ "$root" = "$head" ] && echo HEAD || echo neu)
    echo "$round $name $(grep -E 'RUHE|Fläche da|synchron fertig' probe-out/zeitleiste/log.txt | tr -s ' ' | tr '\n' ';')"
  done
done
