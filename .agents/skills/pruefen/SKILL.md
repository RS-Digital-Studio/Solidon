---
name: pruefen
description: >
  Führt Solidons betroffene Kerntests oder das Entwicklungstor aus und berichtet
  echte Prozessausgänge und Testzahlen. Ohne Argument Kerntests, ruff check,
  ruff format --check und mypy. Fenster-, Renderer- und Leistungsprüfungen laufen
  ausschließlich beim Release mit --release.
argument-hint: "[optional: betroffene Dateien] [--release nur beim Release]"
allowed-tools: Bash, Read, Grep, Glob
---

# Prüfen

## Umfang zuerst

Mit Dateipfaden oder nach einem einzelnen Arbeitsschritt laufen die betroffenen
Kerntests über `tools/affected_tests.py --run`. Nenne die Dateien ausdrücklich:
Ohne Dateiliste untersucht das Werkzeug auch fremde lokale Änderungen.
Meldet der Importgraph, dass die vollständige Suite betroffen ist, läuft die
gesamte Kernsammlung. Fenster-, Renderer- und Leistungstests bleiben auch bei einer
gezielten Dateiauswahl bis zum Release zurückgestellt. Das ist keine fehlende
Umgebung und kein Anlass, sie mit einem direkten Pytest-Aufruf nachzuholen.
Keine vollständige Suite allein wegen eines kleinen Doku-Edits.

Ohne Argument und vor jedem Merge nach main läuft das Entwicklungstor (auf
Paket- und Fixzweigen vor dem Commit nur die betroffenen Tests, ruff, format,
mypy):
alle Tests ohne Fenster (`not windowed`), ohne echte Renderer (`not rendering`),
ohne `performance` und ohne die
Erzeugnisvergleiche (`not rendered` — sie brauchen einen Lauf von `.agents/skills/erzeugen/SKILL.md`
und gehören wie in der CI zum Release), dazu Ruff, Format und mypy.
**Fenster-, Renderer- und Leistungsprüfungen laufen lokal ausschließlich beim
Release**; auf Linux und macOS fährt sie die CI beim Push nach main, auf
Zweigen nie.
Nur dort wählt `--release` das zusätzliche Release-Tor. Die Option autorisiert
weder einen Paketbau noch eine Veröffentlichung.
Ein bereits vollständig grüner Nachweis für denselben relevanten Stand muss
nicht wiederholt werden. Prüfe dazwischenliegende Änderungen, bevor du ihn
übernimmst. Eine reine Prüfanfrage autorisiert weder Reparaturen noch Commits.

## Umgebung und Protokoll

Lies den aktuellen Diff und bei Bedarf `.claude/rules/tests.md`. Prüfe den
Interpreter dieses Arbeitsbaums gegen `pyproject.toml`; Pakete prüft
`tools/check_env.py` gegen `constraints.txt`. Keine ungeprüfte andere Umgebung
als stillen Ersatz benutzen. Jeder Lauf bekommt einen eigenen Protokollordner,
keine gemeinsam überschriebenen Dateien wie `g1.txt` direkt im Temp-Verzeichnis.

PowerShell, für einen gezielten Lauf:

```powershell
$testPython = (Resolve-Path '.venv/Scripts/python.exe').Path
& $testPython --version
```

Nach Prüfung der Versionsausgabe den betroffenen Lauf starten:

```powershell
& $testPython tools/affected_tests.py tests/test_agent_mirror.py --run
$testExit = $LASTEXITCODE
```

Die Beispieldatei durch die tatsächlich betroffenen Dateien ersetzen. Bei
Umleitung zuerst den nativen Exit-Code sichern und danach das Protokoll lesen.
Keine Pipeline zu `tail`, `Select-String` oder `Tee-Object` als Erfolgsnachweis.
Ein laufender oder abgebrochener Prozess hat noch kein bestandenes Ergebnis.

## Entwicklungstor und Release-Tor

Der normale Lauf enthält alle Tests ohne Fenster und Renderer. Beim Release
kommen separate Prozesse für Fenster- und Rendererfälle je Datei hinzu. Die
Aufteilung liegt in `.claude/scripts/suite-getrennt.sh`, die Erkennung in
`tools/list_windowed_tests.py`. Das Skript nimmt diese Fälle nur mit
`--release` hinzu und lässt Leistungstests immer aus. Beim Release gehören die
Leistungstests als eigener Lauf auf der Referenzmaschine dazu.
Getrennt wird je Test: `tests/conftest.py` gibt jedem Test mit `qt_app` im
Fixture-Graphen den Marker `windowed`; Fenster in Unterprozessen tragen ihn
ausdrücklich. Die zentrale Fixture `require_graphics_adapter` und der Marker
`rendering` erfassen echte Grafik. Die Geräteabfrage erfolgt erst beim
ausgewählten Test, nie beim Import oder Sammeln. Das reguläre Tor wählt
`not windowed and not rendering`, das Release-Tor fährt Fenster und Renderer
je Datei einmal.

