"""Explosion view and build plate selector (Bauplan §18.8, §25).

Two controls on one bar, and both only appear when there is something for them
to do: the slider from two bodies on, the plate selector from two plates on. A
control that is always visible and does nothing most of the time teaches people
to ignore it.

Both change the picture and nothing else — the stack, the export and the report
see every part where it is, on the plate it belongs to.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from app.i18n import tr

#: The slider counts in tenths, so 20 means "twice the distance from the middle".
MAX_STEPS = 20

#: What the selector calls "no filter".
ALL_PLATES = -1


class ExplodeBar(QWidget):
    """Pull the parts of a split apart, and pick a build plate to look at."""

    factorChanged = Signal(float)
    plateChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, MAX_STEPS)
        self.slider.setValue(0)
        self.slider.setToolTip(tr("Zieht geteilte Objekte zum Ansehen auseinander."))
        self.slider.valueChanged.connect(self._on_moved)

        self.reset = QPushButton(tr("Zusammen"), self)
        self.reset.clicked.connect(lambda: self.slider.setValue(0))

        self.plate_label = QLabel(tr("Druckplatte"), self)
        self.plates = QComboBox(self)
        self.plates.setToolTip(tr("Zeigt nur die Objekte einer Platte."))
        self.plates.currentIndexChanged.connect(self._on_plate)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.addWidget(QLabel(tr("Explosionsansicht"), self))
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.reset)
        layout.addWidget(self.plate_label)
        layout.addWidget(self.plates)
        self._show_plates(0)
        self.setVisible(False)

    @property
    def factor(self) -> float:
        return self.slider.value() / 10.0

    @property
    def plate(self) -> int:
        """The plate being shown, or ``ALL_PLATES``."""
        value = self.plates.currentData()
        return ALL_PLATES if value is None else int(value)

    def show_for(self, objects: int, plates: int = 1) -> None:
        """Visible from two bodies on; folded back together when it disappears."""
        wanted = objects > 1
        if not wanted and self.slider.value():
            self.slider.setValue(0)
        self._show_plates(plates)
        self.setVisible(wanted)

    def _show_plates(self, plates: int) -> None:
        """Rebuild the selector, keeping the plate that was being looked at."""
        previous = self.plate
        self.plates.blockSignals(True)
        self.plates.clear()
        self.plates.addItem(tr("Alle"), ALL_PLATES)
        for index in range(plates):
            self.plates.addItem(f"{tr('Platte')} {index + 1}", index)
        if previous != ALL_PLATES and previous < plates:
            self.plates.setCurrentIndex(previous + 1)
        self.plates.blockSignals(False)

        many = plates > 1
        self.plates.setVisible(many)
        self.plate_label.setVisible(many)
        if not many and previous != ALL_PLATES:
            self.plateChanged.emit(ALL_PLATES)

    def _on_moved(self, value: int) -> None:
        self.factorChanged.emit(value / 10.0)

    def _on_plate(self, index: int) -> None:
        del index
        self.plateChanged.emit(self.plate)
