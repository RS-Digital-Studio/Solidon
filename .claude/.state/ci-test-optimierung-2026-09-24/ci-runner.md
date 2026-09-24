# CI-Läufer: Umsetzung und Nachweis

Geändert wurden ausschließlich `tools/run_suite_isolated.py`,
`tools/list_windowed_tests.py`, `tests/test_ci_runner.py` und
`tests/data/ci_window_durations.json`; keine Commits.

## Verhalten

- Lokaler Aufruf und seine Markerwahl bleiben kompatibel.
- CI-CLI: `--release --ci-group windowed|contracts --shard-index N
  --shard-count N --report-dir PFAD`; `contracts` verlangt einen Shard,
  `windowed` schließt genau die beiden Plattformverträge aus.
- `--plan-only` sammelt ohne Releasefreigabe und führt keine Tests aus.
- Aktuelle Pytest-Sammlung einschließlich Fixture-Graph entscheidet über
  Dateien und Fallzahlen. `performance` und `rendered` bleiben draußen.
- Deterministische LPT-Verteilung, Gleichstand über Pfad und Shardindex.
  Neue Dateien bleiben enthalten; alte Zeiteneinträge erzeugen keine Auswahl.
- Je Datei frischer Prozess, festes `windowed and not performance and not
  rendered`, kein xdist, faulthandler 120 s, `--durations=30`.
- Pro Datei Protokoll und JUnit; JSON und Markdown enthalten vollständigen
  Plan, Auswahl, echte Prozesszeit, Exit, Soll-/Istfallzahlen und Fehler.
  Zwischenstände bleiben ausdrücklich unvollständig.
- Sammlung, leere Auswahl, fehlende Verträge, Exit 5, abrupter Exit 139,
  fehlendes/beschädigtes JUnit, falsche Fallzahlen und JUnit-Fehler sperren
  den Lauf. Später erfolgreiche Dateien entfernen keinen früheren Fehler.
- Zeitgrenze beendet unter Windows den Prozessbaum mit `taskkill /T /F`,
  unter POSIX die neu angelegte Sitzung mit `killpg`. Fehler der vollständigen
  Beendigung bleiben im Bericht; das direkte Kind wird zusätzlich beendet
  und abgewartet.

## Ausgangsmessung

Live aus dem erfolgreichen Run `35982366247`, Windows-Job `107577041008`,
Commit `0895c4a69eb6adcb03834ee7f005087dcc3c2c6d` übernommen: alle 92
Dateisitzungen, davon 90 in der bisherigen Vollgruppe und zwei Verträge.
Summe 2379,88 s innerhalb pytest; `test_ui.py` 665,03 s.
Ersatzgewicht für unbekannte Dateien ist das 90. Perzentil: 49,88 s.
Die JSON-Datei enthält URL, Commit, Job, Plattform und SHA-256 des Rohprotokolls.
Protokoll und einmaliger Extraktionshelfer liegen in diesem Nachweisordner.

## Verifikation

`.venv/Scripts/python.exe -m pytest -q tests/test_ci_runner.py
tests/test_affected_tests.py -m "not windowed and not performance" --durations=10`

Ergebnis: **83 passed in 30.98s**, echter Exit 0.
Das Protokoll liegt in `ci-runner-tests.log`.
Die Tests führen kleine pytest-/Python-Kindprozesse ohne Qt aus:
Erfolg, Assertion, fehlender Bericht, falsche Fallzahl, abruptes Ende nach
gültigem JUnit und Timeout. Die reale Timeoutprobe hat drei Prozessebenen;
nach der Rückkehr war kein Probeprozess mehr aktiv. Der POSIX-Zweig ist
typgeprüft; sein nativer Prozessnachweis läuft erst auf der jeweiligen CI-Plattform.

Ruff, Formatprüfung und mypy für beide Werkzeuge sind grün. Mypy wurde mit
`--explicit-package-bases` für Windows und zusätzlich `--platform linux`
ausgeführt; ohne diese Modulbasis meldet mypy beim gezielten Dateiaufruf
dieselbe Datei unter zwei Modulnamen.

Die echte `--plan-only`-Sammlung lief mit Exit 0:
`current-plan/summary.json` und `current-plan/summary.md`.
Am dabei gelesenen gemeinsamen Stand waren es 94 Windows-Dateien ohne die
zwei Plattformverträge: 44/50 Dateien und 1394/2032 Fälle. Die Gewichte
summieren sich auf 1239,15/1239,65 s. Das sind **Planschätzungen**, keine
gemessenen neuen CI-Zeiten. Der gemeinsame Baum wurde während der Arbeit
weiterbearbeitet; diese Fallzahlen benennen nur diesen Sammlungsstand.

Keine Fensterdatei, keine Leistungsprüfung, kein Release- oder Paketbau
wurde ausgeführt. Die volle CI-/Release-Abnahme bleibt offen.
