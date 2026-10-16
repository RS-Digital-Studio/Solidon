"""Ein Wachhund gegen Größenschleifen in Fenstertests (Nachprüfung Restpaket A, L3).

Schaltet ein Dialog seinen Rollbalken ohne Ende hin und her, käme
``processEvents`` nie zurück, und ein Fall hinge bis zur Zeitgrenze der CI.
Der Wachhund macht daraus einen roten Fall. Eigenes Modul, weil
``test_generate_ui.py`` unter der Sperrklinke steht.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QWidget

#: So oft darf der Ausschnitt seine Größe ändern, während ein Status ankommt —
#: weit über dem, was ein Wachsen braucht. Darüber schaltet der Dialog ohne Ende.
RESIZES_PER_STATUS = 200


class ResizeWatchdog(QObject):
    """Zählt die Größenänderungen des Ausschnitts und hält eine Endlosschleife an.

    Schaltet der Dialog seinen Balken ohne Ende hin und her, käme ``processEvents``
    nie zurück, und der Fall hinge bis zur Zeitgrenze der CI. Über der Grenze
    verbirgt der Wachhund den Dialog — verborgen misst er nicht mehr —, und der
    Fall wird an der Zählung rot (Nachprüfung, L3).
    """

    def __init__(self, dialog: QWidget) -> None:
        super().__init__(dialog)
        self.dialog = dialog
        self.count = 0

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        if event.type() == QEvent.Type.Resize:
            self.count += 1
            if self.count > RESIZES_PER_STATUS and self.dialog.isVisible():
                self.dialog.hide()
        return False
