"""Eine umgebrochene Beschriftung bekommt die Höhe aller ihrer Zeilen (FD-183).

``dialogs.align_to_the_front`` lässt eine Beschriftung der Rückseite in der
Spalte der Vorderseite umbrechen und hält ihre Breite fest. Die Höhe der Zeile
nimmt das Formular aber aus der Wunschgröße des Labels, und die rechnet Qt
für eine breitere Zeile: „Durchmesser der Aufweitung“ an *Bohrung setzen*
brauchte drei Zeilen, bekam zwei, und „Aufweitung“ fehlte. Die Untergrenze der
Höhe ist deshalb die Höhe des Textes in der Breite, die das Label hat — neu
gerechnet, wenn sich Schrift, Stil oder Breite ändern.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QTimer
from PySide6.QtWidgets import QLabel

#: Wann die Zeilen neu gezählt werden.
_RECOUNT_ON = frozenset(
    {QEvent.Type.FontChange, QEvent.Type.StyleChange, QEvent.Type.Resize, QEvent.Type.Show}
)


def _hold(label: QLabel) -> None:
    """Die Untergrenze der Höhe auf die Höhe des Textes in der festen Breite setzen.

    **Gemessen ohne die gepinnte Höhe**, wie ``style.WrappedNote.claim_height``:
    ``QLabel.heightForWidth`` meldet nie weniger als die Mindesthöhe, und nach
    einer kleineren Schrift hielt „Durchmesser der Aufweitung“ die 84 Punkte der
    großen statt 48 (Review F2a, R3).
    """
    width = label.maximumWidth() if label.maximumWidth() < 16_000 else label.width()
    if width <= 0:
        return
    pinned = label.minimumHeight()
    label.setMinimumHeight(0)
    need = label.heightForWidth(width)
    label.setMinimumHeight(need if need > 0 else pinned)


class _KeepsLines(QObject):
    """Zählt die Zeilen nach jeder Änderung von Schrift, Stil oder Breite neu."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt-Name
        if event.type() in _RECOUNT_ON and isinstance(watched, QLabel):
            # Nach Qts eigener Behandlung: Erst danach misst das Label in der
            # neuen Schrift.
            QTimer.singleShot(0, watched, lambda label=watched: _hold(label))
        return False


def keep_whole_lines(label: QLabel) -> None:
    """Die Beschriftung zeigt jede Zeile ihres Umbruchs, auch nach einem Schriftwechsel.

    Wiederholbar: Ein zweiter Aufruf legt keinen zweiten Filter an.
    """
    _hold(label)
    if label.findChild(_KeepsLines) is None:
        label.installEventFilter(_KeepsLines(label))
