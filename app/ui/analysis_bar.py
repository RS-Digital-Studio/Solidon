"""Bedienelemente für die Analysekarten und die Schichtvorschau (Bauplan
§18.4, §18.10).

Zwei Leisten, ein Gedanke: den Körper durch einen Filter ansehen, der eine
Frage beantwortet. Welche Karte gerade zeigt, ist immer sichtbar, und was ihre
Farben bedeuten auch — §18.4 verlangt Legende und Zahlenbereich an jeder
Karte, und §19.1 verbietet Farbe als einzigen Träger, also schreibt die Legende
die Zahlen neben die Farbfelder.

Die Schichtvorschau heißt „Schichtanalyse", nie „Vorschau": sie zeigt
Geometrie, keine Werkzeugwege, und sie Vorschau zu nennen versprüche etwas, das
der externe Slicer liefert (§18.10, §22.5).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QSlider,
    QWidget,
)

from app.core.perceive.maps import AnalysisMap, MapKind
from app.core.types import SliceResult
from app.i18n import tr
from app.ui.labels import length
from app.ui.palette import VIRIDIS, map_colour
from app.ui.panels import origin_label
from app.ui.style import NORMAL, TIGHT
from app.ui.tool_strip import BarComboBox

#: Reihenfolge der Karten im Wähler, passend zur Tabelle in §18.4.
MAP_ORDER: tuple[MapKind, ...] = (
    "wall",
    "overhang",
    "defects",
    "curvature",
    "features",
    "fits",
    "support",
)

#: How many swatches the continuous legend shows.
LEGEND_STEPS = 5


class MapLegend(QWidget):
    """Farbfelder mit ihren Zahlen — die Legende, die §18.4 an jeder Karte
    verlangt.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(NORMAL)
        self.note = QLabel("", self)
        self.note.setWordWrap(True)
        self.entries: list[tuple[str, str]] = []
        """Label and colour of every swatch, kept for the test and the tooltip."""

    def show_map(self, analysis: AnalysisMap | None) -> None:
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None and widget is not self.note:
                widget.deleteLater()
        self.entries = []
        if analysis is None:
            self.note.setText("")
            return

        for label, colour in _legend_entries(analysis):
            self.entries.append((label, colour))
            swatch = QLabel(label, self)
            swatch.setStyleSheet(
                f"background: {colour}; color: {_readable_on(colour)}; padding: 1px 5px;"
            )
            self._layout.addWidget(swatch)

        # §22.5: woher eine Zahl kommt, gehört neben die Zahl.
        parts = [f"{tr('Herkunft')}: {origin_label(analysis.source)}"]
        if analysis.resolution is not None:
            parts.append(f"{tr('Raster')} {length(analysis.resolution)}")
        if analysis.note is not None:
            parts.append(str(analysis.note))
        if analysis.unknown_count:
            parts.append(f"{analysis.unknown_count} × {tr('nicht bestimmbar')}")
        self.note.setText(" · ".join(parts))
        self._layout.addWidget(self.note, stretch=1)


def _legend_entries(analysis: AnalysisMap) -> list[tuple[str, str]]:
    """Beschriftungen und Farben: benannte Stufen, wo es welche gibt, sonst
    eine Rampe.
    """
    if analysis.categories:
        count = len(analysis.categories)
        return [
            (name, map_colour(index / max(count - 1, 1)))
            for index, name in enumerate(analysis.categories)
        ]

    low, high = analysis.low, analysis.high
    if high <= low:
        high = low + 1.0
    entries: list[tuple[str, str]] = []
    for step in range(LEGEND_STEPS):
        fraction = step / (LEGEND_STEPS - 1)
        value = low + (high - low) * fraction
        text = length(value) if analysis.unit == "mm" else f"{value:.0f} {analysis.unit}"
        entries.append((text, map_colour(fraction, VIRIDIS)))
    return entries


def _readable_on(colour: str) -> str:
    """Schwarze oder weiße Schrift, je nachdem, was auf dem Farbfeld lesbar
    bleibt (§19.3).
    """
    from app.ui.theme import relative_luminance

    return "#101418" if relative_luminance(colour) > 0.35 else "#f2f4f7"


