"""Die Meldung der Statusleiste: Sie gibt zuerst nach, wenn die Leiste voll ist (FD-90).

Die Statusleiste trägt neben der Meldung dauerhafte Auskünfte — Material und
Druckdauer, Testzeitraum, Befunde. Ein ``QLabel`` meldet als Mindestbreite
seine volle Textbreite, und ein langer Satz nahm so der Zahlenzeile den Platz:
„14 g ·“, die Differenz endete in „Schrit…“. Die Meldung ist der eine Teil,
der kürzen darf — sie steht mit dem ganzen Satz in Kurzhilfe und für den
Bildschirmleser, und die nächste ersetzt sie ohnehin.

``text()`` bleibt der ganze Satz; gekürzt wird nur beim Zeichnen.

Ein Feld, dessen Text wächst, nimmt seine Breite sofort (:func:`settle_in_bar`).
"""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPainter, QPaintEvent, QResizeEvent
from PySide6.QtWidgets import QLabel, QSizePolicy, QStatusBar, QWidget


def settle_in_bar(field: QWidget) -> None:
    """Ein Feld der Statusleiste steht nach neuem Text gleich in seiner Breite (FD-90).

    Qt legt einen geänderten Text erst mit nachgereichten ``LayoutRequest``-
    Ereignissen aus — beim Feld mit eigenem Layout zweimal, erst im Feld,
    dann in der Leiste. Kam eines davon nicht an, blieb das Feld in der
    alten Breite stehen, über Sekunden und viele Ereignisrunden: Am echten
    Fenster zeigte die Zahlenzeile nach dem Öffnen „3,5 ç“ statt
    „3,5 g · 6 min“. Hier werden beide Layouts gleich gelegt; was danach
    gezeichnet wird, passt zum Text.
    """
    own = field.layout()
    if own is not None:
        own.invalidate()
        own.activate()
    field.updateGeometry()
    # Nur in der Leiste: Vor ``addPermanentWidget`` hängt das Feld noch am
    # Hauptfenster, und dessen Layout legt man nicht nebenbei neu.
    bar = field.parentWidget()
    layout = bar.layout() if isinstance(bar, QStatusBar) else None
    if layout is not None:
        layout.invalidate()
        layout.activate()


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
