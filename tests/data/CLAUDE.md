# `tests/data/` — der Referenzkorpus

Die Modelle und Projekte, gegen die gemessen wird (§34) — selbst erzeugt und
unter MIT (`LICENSE`), weil der Korpus mit veröffentlicht wird. **Jede Datei
hat ihre Zeile in `README.md`**: Inhalt, erwartete Kennzahlen, Test —
`test_corpus.py` hält das gegen die versionierten Dateien.

| Ordner | Inhalt |
|---|---|
| `meshes/` | Netze für die Geometrietests, erzeugt von `make_corpus.py`; die Erkennungskörper (`recognition_*.npz`, Koordinaten und Dreiecksnummern in doppelter Genauigkeit) von `make_recognition_corpus.py` |
| `projects/` | Projektdateien, darunter **alte Formatversionen** für die Migrationstests |
| `step/` | Sechs STEP-Baugruppen aus Konstruktionsmaßen (`make_step_assembly_corpus.py`): Instanzen mit Lage und Instanzfarbe, verschachtelt mit SHUO und Spiegelung, ein Teil mit mehreren Körpern, ohne Namen, in Zoll, Flächenmodell — die Sollwerte stehen im Erzeuger, `--check` vergleicht den XCAF-Baum |
| `threads/` | STEP-Gewindekörper aus Konstruktionsmaßen (`make_thread_corpus.py`): M6, M10, M8 innen, zwei- und dreigängig, innen zweigängig, kegelig und eine Naht ohne Rille — die Basis der Fallmatrix in `test_thread_import.py`; alles Abgeleitete baut der Test selbst |
| `recipes/` · `linux/` · `spacemouse/` | Ein altes Bausteinrezept (`test_part_file.py`) · der Abhängigkeitskorpus eines Linux-Pakets (`test_packaging.py`) · eine SpaceMouse-Aufzeichnung (`test_spacemouse.py`) |
| `text_lengths/` | Je Textart der eingefrorene Bestand über der Längengrenze (`test_text_length.py`, RM-509): sortiert, darf nur schrumpfen; wer einen Text kürzt, streicht ihn hier und senkt `FROZEN_COUNTS` |

Daneben liegen Referenzwerte einzelner Tests als `*.json` (und
`check_subject.php` für `test_support.py`). Der STEP-Baumvergleich
normalisiert das Vorzeichen gerundeter Nullwerte in Transformationsmatrizen
(`z.6f`); negative Maße und Spiegelungen bleiben, `-0.000000` und `0.000000`
sind dieselbe Lage.

`ci_window_durations.json` enthält historische Sekunden je Fensterdatei,
`ci_core_durations.json` dasselbe je Datei der Kernsuite — je mit einem
Ersatzwert für neue Dateien und ihrer Herkunft. Diese Gewichte verteilen
ausschließlich die aktuell gesammelten Tests; sie bestimmen niemals die
Auswahl. Neu erzeugt werden sie mit `tools/ci_shards.py` aus den
JUnit-Berichten eines abgeschlossenen Laufs, nicht von Hand. Den Vertrag und
die Aufteilung prüfen `test_ci_runner.py` und `test_packaging.py`.

## Ein Fehlerbild wird eine Datei hier

Das ist die Regel, die diesen Ordner erklärt: **Neue Fehlerbilder werden
Testdateien, keine Sonderfälle im Code.** Wer ein Netz findet, das die
Boolesche Operation zerlegt, legt es hierher und schreibt den Test dagegen.

## Was hier nicht abgelegt wird

Was ein Skript wiederherstellt. Das parametrische Skript ist die Quelle, die
Datei daraus ist das Ergebnis — dieselbe Regel wie im Ordner „3D Drucker".

**Die Ausnahme dazu ist die Zeit:** Der zweigängige Bolzen und die Naht ohne
Rille entstehen als Sweep mit Fuzzy-Vereinigung und kosten Sekunden. Die
Körper in `threads/` liegen deshalb als Ergebnis ihres Skripts hier —
das Skript bleibt die Quelle, und wer ein Maß oder den Erzeuger ändert, fährt
es neu; `make_thread_corpus.py --check` sagt, ob Datei und Erzeuger noch
dasselbe sind, und `test_thread_import.py` fragt das je Lauf für jeden
genähten Körper. Was aus einem Körper abzuleiten ist (Spiegelung, Lage,
Zuschnitt), baut der Test.

## Alte Projektdateien bleiben liegen

Eine Beispieldatei einer früheren `format_version` wird **nie** aktualisiert
und nie gelöscht. Sie ist der Beweis, dass die Migrationskette noch trägt;
ältere Migrationen werden aus demselben Grund nie zusammengefasst.
