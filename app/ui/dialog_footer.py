"""Operationsknöpfe bleiben auch in einer selbst gewählten Breite vollständig."""

from typing import override

from PySide6.QtCore import QEvent, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QTextLayout, QTextOption
from PySide6.QtWidgets import (
    QDialogButtonBox,
    QPushButton,
    QSizePolicy,
    QStyle,
    QStyleOptionButton,
    QWidget,
)

from app.ui.style import SPACE, make_primary


class DialogFooter(QDialogButtonBox):
    """Qt behält Rollen und Tasten; bei Platzmangel stehen Knöpfe untereinander."""

    geometryChanged = Signal()

    def __init__(self, buttons: QDialogButtonBox.StandardButton, parent: QWidget) -> None:
        super().__init__(buttons, parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._labels: dict[QPushButton, tuple[str, str]] = {}
        self._natural_width = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reflow)
        self._timer.start(0)

    @staticmethod
    def _size(button: QPushButton, text: str) -> QSize:
        option = QStyleOptionButton()
        button.initStyleOption(option)
        return button.style().sizeFromContents(
            QStyle.ContentsType.CT_PushButton,
            option,
            button.fontMetrics().size(Qt.TextFlag.TextShowMnemonic, text),
            button,
        )

    @property
    def natural_width(self) -> int:
        """Die volle Knopfzeile, unabhängig von ihrem vorübergehenden Umbruch."""
        return self._natural_width

    def _reflow(self) -> None:
        buttons = [button for button in self.buttons() if isinstance(button, QPushButton)]
        for button in buttons:
            source, painted = self._labels.get(button, (button.text(), button.text()))
            if button.text() != painted:
                source = button.text()
            self._labels[button] = source, painted
            if button.isDefault() and button.font().weight() != QFont.Weight.DemiBold:
                make_primary(button)
        width = sum(self._size(button, self._labels[button][0]).width() for button in buttons)
        width += SPACE * max(0, len(buttons) - 1)
        changed = width != self._natural_width
        self._natural_width = width
        orientation = (
            Qt.Orientation.Horizontal if width <= self.width() else Qt.Orientation.Vertical
        )
        if orientation != self.orientation():
            self.setOrientation(orientation)
            self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            changed = True
        layout = self.layout()
        if layout is not None:
            layout.setSpacing(SPACE)
        for button in buttons:
            source, painted = self._labels[button]
            text = source
            if self._size(button, source).width() > self.width():
                # Auch ein einzelner langer Knopf setzt keine neue Mindestbreite.
                # Qt bricht an Wortgrenzen, nötigenfalls innerhalb eines Wortes;
                # die Originalbeschriftung bleibt für spätere Breiten erhalten.
                metrics = button.fontMetrics()
                chrome = (
                    self._size(button, source).width()
                    - metrics.size(Qt.TextFlag.TextShowMnemonic, source).width()
                )
                lines = []
                for paragraph in source.split("\n"):
                    text_layout = QTextLayout(paragraph, button.font())
                    option = QTextOption()
                    option.setWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
                    text_layout.setTextOption(option)
                    encoded = paragraph.encode("utf-16-le")
                    text_layout.beginLayout()
                    while (line := text_layout.createLine()).isValid():
                        line.setLineWidth(max(1, self.width() - chrome))
                        start, end = line.textStart(), line.textStart() + line.textLength()
                        lines.append(encoded[start * 2 : end * 2].decode("utf-16-le").rstrip())
                    text_layout.endLayout()
                text = "\n".join(lines)
            if button.text() != text:
                button.setText(text)
                changed = True
            button.setAccessibleName(source)
            self._labels[button] = source, text
        if changed:
            self.updateGeometry()
            self.geometryChanged.emit()

    @override
    def event(self, event: QEvent) -> bool:
        handled = super().event(event)
        if event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.FontChange,
            QEvent.Type.StyleChange,
            QEvent.Type.LayoutRequest,
        ) and hasattr(self, "_timer"):
            self._timer.start(0)
        return handled
