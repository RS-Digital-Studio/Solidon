# `tests/data/` — der Referenzkorpus

Die Modelle und Projekte, gegen die gemessen wird.

| Ordner | Inhalt |
|---|---|
| `meshes/` | Netze für die Geometrietests |
| `projects/` | Projektdateien, darunter **alte Formatversionen** für die Migrationstests |

## Ein Fehlerbild wird eine Datei hier

Das ist die Regel, die diesen Ordner erklärt: **Neue Fehlerbilder werden
Testdateien, keine Sonderfälle im Code.** Wer ein Netz findet, das die
Boolesche Operation zerlegt, legt es hierher und schreibt den Test dagegen.

## Was hier nicht abgelegt wird

Was ein Skript wiederherstellt. Das parametrische Skript ist die Quelle, die
Datei daraus ist das Ergebnis — dieselbe Regel wie im Ordner „3D Drucker".

## Alte Projektdateien bleiben liegen

Eine Beispieldatei einer früheren `format_version` wird **nie** aktualisiert
und nie gelöscht. Sie ist der Beweis, dass die Migrationskette noch trägt;
ältere Migrationen werden aus demselben Grund nie zusammengefasst.
