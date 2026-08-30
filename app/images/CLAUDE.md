# `app/images/` — was das Handbuch zeigt

**Alles hier ist erzeugt.** Von Hand wird kein Bild bearbeitet und keines
hinzugefügt.

| Ordner | Inhalt | Werkzeug |
|---|---|---|
| `manual/<sprache>/` | Bildschirmfotos fürs Handbuch, je Sprache ein Ordner | `tools/make_figures.py` |
| `icon/` | `solidon3d.svg` und `-small.svg` — **die Quelle** des Anwendungssymbols | von Hand |

## Die Ausnahme ist `icon/`

Die beiden SVG sind Quelle, nicht Ergebnis. `tools/make_icon.py` rastert
daraus `packaging/solidon3d.ico`, `packaging/solidon3d.icns` und
`website/icon.svg`. Wer das Symbol ändert, ändert hier — und lässt danach das
Werkzeug laufen.

## Die Bildschirmfotos: ein Prozess je Sprache

Ein Lauf über alle sechs Sprachen in einem Prozess **stirbt** mit
Segmentation fault, nach der ersten Sprache. Ein Prozess je Sprache — dieselbe
Antwort wie bei der Testsuite. Eine Hintergrund-Hülle meldet darüber „exit
code 0"; der Beweis ist der Bildbestand, nicht der Rückgabewert.

**Und auch ein Ein-Sprachen-Lauf stirbt.** Am 31.08.2026 riss der spanische
nach drei von neun Bildern; die übrigen sechs blieben acht Stunden alt stehen,
und die Shell meldete 139. Fünf andere Sprachen liefen in derselben Reihe beim
ersten Anlauf durch. Ein Prozess je Sprache senkt die Wahrscheinlichkeit, er
beseitigt sie nicht — **nach jedem Lauf die Zeitstempel zählen und bei einer
alten Datei denselben Aufruf wiederholen.**

Der Ablauf steht im Skill `/erzeugen`, dort auch die Falle mit den fehlenden
Schriften.

## Ein neues Bild entsteht nicht hier

Es entsteht im Abbildungskatalog (`app/core/figures.py`). Wer ein Bild
braucht, trägt die Abbildung dort ein; der Lauf legt die Datei an.