Setze `SUITE_PYTHON` auf den geprüften absoluten Interpreterpfad. Unter
PowerShell beispielsweise `$env:SUITE_PYTHON = $testPython`. Die regulären
Pfade sind `.venv/Scripts/python.exe` unter Windows und `.venv/bin/python`
unter Linux/macOS. Der folgende Block ist **Bash**, unter PowerShell über
vorher lokalisiertes Git Bash ausführen. Nicht direkt als PowerShell einfügen.

```bash
(
set +e
# Nur für einen beauftragten Release auf 1 setzen.
release_tests=0
CHECK_DIR=$(mktemp -d) || exit 2
printf 'Protokolle: %s\n' "$CHECK_DIR"
"$SUITE_PYTHON" -m ruff check . > "$CHECK_DIR/ruff-check.txt" 2>&1
ruff_status=$?
"$SUITE_PYTHON" -m ruff format --check . > "$CHECK_DIR/ruff-format.txt" 2>&1
format_status=$?
"$SUITE_PYTHON" -m mypy > "$CHECK_DIR/mypy.txt" 2>&1
mypy_status=$?
suite_args=()
if [ "$release_tests" -eq 1 ]; then suite_args+=(--release); fi
bash .claude/scripts/suite-getrennt.sh "${suite_args[@]}" > "$CHECK_DIR/suite.txt" 2>&1
suite_status=$?
performance_status="zurückgestellt"
if [ "$release_tests" -eq 1 ]; then
    "$SUITE_PYTHON" -m pytest -q -m performance > "$CHECK_DIR/performance.txt" 2>&1
    performance_status=$?
fi
printf 'ruff=%s format=%s mypy=%s suite=%s performance=%s\n' "$ruff_status" "$format_status" "$mypy_status" "$suite_status" "$performance_status"
if [ "$ruff_status" -ne 0 ] || [ "$format_status" -ne 0 ] || [ "$mypy_status" -ne 0 ] || [ "$suite_status" -ne 0 ]; then
    exit 1
fi
if [ "$release_tests" -eq 1 ] && [ "$performance_status" -ne 0 ]; then
    exit 1
fi
)
```

Zum Entwicklungstor gehören vier Ergebnisse: Kernsammlung, Ruff, Format und
mypy. Zum Release-Tor gehören zusätzlich die Fenster- und Renderergruppe im Suite-Protokoll
und der separate Leistungslauf. Zurückgestellte Prüfungen nie als bestanden
ausweisen; ein grünes Entwicklungstor ist keine vollständige Release-Abnahme.
Der Wrapper gibt bei einem Fehllauf selbst Nichtnull zurück. Einen
abgebrochenen Gesamtauftrag nicht durch später weiterlaufende
Hintergrundbefehle fortsetzen. Bei fehlender Umgebung oder systematisch
gleichem Infrastrukturfehler erst die Ursache klären.

## Ergebnis richtig lesen

Exit-Code **und** vollständiges Protokoll prüfen: Ein grüner Wrapper beweist
nicht, dass die erwarteten Tests liefen. Testzahlen aus abgeschlossenen
Pytest-Zusammenfassungen oder strukturierten Berichten nehmen. Punkte und
Buchstaben im Fortschrittsstrom sind bei parallelen Läufen keine verlässliche
Zuordnung zu Testnamen; eine leere Suche nach `FAILED` beweist nichts.

Sammlungsfehler, fehlende Tests und Abbrüche einschließlich nativer Fehler
beim Aufräumen bleiben rot, auch wenn davor „N passed“ steht. Übersprungene
Tests separat nennen. Erfolgreiche Diagnose-Teilmengen machen den ursprünglichen
Fehllauf nicht nachträglich grün. Ein sauberer späterer Lauf ist ein neuer Nachweis.

Ein roter Leistungstest zeigt zunächst eine Grenzwertverletzung. Wiederhole
nur die betroffenen Messungen bei kontrollierter Last und vergleiche bei
Regressionsverdacht mit dem Vorgängerstand unter denselben Bedingungen.
Schwankende Ergebnisse allein beweisen weder Fremdlast noch Fehlerfreiheit;
zweimal rot beweist noch keine Ursache. Laufzeit, Systemlast und Stand nennen.

## Neue Prozessstarts unter Windows

Wer eine `subprocess`-Stelle neu baut oder ihre Startflaggen ändert, fährt den
betroffenen Test einmal unter `tools/count_new_windows.py -- <befehl>`. Ein
Konsolenfenster, das dabei aufgeht, ist ein Nebeneffekt der
Konsolenzuweisung, den kein Test sieht; Exit 1 heißt, es ging eines auf. Das
Ergebnis gilt für den Konsolenhost und die Startlage, die der Kopf der Ausgabe
nennt.

## Bericht

Pro Lauf: getesteter Stand, Umfang, Befehl, Prozessausgang, bestanden/fehlgeschlagen/
übersprungen und Protokollpfad. Fehler nach Ursache gruppieren und ungeprüfte
Bereiche nennen. Automatisierte, echte UI-, Hardware- und Feldnachweise trennen.
Bei beauftragter Reparatur Ursache beheben und gezielt erneut prüfen; Tests
nicht passend machen und Warnungen nicht zur Grünfärbung unterdrücken.
