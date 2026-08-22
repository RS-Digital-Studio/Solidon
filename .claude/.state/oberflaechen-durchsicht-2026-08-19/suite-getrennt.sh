#!/usr/bin/env bash
# Die Suite so fahren, wie die CI sie fährt: je Fensterdatei ein eigener Prozess.
#
# In einem Prozess baut die Suite über siebenhundert VTK-Fenster nacheinander
# auf, und irgendwann reißt eine Grenze — eine Zugriffsverletzung ohne Zeile,
# irgendwann und selten reproduzierbar. Der CI-Workflow löst das seit dem
# 12.08.2026 so; lokal auf Windows ging es bisher gut, bis es nicht mehr ging.
#
# **Gesucht statt gepflegt**, wie in der CI: Wer eine neue Fensterdatei anlegt,
# bekommt ihren eigenen Prozess, ohne hier etwas zu ändern. Gesucht wird nach
# ``MainWindow`` **und** nach ``Viewport``/``pyvista`` — acht Dateien bauen ein
# VTK-Fenster, ohne ``MainWindow`` zu erwähnen, und liefen deshalb im großen
# Stapel mit.
set -u
cd "$(dirname "$0")/../../.." || exit 1

PY=.venv/Scripts/python.exe
windowed=$(grep -lE "MainWindow|Viewport|pyvista" tests/test_*.py | tr '\n' ' ')
ignores=""
for file in $windowed; do ignores="$ignores --ignore=$file"; done

fails=0
echo "=== der Rest in einem Zug ==="
PYTHONIOENCODING=utf-8 $PY -m pytest -q -m "not performance" $ignores
status=$?
echo "--> Exit $status"
[ $status -ne 0 ] && fails=$((fails + 1))

for file in $windowed; do
  echo "=== $file ==="
  PYTHONIOENCODING=utf-8 $PY -m pytest -q -m "not performance" "$file"
  status=$?
  echo "--> Exit $status"
  [ $status -ne 0 ] && fails=$((fails + 1))
done

echo "======================================"
echo "Läufe mit Fehler: $fails"
exit $fails
