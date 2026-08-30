"""Bedienelemente für die Schnittebene (Bauplan §18.2).

Die Ebene wird mit einem Schieber bewegt: durch einen Körper zu sehen ist eine
suchende Bewegung. **Und sie lässt sich eintippen** — „schneide bei 12,5" ist
keine Suche, sondern eine Zahl. Der Regler bleibt dabei die Wahrheit über die
Position; das Feld ist ein zweiter Weg zu derselben Zahl, kein zweiter Zustand.

Der Absatz stand hier zwei Phasen lang andersherum („statt eingetippt") und
klang schlüssig. Er war es auch — für die Hälfte der Fälle, die er beschrieb.

Die Scheibendicke sitzt daneben, und wenn ein Körper zu offen war, um die
Schnittfläche zu schließen, sagt diese Leiste das, statt vorzugeben, das Bild
sei vollständig.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QWidget,
)

from app.core.geom.section import AXIS_NORMALS, SectionPlane
from app.core.units import round_display
from app.i18n import tr
from app.ui.labels import LengthSpin, length, localised
from app.ui.leash import weak_slot
from app.ui.style import NORMAL, TIGHT
from app.ui.tool_strip import BarComboBox

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

        self.mode = BarComboBox(self)
        self.mode.setAccessibleName(tr("Messart"))
        self.mode.addItem(tr("Nicht messen"), userData="off")
        self.mode.addItem(tr("Abstand messen"), userData="distance")
        self.mode.addItem(tr("Wandstärke messen"), userData="thickness")
        self.mode.addItem(tr("Winkel messen"), userData="angle")
        self.mode.currentIndexChanged.connect(
            weak_slot(self, lambda bar: bar.modeChanged.emit(bar.mode.currentData()))
        )

        self.readout = QLabel("", self)
        clear = QPushButton(tr("Bemaßungen löschen"), self)
        clear.clicked.connect(self.clearRequested)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addWidget(self.mode)
        layout.addWidget(self.readout, stretch=1)
        layout.addWidget(clear)

    def show_measurement(self, kind: str, value: float, count: int) -> None:
        name = {
            "distance": tr("Abstand"),
            "thickness": tr("Wandstärke"),
            "angle": tr("Winkel"),
        }.get(kind, kind)
        shown = localised(f"{round_display(value):g}°") if kind == "angle" else length(value)
        self.readout.setText(f"{name}: {shown}   ({count})")

    def show_status(self, text: str) -> None:
        """Sagt, welcher Klick als Nächstes fehlt oder warum keiner zählte."""
        self.readout.setText(text)


class SectionBar(QWidget):
    """Achse, Position und Dicke des Schnitts."""

    sectionChanged = Signal(object, object)
    """Trägt die Ebene (oder None) und die Scheibendicke (oder None)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._pending = QTimer(self)
        self._pending.setSingleShot(True)
        self._pending.timeout.connect(self._settled)

        self.axis = BarComboBox(self)
        self.axis.setAccessibleName(tr("Schnittachse"))
        self.axis.addItem(tr("Kein Schnitt"), userData=None)
        for axis, label in (("x", tr("Schnitt X")), ("y", tr("Schnitt Y")), ("z", tr("Schnitt Z"))):
            self.axis.addItem(label, userData=axis)
        self.axis.currentIndexChanged.connect(self._axis_changed)

        self.position = QSlider(Qt.Orientation.Horizontal, self)
        self.position.setAccessibleName(tr("Schnittposition"))
        self.position.setMinimum(-1000)
        self.position.setMaximum(1000)
        self.position.setValue(0)
        self.position.valueChanged.connect(self._emit)

        # Eingabefeld, nicht Beschriftung: durch einen Körper zu sehen ist eine
        # suchende Bewegung, und dafür ist der Regler da — aber „schneide bei
        # 12,5" ist keine Suche, sondern eine Zahl, und die tippt man. Beides,
        # nicht eines von beiden (Konzept P15 §4, E2).
        # Eine Länge, also in der Anzeigeeinheit (§19.3). Der **Regler** bleibt
        # die Wahrheit über die Position und rechnet weiter in Zehntelmillimetern:
        # Er hält den Bereich der Szene, und die kommt aus dem Kern.
        self.readout = LengthSpin(self)
        self.readout.set_step_mm(1.0)
        self.readout.setMinimumWidth(90)
        self.readout.setKeyboardTracking(False)
        self.readout.valueChanged.connect(self._typed)
        self._syncing = False
        """Schutz gegen das Echo: Regler setzt Feld setzt Regler."""

        self.as_slice = QCheckBox(tr("Scheibe"), self)
        self.as_slice.toggled.connect(self._emit)

        self.thickness = LengthSpin(self)
        self.thickness.set_range_mm(0.1, 500.0)
        self.thickness.set_value_mm(10.0)
        self.thickness.setMinimumWidth(90)
        # **Wie das Positionsfeld daneben, und aus demselben Grund.** Ohne
        # diese Zeile sendet das Feld bei jedem Tastendruck: Wer „10" zu „30"
        # ändert, schneidet erst mit 3 mm und dann mit 30 — zwei Schnitte für
        # eine Eingabe, und der erste mit einer Dicke, die niemand wollte. Wer
        # die Zehn löscht, steht kurz unter dem Mindestwert und sieht das Feld
        # auf 0,1 springen. Zwei gleichartige Felder nebeneinander, von denen
        # eines die Tastatur abwartet und das andere nicht, ist zudem eine
        # Inkonsistenz, die niemand erklären kann (Roberts Fehlerbericht,
        # 30.08.2026).
        self.thickness.setKeyboardTracking(False)
        self.thickness.valueChanged.connect(self._emit)

        self.warning = QLabel("", self)
        self.warning.setWordWrap(True)

        self._ranges: dict[str, tuple[float, float]] = {}

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addWidget(self.axis)
        layout.addWidget(self.position, stretch=1)
        layout.addWidget(self.readout)
        layout.addWidget(self.as_slice)
        layout.addWidget(self.thickness)
        layout.addWidget(self.warning)
        self._update_enabled()

    def _axis_changed(self) -> None:
        """Andere Achse, anderer Weg — und dann erst rechnen."""
        self._apply_range()
        self._emit()

    # --- state ------------------------------------------------------------------

    def set_ranges(self, ranges: dict[str, tuple[float, float]]) -> None:
        """Je Achse ihr eigener Weg.

        Vorher galt eine Spanne für alle drei. Bei einem flachen Brett lief
        der Z-Regler über dessen Länge statt über seine Dicke, und ein Zug in
        die Mitte landete weit über dem Teil — kein Schnitt zu sehen, obwohl
        der Regler sich bewegt hatte.
        """
        self._ranges = dict(ranges)
        self._apply_range()

    def _apply_range(self) -> None:
        """Setzt den Weg auf die gewählte Achse, mit etwas Luft an den Enden."""
        axis = self.axis.currentData()
        low, high = self._ranges.get(axis, (-100.0, 100.0))
        margin = max(1.0, (high - low) * 0.05)
        was = self.readout.value_mm()
        self.position.setMinimum(int((low - margin) * STEPS_PER_MM))
        self.position.setMaximum(int((high + margin) * STEPS_PER_MM))
        self.readout.set_range_mm(low - margin, high + margin)
        # Die Achse zu wechseln heißt, an einer anderen Stelle zu schneiden —
        # der alte Wert gehörte zur alten Achse. In die Mitte, das ist die
        # Stelle, an der ein Schnitt am ehesten etwas zeigt.
        if not (low - margin <= was <= high + margin):
            self.readout.set_value_mm((low + high) / 2.0)

    def plane(self) -> SectionPlane | None:
        axis = self.axis.currentData()
        if axis is None:
            return None
        return SectionPlane(
            normal=AXIS_NORMALS[axis], position=self.position.value() / STEPS_PER_MM
        )

    def thickness_value(self) -> float | None:
        return self.thickness.value_mm() if self.as_slice.isChecked() else None

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
        if not self._syncing:
            self._syncing = True
            self.readout.set_value_mm(self.position.value() / STEPS_PER_MM)
            self._syncing = False
        self._pending.start(SETTLE_MS)

    def _typed(self, _value: float) -> None:
        """Eine getippte Höhe bewegt den Regler — und damit den Schnitt.

        Der Regler bleibt die Wahrheit über die Position: er hält den Bereich
        der Szene, und die Rundung auf Zehntelmillimeter ist seine. Das Feld
        ist ein zweiter Weg zu derselben Zahl, kein zweiter Zustand.

        Gelesen wird deshalb ``value_mm`` und nicht das Argument des Signals:
        Das trägt die **Anzeige**, und in Zoll wäre der Regler damit auf ein
        Fünfundzwanzigstel der gemeinten Höhe gesprungen.
        """
        if self._syncing:
            return
        self._syncing = True
        self.position.setValue(round(self.readout.value_mm() * STEPS_PER_MM))
        self._syncing = False
        self._pending.start(SETTLE_MS)

    def _settled(self) -> None:
        self.sectionChanged.emit(self.plane(), self.thickness_value())
