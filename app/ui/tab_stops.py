"""Die Halte der Tabulatortaste nach dem Layout — und eine Kette, die ihm folgt.

Qt reiht ein Widget in die Fokuskette, wenn es entsteht, und lässt es dort,
wenn es umzieht. Eine Fläche, deren Felder später oder an anderer Stelle
entstehen als ihr Rahmen, führt die Tabulatortaste deshalb durch fremde
Bereiche: Die Felder der Maßgruppe kamen nach dem Kartengriff „Objekte“
(FD-86), vom Reiter *Prüfbericht* ging es zur Kopfzeile statt in den Bericht
(FD-177). Gefragt wird hier das Layout, nicht die Fokuskette — die folgt der
Entstehung, nicht dem Bild, und in Python an ihr entlangzulaufen räumt
Widgets mit ab (``oberflaeche.md``).
"""

from __future__ import annotations

from itertools import pairwise
from typing import cast

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFormLayout, QGridLayout, QLayout, QLayoutItem, QScrollArea, QWidget

#: Die Rollen einer Formularzeile in Lesereihenfolge.
_ROW_ROLES = (
    QFormLayout.ItemRole.LabelRole,
    QFormLayout.ItemRole.FieldRole,
    QFormLayout.ItemRole.SpanningRole,
)


def tab_stops(root: QWidget) -> list[QWidget]:
    """Die Halte der Tabulatortaste unter ``root`` in der Reihenfolge des Layouts.

    Ein Halt ist ein Widget, das Fokus per Tabulatortaste nimmt; sein
    Innenleben (das Textfeld eines Drehfelds) zählt nicht extra. Ein
    Rollbereich reicht an seinen Inhalt weiter; ist er selbst ein Halt (ein
    Lesebereich, ``scroll_areas.ReadingScrollArea``), steht er davor.
    Verborgene und gesperrte Halte zählen mit — sie bekommen so ihren Platz,
    bevor sie erscheinen; übergangen werden sie von Qt beim Drücken.
    """
    stops: list[QWidget] = []
    # Gehalten, nicht nur gezählt: So bleibt jede Hülle bis zum Ende dieselbe.
    seen: dict[int, QWidget] = {}

    def visit(widget: QWidget) -> None:
        # Eine Zeile über die ganze Breite meldet das Formular unter zwei Rollen.
        if id(widget) in seen:
            return
        seen[id(widget)] = widget
        takes_tab = bool(widget.focusPolicy().value & Qt.FocusPolicy.TabFocus.value)
        if isinstance(widget, QScrollArea):
            if takes_tab:
                stops.append(widget)
            content = widget.widget()
            if content is not None:
                visit(content)
            return
        if takes_tab:
            stops.append(widget)
            return
        layout = widget.layout()
        if layout is not None:
            walk(layout)

    def walk(layout: QLayout) -> None:
        for item in _items_in_reading_order(layout):
            inner = item.layout()
            if inner is not None:
                walk(inner)
                continue
            widget = item.widget()
            if widget is not None:
                visit(widget)

    layout = root.layout()
    if layout is not None:
        walk(layout)
    return stops


def _items_in_reading_order(layout: QLayout) -> list[QLayoutItem]:
    """Die Elemente eines Layouts, wie das Auge sie liest — Zeile für Zeile."""
    if isinstance(layout, QFormLayout):
        return [
            item
            for row in range(layout.rowCount())
            for role in _ROW_ROLES
            if (item := layout.itemAt(row, role)) is not None
        ]
    count = layout.count()
    if isinstance(layout, QGridLayout):
        cells = sorted(
            (cast(tuple[int, int, int, int], layout.getItemPosition(index))[:2], index)
            for index in range(count)
        )
        order = [index for _cell, index in cells]
    else:
        order = list(range(count))
    return [item for index in order if (item := layout.itemAt(index)) is not None]


def chain_after(anchor: QWidget, root: QWidget) -> None:
    """Legt die Halte unter ``root`` in Layoutfolge direkt hinter ``anchor``.

    ``setTabOrder`` hängt das zweite Widget hinter das erste; paarweise von
    vorn gesetzt, stehen die Halte am Ende beieinander, und wer sie verlässt,
    geht dorthin, wo die Kette nach ``anchor`` vorher weiterging.
    """
    for first, second in pairwise([anchor, *tab_stops(root)]):
        QWidget.setTabOrder(first, second)
