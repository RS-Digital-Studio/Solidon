# RM-298(d): Vergleichsmarken am öffentlichen Hilfsprozessweg

Stand: 02.10.2026. Diese Einheit ergänzt zwei vorbereitete Release-Messungen und schützt das Markenschreiben mit reinen Entwicklungstests. **Keine Leistungsmessung wurde für diesen Nachweis gesammelt oder ausgeführt.** RM-298(d) ist damit nicht vollständig abgenommen.

## Vorbereiteter Messweg

| Öffentlicher Kundenweg | Neue, getrennte Marke | Korpus und bestehende Absagegrenze |
|---|---|---|
| `boolean("difference", ...)` | `boolean_medium_helper_warm` | Zwei Kugeln mit je 327.680 Dreiecken, Mittenabstand 30 mm; 20 s |
| `decimate_for_display(...)` | `display_decimate_1m_helper_warm` | Bestehender Millionen-Korpus, Anzeigeziel 200.000 und Obergrenze 400.000 Dreiecke; 30 s |

Die Grenzen bleiben die bestehenden Größenordnungswächter; sie ersetzen weder die §31-Ziele von 2 beziehungsweise 4 s noch die Regressionsprüfung auf der Referenzmaschine. Die bisherigen Hauptfadenmarken bleiben unverändert erhalten.

Die zusätzlichen Tests rufen aus einem Arbeiterfaden dieselben öffentlichen APIs mit dem Produktionsschwellenwert auf. Der Helfer ist vor der Uhr bereit. Die Uhr umfasst den API-Aufruf einschließlich Übertragung und Nacharbeit; Start, Ergebnisprüfung und Abbau liegen außerhalb. Referenznetze haben eigene Caches, damit ihre lokale Auswertung die gemessenen Eingangscaches nicht vorwärmt.

Vor jeder Markendatei-Abfrage prüft `measure(..., verify=...)` den tatsächlich passenden Helferjob, unveränderte Start-/Rückfall-/Tod-/Abbruchzähler, genau ein Ergebnis sowie die Ergebnis- und Eingangsbytes. Bei den Ergebnisfeldern zählen Typ, Form und Bytes; Slots werden ebenfalls verglichen. **Die Slots dieser beiden Korpusfälle sind leer; eine mehrfarbige Slotübertragung ist damit nicht nachgewiesen.**

Ein `CancelSignal` wird vor dem Helferabbau und vor dem Executor-Beitritt gesetzt. Ein zweites `shutdown` nach dem Beitritt sammelt verspätete Starts. Der optionale Prüfgriff ändert bestehende zweistellige `measure`-Aufrufe nicht.

## Tatsächlich ausgeführte Entwicklungskontrollen

| Lauf | Vollständiges Ergebnis | Aussage |
|---|---|---|
| `tests/test_performance_marks.py`, frischer Endstand | 14 bestanden, 0 Fehler/Skips, Exit 0 | Sieben bestehende und sieben neue reine Mechanikfälle; nachgestellte Prüfablehnungen, gestellte Uhr, temporäre Markendateien |
| Nur die sieben neuen Fälle mit wieder verspäteter Prüfung im eigenen Testprozess | 7 echte Assert-Fehler, 0 Setupfehler/Skips, Exit 1 | Dieselben Zusicherungen erkennen bereits angelegte oder veränderte Marken |
| Vorgeschriebener Importgraph-Nachlauf, damaliger gemeinsam bearbeiteter Baum | 375 bestanden, 9 fehlgeschlagen, 0 Setupfehler/Skips, Exit 1 | Alle 14 eigenen Mechanikfälle bestanden; neun damalige RM-320-Gegenfälle in `test_slot_features.py` waren rot und wurden dem zuständigen Bearbeiter übergeben |
| Ruff, Format, Diffcheck und AST der beiden eigenen Dateien | jeweils Exit 0 | Beide Quellhashes vor und nach der Kontrolle unverändert |
| Nachweiskarten und Roadmap | 32 bestanden, 0 Fehler/Skips, Exit 0 | `test_roadmap.py` und `test_directory_docs.py`; sechs Quell-/Dokumenthashes während des Laufs unverändert |

Die sechs Ablehnungsfälle kombinieren neue/vorhandene Marken mit **nachgestellten** Prüfablehnungen: `AssertionError` für einen falschen Helferweg, `ValueError` für veränderte Ergebnisbytes und `KeyboardInterrupt`. Dabei wird kein echter Helferweg geändert und kein Geometrieergebnis manipuliert; die Zusage betrifft allein die Markenpersistenz nach einer abweisenden `verify`-Prüfung. Der siebte Fall sichert, dass 99 gestellte Sekunden der Nachprüfung nicht zur API-Zeit von 0,25 s zählen und die erste Marke erst nach der Prüfung entsteht. Die tatsächliche Maschinen-Baseline blieb bytegleich; SHA-256 `d791c0ecaad450cdaa5bdae40fd9e28d33e1a5a1b3b8a5f96194fc5207bfe40d`.

