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
# das setzt `tools/to_main.py`), dann die eigene `.venv`, dann die des
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
# Pytest löst auch indirekte Fixtures aus ``conftest.py`` auf. Damit hängt die
# Trennung daran, ob ein Test wirklich ``qt_app`` braucht — nicht daran, ob in
# Quelltext oder Docstring zufällig MainWindow, Viewport oder pyvista steht.
# Der Windows-Interpreter schreibt CRLF. Bleibt das ``\r`` am Dateinamen,
# sucht pytest wörtlich nach ``tests/test_ui.py\r`` und meldet jede vorhandene
# Fensterdatei als fehlend.
# Der Prüfstand will nur die Entscheidungsfunktionen (siehe den Ausstieg
# weiter unten) und braucht die Dateiliste nicht — sie zu erheben kostet
# einen Python-Start je Aufruf, und der Test ruft achtmal.
if [ -n "${SUITE_NUR_FUNKTIONEN:-}" ]; then
  windowed=""
else
  windowed=$("$PY" tools/list_windowed_tests.py | tr -d '\r' | tr '\n' ' ')
fi
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

# **Die Fortschrittszeichen, wenn die Zusammenfassung fehlt.**
#
# Ein Riss beim Abbau verschluckt die Schlusszeile — der Prozess stirbt,
# nachdem der letzte Test durch ist und bevor pytest sie schreibt. Was ihn
# überlebt, sind die Zeichen davor: ein Punkt je bestandenem Test, ``F`` und
# ``E`` für die anderen. Gemessen am 30.08.2026 an einer Portion von
# ``test_ui.py``: sechzig Punkte, keine Zusammenfassung, Exit 127.
#
# Ohne diesen Leser wäre jede solche Portion ein „NICHT-GELAUFEN", also der
# schwerste Befund, den dieses Skript kennt — für einen Lauf, in dem jeder
# einzelne Test bestanden hat.
#
# Gezählt wird nur, was am Zeilenanfang steht oder auf einen Fortschrittsblock
# folgt; ein ``F`` mitten in einem Dateinamen zählt nicht.
fortschritt() {
  protokoll=${1:-}
  [ -n "$protokoll" ] && [ -f "$protokoll" ] || return 1
  grep -oE "^[.sFExX]+" "$protokoll" | tr -d "\n"
}

# **Ein Riss, der Tests verschluckt hat — und kein roter Test.**
#
# ``zaehlt_als_fehler`` beantwortet „ist dieser Lauf schlecht ausgegangen".
# Für die Halbierung unten braucht es die schärfere Frage: Ist er schlecht
# ausgegangen, **weil er nicht zu Ende lief**? Nur dann hilft Teilen. Bei
# echten roten Tests hilft es nicht — sie bleiben in jeder Hälfte rot, und
# das Skript teilte bis zur Mindestgröße, ohne etwas zu gewinnen.
#
# Der Unterschied ist an drei Stellen abzulesen: eine Schlusszeile mit
# ``failed``/``error``, ein rotes Zeichen im Fortschritt, oder schlicht
# weniger Zeichen als erwartet. Die ersten beiden sind Testfehler, das
# dritte ist der Riss.
nicht_gelaufen() {
  status=$1
  protokoll=${2:-}
  soll=${3:-}
  [ "$status" -eq 0 ] && return 1
  [ -n "$protokoll" ] && [ -f "$protokoll" ] || return 1
  [ -n "$soll" ] || return 1
  grep -qE "[0-9]+ (failed|error)" "$protokoll" && return 1
  zeichen=$(fortschritt "$protokoll" || true)
  printf '%s' "$zeichen" | grep -q "[FEX]" && return 1
  [ "${#zeichen}" -lt "$soll" ]
}

