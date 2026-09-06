---
name: pruefen
description: >
  Führt das vollständige Tor von Solidon aus — die geteilte Testsuite, die
  Leistungstests, ruff check, ruff format --check und mypy — unter einem
  Schloss, damit parallele Sitzungen sich nicht gegenseitig verfälschen, und
  meldet das Ergebnis zusammengefasst. Benutzen, bevor etwas als fertig gilt,
  vor jedem Commit und nach jedem Arbeitsschritt an app/ oder tests/.
argument-hint: "[optional: Testdatei oder -pfad]"
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Prüfen

Rot heißt nicht fertig — es gibt keine Ausnahme, keine „unwichtige" Warnung und
kein „das war vorher schon so", ohne dass du es nachweist.

Drei Dinge an diesem Ablauf sehen nach Umständlichkeit aus und sind es nicht.
Jedes hat am 22.08.2026 eine Stunde gekostet, bevor es hier stand.

## Erstens: nie eine Pipe um einen Lauf

**Der Rückgabewert einer Pipe ist der des letzten Glieds.** `pytest … | tail`
meldet den Erfolg von `tail`; ein Absturz mit 139 sah damit zweimal wie ein
grüner Lauf aus, und ein `ruff check … | tail -2 && git commit` committete
trotz roter Prüfung.

Und pytest **puffert** hinter einer Pipe: Ein Lauf mit `-q 2>&1 | tail -25`
gab anderthalb Stunden lang kein einziges Zeichen aus und stand dabei längst.

Also: in eine Datei schreiben, den Rückgabewert **davon** lesen, danach die
Datei ansehen.

Vor den Befehlen den **geprüften Interpreter dieses Arbeitsbaums** im aufrufenden Prozess als
Umgebungsvariable `SUITE_PYTHON` setzen, beispielsweise den absoluten Pfad zu
`.venv314/Scripts/python.exe` in der privaten Python-3.14-Prüfumgebung.
Eine reguläre Umgebung liegt unter `.venv/Scripts/python.exe`, auf Linux und
macOS unter `.venv/bin/python`. Die Versionsprobe muss zu `constraints.txt`
und der Prüfakte passen. Ein ausdrücklich gesetzter ungültiger Pfad stoppt;
er darf nicht durch eine ältere Umgebung ersetzt werden.

```
S="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-$$}}"; "$SUITE_PYTHON" -m ruff check . > "$TEMP/ruff-$S.txt" 2>&1; echo "Exit=$?"
```

Wer den Fortschritt sehen will, nimmt `"$SUITE_PYTHON" -u`.

**Der Sitzungsmarker im Dateinamen ist kein Schmuck.** `$TEMP` ist
benutzerweit, und an diesem Projekt arbeiten zwei bis vier Sitzungen. Bis zum
04.09.2026 hießen die sieben Ausgaben hier fest `ruff.txt`, `t.txt` und `g1`
bis `g5` — zwei Sitzungen schrieben also in dieselbe Datei. Der Schaden ist
nicht kaputter Müll, sondern **plausibler**: Wer danach seinen Exit-Code aus
der Datei liest, bekommt eine gültig aussehende Zahl aus einem fremden Lauf.
Damit brachte ausgerechnet die Empfehlung dieses Abschnitts die Falle mit,
sobald zwei Sitzungen ihr folgten — dieselbe Familie wie der `tail`-Fall und
der `echo`-Fall in `CLAUDE.md`: Gefährlich ist nicht der Abbruch, sondern die
glaubwürdige falsche Auskunft.

Gefunden von solidon-b4 am 04.09.2026, und zwar als Beobachtung: Während ihr
geteilter Lauf noch bei `tests/test_sculpt_session.py` stand, lag in `g5.txt`
bereits ein vollständiges Ergebnis der Leistungstests. Sequenziell unmöglich.

Die Kette hat drei Glieder: `CODEX_THREAD_ID` bezeichnet die Aufgabe,
`CODEX_SESSION_ID` ist der kompatible Rückfall, `$$` der letzte Ausweg. Die
Befehle sind Bash-Befehle. Codex übergibt auf diesem Windows-Rechner jeden
Block als `-lc`-Argument an das vorhandene Git Bash; Bash-Code läuft nie direkt
in PowerShell. Der Einstieg und zugleich die Probe für Interpreter und
Slash-Pfad lautet:

