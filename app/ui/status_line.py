"""Die Meldung der Statusleiste: Sie gibt zuerst nach, wenn die Leiste voll ist (FD-90).

Die Statusleiste trägt neben der Meldung dauerhafte Auskünfte — Material und
Druckdauer, Testzeitraum, Befunde. Ein ``QLabel`` meldet als Mindestbreite
seine volle Textbreite, und ein langer Satz nahm so der Zahlenzeile den Platz:
„14 g ·“, die Differenz endete in „Schrit…“. Die Meldung ist der eine Teil,
der kürzen darf — sie steht mit dem ganzen Satz in Kurzhilfe und für den
Bildschirmleser, und die nächste ersetzt sie ohnehin.

``text()`` bleibt der ganze Satz; gekürzt wird nur beim Zeichnen.
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget


class StatusLine(QLabel):
    """Eine einzeilige Meldung, die sich kürzt, statt ihre Nachbarn zu kürzen."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("", parent)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Ein Auslassungszeichen breit: Alles darüber gibt die Leiste zuerst den Nachbarn."""
        return QSize(self.fontMetrics().horizontalAdvance("…"), super().minimumSizeHint().height())

    def setText(self, text: str) -> None:  # noqa: N802 — Qt-Name
        super().setText(text)
        self._tell()

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)
        self._tell()

    def shown_text(self) -> str:
        """Was bei dieser Breite dasteht — der Satz oder sein gekürzter Anfang."""
        return self.fontMetrics().elidedText(
            self.text(), Qt.TextElideMode.ElideRight, self.contentsRect().width()
        )

    def _tell(self) -> None:
        """Gekürzt steht der ganze Satz in der Kurzhilfe, ungekürzt keine."""
        self.setToolTip(self.text() if self.shown_text() != self.text() else "")

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 — Qt-Name
        del event
        painter = QPainter(self)
        self.style().drawItemText(
            painter,
            self.contentsRect(),
            int(self.alignment()),
            self.palette(),
            self.isEnabled(),
            self.shown_text(),
            self.foregroundRole(),
        )
        painter.end()
