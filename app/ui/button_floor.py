"""Ein Knopf wird nie niedriger als seine Beschriftung (FD-185).

Das Stylesheet gibt ``QPushButton`` eine ``min-height`` (``style.stylesheet``),
und Qt setzt daraus beim Polieren eine **ausdrückliche** Mindesthöhe: Rahmen,
Innenabstand und ``WIDE``, zusammen 26 Bildpunkte. Eine ausdrückliche
Mindesthöhe schlägt in jedem Layout die Höhe, die der Knopf für seine Schrift
braucht (``qSmartMinSize``). Wird es eng, staucht das Layout den Knopf darauf:
Bei 18 Punkt standen die Handlungen im Prüfbericht 26 statt 38 Bildpunkte hoch,
die Beschriftung oben und unten abgeschnitten — und so jeder Knopf in einer
Spalte, der Platz fehlt.

Hier hebt ein Zuhörer an der Anwendung die Mindesthöhe jedes Knopfs auf die
Höhe seiner Beschriftung, nach jedem Polieren, Stil- und Schriftwechsel. Eine
Mindesthöhe, die der Code selbst gesetzt hat, bleibt Untergrenze; eine, die er
hier gesetzt hat, wird bei kleinerer Schrift wieder kleiner. Ein Knopf, dessen
Höchsthöhe darunter liegt, ist absichtlich klein und bleibt, wie er ist; einer
mit eigenem Layout ebenso.
"""

from __future__ import annotations

import weakref

from PySide6.QtCore import QCoreApplication, QEvent, QObject, QTimer
from PySide6.QtWidgets import QPushButton

from app.ui import app_events

#: Unter diesem Namen merkt sich ein Knopf die Höhe, die er hier bekam.
_SET_HERE = "textHeightFloor"

#: Nach diesen Ereignissen steht die Höhe der Beschriftung neu fest.
_KINDS = (QEvent.Type.Polish, QEvent.Type.StyleChange, QEvent.Type.FontChange)


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


class _TextHeightFloor(QObject):
    """Sammelt die Knöpfe eines Ereignisschwalls und hebt sie in der nächsten Runde.

    Erst dann: Der Zuhörer sieht ein Ereignis, bevor der Knopf es selbst
    verarbeitet, und sein Wunschmaß ist bis dahin das der alten Schrift.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._waiting: dict[int, weakref.ReferenceType[QPushButton]] = {}
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        self._timer.timeout.connect(self._settle)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt gibt den Namen
        if isinstance(watched, QPushButton):
            self._waiting[id(watched)] = weakref.ref(watched)
            self._timer.start()
        return False

    def _settle(self) -> None:
        waiting, self._waiting = self._waiting, {}
        for reference in waiting.values():
            button = reference()
            if button is None:
                continue
            try:
                hold_text_height(button)
            except RuntimeError:
                # Das C++-Objekt ist schon fort; der Python-Wrapper lebte noch.
                continue


def install() -> None:
    """Den Zuhörer einmal je Anwendung anmelden (``style.apply_style``)."""
    application = QCoreApplication.instance()
    if application is None or application.findChildren(_TextHeightFloor):
        return
    app_events.listen(_TextHeightFloor(application), _KINDS)
