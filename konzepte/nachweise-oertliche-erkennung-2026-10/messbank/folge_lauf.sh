#!/usr/bin/env bash
# Messbank A1 (RM-592): folge.py über eine Fallliste, in <teile> Prozessen nebeneinander.
#
#   bash folge_lauf.sh <baum> <praefix> <teile> <liste.txt> [Optionen von folge.py]
#
# Die Liste wird reihum auf die Teile verteilt; Teil i schreibt <praefix>_<i>.jsonl und
# <praefix>_<i>.out. Ein abgebrochener Lauf setzt bei den Fällen ohne Schlusszeile fort.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PY="F:/3D Druck/.venv/Scripts/python.exe"
TREE="$1"; PREFIX="$2"; PARTS="$3"; LIST="$4"; shift 4
for part in $(seq 0 $((PARTS - 1))); do
  awk -v n="$PARTS" -v k="$part" 'NF && (NR - 1) % n == k' "$LIST" > "${PREFIX}_${part}.liste"
  "$PY" "$HERE/folge.py" "$TREE" "${PREFIX}_${part}.jsonl" "$@" "@${PREFIX}_${part}.liste" \
    > "${PREFIX}_${part}.out" 2>&1 &
done
wait
echo "folge_lauf fertig: $PREFIX"
