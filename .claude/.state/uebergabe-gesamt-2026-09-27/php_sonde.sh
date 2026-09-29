#!/usr/bin/env bash
# PHP-Wackler: die drei PHP-Dateien mehrmals mit -n 4, Serverausgabe je Test.
#   cmd //c "start /b /wait /affinity <maske> bash php_sonde.sh <läufe> <baum>"
runs="${1:-6}"
tree="${2:-/f/3D Druck.probe}"
cd "$tree" || exit 9
out="/f/3D Druck/output/review/gesamt-2026-09-27/php-sonde"
mkdir -p "$out"
py="/f/3D Druck/.venv/Scripts/python.exe"
export PYTHONUTF8=1
for n in $(seq 1 "$runs"); do
  rm -rf "$out/lauf-$n"
  "$py" -m pytest -q -p no:cacheprovider -p tests.php_log_plugin -n 4 \
    --basetemp="$out/lauf-$n" \
    tests/test_public_php_security.py tests/test_activation_server.py tests/test_shared_hosting_removed.py \
    > "$out/lauf-$n.txt" 2>&1
  echo "Lauf $n: Exit $? $(tail -1 "$out/lauf-$n.txt")" >> "$out/uebersicht.txt"
done
echo "ENDE $(date +%H:%M:%S)" >> "$out/uebersicht.txt"
