---
name: vorgabelage-bricht-fremde-tests
description: "Wer die Vorgabelage ändert, bricht Tests, die von Geometrie nie sprechen — sie tragen Koordinaten als feste Zahl."
metadata:
  type: feedback
---

Am 03.09.2026 kam auf Roberts Anordnung das erste Modell eines Projekts
aufgesetzt und mittig herein. Die Änderung selbst ist klein: ein Parameter an
`load`, gesetzt bei leerem Stapel. Rot wurden **siebzehn Tests in fünf
Dateien**, und keine davon handelt vom Einlesen:

| Datei | Was dort stand |
|---|---|
| `test_selection.py` | Klickpunkt `(-30, -20, 4.0)`, Strahlreichweite `96.0` |
| `test_split_tool.py` | Trennlinie auf `z=2.0` — die Würfelmitte von damals |
| `test_operation_ui.py` | „die Oberseite der Platte" als `4.0` |
| `test_ui.py` | „ein geladenes Modell steckt unter der Platte" |
| `test_manual.py` | die Website-Referenz kannte den neuen Parameter nicht |

Der Versatz betrug **vier bis zehn Millimeter in Z**, und er kam nicht vom
Zentrieren: Die Korpusmodelle liegen ohnehin mittig, verschoben hat sie das
Aufsetzen. Eine echte Slicer-3MF verschiebt sich um 76 bis 210 mm — dort
stellt sich die Frage erst richtig.

**Why:** Eine Vorgabelage ist keine Eigenschaft ihres Moduls, sondern die
Voraussetzung jedes Tests, der auf Geometrie zeigt. Diese Tests nennen weder
`load` noch die Lage; sie tragen eine Zahl, die einmal richtig abgelesen war.
`tools/affected_tests.py` findet sie nicht — der Importgraph verbindet sie
nicht. Zwei Tests warnten im **eigenen Docstring** vor genau dem Fall
(„bei einem Körper, der auf dem Bett angeordnet ist, lag er fünfundsechzig
Millimeter daneben") und schrieben die Zahl trotzdem daneben:
[[benannte-falle-schuetzt-nicht]].

**How to apply:** Wer eine Vorgabelage, eine Vorgabeeinheit oder einen
Nullpunkt ändert, greppt vorher `tests/` nach Zahlentupeln und
`pytest.approx(<zahl>)` statt sich auf den Importgraphen zu verlassen — und
fährt die Fensterdateien, auch wenn sie „nicht betroffen" heißen. Repariert
wird nicht die Zahl, sondern ihre Herkunft: `top_of(window)` aus den
Objektgrenzen, `mid_of(window)` aus dem Hüllquader. Eine nachgezogene Zahl
altert beim nächsten Umbau wieder still ([[abgelesene-zahl-altert-still]]).

Und ein neuer Operationsparameter macht die Website-Referenz am selben Tag
falsch; `make_manual.py`, danach `stamp_assets.py`
([[erzeugte-datei-fuehrt-ins-fremde-werkzeug]]).
