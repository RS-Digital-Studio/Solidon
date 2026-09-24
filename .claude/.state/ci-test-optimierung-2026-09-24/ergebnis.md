# CI-Testlaufzeiten: Umsetzung und Abnahme

Arbeitsbaum `F:\3D Druck`, Ausgangs-HEAD
`8ed5d6299ce425de90366fd9c4128ccb2147fcf6`, CPython 3.14.7 unter Windows.
Der gemeinsame Arbeitsbaum enthält weitere Produktänderungen aus parallelen
Aufgaben. Es wurden keine fremden Änderungen zurückgesetzt und keine Commits,
CI-Starts, Fensterläufe, Leistungsläufe oder Releases ausgelöst.

## Konzept und dauerhafte Absicherung

Vor der Umsetzung entstand
`konzepte/konzept-ci-testlaufzeiten-2026-09.md`. CI-01 bis CI-08 beschreiben
die verbindlichen Zusagen. AGENTS, Bereichskarten und Regeln verweisen darauf;
`test_ci_runner.py`, `test_packaging.py` und `test_toolchain.py` prüfen die
Aufteilung, Releasegrenze, Fehlerausgänge und Paketfreigabe automatisch.

## Umsetzung

- Unabhängiger Stiljob; bisherige Kernmatrix mit nativer Typprüfung.
- Drei Plattformen für die beiden besonderen Fensterverträge.
- Zwei unabhängige Windows-Gruppen, frischer Prozess je Fensterdatei.
- Aktuelle Sammlung bestimmt die Auswahl; historische Zeiten verteilen sie.
  Neue Dateien erhalten ein Ersatzgewicht und bleiben enthalten.
- Paketbau benötigt alle vier Pflichtjobs. Versionswächter beim Handstart
  ausdrücklich zuschaltbar, wöchentlich weiterhin automatisch.
- JUnit, Dauern und hochgeladene Berichte; fehlende Ergebnisse und native
  Abbrüche bleiben rot. Timeout beendet auch Kind- und Enkelprozesse.
- Weniger wiederholte AST-/Übersetzungsauswertung und Verzeichnissuche;
  zwei unabhängige Bausteinbauten bleiben der Determinismusnachweis.
- 104 UI-Fälle in vier Fachmodule verschoben. 18 reine Anzeigeprüfungen
  brauchen keinen STL-Import mehr. Qt-Abbau bleibt unverändert.

## Abgeschlossene gezielte Nachweise

| Umfang | Ergebnis | Beleg |
|---|---|---|
| Workflow, Paket-/Werkzeugkette, Lieferkette, Runner und Sammlung nach Gegenprüfung | 339 bestanden, 2 Fensterfälle abgewählt; Exit 0; 61,55 s | `C:/Users/rober/AppData/Local/Temp/solidon-ci-optimierung-20260924/after-contract-review.txt`, gleichnamige `.xml` |
| Statische Prüfungen und Bausteine | 1970 bestanden / 92,90 s → 1080 bestanden / 50,17 s; unveränderte Zusicherungen gebündelt | `statische-tests.md` mit Parameterzuordnung und vollständigen Protokollen |
| Importierende Regel-/Bausteintests | 1205 bestanden, 52 abgewählt; Exit 0 | `statisch-importe/` |
| UI-Aufteilung, reguläre Fälle | 64 bestanden, 830 abgewählt; Exit 0 | `ui-testaufteilung.md`, `ui-split-comparison.json` |
| UI-Sammlung | Alle ursprünglichen Testkörper erhalten; Sammlung wächst nur um 8 parallele fremde Ergänzungen | `ui-testaufteilung.md` |
| Echte CI-Planung ohne Fensterlauf | Exit 0, vollständige deterministische Verteilung | `current-plan/summary.json` |
| Runner-/Sammlernachweis | 83 bestanden; echter dreistufiger Windows-Prozessbaum beendet; keine Qt-Prozesse | `ci-runner.md` |
| Ruff und Format über alle 19 eigenen Python-Dateien | Exit 0 | Abschließender gezielter Aufruf |
| Workflow-Syntax und GitHub-Ausdrücke | actionlint 1.7.12, Exit 0 | `C:/Users/rober/AppData/Local/Temp/solidon-ci-optimierung-20260924/actionlint/result.txt` |
| Installierte Umgebung | entspricht `constraints.txt`, Exit 0 | `tools/check_env.py` |

Die Zeilen sind keine addierbare Gesamtfallzahl: einzelne Umfänge überlappen.
Die statischen Zahlen sinken durch zusammengeführte Zusicherungen, nicht durch
Abwahl von Parameterwerten. Der lokale Zeitvergleich ist eine Einzelmessung,
kein Nachweis neuer CI-Laufzeiten.

Die unabhängige Gegenprüfung fand zwei Lücken in neuen Schutztests: einen
zu breit gelesenen Upload-Schritt und eine eingeschränkte B-Rep-Installationsprüfung.
Beide sind korrigiert. Vier negative Varianten stellen sicher, dass `always()`
eines fremden Schritts einen nicht abgesicherten Upload nicht grün färbt.
Der ursprüngliche globale B-Rep-Vertrag bleibt zusätzlich erhalten.

Das actionlint-Archiv stammt aus dem offiziellen Release von
`rhysd/actionlint`; seine veröffentlichte SHA-256-Prüfsumme wurde abgeglichen:
`6e7241b51e6817ea6a047693d8e6fed13b31819c9a0dd6c5a726e1592d22f6e9`.
Shellcheck und Pyflakes sind dabei nicht mitgelaufen; die kritischen
Shellblöcke werden von den Workflowtests tatsächlich ausgeführt.

## Gemeinsames Entwicklungstor

Gefahren am Abend des 24.09.2026 nach der Durchsicht und Fortsetzung durch
Claude; Ergebnis, Befunde an diesem Stand und Messbelege stehen in
`claude-durchsicht/README.md`. Die drei großen Sammlungsabzüge
(`ui-collection-*.json`), die Vorher-Kopien der beiden UI-Testdateien, die
JUnit-Dateien der statischen Läufe und das Windows-Protokoll des Ausgangslaufs
sind nicht eingecheckt: Sie tragen je mehrere hundert Kilobyte bis Megabyte,
das Protokoll ist über den Lauf in `tests/data/ci_window_durations.json`
abrufbar, und der Umzug ist gegen HEAD nachgeprüft (`claude-durchsicht/ui_split_vs_head.py`).

## Offene Release-Abnahme

Die neue vollständige CI-Matrix einschließlich nativer POSIX-Prozessbaumprobe,
Fensterausführung und tatsächlicher CI-Zeitvergleich benötigen den nächsten
autorisierten Release-Lauf. Die rechnerischen Planwerte sind keine gemessenen
neuen Laufzeiten. Dieser Bericht behauptet keinen bestandenen Release.
