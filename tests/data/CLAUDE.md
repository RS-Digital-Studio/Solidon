# `tests/data/` — der Referenzkorpus

Die Modelle und Projekte, gegen die gemessen wird.

| Ordner | Inhalt |
|---|---|
| `meshes/` | Netze für die Geometrietests |
| `projects/` | Projektdateien, darunter **alte Formatversionen** für die Migrationstests |
| `threads/` | Fünf STEP-Gewindekörper aus Konstruktionsmaßen (`make_thread_corpus.py`): M6, M10, M8 innen, zweigängig, eine Naht ohne Rille — die Basis der Fallmatrix in `test_thread_import.py`; alles Abgeleitete baut der Test selbst |

## Ein Fehlerbild wird eine Datei hier

Das ist die Regel, die diesen Ordner erklärt: **Neue Fehlerbilder werden
Testdateien, keine Sonderfälle im Code.** Wer ein Netz findet, das die
Boolesche Operation zerlegt, legt es hierher und schreibt den Test dagegen.

## Was hier nicht abgelegt wird

Was ein Skript wiederherstellt. Das parametrische Skript ist die Quelle, die
Datei daraus ist das Ergebnis — dieselbe Regel wie im Ordner „3D Drucker".

**Die Ausnahme dazu ist die Zeit:** Ein Gewindebolzen kostet im exakten Kern
rund zwanzig Sekunden, ein Innengewinde fast eine Minute. Die fünf Körper in
`threads/` liegen deshalb als Ergebnis ihres Skripts hier — das Skript bleibt
die Quelle, und wer ein Maß ändert, fährt es neu. Was in unter einer Sekunde
aus einem Körper abzuleiten ist (Spiegelung, Lage, Zuschnitt), baut der Test.

## Alte Projektdateien bleiben liegen

Eine Beispieldatei einer früheren `format_version` wird **nie** aktualisiert
und nie gelöscht. Sie ist der Beweis, dass die Migrationskette noch trägt;
ältere Migrationen werden aus demselben Grund nie zusammengefasst.
