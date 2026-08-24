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

# **Das Skript fährt eine Kopie seiner selbst, und zwar aus einem gemessenen
# Grund.**
#
# Bash liest ein Skript nicht auf einmal ein, sondern **zeilenweise nach** und
# merkt sich dabei die Byte-Position. Wird die Datei während des Laufs länger
# oder kürzer, liest der laufende Prozess an der alten Position in der neuen
# Datei weiter — und landet mitten in einem Wort.
#
# Am 23.08.2026 um 00:45:48 hat das einen Torlauf zerrissen, der seit 00:41
# lief: Eine andere Sitzung fügte oben einen Kommentar ein, und der Prozess
# starb mit „syntax error near unexpected token" in einer Zeile, die es so nie
# gegeben hat. `bash -n` sagte danach „Syntax ok" — der Fehler steckte nicht in
# der Datei, sondern zwischen zwei Fassungen davon.
#
# Das ist dieselbe Familie wie der ImportError aus einem fremden Zwischenstand,
# nur eine Stufe heimtückischer: Dort war der **Prüfling** halbfertig, hier das
# **Prüfwerkzeug**. Der Prüfling war in Ordnung, und die Meldung zeigte auf eine
# Zeile, die niemand geschrieben hatte.
#
# Die Kopie macht einen laufenden Lauf gegen jede Änderung immun — auch gegen
# die eigene. Sie kostet drei Zeilen und erzieht niemanden zu etwas.
if [ -z "${SUITE_WURZEL:-}" ]; then
  SUITE_WURZEL=$(cd "$(dirname "$0")/../../.." && pwd) || exit 1
  SUITE_KOPIE=$(mktemp) || exit 1
  cp "$0" "$SUITE_KOPIE" || exit 1
  export SUITE_WURZEL SUITE_KOPIE
  exec bash "$SUITE_KOPIE" "$@"
fi
trap 'rm -f "$SUITE_KOPIE"' EXIT
cd "$SUITE_WURZEL" || exit 1

# **Der Interpreter, auch wenn er nicht hier liegt.** Ein eigener Arbeitsbaum
# (`claude --worktree`) hat keine `.venv` — sie ist per `.gitignore` draußen und
# gehört dem Hauptbaum. Fest verdrahtet gab dieses Skript dort **jede**
# Fensterdatei mit Exit 127 zurück („Befehl nicht gefunden"), und das sieht aus
# wie der bekannte Absturz beim Abbau, ist aber keiner.
#
# Gesucht wird in dieser Reihenfolge: was der Aufrufer nennt (`SUITE_PYTHON`,
# das setzt `tools/nach_main.py`), dann die eigene `.venv`, dann die des
# Hauptbaums über das gemeinsame Git-Verzeichnis.
# **In Anführungszeichen, überall.** Der Projektordner heißt "3D Druck" —
# mit Leerzeichen. Relativ (`.venv/…`) fiel das nie auf; sobald der Pfad
# absolut wird, zerlegt die Shell ihn an der Lücke und meldet
# "F:/3D: No such file or directory" — als Exit 127, das aussieht wie der
# bekannte Absturz beim Abbau.
PY=${SUITE_PYTHON:-.venv/Scripts/python.exe}
if [ ! -x "$PY" ]; then
  haupt=$(git rev-parse --git-common-dir 2>/dev/null)
  PY="${haupt%/.git}/.venv/Scripts/python.exe"
fi
if [ ! -x "$PY" ]; then
  echo "Kein Interpreter gefunden. Setze SUITE_PYTHON auf den vollen Pfad." >&2
  exit 2
fi
# **Zuerst die Frage, ob der Baum überhaupt importierbar ist.**
#
# Am 23.08.2026 meldete ein Torlauf 27 Fehlschläge über zwölf Testdateien, alle
# mit derselben Zeile: `cannot import name 'pair_radii'`. Der Aufrufer stand
# seit 20:36 im Baum, die Funktion kam um 00:02 dazu — der Lauf fiel in die
# Lücke dazwischen. Niemand hatte etwas falsch gemacht: Erst den Aufrufer
# schreiben und dann die Funktion ist beim Arbeiten normal, und wann ein
# anderer sein Tor startet, weiß niemand.
#
# Was diese fünf Sekunden fangen, ist deshalb kein Fehler, sondern eine
# **falsche Fehlerursache**: Statt 27 roter Tests, die jeder erst einmal auf
# die eigene Änderung bezieht, steht hier ein Satz. Die Grenze gehört dazu —
# geprüft wird der Kern, den alle Testdateien gemeinsam importieren; ein
# halbfertiger Zustand in `app/ui/` oder in einer einzelnen Testdatei rutscht
# weiter durch. Das ist trotzdem der Großteil: Genau weil alle zwölf Dateien
# denselben Kern importieren, hat er alle zwölf umgeworfen.
#
# Vorgeschlagen von 3d-druck-64 nach dem Fall.
import_meldung=$(mktemp)
if ! "$PY" -c "import app.core.bootstrap as b; b.load_operations()" 2>"$import_meldung"; then
  echo "Der Baum ist gerade nicht importierbar — mit hoher Wahrscheinlichkeit"
  echo "ist das nicht deine Änderung. Sieh auf den Zeitstempel der genannten"
  echo "Datei, bevor du im eigenen Diff suchst:"
  sed 's/^/    /' "$import_meldung"
  rm -f "$import_meldung"
  exit 4
