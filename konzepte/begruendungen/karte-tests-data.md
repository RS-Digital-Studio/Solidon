# Begründungen zu `tests/data/CLAUDE.md`

> Stand 27.09.2026. Aus der Karte verschoben, als sie ihre Registernummern und
> Messwerte abgab. Die Karte steht dort; hier stehen die Absätze in ihrer
> früheren Fassung — wörtlich, gegliedert nach den Überschriften der Karte.
> *Früher unter …* nennt die Stelle der alten Karte.

## Kopf

Die Karte nennt die Phase P7.4 nicht mehr; die Tabelle trägt heute auch die
Erzeuger, `recipes/`, `linux/`, `spacemouse/` und den Verweis auf `README.md`.

*Früher unter „`tests/data/` — der Referenzkorpus“.*

| Ordner | Inhalt |
|---|---|
| `meshes/` | Netze für die Geometrietests |
| `projects/` | Projektdateien, darunter **alte Formatversionen** für die Migrationstests |
| `step/` | Sechs STEP-Baugruppen aus Konstruktionsmaßen (`make_step_assembly_corpus.py`, P7.4): Instanzen mit Lage und Instanzfarbe, verschachtelt mit SHUO und Spiegelung, ein Teil mit mehreren Körpern, ohne Namen, in Zoll, Flächenmodell — die Sollwerte stehen im Erzeuger, `--check` vergleicht den XCAF-Baum |
| `threads/` | Fünf STEP-Gewindekörper aus Konstruktionsmaßen (`make_thread_corpus.py`): M6, M10, M8 innen, zweigängig, eine Naht ohne Rille — die Basis der Fallmatrix in `test_thread_import.py`; alles Abgeleitete baut der Test selbst |

## Was hier nicht abgelegt wird

Die Zeitangabe „unter einer halben Sekunde je Körper“ (RM-195) steht nicht
mehr in der Karte: `README.md` nennt für denselben Vergleich „je unter zwei
Sekunden“ — gemessen ist das jeweils am Tag seiner Zeile, keine Zusage.

*Früher unter „Was hier nicht abgelegt wird“.*

**Die Ausnahme dazu ist die Zeit:** Der zweigängige Bolzen und die Naht ohne
Rille entstehen als Sweep mit Fuzzy-Vereinigung und kosten Sekunden. Die
fünf Körper in `threads/` liegen deshalb als Ergebnis ihres Skripts hier —
das Skript bleibt die Quelle, und wer ein Maß oder den Erzeuger ändert, fährt
es neu; `make_thread_corpus.py --check` sagt, ob Datei und Erzeuger noch
dasselbe sind, und `test_thread_import.py` fragt das je Lauf für die drei
genähten Bolzen (RM-195: unter einer halben Sekunde je Körper). Was aus einem
Körper abzuleiten ist (Spiegelung, Lage, Zuschnitt), baut der Test.
