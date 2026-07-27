"""Controls for the section plane (Bauplan §18.2).

The plane is moved with a slider rather than typed in: looking through a body is
a searching motion, not a numeric entry. The slice thickness sits next to it, and
when a body was too open to close the cut face, this bar says so instead of
pretending the picture is complete.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)

from app.core.geom.section import AXIS_NORMALS, SectionPlane
from app.core.units import DISPLAY_UNITS, format_length
from app.i18n import tr

#: The slider works in tenths of a millimetre; EPS_DISPLAY is finer than any drag.
STEPS_PER_MM = 10


class MeasureBar(QWidget):
    """Which measuring tool is active, and the way to clear dimensions (§18.3)."""

    modeChanged = Signal(str)
    clearRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.mode = QComboBox(self)
        self.mode.addItem(tr("Nicht messen"), userData="off")
        self.mode.addItem(tr("Abstand messen"), userData="distance")
        self.mode.addItem(tr("Wandstärke messen"), userData="thickness")
        self.mode.currentIndexChanged.connect(
            lambda _index: self.modeChanged.emit(self.mode.currentData())
        )

        self.readout = QLabel("", self)
        clear = QPushButton(tr("Bemaßungen löschen"), self)
        clear.clicked.connect(self.clearRequested)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.addWidget(self.mode)
        layout.addWidget(self.readout, stretch=1)
        layout.addWidget(clear)

    def show_measurement(self, kind: str, value: float, count: int) -> None:
        name = {
            "distance": tr("Abstand"),
            "thickness": tr("Wandstärke"),
            "angle": tr("Winkel"),
        }.get(kind, kind)
        self.readout.setText(f"{name}: {format_length(value)}   ({count})")


class SectionBar(QWidget):
    """Axis, position and thickness of the section."""

    sectionChanged = Signal(object, object)
    """Carries the plane (or None) and the slice thickness (or None)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.axis = QComboBox(self)
        self.axis.addItem(tr("Kein Schnitt"), userData=None)
        for axis, label in (("x", tr("Schnitt X")), ("y", tr("Schnitt Y")), ("z", tr("Schnitt Z"))):
            self.axis.addItem(label, userData=axis)
        self.axis.currentIndexChanged.connect(self._emit)

        self.position = QSlider(Qt.Orientation.Horizontal, self)
        self.position.setMinimum(-1000)
        self.position.setMaximum(1000)
        self.position.setValue(0)
        self.position.valueChanged.connect(self._emit)

        self.readout = QLabel(format_length(0.0), self)
        self.readout.setMinimumWidth(90)

        self.as_slice = QCheckBox(tr("Scheibe"), self)
        self.as_slice.toggled.connect(self._emit)

        self.thickness = QDoubleSpinBox(self)
        self.thickness.setDecimals(2)
        self.thickness.setRange(0.1, 500.0)
        self.thickness.setValue(10.0)
        # A unit symbol is not a translation — it comes from the unit table (§11.1).
        self.thickness.setSuffix(f" {DISPLAY_UNITS[0]}")
        self.thickness.valueChanged.connect(self._emit)

        self.warning = QLabel("", self)
        self.warning.setWordWrap(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 2, 6, 2)
        layout.addWidget(self.axis)
        layout.addWidget(self.position, stretch=1)
        layout.addWidget(self.readout)
        layout.addWidget(self.as_slice)
        layout.addWidget(self.thickness)
        layout.addWidget(self.warning)
        self._update_enabled()

    # --- state ------------------------------------------------------------------

    def set_range(self, low: float, high: float) -> None:
        """Follow the size of the scene, with a little air on both sides."""
        margin = max(1.0, (high - low) * 0.05)
        self.position.setMinimum(int((low - margin) * STEPS_PER_MM))
        self.position.setMaximum(int((high + margin) * STEPS_PER_MM))

    def plane(self) -> SectionPlane | None:
        axis = self.axis.currentData()
        if axis is None:
            return None
        return SectionPlane(
            normal=AXIS_NORMALS[axis], position=self.position.value() / STEPS_PER_MM
        )

    def thickness_value(self) -> float | None:
        return float(self.thickness.value()) if self.as_slice.isChecked() else None

    def show_capping_state(self, uncapped: bool) -> None:
        self.warning.setText(tr("Offenes Modell — Schnittfläche bleibt offen.") if uncapped else "")

    def _update_enabled(self) -> None:
        active = self.axis.currentData() is not None
        self.position.setEnabled(active)
        self.readout.setEnabled(active)
        self.as_slice.setEnabled(active)
        self.thickness.setEnabled(active and self.as_slice.isChecked())

    def _emit(self) -> None:
        self._update_enabled()
        self.readout.setText(format_length(self.position.value() / STEPS_PER_MM))
        self.sectionChanged.emit(self.plane(), self.thickness_value())
