"""Gizmo switch and snapping steps (Bauplan §18.11).

Numeric entry happens in the operation dialogs — they are generated from the
same schema and are editable afterwards. What this bar adds is the direct
manipulation: the gizmo, and how far it snaps.
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
    """Turn the gizmo on, and set what it snaps to."""

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
        """Grid step in millimetres and angle step in degrees. Zero means no snapping."""
        return float(self.grid.value()), float(self.angle.value())

    def _emit_snapping(self) -> None:
        grid, angle = self.steps()
        self.snappingChanged.emit(grid, angle)
