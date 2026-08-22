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

# **Exit 5 ist kein Fehllauf.** pytest meldet damit „keine Tests gesammelt“,
# und das ist keine Aussage über den Code. Der Fall entsteht aus der Suche
# oben: Sie findet die Fensterdateien im *Text* und erwischt damit auch eine
# Datei, die über eine Ansicht **schreibt** statt eine zu bauen — stehen darin
# nur Leistungstests, sammelt `-m "not performance"` nichts. Am 22.08.2026
# landete `tests/test_performance.py` wegen zweier Docstrings hier und zählte
# als Fehllauf.
zaehlt_als_fehler() {
  [ "$1" -eq 0 ] && return 1
  [ "$1" -eq 5 ] && return 1
  return 0
}

fails=0
# Die Namen der Fehlläufe, durch Leerzeichen getrennt — Testpfade haben keine.
schlecht=""

echo "=== der Rest in einem Zug ==="
PYTHONIOENCODING=utf-8 $PY -m pytest -q -m "not performance" $ignores
status=$?
echo "--> Exit $status"
if zaehlt_als_fehler $status; then
  fails=$((fails + 1))
  schlecht="$schlecht rest-in-einem-zug(Exit:$status)"
fi

for file in $windowed; do
  echo "=== $file ==="
  PYTHONIOENCODING=utf-8 $PY -m pytest -q -m "not performance" "$file"
  status=$?
  echo "--> Exit $status"
  if zaehlt_als_fehler $status; then
    fails=$((fails + 1))
    schlecht="$schlecht $file(Exit:$status)"
  fi
done

echo "======================================"
echo "Läufe mit Fehler: $fails"
# **Die Namen, nicht nur die Zahl.** Wer die Ausgabe durch `tail` schickt,
# verliert sonst genau das, was er braucht: Am 22.08.2026 meldete ein Lauf
# „Läufe mit Fehler: 4“, und niemand wusste, welche vier. Die Zeilen kosten
# nichts und stehen am Ende, wo auch ein kurzes `tail` sie noch mitnimmt.
for entry in $schlecht; do
  echo "  $entry"
done
exit $fails