fi
rm -f "$import_meldung"
windowed=$(grep -lE "MainWindow|Viewport|pyvista" tests/test_*.py | tr '\n' ' ')
ignores=""
for file in $windowed; do ignores="$ignores --ignore=$file"; done

# **Exit 5 ist kein Fehllauf — für eine Fensterdatei.** pytest meldet damit
# „keine Tests gesammelt“, und das ist keine Aussage über den Code. Der Fall
# entsteht aus der Suche oben: Sie findet die Fensterdateien im *Text* und erwischt damit auch eine
# Datei, die über eine Ansicht **schreibt** statt eine zu bauen — stehen darin
# nur Leistungstests, sammelt `-m "not performance"` nichts. Am 22.08.2026
# landete `tests/test_performance.py` wegen zweier Docstrings hier und zählte
# als Fehllauf.
#
# **Und ein Abriss beim Abbau ist kein roter Test.** Drei Fensterdateien melden
# „N passed" und sterben danach beim Aufräumen — mit 127 oder mit einer
# Zugriffsverletzung. `CLAUDE.md` kennt den Fall und sagt ausdrücklich: Wer ihn
# nicht kennt, sucht den Fehler in einem Test, der nie fehlgeschlagen ist.
# Dieses Skript kannte ihn nicht, zählte ihn als Fehllauf — und damit war das
# Tor dauerhaft rot, ganz gleich wie sauber der Code war.
#
# Erkannt wird er an dem, was er ist: eine vollständige Zusammenfassung ohne
# ein einziges `failed` oder `error`. Wer sie hat, hat alle Tests bestanden;
# was danach passiert, ist ein Abriss und keine Aussage über den Code.
# **Verschwiegen wird nichts** — die Zeile „--> Exit 127" steht weiter da, sie
# zählt nur nicht mehr als Fehlschlag.
#
# Ohne Protokoll bleibt es bei der alten, strengen Bewertung: Ein Aufrufer, der
# die Ausgabe nicht mitschreibt, bekommt keinen Freibrief.
#
# **Für die Sammelgruppe gilt das Gegenteil, und das hat am 24.08.2026 eine
# halbe Prüfung gekostet.** Dort sind 3554 Tests zu erwarten; „keine gesammelt“
# ist dann kein harmloser Sonderfall, sondern der schlimmste Ausgang, den es
# gibt. `pytest-xdist` fehlte in der Deklaration, pytest antwortete mit
# `unrecognized arguments: -n` und Exit 4, und dieses Skript zählte das als
# **einen** Fehllauf — gleichwertig neben zwei sporadischen Fensterabstürzen.
# Der Bericht sagte „Läufe mit Fehler: 3" und sah aus wie drei kaputte Dateien.
# Tatsächlich waren Geometrie, Skizzen, Schichtanalyse und Agentenschicht gar
# nicht erst gelaufen.
#
# Die Lehre ist nicht „xdist eintragen" — das ist erledigt (ad2d1729). Sie ist,
# dass die Bewertung die falsche Frage stellte: „ist der Lauf rot?" statt „hat
# der Lauf stattgefunden?". Beantwortet wird die zweite jetzt an dem einzigen
# Zeugen, der beides unterscheidet — der Zusammenfassungszeile. Fehlt sie, hat
# kein Test stattgefunden, ganz gleich welchen Code die Shell zurückgibt.
#
# **Und die 127 ist gar kein eigener Code.** Am 23.08.2026 gemessen, indem
# dieselben Dateien nicht über die Shell, sondern direkt aus Python gestartet
# wurden — dort kommt der Windows-Rückgabewert an, statt der Bash-Konvention:
#
#     tests/test_first_run.py   0xC0000409   47 passed   (2 von 2 Läufen)
#     tests/test_chat_ui.py     0xC0000409   40 passed   (2 von 2 Läufen)
#
# `0xC0000409` ist der Code, den `CLAUDE.md` als bekannten Abbau-Absturz führt.
# Für diese beiden Dateien gilt also: **die 127 und der bekannte Absturz sind
# dasselbe**, und der Abriss ist nicht sporadisch — vier von vier Läufen, jedes
# Mal nach vollständiger Zusammenfassung.
#
# **Aber die 127 ist keine Signatur, sondern ein Vorhang.** Am selben Tag hat
# 3d-druck-3a zwei andere Dateien mit 127 gemessen, die **vor** der Schlusszeile
# rissen — dort stand `0xc0000374`, Heap-Korruption, und der Stapel sagte
# „Garbage-collecting". Wer aus „Exit 127" auf eine gemeinsame Ursache schließt,
# schließt zu schnell: Die Shell wirft verschiedene Windows-Codes in denselben
# Topf. Die Frage ist immer, was **hinter** der 127 steht, und die beantwortet
# nur ein Lauf ohne Shell dazwischen.
# Die Zusammenfassungszeile eines Laufs („3554 passed, 23 skipped in 61.00s"),
# oder nichts, wenn der Lauf keine geschrieben hat. Sie ist der Beleg dafür,
# dass überhaupt Tests ausgeführt wurden — ein Exit-Code ist das nicht.
zusammenfassung() {
  protokoll=${1:-}
  [ -n "$protokoll" ] && [ -f "$protokoll" ] || return 1
  grep -m1 -E "^[0-9]+ (passed|failed|error)" "$protokoll"
}

