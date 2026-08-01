"""Bedienelemente für die Schnittebene (Bauplan §18.2).

Die Ebene wird mit einem Schieber bewegt statt eingetippt: durch einen Körper
zu sehen ist eine suchende Bewegung, keine Zahleneingabe. Die Scheibendicke
sitzt daneben, und wenn ein Körper zu offen war, um die Schnittfläche zu
schließen, sagt diese Leiste das, statt vorzugeben, das Bild sei vollständig.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
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

#: Der Schieber arbeitet in Zehntelmillimetern; EPS_DISPLAY ist feiner als
#: das.
STEPS_PER_MM = 10

#: Wie lange der Schnitt wartet, bis der Schieber zur Ruhe gekommen ist.
#: Kurz genug, dass es sich unmittelbar anfühlt (§2.8: unter 0,2 s wird nichts
#: angezeigt), lang genug, dass ein Zug über den Regler eine Rechnung auslöst
#: statt dreißig.
SETTLE_MS = 120


class MeasureBar(QWidget):
    """Welches Messwerkzeug aktiv ist, und der Weg, Maße zu löschen (§18.3)."""

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
    """Achse, Position und Dicke des Schnitts."""

    sectionChanged = Signal(object, object)
    """Carries the plane (or None) and the slice thickness (or None)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._pending = QTimer(self)
        self._pending.setSingleShot(True)
        self._pending.timeout.connect(self._settled)

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
        # Ein Einheitenzeichen ist keine Übersetzung — es kommt aus der
        # Einheitentabelle (§11.1).
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
        """Folgt der Größe der Szene, mit etwas Luft auf beiden Seiten."""
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
        """Die Zahl folgt sofort, der Schnitt entprellt.

        Ein Schnitt ist eine boolesche Operation je Körper (§18.2), und der
        Schieber sendet bei jedem Pixel. An einem großen Netz hieß das: die
        Ansicht rechnet dreißigmal, was einmal gereicht hätte, und der
        Schieber ruckelt. Die Beschriftung bleibt trotzdem am Zeiger — sie
        kostet nichts, und ohne sie fühlt sich der Regler tot an.
        """
        self._update_enabled()
        self.readout.setText(format_length(self.position.value() / STEPS_PER_MM))
        self._pending.start(SETTLE_MS)

    def _settled(self) -> None:
        self.sectionChanged.emit(self.plane(), self.thickness_value())
