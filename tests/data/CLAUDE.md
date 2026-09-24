# `tests/data/` — der Referenzkorpus

Die Modelle und Projekte, gegen die gemessen wird.

| Ordner | Inhalt |
|---|---|
| `meshes/` | Netze für die Geometrietests |
| `projects/` | Projektdateien, darunter **alte Formatversionen** für die Migrationstests |
| `step/` | Sechs STEP-Baugruppen aus Konstruktionsmaßen (`make_step_assembly_corpus.py`, P7.4): Instanzen mit Lage und Instanzfarbe, verschachtelt mit SHUO und Spiegelung, ein Teil mit mehreren Körpern, ohne Namen, in Zoll, Flächenmodell — die Sollwerte stehen im Erzeuger, `--check` vergleicht den XCAF-Baum |
| `threads/` | Fünf STEP-Gewindekörper aus Konstruktionsmaßen (`make_thread_corpus.py`): M6, M10, M8 innen, zweigängig, eine Naht ohne Rille — die Basis der Fallmatrix in `test_thread_import.py`; alles Abgeleitete baut der Test selbst |

Der STEP-Baumvergleich normalisiert das Vorzeichen gerundeter Nullwerte in
Transformationsmatrizen (`z.6f`). Negative Maßwerte und Spiegelungen bleiben
erhalten; `-0.000000` und `0.000000` bezeichnen dieselbe Lage.

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
fünf Körper in `threads/` liegen deshalb als Ergebnis ihres Skripts hier —
das Skript bleibt die Quelle, und wer ein Maß oder den Erzeuger ändert, fährt
es neu; `make_thread_corpus.py --check` sagt, ob Datei und Erzeuger noch
dasselbe sind, und `test_thread_import.py` fragt das je Lauf für die drei
genähten Bolzen (RM-195: unter einer halben Sekunde je Körper). Was aus einem
Körper abzuleiten ist (Spiegelung, Lage, Zuschnitt), baut der Test.

## Alte Projektdateien bleiben liegen

Eine Beispieldatei einer früheren `format_version` wird **nie** aktualisiert
und nie gelöscht. Sie ist der Beweis, dass die Migrationskette noch trägt;
ältere Migrationen werden aus demselben Grund nie zusammengefasst.