```powershell
$env:SUITE_PYTHON = (Resolve-Path '.venv314/Scripts/python.exe').Path
& 'C:\Program Files\Git\bin\bash.exe' -lc '"$SUITE_PYTHON" --version'
```

Die Probe muss eine Python-Version und Exit 0 liefern. Danach denselben Einstieg
mit dem jeweiligen Bash-Block anstelle der Probe verwenden.

## Zweitens: die Suite läuft geteilt, nicht am Stück

`pytest -q` über alles kommt seit dem 16.08.2026 **nicht mehr durch**. In einem
Prozess baut die Suite über siebenhundert VTK-Fenster nacheinander auf, und
irgendwann reißt eine Grenze — zweimal gemessen, beide Male bei 83 Prozent
hängengeblieben.

Die CI löst das mit je einem Prozess pro Fensterdatei, und dafür gibt es ein
Skript: `suite-getrennt.sh` unter `.claude/.state/oberflaechen-durchsicht-2026-08-19/`.
Es bestimmt die Fensterdateien aus Pytests aufgelöstem Fixture-Graphen,
auch über mittelbare `qt_app`-Abhängigkeiten, und zählt am Ende „Läufe mit
Fehler: N". Ein Sammlungsfehler hält an; eine Teilmenge wird nicht still zur
vollständigen Liste erklärt.

**Es lässt die Leistungstests aus** (`-m "not performance"`), also gehören sie
als eigener Lauf dazu. Der geteilte Lauf allein ist nicht das Tor.

## Drittens: unter dem Schloss

An diesem Projekt arbeiten oft zwei bis vier Sitzungen. Die Dateien trennt
Codex über Arbeitsbäume, die **Maschine** trennt niemand — und gegen
Fremdlast zu messen erzeugt Regressionen, die es nicht gibt: 48 Prozent Last
ergaben fünf rote Leistungstests, 16 Prozent bei identischem Stand neunzehn
grüne.

`tools/gate_lock.py` umschließt einen Lauf. Ist das Tor belegt, endet es mit
**75** und nennt den Halter; `--wait SEKUNDEN` wartet stattdessen.

**Schloss und Dateinamen sind zwei Werkzeuge, nicht eines** — sie zu
verwechseln war der Fehler, der die festen Namen so lange stehen ließ. Das
Schloss trennt die **Messung**, deshalb laufen die Leistungstests darunter; die
Dateinamen trennen die **Ausgabe**, und die braucht kein Schloss, sondern einen
eindeutigen Namen. Das gilt gerade auch für die drei schnellen Läufe weiter
unten, die ausdrücklich **ohne** Schloss fahren: Sie sind gegen Fremdlast
gleichgültig und gegen einen fremden Schreiber nicht.

## Ablauf

Mit Argument läuft nur `pytest` darauf, und zwar direkt — ein einzelner Lauf
braucht weder Teilung noch Schloss:

```
S="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-$$}}"; "$SUITE_PYTHON" -m pytest -q $ARGUMENTS > "$TEMP/t-$S.txt" 2>&1; echo "Exit=$?"
```

Ohne Argument das ganze Tor. Die drei Werkzeuge zuerst, weil sie Sekunden
dauern und die teuren Läufe erübrigen, wenn sie rot sind:

```
S="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-$$}}"; "$SUITE_PYTHON" -m ruff check . > "$TEMP/g1-$S.txt" 2>&1; echo "ruff check   Exit=$?"
S="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-$$}}"; "$SUITE_PYTHON" -m ruff format --check . > "$TEMP/g2-$S.txt" 2>&1; echo "ruff format  Exit=$?"
S="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-$$}}"; "$SUITE_PYTHON" -m mypy > "$TEMP/g3-$S.txt" 2>&1; echo "mypy         Exit=$?"
```

Die Zuweisung steht **vor** dem Lauf, nicht dahinter: `$?` gehört dem letzten
Befehl, und ein `S=…` danach überschriebe genau die Zahl, die gebraucht wird.

Dann die Suite und die Leistungstests, beide unter dem Schloss, beide in einem
Aufruf, damit das Schloss nur einmal genommen wird:

