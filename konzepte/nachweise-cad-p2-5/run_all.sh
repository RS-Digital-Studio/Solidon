#!/usr/bin/env bash
# Alle P2.5-Sonden nacheinander, jede in ihrem eigenen Prozess; Ausgabe je
# Sonde in <name>.out, Exit-Codes in laeufe.txt. Aufruf aus dem Projektstamm:
#
#     bash konzepte/nachweise-cad-p2-5/run_all.sh
#
# S2 muss vor S3 laufen (S3 liest step/ und cases.json). S4 ist unabhängig.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY="$ROOT/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$ROOT/.venv/bin/python"
export PYTHONUTF8=1
: > "$HERE/laeufe.txt"
for probe in s1_inventory s2_reference s3_matrix s4_rod_lengths; do
    "$PY" "$HERE/$probe.py" > "$HERE/$probe.out" 2>&1
    code=$?
    printf '%s Exit %d\n' "$probe" "$code" | tee -a "$HERE/laeufe.txt"
done
