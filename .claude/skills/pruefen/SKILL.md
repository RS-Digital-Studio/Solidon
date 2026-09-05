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
S="${CLAUDE_SESSION_NAME:-${CLAUDE_CODE_SESSION_ID:-$$}}"; .venv\Scripts\python.exe -m ruff check . > "$TEMP/ruff-$S.txt" 2>&1; echo "Exit=$?"
```

Wer den Fortschritt sehen will, nimmt `python -u`.

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

Die Kette hat drei Glieder, weil das erste nicht überall gesetzt ist:
`CLAUDE_SESSION_NAME` trägt einen lesbaren Namen, wenn die Sitzung einen hat
(`claude --worktree <name>`), sonst ist sie **leer** — gemessen am 04.09.2026;
`CLAUDE_CODE_SESSION_ID` steht immer und ist über Aufrufe hinweg stabil, `$$`
ist der letzte Ausweg.

## Zweitens: die Suite läuft geteilt, nicht am Stück

`pytest -q` über alles kommt seit dem 16.08.2026 **nicht mehr durch**. In einem
Prozess baut die Suite über siebenhundert VTK-Fenster nacheinander auf, und
irgendwann reißt eine Grenze — zweimal gemessen, beide Male bei 83 Prozent
hängengeblieben.

Die CI löst das mit je einem Prozess pro Fensterdatei, und dafür gibt es ein
Skript: `suite-getrennt.sh` unter `.claude/.state/oberflaechen-durchsicht-2026-08-19/`.
Es sucht die Fensterdateien selbst (über den Fixture-Graphen,
`tools/list_windowed_tests.py`) und zählt am Ende „Läufe mit Fehler: N".

**Es lässt die Leistungstests aus** (`-m "not performance"`), also gehören sie
als eigener Lauf dazu. Der geteilte Lauf allein ist nicht das Tor.

## Drittens: unter dem Schloss

An diesem Projekt arbeiten oft zwei bis vier Sitzungen. Die Dateien trennt
Claude Code über Arbeitsbäume, die **Maschine** trennt niemand — und gegen
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
S="${CLAUDE_SESSION_NAME:-${CLAUDE_CODE_SESSION_ID:-$$}}"; .venv\Scripts\python.exe -m pytest -q $ARGUMENTS > "$TEMP/t-$S.txt" 2>&1; echo "Exit=$?"
```

Ohne Argument das ganze Tor. Die drei Werkzeuge zuerst, weil sie Sekunden
dauern und die teuren Läufe erübrigen, wenn sie rot sind:

```
S="${CLAUDE_SESSION_NAME:-${CLAUDE_CODE_SESSION_ID:-$$}}"; .venv\Scripts\python.exe -m ruff check . > "$TEMP/g1-$S.txt" 2>&1; echo "ruff check   Exit=$?"
S="${CLAUDE_SESSION_NAME:-${CLAUDE_CODE_SESSION_ID:-$$}}"; .venv\Scripts\python.exe -m ruff format --check . > "$TEMP/g2-$S.txt" 2>&1; echo "ruff format  Exit=$?"
S="${CLAUDE_SESSION_NAME:-${CLAUDE_CODE_SESSION_ID:-$$}}"; .venv\Scripts\python.exe -m mypy > "$TEMP/g3-$S.txt" 2>&1; echo "mypy         Exit=$?"
```

Die Zuweisung steht **vor** dem Lauf, nicht dahinter: `$?` gehört dem letzten
Befehl, und ein `S=…` danach überschriebe genau die Zahl, die gebraucht wird.

Dann die Suite und die Leistungstests, beide unter dem Schloss, beide in einem
Aufruf, damit das Schloss nur einmal genommen wird:

```
S="${CLAUDE_SESSION_NAME:-${CLAUDE_CODE_SESSION_ID:-$$}}"; export S; .venv\Scripts\python.exe tools/gate_lock.py run --who "$S" --wait 1800 -- bash -c '.claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh > "$TEMP/g4-$S.txt" 2>&1; echo "geteilt Exit=$?"; .venv/Scripts/python.exe -m pytest -q -m performance > "$TEMP/g5-$S.txt" 2>&1; echo "performance Exit=$?"'
```

`export S`, weil der innere `bash -c` eine eigene Shell ist — ohne das stünde
dort ein leerer Marker, und beide Läufe schrieben wieder in dieselbe Datei.

**Und `--who` nimmt denselben Marker.** Dort stand `"$CLAUDE_SESSION_NAME"`
allein; die Variable ist leer, wenn die Sitzung keinen Namen trägt, und das
Schloss meldete dem Wartenden dann einen namenlosen Halter — eine Auskunft, mit
der niemand jemanden ansprechen kann.

Alle fünf ausführen, auch wenn einer früh fehlschlägt — ein vollständiges Bild
ist mehr wert als ein schneller Abbruch. Fehlt `.venv`, sag das mit dem
Einrichtungsbefehl aus `CLAUDE.md`, statt auf das System-Python auszuweichen.

**In einem Arbeitsbaum** (`.claude/worktrees/…`) gibt es kein `.venv`. Dann den
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
(`test_ui.py`, `test_chat_ui.py`, `test_first_run.py`). Zwei Fensterdateien
enden inzwischen mit **127** statt mit dem bekannten Code, einzeln gefahren
auch — ein eigener offener Punkt, nicht derselbe Absturz.

`suite-getrennt.sh` unterscheidet das selbst: `zaehlt_als_fehler` vergleicht
die Zahl der Fortschrittszeichen mit der Sollgröße aus `--collect-only`, und
ein Lauf, der alle Tests durch hatte und erst beim Aufräumen riss, zählt als
grün (`tests/test_suite_script.py`). **Ein Exit ungleich null des Skripts ist
deshalb ein echter Befund** — ein roter Test, oder ein Riss, der Tests
verschluckt hat. Wer ihn für den bekannten Abbau-Abriss hält, sucht an der
falschen Stelle; das Protokoll sagt, wie viele Zeichen vor dem Abbruch
standen. Der offene Punkt steht in `ROADMAP.md`.

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
