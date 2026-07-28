"""The explosion view for split results (Bauplan §18.8).

One slider, and it only appears when there is more than one body to pull apart.
A control that is always visible and does nothing most of the time teaches
people to ignore it.

What it changes is the picture and nothing else — the stack, the export and the
report see the parts where they are.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from app.i18n import tr

#: The slider counts in tenths, so 20 means "twice the distance from the middle".
MAX_STEPS = 20


class ExplodeBar(QWidget):
    """Pull the parts of a split apart, for looking at them."""

    factorChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, MAX_STEPS)
        self.slider.setValue(0)
        self.slider.setToolTip(tr("Zieht geteilte Objekte zum Ansehen auseinander."))
        self.slider.valueChanged.connect(self._on_moved)

        self.reset = QPushButton(tr("Zusammen"), self)
        self.reset.clicked.connect(lambda: self.slider.setValue(0))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.addWidget(QLabel(tr("Explosionsansicht"), self))
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.reset)
        self.setVisible(False)

    @property
    def factor(self) -> float:
        return self.slider.value() / 10.0

    def show_for(self, objects: int) -> None:
        """Visible from two bodies on; folded back together when it disappears."""
        wanted = objects > 1
        if not wanted and self.slider.value():
            self.slider.setValue(0)
        self.setVisible(wanted)

    def _on_moved(self, value: int) -> None:
        self.factorChanged.emit(value / 10.0)
