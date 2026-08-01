"""Explosionsansicht und Plattenwähler (Bauplan §18.8, §25).

Zwei Bedienelemente auf einer Leiste, und beide erscheinen nur, wenn es für sie
etwas zu tun gibt: der Schieber ab zwei Körpern, der Plattenwähler ab zwei
Platten. Ein Element, das immer sichtbar ist und meistens nichts tut, bringt
Leuten bei, es zu ignorieren.

Beide ändern das Bild und sonst nichts — Stapel, Export und Prüfbericht sehen
jedes Teil dort, wo es ist, auf der Platte, auf die es gehört.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QPushButton, QSlider, QWidget

from app.i18n import tr
from app.ui.section_bar import SETTLE_MS

#: Der Schieber zählt in Zehnteln, 20 heißt also „doppelter Abstand zur
#: Mitte".
MAX_STEPS = 20

#: Wie der Wähler „kein Filter" nennt.
ALL_PLATES = -1


class ExplodeBar(QWidget):
    """Zieht die Teile einer Teilung auseinander und wählt eine Druckplatte
    zum Ansehen.
    """

    factorChanged = Signal(float)
    plateChanged = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pending = QTimer(self)
        self._pending.setSingleShot(True)
        self._pending.timeout.connect(self._settled)

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
        """Die Platte, die gezeigt wird, oder ``ALL_PLATES``."""
        value = self.plates.currentData()
        return ALL_PLATES if value is None else int(value)

    def show_for(self, objects: int, plates: int = 1) -> None:
        """Sichtbar ab zwei Körpern; klappt wieder zusammen, wenn sie
        verschwindet.
        """
        wanted = objects > 1
        if not wanted and self.slider.value():
            self.slider.setValue(0)
        self._show_plates(plates)
        self.setVisible(wanted)

    def _show_plates(self, plates: int) -> None:
        """Baut den Wähler neu und behält die Platte, die betrachtet wurde."""
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
        """Entprellt wie der Schnitt: jede Stufe baut die ganze Ansicht neu."""
        del value
        self._pending.start(SETTLE_MS)

    def _settled(self) -> None:
        self.factorChanged.emit(self.factor)

    def _on_plate(self, index: int) -> None:
        del index
        self.plateChanged.emit(self.plate)
