# Statische Prüfungen und Bausteinvorgaben

Umgesetzt gemäß Konzept §4.2 und Bausteinteil §4.3. Eigentum dieses Teilauftrags:
`tests/test_translations.py`, `tests/test_language_rules.py`,
`tests/test_directory_docs.py`, `tests/test_parts.py`. Kein Kerncode, keine
global geteilte veränderliche Szene, kein neues Testhilfsmodul, kein Commit.

Basis: `8ed5d6299ce425de90366fd9c4128ccb2147fcf6`. Die vier Dateien waren am
Anfang sauber. Der endgültige Diff liegt in `statisch-final.patch`, die
SHA-256-Werte in `statisch-hashes.txt`. Betriebssystem Windows,
Interpreter `F:\3D Druck\.venv\Scripts\python.exe`, CPython 3.14.7.

## Umsetzung

- Sprachprüfung: Bezeichner, Umlaute und Feld-Docstrings prüfen pro Quelldatei
  einen gemeinsam geparsten AST; Bezeichner werden einmal extrahiert.
- Übersetzungen: Alle gefundenen Kataloge und die Quellen-Umlautprüfung nutzen
  einen `message_ids()`-Lauf. Fehlende und verwaiste Einträge bleiben für jede
  Sprache getrennt ausgewiesen. Dateifilter und Anzeigeaufrufe nutzen pro
  UI-Quelldatei einen gemeinsamen AST. Die Tests des Extraktors mit eigenen
  veränderlichen Quellen rufen ihn weiterhin direkt und frisch auf.
- Keine Cache-Invalidierungsfrage und keine Mehrfachcaches unter xdist:
  Zusammengehörige Zusicherungen laufen im selben Testaufruf.
- Kartenprüfung: `Path.walk()` entfernt ausgeschlossene Unterverzeichnisse
  vor dem Betreten. Die bisherige Mitgliedschaft bleibt erhalten. Der Filter
  hängt nur an Unterverzeichnissen der Wurzel, nicht an gleichnamigen Vorfahren.
- Bausteine: Zwei frische `spec.params()`/`spec.fn()`-Aufrufe je Vorgabe;
  der erste Bau trägt gleichzeitig die Merkmalsprüfung. Volumentoleranz
  `rel=1e-9`, Dreiecksanzahl, Merkmals-ID, Provenienz und Maße bleiben unverändert.

## Fallmapping und erhaltene Prüfdeckung

| Alt | Neu | Parameter/Zusicherungen |
|---|---|---|
| `test_identifiers_are_english[path]`, `test_identifiers_have_no_umlauts[path]`, `test_field_docstrings_are_german[path]` | `test_identifiers_are_english[path]` | dieselben 383 Dateien; alle drei Regeln, dieselben Prüfer und Schwellen |
| `test_no_hard_wired_file_filter[path]`, `test_no_hard_wired_text_in_the_surface[path]` | `test_no_hard_wired_text_in_the_surface[path]` | dieselben 86 UI-Dateien, beide Prüfungen |
| `test_every_text_is_translated[en/es/fr/it/pt]`, `test_no_source_text_writes_ae_for_a_umlaut` | `test_every_text_is_translated` | alle Sprachen aus `available_languages()` außer Quellsprache; fehlende/verwaiste Einträge und dieselbe Umlautprüfung |
| `test_a_part_names_the_features_it_promised[spec]`, `test_a_part_is_reproducible[spec]` | `test_a_part_names_the_features_it_promised[spec]` | dieselben 35 Bausteine aus `PARTS.all()`, zwei unabhängige Bauten |

Der Importvertrag `test_registry_consistency.PARTS_SWEEP` behält seinen Namen
und die unveränderte `spec`-Parametrisierung. Die Importreferenzen wurden vor
dem Umbau gesucht. `test_value_labels.py` verwendet weiterhin unveränderte
Helfer aus `test_language_rules.py`.

Fallzahl: 1970 − 766 Sprach-Doppelprüfungen − 91 Übersetzungs-Doppelprüfungen
− 35 getrennte Determinismusfälle + 2 Traversierungsregressionen = 1080.
Keine Parameterwerte, Fensterzuordnungen oder fachlichen Zusicherungen entfallen.
Die JUnit-Parameter-IDs aller sieben alten→neuen Zuordnungen wurden als Mengen
verglichen und sind identisch; `statisch-parametermengen.txt`, Exit 0.

