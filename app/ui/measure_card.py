"""Die Karte der Maßgruppe über der Ansicht: runde Ecken und der Weg der Tabulatortaste.

Die Karte trägt die Fachfelder des Merkmals im Rollbereich, den Sammelhaken und
*Übernehmen*/*Abbrechen* (``PlacementFlow._build_floating``). Die Felder
entstehen im Merkmalfenster und ziehen später in die Karte; Qt reiht sie in der
Fokuskette deshalb hinter die Knöpfe, und nach dem letzten Feld ging die
Tabulatortaste zum nächsten Widget des Fensters, dem Kartengriff „Objekte“ —
Haken und Knöpfe erreichte sie nie (FD-86). Hier gilt das Layout: Felder,
„Weitere Werte“, Sammelhaken, *Übernehmen*, *Abbrechen*, und danach wieder das
erste Feld (``oberflaeche.md``, „Die Tabulatortaste geht denselben Weg wie das
Auge“).
"""

from __future__ import annotations

from itertools import pairwise
from typing import cast, override

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QFrame,
    QGridLayout,
    QLayout,
    QLayoutItem,
    QScrollArea,
    QWidget,
)

from app.ui.overlay import _round_corners

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
    Rollbereich ist kein Halt, er reicht an seinen Inhalt weiter. Gefragt wird
    das Layout und nicht die Fokuskette: Die folgt der Entstehung, nicht dem
    Bild — und in Python an ihr entlangzulaufen räumt Widgets mit ab
    (``oberflaeche.md``).
    """
    stops: list[QWidget] = []
    # Gehalten, nicht nur gezählt: So bleibt jede Hülle bis zum Ende dieselbe.
    seen: dict[int, QWidget] = {}

    def visit(widget: QWidget) -> None:
        # Eine Zeile über die ganze Breite meldet das Formular unter zwei Rollen.
        if id(widget) in seen:
            return
        seen[id(widget)] = widget
        if isinstance(widget, QScrollArea):
            content = widget.widget()
            if content is not None:
                visit(content)
            return
        if widget.focusPolicy().value & Qt.FocusPolicy.TabFocus.value:
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


class MeasureCard(QFrame):
    """Die Karte der Maßgruppe — mit runden Ecken wie die Karten am Rand.

    Das Stilblatt rundet den Rahmen (``overlay.card_stylesheet``); die Maske
    stellt die Zwickel daneben frei, sonst stünden dort schwarze Ecken über
    dem Bild (:func:`overlay._round_corners`).

    **Die Tabulatortaste bleibt in der Karte** (FD-86): Sie geht die Halte nach
    dem Layout (:func:`tab_stops`) und schließt sich am Ende zum ersten Feld.
    Graue und verborgene Halte übergeht sie. Verlassen wird die Karte mit
    Escape, *Übernehmen* oder *Abbrechen*.
    """

    def settle_tab_order(self) -> None:
        """Die Fokuskette von Qt an das Layout angleichen — nach jedem Aufbau der Gruppe.

        ``setTabOrder`` hängt das zweite Widget hinter das erste; paarweise von
        vorn gesetzt, stehen die Halte am Ende in Layoutfolge beieinander.
        Unsichtbare und gesperrte übergeht Qt selbst.
        """
        for first, second in pairwise(tab_stops(self)):
            QWidget.setTabOrder(first, second)

    @override
    def focusNextPrevChild(self, next: bool) -> bool:
        """Tab und Umschalt+Tab innerhalb der Karte, nach dem Layout und im Kreis."""
        focused = QApplication.focusWidget()
        if focused is None or not self.isAncestorOf(focused):
            return super().focusNextPrevChild(next)
        stops = [stop for stop in tab_stops(self) if stop.isVisibleTo(self) and stop.isEnabled()]
        held: int | None = None
        for index, stop in enumerate(stops):
            if stop is focused or stop.isAncestorOf(focused):
                held = index
                break
        if held is None:
            return super().focusNextPrevChild(next)
        next_stop = stops[(held + (1 if next else -1)) % len(stops)]
        next_stop.setFocus(
            Qt.FocusReason.TabFocusReason if next else Qt.FocusReason.BacktabFocusReason
        )
        # Ein Halt im Rollbereich rollt ins Bild, auch von einem Knopf darunter aus.
        scroll = next_stop.parentWidget()
        while scroll is not None and scroll is not self and not isinstance(scroll, QScrollArea):
            scroll = scroll.parentWidget()
        if isinstance(scroll, QScrollArea):
            scroll.ensureWidgetVisible(next_stop)
        return True

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        _round_corners(self)
