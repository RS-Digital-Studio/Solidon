"""Die Pinselleiste (Bauplan §20, „Bemalen").

Einschalten, einen Slot und einen Radius wählen, aufs Modell klicken. Jeder
Klick ist eine Operation im Stapel — genau das macht das Malen Strich für
Strich rücknehmbar, und es hält Bild und Datei dieselbe Sache.

Per Vorgabe aus, und sie sagt das: eine Ansicht, die still malt, wenn jemand
das Modell drehen wollte, ist die Art Überraschung, die ein Undo behebt und
Vertrauen nicht übersteht.
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
from app.ui.style import NORMAL, TIGHT

#: Die Einheit eines Winkels — in jeder Sprache, die dieses Programm
#: mitbringt, dieselbe.
DEGREE = "°"


class PaintBar(QWidget):
    """Slot, Radius und Kantenwinkel für den Pinsel (§20)."""

    paintingToggled = Signal(bool)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        # Nicht „Bemalen": so heißt der Umschalter, der diese Leiste öffnet,
        # und beide standen mit demselben Wort direkt übereinander. Der
        # Umschalter holt das Werkzeug hervor, dieses Häkchen macht den Pinsel
        # scharf — zwei Dinge, die man auseinanderhalten muss, sobald man
        # einmal geklickt hat, ohne dass etwas passierte.
        self.active = QCheckBox(tr("Pinsel scharf"), self)
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
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
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
        """Woraus ein Strich besteht."""
        return {
            "slot": int(self.slot.value()),
            "radius": float(self.radius.value()),
            "edge_angle": float(self.edge.value()),
        }

    def stop(self) -> None:
        """Ausschalten — benutzt, wenn sich die Szene unter dem Pinsel ändert."""
        if self.active.isChecked():
            self.active.setChecked(False)
