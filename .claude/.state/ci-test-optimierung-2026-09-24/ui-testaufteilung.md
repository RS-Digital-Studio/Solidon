# Fachliche UI-Testaufteilung und kleinere Vorbereitung

## Umfang

Umsetzung von Konzept §4.1 und dem UI-Anteil §4.3, ausschließlich Tests.
Keine Änderung an Produktivcode, Qt-Abbau, Garbage Collection oder
Prozessisolation. Keine Fenster- oder Leistungsprüfung ausgeführt.

Aus `tests/test_ui.py` wurden vier stabile Fachgebiete herausgelöst:

| Datei | Gesammelte Fälle |
|---|---:|
| `tests/test_ui_dialogs.py` | 17 |
| `tests/test_ui_export.py` | 48 |
| `tests/test_ui_licensing.py` | 28 |
| `tests/test_ui_remote.py` | 11 |
| Zusammen | 104 |

Damit stehen mehr als 3.100 Zeilen in fachlich benannten Modulen statt in
der bisher größten Fensterdatei. Gemeinsame Session-/Fenster-Fixtures,
Korpuspfad sowie Export- und Aktivierungshilfen liegen in
`tests/ui_helpers.py`. Keine Testfunktion wird aus einem anderen Testmodul
importiert. Die Fenster-Fixtures bleiben pro Test frisch; der zentrale
Abbau aus `tests/conftest.py` ist unverändert.

Der Merkmals-/Auswahlbereich wurde wegen paralleler Arbeiten ausdrücklich
nicht umgezogen. Die ursprünglichen fremden Änderungen am Maßentwurf und
Intersection-Repair bleiben erhalten. Während der Arbeit ergänzte die
andere Aufgabe acht weitere Fälle zu Split-Zeigern und Maßentwürfen.

## Kleinere Anzeigevorbereitung

18 Fälle in `tests/test_operation_ui.py` benötigen das Hauptfenster nur als
Elternfenster des Operationsdialogs, einmal zusätzlich für den Menüeintrag.
Ihre vollständigen Testkörper lesen weder Szene noch importierte Merkmale.
Diese Fälle verwenden jetzt die gemeinsame leere Fenster-Fixture als
`empty_window`; vorher importierte jeder die Lochplatte samt Erkennung.

Betroffen sind Bildquellenauswahl, abhängige Felder, Warnhinweise,
Einheiten/Parametertexte und Feldgrößen. Die genaue Liste steht in
`empty-window-cases.json`. Testkörper und Zusicherungen sind bis auf den
Fixture-Namen unverändert. Import-, Erkennungs-, Bearbeitungs- und
Vorschauprüfungen behalten ihren echten bisherigen Vorbereitungsweg.

## Nachweis der vollständigen Sammlung

Vor Änderung wurden beide Quelldateien vollständig unter
`test_ui.before.py` und `test_operation_ui.before.py` gesichert.
`collect_ui_split.py` erfasst Fallnamen einschließlich Parameterkennung,
sämtliche Marker samt Argumenten, Fixture-Namen, Scope und AST-Prüfsumme
der tatsächlich aufgelösten Fixture-Funktionen. Keine Fixture wird dabei
ausgeführt.

Sammlung vorher: **886 Fälle**, nachher **894 Fälle**. Die Differenz sind
ausschließlich die acht fremd hinzugekommenen Fälle. Kein ursprünglicher
Fall fehlt, kein Fall wird doppelt gesammelt. Der Vergleich normalisiert
nur den Dateipfad und die Speicheradresse der einen Marker-ID-Lambda.
Alle Marker und Parameterkennungen bleiben gleich. Sämtliche Fixture-
Auflösungen bleiben gleich, mit genau den 18 beabsichtigten Austauschen
der schweren Fenster-Fixture gegen die leere Fenster-Fixture.

Zusätzlich wurde der AST aller **619 ursprünglichen UI-Testfunktionen**
verglichen: vollständig identisch. Die **161 Testfunktionen** aus
`test_operation_ui.py` sind nach Rückbenennung des Fixture-Parameters
ebenfalls AST-identisch. Neue Funktionen aus der parallel arbeitenden
Aufgabe wurden gesondert aufgelistet und nicht als eigener Umfang gewertet.

Maschinenlesbarer Beleg: `ui-split-comparison.json`; Prüfung:

```powershell
.venv/Scripts/python.exe .claude/.state/ci-test-optimierung-2026-09-24/compare_ui_split.py
```

Exit **0**, Protokoll `ui-comparison.log`. Sammlungsprotokolle:
`ui-collect-before.log`, `ui-collect-after-split.log`, `ui-collect-final.log`.

## Ausgeführte Prüfungen

```powershell
.venv/Scripts/python.exe -m pytest -q -m 'not windowed and not performance and not rendered' tests/test_ui.py tests/test_ui_dialogs.py tests/test_ui_export.py tests/test_ui_licensing.py tests/test_ui_remote.py tests/test_operation_ui.py --durations=10
```

**64 passed, 830 deselected in 3.50s; Exit 0.** Protokoll `ui-regular.log`.
Die Abwahl enthält die Fensterfälle; dies ist keine Fensterabnahme.

`tools/affected_tests.py` nennt genau diese sechs Testdateien;
Protokoll `ui-affected.log`. Ruff und Formatprüfung über diese sechs Dateien
und `tests/ui_helpers.py`: beide **Exit 0**, `ui-ruff.log` und
`ui-format.log`. Das gemeinsame Entwicklungstor und mypy führt die
Hauptaufgabe für ihren Gesamtstand aus.

## Verbleibende Grenzen

Die echte Fensterausführung bleibt gemäß Konzept beim nächsten ausdrücklich
beauftragten Release. Erst dort werden die neuen Einzelprozesse und die 18
kleineren Vorbereitungen im vollständigen Fensterlauf bestätigt und ihre
Zeitwirkung gemessen. Hier wird kein gemessener CI-Zeitgewinn behauptet.

`tests/test_analysis_ui.py` blieb wegen fremder laufender Änderungen
unverändert. Der Hauptaufgabe wurden die neuen Pfade für Bereichskarte und
Laufzeitplanung gemeldet sowie die notwendige Korrektur des Verweises in
`tests/test_remote.py:5`. Der Verweis im eigenen `test_operation_ui.py`
zeigt bereits auf `test_ui_dialogs.py`.