```
S="${CODEX_THREAD_ID:-${CODEX_SESSION_ID:-$$}}"
export S SUITE_PYTHON
"$SUITE_PYTHON" tools/gate_lock.py run --who "$S" --wait 1800 -- bash -c '
  .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh > "$TEMP/g4-$S.txt" 2>&1
  suite_status=$?
  echo "geteilt Exit=$suite_status"
  "$SUITE_PYTHON" -m pytest -q -m performance > "$TEMP/g5-$S.txt" 2>&1
  performance_status=$?
  echo "performance Exit=$performance_status"
  [ "$suite_status" -eq 0 ] && [ "$performance_status" -eq 0 ]
'
```

`export S`, weil der innere `bash -c` eine eigene Shell ist — ohne das stünde
dort ein leerer Marker, und beide Läufe schrieben wieder in dieselbe Datei.

**Und `--who` nimmt denselben Marker.** Nur `CODEX_THREAD_ID` oder nur
`CODEX_SESSION_ID` zu verwenden wäre unnötig brüchig; dieselbe Rückfallkette
benennt deshalb Schloss und Ausgabedateien.

Alle fünf ausführen, auch wenn einer früh fehlschlägt — ein vollständiges Bild
ist mehr wert als ein schneller Abbruch. Der gemeinsame Schlossaufruf bewahrt
beide Rückgabewerte und ist nur bei zwei erfolgreichen Prozessen erfolgreich.
Fehlt die geprüfte Umgebung, den Einrichtungsbefehl aus `CLAUDE.md` nennen,
statt auf ein ungeprüftes System-Python auszuweichen.

**In einem Arbeitsbaum ohne eigene Umgebung** einen ausdrücklich geprüften
Interpreter mit vollem Pfad als `SUITE_PYTHON` setzen und `cwd` im Arbeitsbaum
lassen. Der isolierte Python-Runner übernimmt selbst seinen aufrufenden
Interpreter; er sucht keine zweite Umgebung.

## Zählen

**Die Zusammenfassungszeilen schreibt pytest erst am Schluss.** Ein
`grep -c "^FAILED"` über ein laufendes Protokoll liefert deshalb immer null,
auch wenn zwei Tests längst rot sind — dieser Fehler wurde am 22.08. dreimal
hintereinander gemacht.

Gezählt wird über die **Fortschrittszeichen** (`.` bestanden, `s`
übersprungen, `F`/`E` rot). Ihre Position im Strom nennt zusammen mit
`pytest --collect-only -q` den Namen des Tests, ohne den Lauf zu wiederholen.

Die Zusicherung ist immer der **Exit-Code**, nie eine Zeile im Text.

## Ein Nichtnull-Prozessausgang bleibt rot

Auch „N passed" oder vollständige Fortschrittszeichen machen einen nativen
Abbruch beim Aufräumen nicht erfolgreich. Das geteilte Tor zählt jeden
Nichtnull-Exit, einschließlich erfolgloser Sammlungen, und gibt insgesamt
0 oder 1 zurück.

Portionen mit fehlenden Tests werden weiterhin zur Diagnose halbiert. Der
ursprüngliche Abbruch wird vor der Wiederholung erfasst und bleibt im
Ergebnis. Erfolgreiche kleinere Teilstücke ergänzen den Nachweis; sie löschen
keinen Fehler desselben Laufs. Ein späterer vollständig sauberer Lauf ist
als eigener Lauf mit seinem echten Prozessausgang auszuweisen.

## Melden

Eine Zeile je Lauf: bestanden oder nicht, bei Fehlschlag die Anzahl und die
betroffenen Dateien. Danach die Fehler selbst, gruppiert nach Ursache — nicht
die rohe Ausgabe durchgereicht.

`ruff format --check` meldet nur, dass eine Datei anders aussehen würde. Das
behebst du mit `ruff format .` ohne Rückfrage. Alles andere ist eine
inhaltliche Änderung: erst verstehen, warum der Lauf rot ist, dann beheben —
nie einen Test anpassen, damit er grün wird, und nie eine Warnung
unterdrücken, die `filterwarnings = ["error"]` absichtlich zum Fehler macht.

**Ein roter Leistungstest ist erst dann eine Regression, wenn er es zweimal
ist.** Denselben Stand ein zweites Mal fahren, nicht den Vorgängerstand:
Schwankt die Menge der roten Tests, war es Last. Die Begründung steht in
`.claude/rules/tests.md`.

## Danach

War alles grün und es liegen ungestagte Änderungen vor, nenne den nächsten
Schritt: committen (`/liefern`) oder weiterarbeiten. War etwas rot, ist der
nächste Schritt die Behebung — nicht der Commit.
