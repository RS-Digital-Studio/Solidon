"""The brush bar (Bauplan §20, "Bemalen").

Switch it on, pick a slot and a radius, click on the model. Every click is one
operation in the stack, which is what makes painting undoable one stroke at a
time — and what keeps the picture and the file the same thing.

Off by default, and it says so: a view that silently paints when somebody meant
to turn the model is the kind of surprise an undo fixes and trust does not
survive.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from app.core.geom.paint import EDGE_ANGLE, MAX_SLOTS
from app.core.units import DISPLAY_UNITS
from app.i18n import tr

#: The unit of an angle, which is the same in every language this ships in.
DEGREE = "°"


class PaintBar(QWidget):
    """Slot, radius and edge angle for the brush (§20)."""

    paintingToggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.active = QCheckBox(tr("Bemalen"), self)
        self.active.setToolTip(tr("Klicks im Modell malen den gewählten Slot."))
        self.active.toggled.connect(self.paintingToggled)

        self.slot = QSpinBox(self)
        self.slot.setRange(0, MAX_SLOTS - 1)
        self.slot.setValue(1)

        self.radius = QDoubleSpinBox(self)
        self.radius.setRange(0.1, 500.0)
        self.radius.setValue(10.0)
        self.radius.setSuffix(f" {DISPLAY_UNITS[0]}")

        self.edge = QDoubleSpinBox(self)
        self.edge.setRange(1.0, 180.0)
        self.edge.setValue(EDGE_ANGLE)
        self.edge.setSuffix(f" {DEGREE}")
        self.edge.setToolTip(
            tr("Ab diesem Winkel hält der Pinsel an. 180 Grad heißt: über alles hinweg.")
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.addWidget(self.active)
        layout.addWidget(QLabel(tr("Slot"), self))
        layout.addWidget(self.slot)
        layout.addWidget(QLabel(tr("Radius"), self))
        layout.addWidget(self.radius)
        layout.addWidget(QLabel(tr("Kantenwinkel"), self))
        layout.addWidget(self.edge)
        layout.addStretch(1)

    @property
    def painting(self) -> bool:
        return bool(self.active.isChecked())

    def values(self) -> dict[str, float | int]:
        """What one stroke is made of."""
        return {
            "slot": int(self.slot.value()),
            "radius": float(self.radius.value()),
            "edge_angle": float(self.edge.value()),
        }

    def stop(self) -> None:
        """Switch off — used when the scene changes under the brush."""
        if self.active.isChecked():
            self.active.setChecked(False)
