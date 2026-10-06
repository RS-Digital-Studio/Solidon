# `app/images/` — was das Handbuch zeigt

**Alles hier ist erzeugt.** Von Hand wird kein Bild bearbeitet und keines
hinzugefügt. Das Warum: `konzepte/begruendungen/karte-app-images.md`.

| Ordner | Inhalt | Werkzeug |
|---|---|---|
| `manual/<sprache>/` | Bildschirmfotos fürs Handbuch, je Sprache ein Ordner | `tools/make_figures.py` |
| `icon/` | `solidon3d.svg` und `-small.svg` — **die Quelle** des Anwendungssymbols | von Hand |

## Die Ausnahme ist `icon/`

Die beiden SVG sind Quelle, nicht Ergebnis. `tools/make_icon.py` rastert
daraus `packaging/solidon3d.ico`, `packaging/solidon3d.icns` und
`website/icon.svg`, damit exe, Fenster und Website dasselbe zeigen. Wer das
Symbol ändert, ändert hier — und lässt danach das Werkzeug laufen.

## Die Bildschirmfotos: nur vor einem Release, ein Prozess je Sprache

Erzeugt wird vor einem Release und nur, was sich geändert hat — nicht nach
jedem Schritt (Entscheidung Robert; der Weg steht in `/erzeugen`).

Ein Lauf über alle sechs Sprachen in einem Prozess **stirbt** mit
Segmentation fault, nach der ersten Sprache. Ein Prozess je Sprache — dieselbe
Antwort wie bei der Testsuite. Eine Hintergrund-Hülle meldet darüber „exit
code 0"; der Beweis ist der Bildbestand, nicht der Rückgabewert.

**Und auch ein Ein-Sprachen-Lauf stirbt** gelegentlich mitten in der Reihe;
die übrigen Bilder bleiben dann alt stehen. Ein Prozess je Sprache senkt die
Wahrscheinlichkeit, er beseitigt sie nicht — **nach jedem Lauf die
Zeitstempel zählen und bei einer alten Datei denselben Aufruf wiederholen.**

Der Ablauf steht im Skill `/erzeugen`, dort auch die Falle mit den fehlenden
Schriften.

## Ein neues Bild entsteht nicht hier

Es entsteht im Abbildungskatalog (`app/core/figures.py`). Wer ein Bild
braucht, trägt die Abbildung dort ein; der Lauf legt die Datei an.
