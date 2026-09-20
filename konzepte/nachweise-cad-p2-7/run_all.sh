#!/usr/bin/env bash
# Fährt jede Sonde einzeln, schreibt ihre Ausgabe nach sN.out und den direkten
# Prozessausgang nach laeufe.txt — ohne Pipeline, ohne Schlusszeile dazwischen
# (CLAUDE.md, die drei Fallen).
#
#   bash konzepte/nachweise-cad-p2-7/run_all.sh
#
# Läuft mit der .venv des Hauptklons; die Sonden isolieren die Nutzerverzeichnisse selbst.
cd "$(dirname "$0")/../.." || exit 2
PY=.venv/Scripts/python.exe
[ -x "$PY" ] || PY=.venv/bin/python
DIR=konzepte/nachweise-cad-p2-7
: > "$DIR/laeufe.txt"
echo "Stand: $(git rev-parse HEAD)  $(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$DIR/laeufe.txt"
for probe in s0_smoke s1_register s2_schemas s3_fasteners s3b_thread_debug s4_mechanics s5_mounting s6_structure s7_calibration s8_insertion s8b_anchor_debug; do
    "$PY" "$DIR/$probe.py" > "$DIR/${probe%%_*}.out" 2>&1
    code=$?
    echo "$probe  Exit $code" >> "$DIR/laeufe.txt"
done
cat "$DIR/laeufe.txt"
