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

```
.venv\Scripts\python.exe -m ruff check . > "$TEMP/ruff.txt" 2>&1; echo "Exit=$?"
```

Wer den Fortschritt sehen will, nimmt `python -u`.

## Zweitens: die Suite läuft geteilt, nicht am Stück

`pytest -q` über alles kommt seit dem 16.08.2026 **nicht mehr durch**. In einem
Prozess baut die Suite über siebenhundert VTK-Fenster nacheinander auf, und
irgendwann reißt eine Grenze — zweimal gemessen, beide Male bei 83 Prozent
hängengeblieben.

Die CI löst das mit je einem Prozess pro Fensterdatei, und dafür gibt es ein
Skript: `suite-getrennt.sh` unter `.claude/.state/oberflaechen-durchsicht-2026-08-19/`.
Es sucht die Fensterdateien selbst (`MainWindow|Viewport|pyvista`) und zählt am
Ende „Läufe mit Fehler: N".

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

## Ablauf

Mit Argument läuft nur `pytest` darauf, und zwar direkt — ein einzelner Lauf
braucht weder Teilung noch Schloss:

```
.venv\Scripts\python.exe -m pytest -q $ARGUMENTS > "$TEMP/t.txt" 2>&1; echo "Exit=$?"
```

Ohne Argument das ganze Tor. Die drei Werkzeuge zuerst, weil sie Sekunden
dauern und die teuren Läufe erübrigen, wenn sie rot sind:

```
.venv\Scripts\python.exe -m ruff check . > "$TEMP/g1.txt" 2>&1; echo "ruff check   Exit=$?"
.venv\Scripts\python.exe -m ruff format --check . > "$TEMP/g2.txt" 2>&1; echo "ruff format  Exit=$?"
.venv\Scripts\python.exe -m mypy > "$TEMP/g3.txt" 2>&1; echo "mypy         Exit=$?"
```

Dann die Suite und die Leistungstests, beide unter dem Schloss, beide in einem
Aufruf, damit das Schloss nur einmal genommen wird:

```
.venv\Scripts\python.exe tools/gate_lock.py run --who "$CLAUDE_SESSION_NAME" --wait 1800 -- bash -c '.claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh > "$TEMP/g4.txt" 2>&1; echo "geteilt Exit=$?"; .venv/Scripts/python.exe -m pytest -q -m performance > "$TEMP/g5.txt" 2>&1; echo "performance Exit=$?"'
```

Alle fünf ausführen, auch wenn einer früh fehlschlägt — ein vollständiges Bild
ist mehr wert als ein schneller Abbruch. Fehlt `.venv`, sag das mit dem
Einrichtungsbefehl aus `AGENTS.md`, statt auf das System-Python auszuweichen.

**In einem Arbeitsbaum** gibt es kein `.venv`. Dann den
Interpreter des Hauptbaums mit vollem Pfad rufen und `cwd` im Arbeitsbaum
lassen; gemessen am 22.08.2026, die Suite läuft so.

## Zählen

**Die Zusammenfassungszeilen schreibt pytest erst am Schluss.** Ein
`grep -c "^FAILED"` über ein laufendes Protokoll liefert deshalb immer null,
auch wenn zwei Tests längst rot sind — dieser Fehler wurde am 22.08. dreimal
hintereinander gemacht.

Gezählt wird über die **Fortschrittszeichen** (`.` bestanden, `s`
übersprungen, `F`/`E` rot). Ihre Position im Strom nennt zusammen mit
`pytest --collect-only -q` den Namen des Tests, ohne den Lauf zu wiederholen.

Die Zusicherung ist immer der **Exit-Code**, nie eine Zeile im Text.

## Ein grün gemeldeter Lauf, der rot endet, ist kein roter Test

Drei Fensterdateien enden nach „N passed" mit `0xC0000409` oder einer
Zugriffsverletzung — ein Riss beim **Abbau**, nachdem jeder Test bestanden hat
(`test_ui.py`, `test_chat_ui.py`, `test_first_run.py`). `suite-getrennt.sh`
zählt sie als Fehler und gibt einen Exit ungleich null, obwohl kein Test
fehlgeschlagen ist.

Der offene Punkt dazu steht in `ROADMAP.md`. Wer das nicht weiß, sucht den
Fehler in einem Test, der nie fehlgeschlagen ist — also erst ins Protokoll
sehen, ob vor dem Abbruch „N passed" steht.

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
