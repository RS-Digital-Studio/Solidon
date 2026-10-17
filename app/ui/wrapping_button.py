"""Ein Knopf, dessen Beschriftung umbricht, statt sein Fenster zu verbreitern (FD-182).

Ein ``QPushButton`` verlangt seine ganze Beschriftung in einer Zeile als
Mindestbreite. Im Hinweis einer Absage (``dialogs.ErrorNotice``) steht der Knopf
in der schmalen Spalte des Operationsdialogs, und bei 18 Punkt drückte
„Eine andere Ebene wählen“ den Dialog auf 602 Bildpunkte, samt Rollbalken.
Hier bricht die Beschriftung an Wortgrenzen um; ``text()`` bleibt der ganze
Satz, für Vorlesen und Prüfungen.

Rand, Innenabstand und Mindesthöhe kommen aus der Differenz zu Qts eigenem
Wunschmaß, nicht aus einer Zahl im Stylesheet: Die Suite fährt ohne
Stylesheet, und eine geratene Konstante wäre dort eine andere als beim Kunden.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QPaintEvent, QPalette
from PySide6.QtWidgets import (
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QStylePainter,
    QWidget,
)

#: Wie die Beschriftung steht: mittig und an Wortgrenzen umbrochen.
_FLOW = Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap


class WrappingButton(QPushButton):
    """Ein Knopf, der so schmal sein darf wie sein längstes Wort."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        policy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        policy.setHeightForWidth(True)
        self.setSizePolicy(policy)

    def _chrome(self) -> QSize:
        """Was Rahmen und Innenabstand um die einzeilige Beschriftung legen.

        Die Zeilenhöhe kommt aus demselben Maß wie :meth:`_text_height`: Unter macOS
        misst ``boundingRect`` mit Umbruch eine Zeile einen Punkt höher als ``size``,
        und eine einzeilige Beschriftung meldete in ihrer eigenen Breite 27 statt 26
        Punkte (Fensterauswahl 39035816730).
        """
        line = self.fontMetrics().size(Qt.TextFlag.TextSingleLine, self.text())
        whole = super().sizeHint()
        line_height = self._text_height(1_000_000) if self.text() else line.height()
        return QSize(max(0, whole.width() - line.width()), max(0, whole.height() - line_height))

    def _text_height(self, width: int) -> int:
        """Die Höhe der Beschriftung, umbrochen auf ``width`` Bildpunkte."""
        room = QRect(0, 0, max(1, width), 1_000_000)
        return self.fontMetrics().boundingRect(room, int(_FLOW), self.text()).height()

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt-Name
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt-Name
        chrome = self._chrome()
        one_line = super().sizeHint().height()
        return max(one_line, chrome.height() + self._text_height(width - chrome.width()))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        words = self.text().split() or [""]
        metrics = self.fontMetrics()
        width = self._chrome().width() + max(metrics.horizontalAdvance(word) for word in words)
        return QSize(width, self.heightForWidth(width))

    def paintEvent(self, _event: QPaintEvent) -> None:  # noqa: N802 - Qt-Name
        option = QStyleOptionButton()
        self.initStyleOption(option)
        painter = QStylePainter(self)
        # Fläche, Rahmen und Fokus zeichnet der Stil ohne Text; die Beschriftung
        # folgt umbrochen in der Inhaltsfläche, die der Stil dafür nennt.
        text = option.text
        option.text = ""
        painter.drawControl(QStyle.ControlElement.CE_PushButton, option)
        contents = self.style().subElementRect(
            QStyle.SubElement.SE_PushButtonContents, option, self
        )
        self.style().drawItemText(
            painter,
            contents,
            int(_FLOW),
            option.palette,
            self.isEnabled(),
            text,
            QPalette.ColorRole.ButtonText,
        )