## Abgeschlossene Läufe

Vergleichsbefehl, in beiden erfolgreichen Läufen identisch bis auf Berichtspfad:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_translations.py tests/test_language_rules.py tests/test_directory_docs.py tests/test_parts.py -q -m 'not windowed and not rendered and not performance' --durations=40 --junitxml=<Laufordner>/junit.xml
```

| Laufordner | Ergebnis | pytest-Zeit | Exit |
|---|---|---:|---:|
| `statisch-vorher` | 1970 bestanden, 1 abgewählt | 92,90 s | 0 |
| `statisch-nachher` | 1079 bestanden, 1 fehlgeschlagen, 1 abgewählt | 49,68 s | 1 |
| `statisch-nachher-korrigiert` | 1080 bestanden, 1 abgewählt | 50,17 s | 0 |

Der erste Nachherlauf scheiterte ausschließlich an der erwarteten Reihenfolge
im neuen Traversierungstest: `WindowsPath` sortiert ohne Groß-/Kleinschreibung.
Der Sollwert wird jetzt mit derselben plattformeigenen Pfadordnung sortiert.
Der Fehllauf bleibt gespeichert und zählt nicht als bestandener Nachweis.

`tools/affected_tests.py` nennt zusätzlich die importierenden Dateien
`test_registry_consistency.py` und `test_value_labels.py`. Separat gefahren:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_registry_consistency.py tests/test_value_labels.py -q -m 'not windowed and not rendered and not performance' --durations=10 --junitxml=.claude/.state/ci-test-optimierung-2026-09-24/statisch-importe/junit.xml
```

Ergebnis: 1205 bestanden, 52 abgewählt, 13,93 s, Exit 0. Insgesamt im
endgültigen betroffenen Kernumfang 2285 bestanden, 53 abgewählt, kein Skip.
Jeder Laufordner enthält `pytest.txt`, `junit.xml` und den gesicherten
nativen Rückgabewert `exit.txt`.

Ruff und Format über die vier Dateien: Exit 0, `All checks passed!` und
`4 files already formatted`; Protokolle `statisch-ruff.txt` und
`statisch-format.txt` mit jeweiligen `*-exit.txt`. `git diff --check` ohne Befund.

## Gegenproben

`statisch-gegenprobe.py` vergleicht die bisherige und neue Suche am aktuellen
Repository: identische 3364 Kartenpfade und 20 Codeverzeichnisse, gleiche
Reihenfolge. Beide neuen Regressionstests lehnen die alte Suche durch den
belegten Zugriff auf ausgeschlossene Verzeichnisse ab. Exit 0 bedeutet hier,
dass beide erwarteten Ablehnungen eingetreten sind; Protokoll
`statisch-gegenprobe.txt`.

## Messwerte und Grenzen

Summe der JUnit-Testzeiten einschließlich Vorbereitung/Abbau:

| Datei | Vorher | Nachher |
|---|---:|---:|
| Übersetzungen | 21,124 s | 4,088 s |
| Sprachregeln | 16,134 s | 7,522 s |
| Karten | 14,549 s | 6,011 s |
| Bausteine vollständig | 39,014 s | 31,180 s |
| Nur zusammengeführte Baustein-Vorgaben | 1,720 s | 1,210 s |

Die abgeschlossenen lokalen Vergleichsläufe zeigen 42,73 s weniger
Gesamtdauer (rund 46 %). Das ist eine Einzelmessung auf dieser Windows-Maschine,
keine CI-Prognose. Auch unveränderte Bausteintests schwanken; die gesamte
Differenz der Bausteindatei darf deshalb nicht der Bündelung zugerechnet werden.
Die Kartenmenge enthält lokale Release-/Prüfkopien und ist größer als in einem
frischen Klon. Es wurden keine zusätzlichen Ausschlüsse eingeführt, die diese
Bestandsdeckung verkleinern.

Keine Fensterdateien ausgeführt, keine Leistungsmarker ausgeführt, kein
Release-Lauf, kein CI-Lauf, keine Plattformabnahme. Das gemeinsame
Entwicklungstor und die Dokumentation dauerhafter Patterns bleiben beim
Hauptauftrag. Nach diesem Bericht keine weiteren Änderungen an den vier Dateien.
