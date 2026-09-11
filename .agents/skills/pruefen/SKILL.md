---
name: pruefen
description: >
  Führt Solidons betroffene Tests oder das vollständige Tor aus und berichtet
  echte Prozessausgänge und Testzahlen. Mit Dateipfaden nur betroffene Tests;
  ohne Argument vollständiges Tor aus geteilter Suite, Leistungstests, ruff
  check, ruff format --check und mypy. Vor einem Commit gilt das ganze Tor.
argument-hint: "[optional: betroffene Dateien]"
allowed-tools: Bash, Read, Grep, Glob
---

# Prüfen

## Umfang zuerst

Mit Dateipfaden oder nach einem einzelnen Arbeitsschritt laufen die betroffenen
Tests über `tools/affected_tests.py --run`. Nenne die Dateien ausdrücklich:
Ohne Dateiliste untersucht das Werkzeug auch fremde lokale Änderungen.
Meldet der Importgraph, dass die vollständige Suite betroffen ist, gilt das
entsprechend. Keine vollständige Suite allein wegen eines kleinen Doku-Edits.

Ohne Argument oder vor einem beauftragten Commit läuft das vollständige Tor.
Ein bereits vollständig grüner Nachweis für denselben relevanten Stand muss
nicht wiederholt werden. Prüfe dazwischenliegende Änderungen, bevor du ihn
übernimmst. Eine reine Prüfanfrage autorisiert weder Reparaturen noch Commits.

## Umgebung und Protokoll

Lies `CLAUDE.md`, den aktuellen Diff und bei Bedarf `.claude/rules/tests.md`.
Prüfe den Interpreter dieses Arbeitsbaums gegen `pyproject.toml`; Pakete prüft
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

## Vollständiges Tor

Die Suite baut viele Fenster; sie läuft geteilt, mit separaten Prozessen für
Fensterdateien. Die aktuelle Aufteilung liegt in
`.claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh`, die
Fenstererkennung in `tools/list_windowed_tests.py`. Der geteilte Lauf lässt
Leistungstests aus; sie gehören separat dazu.

Setze `SUITE_PYTHON` auf den geprüften absoluten Interpreterpfad. Unter
PowerShell beispielsweise `$env:SUITE_PYTHON = $testPython`. Die regulären
Pfade sind `.venv/Scripts/python.exe` unter Windows und `.venv/bin/python`
unter Linux/macOS. Der folgende Block ist **Bash**, unter PowerShell über
vorher lokalisiertes Git Bash ausführen. Nicht direkt als PowerShell einfügen.

```bash
(
set +e
CHECK_DIR=$(mktemp -d) || exit 2
printf 'Protokolle: %s\n' "$CHECK_DIR"
"$SUITE_PYTHON" -m ruff check . > "$CHECK_DIR/ruff-check.txt" 2>&1
ruff_status=$?
"$SUITE_PYTHON" -m ruff format --check . > "$CHECK_DIR/ruff-format.txt" 2>&1
format_status=$?
"$SUITE_PYTHON" -m mypy > "$CHECK_DIR/mypy.txt" 2>&1
mypy_status=$?
bash .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh > "$CHECK_DIR/suite.txt" 2>&1
suite_status=$?
"$SUITE_PYTHON" -m pytest -q -m performance > "$CHECK_DIR/performance.txt" 2>&1
performance_status=$?
printf 'ruff=%s format=%s mypy=%s suite=%s performance=%s\n' "$ruff_status" "$format_status" "$mypy_status" "$suite_status" "$performance_status"
if [ "$ruff_status" -ne 0 ] || [ "$format_status" -ne 0 ] || [ "$mypy_status" -ne 0 ] || [ "$suite_status" -ne 0 ] || [ "$performance_status" -ne 0 ]; then
    exit 1
fi
)
```

Alle fünf Ergebnisse gehören zum Tor. Der Wrapper gibt bei einem Fehllauf
selbst Nichtnull zurück. Einen abgebrochenen Gesamtauftrag nicht durch später
weiterlaufende Hintergrundbefehle fortsetzen. Bei fehlender Umgebung oder
systematisch gleichem Infrastrukturfehler erst die Ursache klären.

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

## Bericht

Pro Lauf: getesteter Stand, Umfang, Befehl, Prozessausgang, bestanden/fehlgeschlagen/
übersprungen und Protokollpfad. Fehler nach Ursache gruppieren und ungeprüfte
Bereiche nennen. Automatisierte, echte UI-, Hardware- und Feldnachweise trennen.
Bei beauftragter Reparatur Ursache beheben und gezielt erneut prüfen; Tests
nicht passend machen und Warnungen nicht zur Grünfärbung unterdrücken.
