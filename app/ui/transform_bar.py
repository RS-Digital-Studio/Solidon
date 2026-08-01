"""Gizmo-Schalter und Einrastschritte (Bauplan §18.11).

Zahleneingabe passiert in den Operationsdialogen — die entstehen aus demselben
Schema und sind nachträglich änderbar. Was diese Leiste hinzufügt, ist die
direkte Manipulation: der Gizmo, und wie weit er einrastet.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel, QWidget

from app.core.units import DISPLAY_UNITS
from app.i18n import tr

#: Sensible defaults: a millimetre of travel, fifteen degrees of turn.
DEFAULT_GRID_STEP = 1.0
DEFAULT_ANGLE_STEP = 15.0


class TransformBar(QWidget):
    """Schaltet den Gizmo ein und stellt ein, worauf er einrastet."""

    gizmoToggled = Signal(bool)
    snappingChanged = Signal(float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.gizmo = QCheckBox(tr("Gizmo"), self)
        self.gizmo.toggled.connect(self.gizmoToggled)

        self.grid = QDoubleSpinBox(self)
        self.grid.setDecimals(2)
        self.grid.setRange(0.0, 100.0)
        self.grid.setValue(DEFAULT_GRID_STEP)
        self.grid.setSuffix(f" {DISPLAY_UNITS[0]}")
        self.grid.valueChanged.connect(self._emit_snapping)

        self.angle = QDoubleSpinBox(self)
        self.angle.setDecimals(1)
        self.angle.setRange(0.0, 90.0)
        self.angle.setValue(DEFAULT_ANGLE_STEP)
        self.angle.valueChanged.connect(self._emit_snapping)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.addWidget(self.gizmo)
        layout.addWidget(QLabel(tr("Rasterfang"), self))
        layout.addWidget(self.grid)
        layout.addWidget(QLabel(tr("Winkelfang"), self))
        layout.addWidget(self.angle)
        layout.addStretch(1)

    def steps(self) -> tuple[float, float]:
        """Rasterschritt in Millimetern und Winkelschritt in Grad. Null heißt kein
        Einrasten.
        """
        return float(self.grid.value()), float(self.angle.value())

    def _emit_snapping(self) -> None:
        grid, angle = self.steps()
        self.snappingChanged.emit(grid, angle)