class AnalysisBar(QWidget):
    """Welche Karte zeigt, plus ihre Legende (§18.4)."""

    mapChanged = Signal(object)
    """The chosen ``MapKind``, or None for no map."""
    overlayToggled = Signal(bool)
    """Whether the feature overlay is showing (§18.5)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.selector = BarComboBox(self)
        self.selector.addItem(tr("Keine Karte"), userData=None)
        for kind, label in (
            ("wall", tr("Wandstärke")),
            ("overhang", tr("Überhang")),
            ("defects", tr("Netzfehler")),
            ("curvature", tr("Krümmung")),
            ("features", tr("Feature-Zuordnung")),
            ("fits", tr("Passungen")),
            ("support", tr("Stützbedarf")),
        ):
            self.selector.addItem(label, userData=kind)
        self.selector.currentIndexChanged.connect(
            lambda _index: self.mapChanged.emit(self.selector.currentData())
        )

        self.overlay = QCheckBox(tr("Merkmale zeigen"), self)
        self.overlay.toggled.connect(self.overlayToggled)

        self.legend = MapLegend(self)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addWidget(self.selector)
        layout.addWidget(self.overlay)
        layout.addWidget(self.legend, stretch=1)

    def chosen(self) -> MapKind | None:
        value: MapKind | None = self.selector.currentData()
        return value

    def show_map(self, kind: MapKind | None) -> None:
        """Schaltet den Wähler um, ohne zu senden — benutzt, wenn eine Warnung
        eine Karte wählt.
        """
        index = self.selector.findData(kind)
        if index >= 0 and index != self.selector.currentIndex():
            blocked = self.selector.blockSignals(True)
            self.selector.setCurrentIndex(index)
            self.selector.blockSignals(blocked)

    def show_legend(self, analysis: AnalysisMap | None) -> None:
        self.legend.show_map(analysis)

    def show_problem(self, message: str) -> None:
        """Eine Karte, die sich nicht bauen ließ, sagt das, statt nichts zu
        zeigen.
        """
        self.legend.show_map(None)
        self.legend.note.setText(message)


class LayerBar(QWidget):
    """Durch die Höhe des Körpers fahren (§18.10).

    Mit Absicht danach benannt, was sie ist: eine Analyse von Schichten, keine
    Vorschau dessen, was der Drucker tun wird.
    """

    layerChanged = Signal(int)
    """Index of the chosen layer, or -1 when the preview is off."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.active = BarComboBox(self)
        self.active.addItem(tr("Keine Schichtanalyse"), userData=False)
        self.active.addItem(tr("Schichtanalyse"), userData=True)
        self.active.currentIndexChanged.connect(lambda _index: self._emit())

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.valueChanged.connect(lambda _value: self._emit())

        self.readout = QLabel("", self)
        self.readout.setMinimumWidth(220)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addWidget(self.active)
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.readout)
        self._result: SliceResult | None = None
        self._update_enabled()

    def show_result(self, result: SliceResult | None) -> None:
        self._result = result
        count = len(result.layers) if result else 0
        self.slider.setMaximum(max(count - 1, 0))
        self.slider.setValue(0)
        self._show_readout()

    def enabled(self) -> bool:
        return bool(self.active.currentData())

    def index(self) -> int:
        return self.slider.value() if self.enabled() else -1

    def _update_enabled(self) -> None:
        self.slider.setEnabled(self.enabled())

    def _emit(self) -> None:
        self._update_enabled()
        self._show_readout()
        self.layerChanged.emit(self.index())

    def _show_readout(self) -> None:
        result = self._result
        if result is None or not result.layers or not self.enabled():
            self.readout.setText("")
            return
        layer = result.layers[min(self.slider.value(), len(result.layers) - 1)]
        parts = [
            f"{tr('Schicht')} {self.slider.value() + 1}/{len(result.layers)}",
            f"z {length(layer.z)}",
            f"{layer.area:.0f} mm²",
        ]
        if layer.islands:
            parts.append(f"{len(layer.islands)} × {tr('Insel')}")
        if layer.overhang_area > 0.0:
            parts.append(f"{tr('Überhang')} {layer.overhang_area:.0f} mm²")
        self.readout.setText(" · ".join(parts))
