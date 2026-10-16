"""Merkmallisten bemessen ihren Platz an den Zeilen statt an Qts leerem Vorgabefeld."""

from typing import Final, override

from PySide6.QtCore import QEvent, QSize, QTimer
from PySide6.QtWidgets import QAbstractItemView, QListWidget, QSizePolicy, QWidget

from app.ui.overlay import rows_height

#: Acht Zeilen bleiben neben den übrigen Eingaben überschaubar. Weitere
#: Merkmale bleiben in derselben Liste mit Rad und Tastatur erreichbar.
FEATURE_ROWS_SHOWN: Final = 8


class FeatureList(QListWidget):
    """Kurze Auswahlen passen genau; lange rollen in einem mit der Schrift wachsenden Feld."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self._fit_timer = QTimer(self)
        self._fit_timer.setSingleShot(True)
        self._fit_timer.timeout.connect(self._fit_height)
        model = self.model()
        model.rowsInserted.connect(self._queue_fit)
        model.rowsRemoved.connect(self._queue_fit)
        model.modelReset.connect(self._queue_fit)
        model.dataChanged.connect(self._queue_fit)
        self.horizontalScrollBar().rangeChanged.connect(self._queue_fit)
        self._queue_fit()

    def _queue_fit(self) -> None:
        self._fit_timer.start(0)

    def fit_now(self) -> None:
        """Die Höhe jetzt setzen, in der Breite, die die Liste gerade hat.

        Für die Anfangsmessung eines Dialogs: Fiel sie vor den Zeitgeber oder
        vor das Wegfallen der Querleiste in der endgültigen Breite, maß der
        Dialog die Liste in ihrer alten Höhe, und der Streifen, um den sie
        danach schrumpfte, blieb über den Knöpfen leer — passives Nachmessen
        gibt nie Höhe zurück (FD-45).
        """
        self._fit_timer.stop()
        self._fit_height()

    def _fit_height(self) -> None:
        # Erst nach Qts verzögertem Modell-/Schriftwechsel messen; während
        # rowsInserted kann selbst der Text der neuen Zeile noch fehlen.
        self.doItemsLayout()
        self.setFixedHeight(self.sizeHint().height())

    @override
    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        row = max(self.fontMetrics().lineSpacing(), self.sizeHintForRow(0))
        chrome = 2 * self.frameWidth()
        bar = self.horizontalScrollBar()
        if bar.isVisibleTo(self):
            chrome += bar.sizeHint().height()
        hint.setHeight(min(rows_height(self), FEATURE_ROWS_SHOWN * row + chrome))
        return hint

    @override
    def event(self, event: QEvent) -> bool:
        handled = super().event(event)
        if event.type() in (
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.DevicePixelRatioChange,
        ):
            self._queue_fit()
        return handled
