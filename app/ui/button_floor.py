"""Ein Knopf wird nie niedriger als seine Beschriftung (FD-185).

Das Stylesheet gibt ``QPushButton`` eine ``min-height`` (``style.stylesheet``),
und Qt setzt daraus beim Polieren eine **ausdrückliche** Mindesthöhe: Rahmen,
Innenabstand und ``WIDE``, zusammen 26 Bildpunkte. Eine ausdrückliche
Mindesthöhe schlägt in jedem Layout die Höhe, die der Knopf für seine Schrift
braucht (``qSmartMinSize``). Wird es eng, staucht das Layout den Knopf darauf:
Bei 18 Punkt standen die Handlungen im Prüfbericht 26 statt 38 Bildpunkte hoch,
die Beschriftung oben und unten abgeschnitten — und so jeder Knopf in einer
Spalte, der Platz fehlt.

Hier steht, wie hoch die Mindesthöhe eines Knopfs sein muss; der Zuhörer,
der sie nach jedem Polieren, Stil- und Schriftwechsel hebt, ist
``style_follow`` (zusammen mit dem Stil, der der Schrift folgt, FD-194). Eine
Mindesthöhe, die der Code selbst gesetzt hat, bleibt Untergrenze; eine, die er
hier gesetzt hat, wird bei kleinerer Schrift wieder kleiner. Ein Knopf, dessen
Höchsthöhe darunter liegt, ist absichtlich klein und bleibt, wie er ist; einer
mit eigenem Layout ebenso.
"""

from __future__ import annotations

from PySide6.QtWidgets import QPushButton

#: Unter diesem Namen merkt sich ein Knopf die Höhe, die er hier bekam.
_SET_HERE = "textHeightFloor"


def text_height(button: QPushButton) -> int:
    """Die Höhe, die die Beschriftung in einer Zeile braucht, samt Rahmen.

    Das Kleinere aus Wunsch- und Mindestmaß: Ein umbrechender Knopf
    (``wrapping_button``) meldet als Mindestmaß die Höhe in der schmalsten
    Breite; untergrenze ist dort eine Zeile, den Rest gibt ``heightForWidth``.
    """
    return min(button.sizeHint().height(), button.minimumSizeHint().height())


def hold_text_height(button: QPushButton) -> None:
    """Die Mindesthöhe des Knopfs auf seine Beschriftung heben (oder zurück)."""
    if button.layout() is not None:
        # Ein Knopf mit eigenem Inhalt (die Beispielkachel) bekommt seine
        # Mindesthöhe vom Layout; eine ausdrückliche hier nähme sie ihm.
        return
    need = text_height(button)
    if button.maximumHeight() < need:
        return
    current = button.minimumHeight()
    ours = button.property(_SET_HERE)
    base = 0 if isinstance(ours, int) and current == ours else current
    floor = max(base, need)
    button.setProperty(_SET_HERE, floor)
    if floor != current:
        button.setMinimumHeight(floor)
