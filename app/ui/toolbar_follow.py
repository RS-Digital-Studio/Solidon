"""Die Hauptleiste wählt ihre Form nach einem Schriftwechsel neu (L1, FD-194).

Ob die Werkzeugleiste Wörter oder nur Zeichen trägt, entscheidet
``MainWindow._fit_toolbar`` an der Breite, und das nur bei einer
Größenänderung. Nach 9 → 14 pt behielt die Leiste die Wörter, die bei 9 pt
passten, wurde breiter, und die Kopfzeile bekam 425 statt 1 206 Punkte:
Projektname, Maße und Drucker standen gekürzt da, die ein frisch bei 14 pt
geöffnetes Fenster ganz zeigt. Hier hört ein Filter an der Leiste auf
Schrift- und Stilwechsel und lässt sie in der nächsten Runde neu wählen.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QWidget


class _FontFollower(QObject):
    """Ein Wechsel, eine neue Wahl — auch wenn Qt mehrere Ereignisse schickt."""

    def __init__(self, bar: QWidget, steps: tuple[Callable[[], None], ...]) -> None:
        super().__init__(bar)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(0)
        for step in steps:
            self._timer.timeout.connect(step)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        if event.type() in (QEvent.Type.FontChange, QEvent.Type.StyleChange):
            self._timer.start()
        return False


def follow_the_font(bar: QWidget, *steps: Callable[[], None]) -> None:
    """``steps`` der Reihe nach nach jedem Schrift- oder Stilwechsel der Leiste, gebündelt."""
    bar.installEventFilter(_FontFollower(bar, steps))