Die negative Kontrolle verändert ausschließlich `measure` im isolierten Testprozess: Sie ruft die ursprüngliche Funktion ohne `verify` auf und führt `verify` erst danach aus. Produktdateien bleiben dabei unverändert. Die vollständigen JUnit-Berichte wurden gegen die Prozessausgänge geprüft: 14/14 grün und 7/7 bewusst rot, ohne Setupfehler oder Überspringungen.

Historische Prüfaufbaufehler bleiben getrennt: Der erste Nachlauf verwendete für `KeyboardInterrupt` einen leeren `match` und scheiterte an einer Pytest-Warnung. Der erste Gegenlauf hatte deshalb nur fünf echte Markenfehler und zwei Aufbaufehler. Nach `match=str(problem) or None` wurden beide Kontrollen frisch wiederholt. Ein früher Auswertungswrapper erwartete zudem irrtümlich 15 eigene Fälle; die vollständigen Berichte belegen 14. Diese alten Läufe tragen die Freigabe nicht.

Reproduktion der grünen Mechanikfälle, ohne Leistungstests:

```powershell
.venv\Scripts\python.exe -m pytest -q tests/test_performance_marks.py --junitxml=marks.xml
.venv\Scripts\python.exe tools/affected_tests.py tests/test_performance.py tests/test_performance_marks.py --run
```

Der Importgraph lässt die `performance`-Fälle im Entwicklungslauf ausdrücklich aus. Ein damaliger roter Gesamtbaum wird durch die eigenen grünen Fälle nicht zum grünen Gesamtlauf.

## Quellstand und Review

| Datei | SHA-256 des geprüften Endstands |
|---|---|
| `tests/test_performance.py` | `b64a4f5dba4c2990464f839b060d41454942a6f730bfd22d0d2d7f89d277e3d9` |
| `tests/test_performance_marks.py` | `947c5e7c41104b386a9a5ec31fe2d9febdc7a29d4097ba24119fd21b096e89f0` |

Eigenreview und unabhängiges vollständiges Quell-/Mechanikreview sind abgeschlossen. Der erste unabhängige Durchgang fand Markenschreiben vor der Ergebnisprüfung und Executor-Beitritt vor dem Abbau; beide wurden korrigiert und erneut geprüft. Der abschließende Reviewer fand keine offenen Befunde an den beiden Quellen und bestätigte die Grenzen der Nachweise. Die anschließende unabhängige Dokumentprüfung präzisierte die nachgestellten Prüfablehnungen in Bericht, Karte und Roadmap; weitere Dokumentbefunde bestehen nicht. Der Reviewer führte selbst keine Tests aus. Zentrales Entwicklungstor und selektive Integration dieser Einheit stehen am Berichtstand noch aus.

Die separate aktive Windows-Elternbindung und OS-Priorität sind bereits mit `d9f830aec41ae0531784406b75ad4a0fb549b4a6` auf dem tatsächlichen `origin/main` integriert. Ihr Tor bestand mit 19.059 Tests, 62 Überspringungen und jeweils Exit 0 für Suite, Ruff, Format und mypy. **Dieser Lauf enthält die vorliegende neue Leistungseinheit nicht.** Ihr Nachweis steht im [Prozessbericht](rm298-lifecycle-2026-10-02.md).

## Integrationsnachtrag 02.10.2026

Die vorliegende Quellen-/Mechanikeinheit ist mit `7f0de659d2c8fc1e35bd1067e738bcaef7f1ec72` auf dem tatsächlichen `origin/main` integriert. Das vollständige zentrale Entwicklungstor bestand 19.066 Tests mit 62 Überspringungen; Suite, Ruff, Format und mypy jeweils Exit 0, ohne Quelldrift. Commit, Trackingstand und tatsächliche Gegenstelle wurden unabhängig abgeglichen. Das ersetzt die oben datierte Aussage über damals ausstehendes Tor und Integration. Weiterhin wurden keine Leistungsmessungen gesammelt oder ausgeführt; RM-298 bleibt offen.

## Noch fällige Abnahme

Beim Release: Beide neuen tatsächlichen Helfer-Messwege auf der Referenzmaschine einschließlich Kontrollen fehlender Auslagerung und veränderter Ergebnisbytes ausführen. Laufzeit, Marken und vollständige Prozessausgänge festhalten. Ein kalter Start, Bildrate, übrige §31-Marken, Linux/macOS und das gebaute Paket sind hier nicht geprüft. Der offene Gesamtpunkt RM-298 bleibt erhalten.