zaehlt_als_fehler() {
  status=$1
  protokoll=${2:-}
  [ "$status" -eq 0 ] && return 1
  [ "$status" -eq 5 ] && return 1
  if [ -n "$protokoll" ] && [ -f "$protokoll" ]; then
    if grep -qE "^[0-9]+ passed" "$protokoll" &&
       ! grep -qE "[0-9]+ (failed|error)" "$protokoll"; then
      return 1
    fi
  fi
  return 0
}

fails=0
# Die Namen der Fehlläufe, durch Leerzeichen getrennt — Testpfade haben keine.
schlecht=""

#: Wie viele Prozesse die Sammelgruppe teilen.
#:
#: **Eine feste Zahl und nicht `auto`.** Auf dieser Maschine wären es 32, und
#: xdist stirbt dabei im Verteiler (`INTERNALERROR: KeyError <WorkerController
#: gw13>`, keine Tests gelaufen). Wichtiger als der Absturz ist der Grundsatz:
#: `auto` heißt auf jeder Maschine etwas anderes, und ein Tor mit einer stillen
#: Variablen misst nicht überall dasselbe — dieselbe Überlegung wie bei den
#: maschinenabhängigen Bestwerten, die deshalb nicht im Repository liegen.
#:
#: Gemessen am 22.08.2026 (i9-13900K, 24 Kerne): seriell 175 s, mit acht
#: Prozessen 66 s. Die Gruppe darf das, weil kein Qt darin steckt — die
#: Fenstergruppe unten bekommt es ausdrücklich **nicht**, dort ist jeder
#: Prozess schon die Trennung.
KERNE=${SUITE_KERNE:-8}

protokoll=$(mktemp)
trap 'rm -f "$protokoll"' EXIT

echo "=== der Rest in einem Zug (-n $KERNE) ==="
PYTHONIOENCODING=utf-8 "$PY" -m pytest -q -m "not performance" $ignores -n "$KERNE"   2>&1 | tee "$protokoll"
status=${PIPESTATUS[0]}
echo "--> Exit $status"
# Erst die Frage, ob überhaupt gelaufen wurde, dann die, ob es grün war. In
# dieser Reihenfolge, weil ein Nichtlauf sonst als gewöhnlicher Fehllauf
# durchgeht — oder bei Exit 5 sogar als grün.
sammelgruppe=$(zusammenfassung "$protokoll" || true)
if [ -z "$sammelgruppe" ]; then
  fails=$((fails + 1))
  schlecht="$schlecht rest-in-einem-zug(Exit:$status,NICHT-GELAUFEN)"
elif zaehlt_als_fehler "$status" "$protokoll"; then
  fails=$((fails + 1))
  schlecht="$schlecht rest-in-einem-zug(Exit:$status)"
fi

for file in $windowed; do
  echo "=== $file ==="
  PYTHONIOENCODING=utf-8 "$PY" -m pytest -q -m "not performance" "$file"     2>&1 | tee "$protokoll"
  status=${PIPESTATUS[0]}
  echo "--> Exit $status"
  if zaehlt_als_fehler "$status" "$protokoll"; then
    fails=$((fails + 1))
    schlecht="$schlecht $file(Exit:$status)"
  fi
done

echo "======================================"
# **Die Zahl trägt ihr Gewicht nicht mit.** „Läufe mit Fehler: 3" wiegt eine
# rote Fensterdatei genauso wie den Ausfall von 3554 Tests. Deshalb steht die
# Sammelgruppe hier mit ihrer eigenen Zeile: Wer sie einmal gesehen hat, merkt
# beim nächsten Mal, wenn statt 3554 plötzlich 120 dort stehen.
if [ -z "$sammelgruppe" ]; then
  echo "!! DIE SAMMELGRUPPE LIEF NICHT — kein einziger Test ohne Qt wurde"
  echo "!! ausgeführt. Was sonst in diesem Bericht steht, sagt nichts über"
  echo "!! den Code. Sieh in das Protokoll, bevor du irgendetwas glaubst."
else
  echo "Sammelgruppe: $sammelgruppe"
fi
echo "Läufe mit Fehler: $fails"
# **Die Namen, nicht nur die Zahl.** Wer die Ausgabe durch `tail` schickt,
# verliert sonst genau das, was er braucht: Am 22.08.2026 meldete ein Lauf
# „Läufe mit Fehler: 4“, und niemand wusste, welche vier. Die Zeilen kosten
# nichts und stehen am Ende, wo auch ein kurzes `tail` sie noch mitnimmt.
for entry in $schlecht; do
  echo "  $entry"
done
exit $fails
