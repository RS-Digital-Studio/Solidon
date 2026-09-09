---
name: pruefen
description: >
  Führt das vollständige Tor von Solidon aus — die geteilte Testsuite, die
  Leistungstests, ruff check, ruff format --check und mypy — und meldet das
  Ergebnis zusammengefasst. Das vollständige Tor läuft vor dem Commit. Nach
  einem Arbeitsschritt nur die betroffenen Tests über tools/affected_tests.py.
argument-hint: "[optional: Testdatei oder -pfad]"
allowed-tools: Bash, Read, Edit, Grep, Glob
---

# Prüfen

Rot heißt nicht fertig — es gibt keine Ausnahme, keine „unwichtige" Warnung und
kein „das war vorher schon so", ohne dass du es nachweist.

Zwei Dinge an diesem Ablauf sehen nach Umständlichkeit aus und sind es nicht.
Beide haben am 22.08.2026 eine Stunde gekostet, bevor sie hier standen.

## Erstens: nie eine Pipe um einen Lauf

**Der Rückgabewert einer Pipe ist der des letzten Glieds.** `pytest … | tail`
meldet den Erfolg von `tail`; ein Absturz mit 139 sah damit zweimal wie ein
grüner Lauf aus, und ein `ruff check … | tail -2 && git commit` committete
trotz roter Prüfung.

Und pytest **puffert** hinter einer Pipe: Ein Lauf mit `-q 2>&1 | tail -25`
gab anderthalb Stunden lang kein einziges Zeichen aus und stand dabei längst.

Also: in eine Datei schreiben, den Rückgabewert **davon** lesen, danach die
Datei ansehen.

Vor den Befehlen den **geprüften Interpreter dieses Arbeitsbaums** im
aufrufenden Prozess als Umgebungsvariable `SUITE_PYTHON` setzen. Die reguläre
Umgebung liegt unter `.venv/Scripts/python.exe`, auf Linux und macOS unter
`.venv/bin/python`. Die Versionsprobe muss zu `pyproject.toml` passen;
`tools/check_env.py` prüft die Pakete gegen `constraints.txt`. Ein ausdrücklich
gesetzter ungültiger Pfad stoppt; er darf nicht durch eine ältere Umgebung
ersetzt werden.

```
"$SUITE_PYTHON" -m ruff check . > "$TEMP/ruff.txt" 2>&1; echo "Exit=$?"
```

Wer den Fortschritt sehen will, nimmt `"$SUITE_PYTHON" -u`.

Die Befehle unten sind Bash-Befehle. In PowerShell jeden Block als
`-lc`-Argument an Git Bash übergeben; Bash-Code läuft nie direkt in
PowerShell. Der Einstieg lautet:

```powershell
$env:SUITE_PYTHON = (Resolve-Path '.venv/Scripts/python.exe').Path
& 'C:\Program Files\Git\bin\bash.exe' -lc '"$SUITE_PYTHON" --version'
```

Die Probe muss eine Python-Version und Exit 0 liefern. Danach denselben
Einstieg mit dem jeweiligen Bash-Block anstelle der Probe verwenden.

Wer bereits in Bash arbeitet, setzt und prüft die Variable dort:

```bash
export SUITE_PYTHON="$(pwd)/.venv/Scripts/python.exe"
"$SUITE_PYTHON" --version
```

Auf Linux und macOS lautet der Interpreterpfad `.venv/bin/python`.

## Zweitens: die Suite läuft geteilt, nicht am Stück

`pytest -q` über alles kommt seit dem 16.08.2026 **nicht mehr durch**. In einem
Prozess baut die Suite über siebenhundert Fenster mit Ansicht nacheinander auf,
und irgendwann reißt eine Grenze — zweimal gemessen, beide Male bei 83 Prozent
hängengeblieben.

Die CI löst das mit je einem Prozess pro Fensterdatei, und dafür gibt es ein
Skript: `suite-getrennt.sh` unter `.claude/.state/oberflaechen-durchsicht-2026-08-19/`.
Es bestimmt die Fensterdateien aus Pytests aufgelöstem Fixture-Graphen,
auch über mittelbare `qt_app`-Abhängigkeiten, und zählt am Ende „Läufe mit
Fehler: N". Ein Sammlungsfehler hält an; eine Teilmenge wird nicht still zur
vollständigen Liste erklärt.

**Es lässt die Leistungstests aus** (`-m "not performance"`), also gehören sie
als eigener Lauf dazu. Der geteilte Lauf allein ist nicht das Tor.

## Ablauf

Mit Dateipfaden laufen die betroffenen Tests über `affected_tests.py --run`.
Das Werkzeug trennt Fensterdateien auch dann, wenn mehrere angegeben sind.
Die Datei im folgenden Beispiel durch die genannten Dateien ersetzen:

```
"$SUITE_PYTHON" tools/affected_tests.py tests/test_agent_mirror.py --run > "$TEMP/t.txt" 2>&1; echo "Exit=$?"
```

Ohne Argument das ganze Tor. Die drei schnellen Werkzeuge zuerst, danach
die beiden Testläufe; alle fünf Ergebnisse gehören zum Befund:

```
"$SUITE_PYTHON" -m ruff check . > "$TEMP/g1.txt" 2>&1; echo "ruff check   Exit=$?"
"$SUITE_PYTHON" -m ruff format --check . > "$TEMP/g2.txt" 2>&1; echo "ruff format  Exit=$?"
"$SUITE_PYTHON" -m mypy > "$TEMP/g3.txt" 2>&1; echo "mypy         Exit=$?"
```

**`$?` gehört dem letzten Befehl, und „letzter" heißt wörtlich.** Was zwischen
dem Lauf und dem Lesen des Codes steht — eine Zuweisung, ein `echo`, eine
Kommandosubstitution — überschreibt genau die Zahl, die gebraucht wird.

Dann die Suite und die Leistungstests:

```
.claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh > "$TEMP/g4.txt" 2>&1
echo "geteilt Exit=$?"
"$SUITE_PYTHON" -m pytest -q -m performance > "$TEMP/g5.txt" 2>&1
echo "performance Exit=$?"
```

Alle fünf ausführen, auch wenn einer früh fehlschlägt — ein vollständiges Bild
ist mehr wert als ein schneller Abbruch. Das Tor ist nur grün, wenn alle fünf
mit 0 enden. Fehlt die geprüfte Umgebung, den Einrichtungsbefehl aus
`CLAUDE.md` nennen, statt auf ein ungeprüftes System-Python auszuweichen.

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

`ruff format --check` meldet nur, dass eine Datei anders aussehen würde; sie
mit `ruff format <dateipfade>` formatieren. Alles andere ist eine inhaltliche
Änderung: erst verstehen, warum der Lauf rot ist, dann beheben — nie einen
Test anpassen, damit er grün wird, und nie eine Warnung unterdrücken, die
`filterwarnings = ["error"]` absichtlich zum Fehler macht.

**Ein roter Leistungstest ist erst dann eine Regression, wenn er es zweimal
ist.** Denselben Stand ein zweites Mal fahren, nicht den Vorgängerstand:
Schwankt die Menge der roten Tests, war es Last auf der Maschine. Was sonst
gerade rechnet, gehört dabei zur Messung — die Begründung steht in
`.claude/rules/tests.md`.

## Danach

War alles grün und es liegen ungestagte Änderungen vor, nenne den nächsten
Schritt: committen (`/liefern`) oder weiterarbeiten. War etwas rot, ist der
nächste Schritt die Behebung — nicht der Commit.
