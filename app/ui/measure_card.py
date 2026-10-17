"""Die Karte der Maßgruppe über der Ansicht: runde Ecken, Tabulatorweg, Sätze nur einmal.

Die Karte trägt die Fachfelder des Merkmals im Rollbereich, den Sammelhaken, den
Hinweis und *Übernehmen*/*Abbrechen* (``PlacementFlow._build_floating``). Die
Felder entstehen im Merkmalfenster und ziehen später in die Karte; Qt reiht sie
in der Fokuskette deshalb hinter die Knöpfe, und nach dem letzten Feld ging die
Tabulatortaste zum nächsten Widget des Fensters, dem Kartengriff „Objekte“ —
Haken und Knöpfe erreichte sie nie (FD-86). Hier gilt das Layout: Felder,
„Weitere Werte“, Sammelhaken, *Übernehmen*, *Abbrechen*, und danach wieder das
erste Feld (``oberflaeche.md``, „Die Tabulatortaste geht denselben Weg wie das
Auge“). Was eine Feldzeile schon sagt, wiederholt der Hinweis nicht
(:func:`stands_in`, FD-88).
"""

from __future__ import annotations

from itertools import pairwise
from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QScrollArea, QWidget

from app.ui.overlay import _round_corners
from app.ui.tab_stops import tab_stops


def stands_in(surface: QWidget | None, sentence: str) -> bool:
    """Ob ``sentence`` schon sichtbar auf ``surface`` steht — in einer ihrer Beschriftungen.

    Die Ablehnung einer Zahl steht unter ihrem Feld (``FeaturePanel``,
    ``feature-measure-refusal-*``), dort mit dem Weg dahinter. Der Hinweis der
    Karte wiederholte sie, und die Statuszeile ein drittes Mal (FD-88):
    Derselbe Satz dreimal lenkt vom Feld ab, das man ändern muss. Gefragt wird
    das Bild und nicht, woher der Satz kam — ein Feld hinter zugeklappten
    „Weiteren Werten“ zeigt ihn nicht, und dann sagt ihn die Karte.
    """
    if surface is None or not sentence:
        return False
    return any(
        sentence in label.text() and label.isVisibleTo(surface)
        for label in surface.findChildren(QLabel)
    )


class MeasureCard(QFrame):
    """Die Karte der Maßgruppe — mit runden Ecken wie die Karten am Rand.

    Das Stilblatt rundet den Rahmen (``overlay.card_stylesheet``); die Maske
    stellt die Zwickel daneben frei, sonst stünden dort schwarze Ecken über
    dem Bild (:func:`overlay._round_corners`).

    **Die Tabulatortaste bleibt in der Karte** (FD-86): Sie geht die Halte nach
    dem Layout (:func:`tab_stops`) und schließt sich am Ende zum ersten Feld.
    Graue und verborgene Halte übergeht sie. Verlassen wird die Karte mit
    Escape, *Übernehmen* oder *Abbrechen*, und jeder dieser Ausgänge gibt den
    Fokus an die Ansicht zurück (FD-160).
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
        view = self.parentWidget()
        if not self.isVisible() and view is not None and view.isVisible():
            # **Wer die Karte schließt, steht wieder in der Ansicht** (FD-160).
            # Qt fragt beim Verbergen hier nach dem nächsten Halt; der lag
            # hinter der Karte in der Fokuskette des Fensters — nach
            # *Abbrechen* der Kartengriff „Objekte“, nach *Übernehmen* und
            # Strg+Z dagegen die Ansicht, aus der die Maßgruppe kam.
            view.setFocus(Qt.FocusReason.OtherFocusReason)
            return True
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