zaehlt_als_fehler() {
  status=$1
  protokoll=${2:-}
  #: Wie viele Tests der Lauf umfassen sollte. Leer heißt „unbekannt", und
  #: dann bleibt es bei der strengen Bewertung — ein Aufrufer, der die Zahl
  #: nicht kennt, bekommt keinen Freibrief.
  soll=${3:-}
  [ "$status" -eq 0 ] && return 1
  [ "$status" -eq 5 ] && return 1
  if [ -n "$protokoll" ] && [ -f "$protokoll" ]; then
    if grep -qE "^[0-9]+ passed" "$protokoll" &&
       ! grep -qE "[0-9]+ (failed|error)" "$protokoll"; then
      return 1
    fi
    # **Und ohne Schlusszeile entscheiden die Zeichen — aber nur, wenn sie
    # vollzählig sind.**
    #
    # Ein Riss beim Abbau nimmt die Zusammenfassung mit; die Punkte davor
    # stehen noch da. Sie allein genügen jedoch nicht: Ein Riss **mitten** im
    # Lauf hinterlässt ebenfalls nur Punkte, und dreißig gelaufene von sechzig
    # sähen aus wie ein sauberer Durchlauf. Die beiden Fälle unterscheidet
    # nichts als die **Anzahl** — deshalb kommt die Soll-Größe als dritter
    # Parameter herein, und ohne sie bleibt es bei der strengen Bewertung.
    #
    # ``s`` (übersprungen) und ``x`` (erwartet fehlgeschlagen) zählen als
    # gelaufen und als grün: Ein übersprungener Test ist eine Entscheidung des
    # Tests, kein Fehlschlag. Rot sind ``F``, ``E`` und ``X`` — das große X ist
    # ein Test, der bestehen sollte und es unerwartet tut, und auch das will
    # jemand wissen.
    # Grün wird hier nur, was **beides** erfüllt: keine roten Zeichen und so
    # viele Zeichen, wie Tests erwartet wurden. Ohne bekannte Soll-Größe bleibt
    # es bei der strengen Bewertung — ein Aufrufer, der die Zahl nicht kennt,
    # bekommt keinen Freibrief. (Der erste Entwurf schrieb an dieser Stelle
    # ein return 1, also grün, und der Kommentar daneben behauptete das
    # Gegenteil. Eine zutreffende Begründung deckt eine Lücke besonders gut.)
    zeichen=$(fortschritt "$protokoll" || true)
    if [ -n "$zeichen" ] && ! printf '%s' "$zeichen" | grep -q "[FEX]"; then
      if [ -n "$soll" ] && [ "${#zeichen}" -ge "$soll" ]; then
        return 1
      fi
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

# **Ein Ausstieg für den Prüfstand, und der Grund steht in ``tests.md``:** Ein
# Prüfwerkzeug ist auch nur Code, und es war schon viermal der Fehler. Die vier
# Funktionen darüber entscheiden, ob ein Lauf als grün, als rot oder als
# „nie gelaufen" gilt — wer sie prüfen will, muss sie rufen können, ohne die
# ganze Suite zu starten. ``tests/test_suite_script.py`` tut genau das:
# sourcen, gefälschte Protokolle vorlegen, jeden Zweig einmal gehen.
[ -n "${SUITE_NUR_FUNKTIONEN:-}" ] && return 0

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

#: Wie viele Tests eine Portion höchstens umfasst.
#:
#: **Ein eigener Prozess je Datei genügt nicht mehr.** Die größte Fensterdatei
#: ist auf 372 Tests gewachsen, und sie reißt auch allein: Exit 139,
#: Zugriffsverletzung, **keine Zusammenfassung** — der Lauf sagt gar nichts,
#: und damit ist er der schwerste Befund, den dieses Skript kennt. Gemessen am
#: 30.08.2026 dieselbe Datei in Portionen von sechzig: sieben Läufe, 372 von
#: 372 bestanden, ein Abriss beim Abbau nach vollständigem Durchlauf.
#:
#: Sechzig ist kein Naturgesetz, sondern die Zahl, die gemessen durchkommt.
#: Wer sie ändert, misst nach.
PORTION=${SUITE_PORTION:-60}

#: Wie klein eine Portion höchstens wird, bevor der Riss als Befund gilt.
#:
#: **Die Portionsgröße ist keine Konstante, und deshalb steht hier eine
#: Untergrenze statt einer Liste je Datei.** Sechzig kommt bei ``test_ui.py``
#: durch; ``test_print_settings_ui.py`` riss am 31.08.2026 schon bei vierzig,
#: auf ruhiger Maschine, sieben von sieben. Gemessen war dort auch, dass es an
#: keinem einzelnen Test hängt: Dreiundzwanzig rissen, vierundzwanzig nicht,
#: vierunddreißig liefen, vierzig rissen wieder. Wer eine Zahl je Datei
#: pflegt, pflegt sie falsch — sie verschiebt sich mit jedem Test, der
#: dazukommt.
#:
#: Also halbiert das Skript selbst. Vier ist der Boden: Darunter sagt eine
#: weitere Teilung nichts mehr über die Menge, und ein Riss bei vier Tests ist
#: ein Befund, den jemand ansehen muss.
MINDEST=${SUITE_MIN_PORTION:-4}

# Die Testnamen einer Datei, eine je Zeile. Der Windows-Interpreter schreibt
# CRLF; bleibt das ``\r`` am Namen, sucht pytest wörtlich danach und findet
# nichts.
namen_von() {
  "$PY" -m pytest --collect-only -q -m "not performance" "$1" 2>/dev/null \
    | grep -E "^tests/" | tr -d "\r"
}

for file in $windowed; do
  namen=$(namen_von "$file")
  anzahl=$(printf '%s\n' "$namen" | grep -c "::" || true)

  if [ "$anzahl" -le "$PORTION" ]; then
    echo "=== $file ==="
    PYTHONIOENCODING=utf-8 "$PY" -m pytest -q -m "not performance" "$file"     2>&1 | tee "$protokoll"
    status=${PIPESTATUS[0]}
    echo "--> Exit $status"
    if zaehlt_als_fehler "$status" "$protokoll" "$anzahl"; then
      fails=$((fails + 1))
      schlecht="$schlecht $file(Exit:$status)"
    fi
    continue
  fi

  # **Portionsweise, und jede Portion zählt für sich.** Ein Riss in der
  # vierten Portion sagt nichts über die anderen sechs — vorher nahm er die
  # ganze Datei mit, und mit ihr die Auskunft, welche Tests überhaupt liefen.
  echo "=== $file ($anzahl Tests, Portionen zu $PORTION) ==="
  # **Eine Warteschlange und keine feste Schrittweite.** Reißt ein Stück so,
  # dass Tests darin nie liefen, wird es halbiert und beide Hälften kommen
  # vorn wieder herein — dieselbe Datei, kleinere Häppchen, ohne dass jemand
  # eine Zahl pflegt. Ein Riss beim *Abbau* (alle Zeichen da) zählt
  # ausdrücklich nicht: Dort ist jeder Test gelaufen, und Teilen brächte nur
  # einen zweiten Prozessstart.
  warteschlange=()
  von=1
  while [ "$von" -le "$anzahl" ]; do
    bis=$((von + PORTION - 1))
    [ "$bis" -gt "$anzahl" ] && bis=$anzahl
    warteschlange+=("$von:$bis")
    von=$((bis + 1))
  done

  teil=0
  while [ "${#warteschlange[@]}" -gt 0 ]; do
    stueck=${warteschlange[0]}
    warteschlange=("${warteschlange[@]:1}")
    von=${stueck%%:*}
    bis=${stueck##*:}
    teil=$((teil + 1))
    # **In ein Feld, nicht in eine Zeichenkette.** Parametrisierte Testnamen
    # tragen eckige Klammern (``test_x[raft-prusa]``), und eine unquotierte
    # Zeichenkette liest die Shell als Dateimuster — sie sucht eine Datei
    # namens ``raft`` oder ``prusa``, findet keine, und pytest bekommt einen
    # Namen, den es nicht kennt. Gemessen am 30.08.2026: zwei Portionen mit
    # Exit 4, und Exit 4 ist ein Kommandozeilenfehler und kein roter Test.
    portion=()
    while IFS= read -r name; do
      [ -n "$name" ] && portion+=("$name")
    done < <(printf '%s\n' "$namen" | sed -n "${von},${bis}p")
    PYTHONIOENCODING=utf-8 "$PY" -m pytest -q -m "not performance" "${portion[@]}" \
      2>&1 | tee "$protokoll"
    status=${PIPESTATUS[0]}
    groesse=$((bis - von + 1))
    echo "--> Teil $teil (Tests $von-$bis, $groesse Stück): Exit $status"
    if nicht_gelaufen "$status" "$protokoll" "$groesse" && [ "$groesse" -gt "$MINDEST" ]; then
      # Vorn einreihen und nicht hinten: Die Hälften gehören zu dieser Datei
      # und sollen unmittelbar folgen, damit das Protokoll in der Reihenfolge
      # bleibt, in der jemand es liest.
      mitte=$((von + groesse / 2 - 1))
      warteschlange=("$von:$mitte" "$((mitte + 1)):$bis" "${warteschlange[@]}")
      echo "--> geteilt in $von-$mitte und $((mitte + 1))-$bis (der Lauf verschluckte Tests)"
      continue
    fi
    if zaehlt_als_fehler "$status" "$protokoll" "$groesse"; then
      fails=$((fails + 1))
      schlecht="$schlecht $file:Teil$teil(Exit:$status)"
    fi
  done
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
