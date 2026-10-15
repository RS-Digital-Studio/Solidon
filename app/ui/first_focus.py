"""Ein vorgegebener Text ist beim ersten Fokus markiert (FD-114).

Qt markiert den Inhalt eines Textfelds nur, wenn Tab oder ein Kürzel hinführt.
Den ersten Fokus eines Dialogs gibt Qt beim Anzeigen, und dann stand der
Cursor vor dem Namen, den *Umbenennen* vorgibt: Jeder getippte Buchstabe
landete davor. Markiert ersetzt Tippen den Namen, und Ende ergänzt ihn.

Ein Klick mit der Maus setzt den Cursor, wohin geklickt wurde; dort bleibt es.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, Qt, QTimer
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QLineEdit


class _SelectOnFirstFocus(QObject):
    """Markiert den Text beim ersten Fokus und meldet sich danach ab."""

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 - Qt-Name
        if event.type() == QEvent.Type.FocusIn and isinstance(watched, QLineEdit):
            by_mouse = (
                isinstance(event, QFocusEvent) and event.reason() == Qt.FocusReason.MouseFocusReason
            )
            if watched.text() and not by_mouse:
                # Nach Qts eigener Behandlung des Fokus, die eine Markierung
                # ohne Tab wieder aufhebt.
                QTimer.singleShot(0, watched, watched.selectAll)
            watched.removeEventFilter(self)
            self.deleteLater()
        return False


def select_on_first_focus(line: QLineEdit) -> None:
    """Der Text des Felds ist markiert, sobald es zum ersten Mal den Fokus bekommt."""
    line.installEventFilter(_SelectOnFirstFocus(line))
