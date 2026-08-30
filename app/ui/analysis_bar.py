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

from collections.abc import Mapping
from typing import Any

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
from app.ui.labels import area, length
from app.ui.leash import weak_slot
from app.ui.palette import LAYER_WIDTHS, ROLES, VIRIDIS, Role, map_colour, readable_on
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

#: Wie viele Farbfelder eine stufenlose Legende zeigt.
LEGEND_STEPS = 5

#: Wie viele benannte Stufen höchstens einzeln dastehen.
#:
#: Die Merkmalskarte eines Gehäuses hat vierundzwanzig: „ohne Merkmal", elf
#: Flächen, fünf Bohrungen, ein Deckelinneres, vier Stifte. Alle nebeneinander
#: sind eine Zeile über die volle Fensterbreite, und keine davon sagt etwas —
#: die Karte beantwortet „welches Dreieck gehört wozu", und dafür genügt die
#: Farbe im Bild plus die Auskunft, wie viele es sind.
LEGEND_MAX_ENTRIES = 8


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
        """Beschriftung und Farbe jedes Feldes — für den Test und den Kurzhinweis."""

    def show_map(
        self, analysis: AnalysisMap | None, names: Mapping[str, str] | None = None
    ) -> None:
        """Die Legende zur Karte. ``names`` übersetzt interne Kennungen.

        Die Merkmalskarte führt ihre Stufen als Provenienz-IDs — so gehören
        sie in die Karte, und so stünden sie ohne diese Zuordnung auch in der
        Legende: ``face_1``, ``face_10``, ``face_11``, ``hole_3``,
        ``lid_cavity``. Die Namen kennt das Fenster, nicht der Kern.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None and widget is not self.note:
                widget.deleteLater()
        self.entries = []
        if analysis is None:
            # **Der Satz braucht sein Layout zurück.** ``takeAt`` hat auch die
            # Notiz herausgenommen (geschützt war nur ihr Löschen); ohne das
            # Wiedereinhängen stand „Die Analysekarte wird berechnet …" auf
            # 100 auf 30 Punkten Geometrie außerhalb jeder Anordnung — genau die
            # zwei Sätze, die etwas erklären sollen (Gesamtreview I-9).
            self._layout.addWidget(self.note, stretch=1)
            self.note.setText("")
            return

        shown = _legend_entries(analysis, names)
        extra = len(shown) - LEGEND_MAX_ENTRIES
        for label, colour in shown[:LEGEND_MAX_ENTRIES]:
            self.entries.append((label, colour))
            swatch = QLabel(label, self)
            swatch.setStyleSheet(
                f"background: {colour}; color: {_readable_on(colour)}; padding: 1px 5px;"
            )
            self._layout.addWidget(swatch)
        if extra > 0:
            # Nicht weglassen, sondern zählen: eine gekürzte Liste, die ihre
            # Kürzung verschweigt, behauptet Vollständigkeit.
            more = QLabel(tr("+ {count} weitere").format(count=extra), self)
            more.setProperty("level", "caption")
            self.entries.append((more.text(), ""))
            self._layout.addWidget(more)

        # §22.5: woher eine Zahl kommt, gehört neben die Zahl.
        parts = [f"{tr('Herkunft')}: {origin_label(analysis.source)}"]
        if analysis.resolution is not None:
            parts.append(f"{tr('Raster')} {length(analysis.resolution)}")
        if analysis.note is not None:
            parts.append(str(analysis.note))
        if analysis.unknown_count:
            # Die Zahl stand unerklärt da. Was sie heißt, weiß nur die Karte,
            # die sie erzeugt hat — also sagt sie es, und zwar in derselben
            # Zeile: ein Tooltip findet nur, wer schon weiß, dass er da ist.
            unknown = f"{analysis.unknown_count} × {tr('nicht bestimmbar')}"
            if analysis.unknown_note:
                unknown = f"{unknown} ({analysis.unknown_note})"
            parts.append(unknown)
        self.note.setText(" · ".join(parts))
        self._layout.addWidget(self.note, stretch=1)


def _legend_entries(
    analysis: AnalysisMap, names: Mapping[str, str] | None = None
) -> list[tuple[str, str]]:
    """Beschriftungen und Farben: benannte Stufen, wo es welche gibt, sonst
    eine Rampe.

    ``names`` übersetzt Provenienz-IDs in das, was auch im Objektbaum steht —
    aus ``hole_3`` wird „Bohrung 3 · ⌀4,2". Fehlt eine Zuordnung, bleibt die
    Kennung stehen: sie ist immer noch besser als nichts.
    """
    if analysis.categories:
        count = len(analysis.categories)
        return [
            (str((names or {}).get(name, name)), map_colour(index / max(count - 1, 1)))
            for index, name in enumerate(analysis.categories)
        ]

    low, high = analysis.low, analysis.high
    if high <= low:
        high = low + 1.0
    entries: list[tuple[str, str]] = []
    for step in range(LEGEND_STEPS):
        fraction = step / (LEGEND_STEPS - 1)
        value = low + (high - low) * fraction
        if analysis.unit == "mm":
            text = length(value)
        elif analysis.unit == "°":
            # Ohne Leerzeichen, wie überall sonst im Programm: die
            # Winkelparameter schreiben „45°", die Karten schrieben „45 grad".
            text = f"{value:.0f}°"
        else:
            text = f"{value:.0f} {analysis.unit}"
        entries.append((text, map_colour(fraction, VIRIDIS)))
    return entries


#: Die Legende der Differenzansicht braucht dieselbe Rechnung — sie steht
#: deshalb bei den Rollen und nicht hier.
_readable_on = readable_on


class AnalysisBar(QWidget):
    """Welche Karte zeigt, plus ihre Legende (§18.4)."""

    mapChanged = Signal(object)
    """Die gewählte ``MapKind``, oder None für keine Karte."""
    overlayToggled = Signal(bool)
    """Ob die Merkmalsauflage gezeigt wird (§18.5)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.selector = BarComboBox(self)
        self.selector.setAccessibleName(tr("Analysekarte"))
        self.selector.addItem(tr("Keine Karte"), userData=None)
        for kind, label in (
            ("wall", tr("Wandstärke")),
            ("overhang", tr("Überhang")),
            ("defects", tr("Netzfehler")),
            ("curvature", tr("Krümmung")),
            ("features", tr("Merkmale")),
            ("fits", tr("Passungen")),
            ("support", tr("Stützbedarf")),
        ):
            self.selector.addItem(label, userData=kind)
        self.selector.currentIndexChanged.connect(
            weak_slot(self, lambda bar: bar.mapChanged.emit(bar.selector.currentData()))
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

    def show_legend(
        self, analysis: AnalysisMap | None, names: Mapping[str, str] | None = None
    ) -> None:
        """Die Legende zur Karte; ``names`` übersetzt interne Kennungen."""
        self.legend.show_map(analysis, names)

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
    """Nummer der gewählten Schicht, oder -1, wenn die Vorschau aus ist."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._on = False
        """Ob die Schichtanalyse läuft.

        Früher stand hier ein Auswahlfeld mit „Keine Schichtanalyse" und
        „Schichtanalyse" — ein Umschalter hinter dem Umschalter, der diese
        Leiste überhaupt erst öffnet. Wer *Schichten* anklickte, bekam einen
        toten Regler und musste erraten, dass er im Feld daneben noch einmal
        einschalten muss. Jetzt schaltet der Werkzeugknopf, und zwar beides.
        """

        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setAccessibleName(tr("Schicht"))
        self.slider.setMinimum(0)
        self.slider.setMaximum(0)
        self.slider.valueChanged.connect(self._emit)

        self.readout = QLabel("", self)
        self.readout.setMinimumWidth(220)

        self._legend = QHBoxLayout()
        self._legend.setContentsMargins(0, 0, 0, 0)
        self._legend.setSpacing(NORMAL)
        """Welcher Ring im Bild was bedeutet — siehe :meth:`_show_legend`."""

        self.note = QLabel("", self)
        self.note.setWordWrap(True)
        self.note.hide()
        """Warum hier nichts zu sehen ist — statt eines toten Reglers.

        Dieselbe Rolle wie :attr:`MapLegend.note` an der Karte daneben: Wer
        *Schichten* anklickt und nichts gewählt hat, bekam einen Regler, der
        sich ziehen ließ und nichts tat; der Grund stand als „Keine Auswahl" in
        der Statuszeile am unteren Fensterrand, also nicht dort, wo der Kunde
        gerade hinsieht.
        """

        layout = QHBoxLayout(self)
        layout.setContentsMargins(NORMAL, TIGHT, NORMAL, TIGHT)
        layout.addWidget(self.slider, stretch=1)
        layout.addWidget(self.readout)
        layout.addLayout(self._legend)
        layout.addWidget(self.note, stretch=1)
        self._result: SliceResult | None = None
        self._update_enabled()

    def set_active(self, active: bool) -> None:
        """Die Schichtanalyse ein- oder ausschalten.

        Gerufen vom Fenster, wenn das Werkzeug auf- oder zugeht — nicht vom
        Nutzer: für ihn ist der Werkzeugknopf der Schalter.
        """
        if active == self._on:
            return
        self._on = active
        self._emit()

    def show_result(self, result: SliceResult | None) -> None:
        self._result = result
        count = len(result.layers) if result else 0
        self.slider.setMaximum(max(count - 1, 0))
        self.slider.setValue(0)
        self._show_readout()

    def show_note(self, note: str) -> None:
        """Einen Grund zeigen statt der Bedienung — oder wieder zurück.

        Entweder das eine oder das andere: Ein Regler neben einem Satz, der
        sagt, dass es nichts zu regeln gibt, ist ein Widerspruch auf einer
        Leiste. Ein leerer Text stellt die Bedienung wieder her, damit ein
        Grund nicht stehen bleibt, wenn er nicht mehr gilt.
        """
        wanted = bool(note)
        self.note.setText(note)
        self.note.setVisible(wanted)
        self.slider.setVisible(not wanted)
        self.readout.setVisible(not wanted)

    def enabled(self) -> bool:
        return self._on

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
            area(layer.area),
        ]
        if layer.islands:
            parts.append(f"{len(layer.islands)} × {tr('Insel')}")
        if layer.overhang_area > 0.0:
            parts.append(f"{tr('Überhang')} {area(layer.overhang_area)}")
        self.readout.setText(" · ".join(parts))
        self._show_legend(layer)

    def _show_legend(self, layer: Any) -> None:
        """Sagt, welcher Ring im Bild was bedeutet.

        Ohne sie liegen drei Ringe übereinander, und was sie unterscheidet, ist
        die Farbe (Regel 18). Die Strichstärken tragen die Aussage inzwischen
        auch ohne Farbe — aber erst hier steht, welche zu welchem Wort gehört.

        Gezeigt wird nur, was in dieser Schicht vorkommt: Eine Legende, die
        „Insel" führt, wo keine liegt, lässt suchen.
        """
        while self._legend.count():
            item = self._legend.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()

        shown: list[tuple[Role, str, bool]] = [
            ("layer", str(tr("Kontur")), True),
            ("island", str(tr("Insel")), bool(layer.islands)),
            ("overhang", str(tr("Überhang")), layer.overhang_area > 0.0),
        ]
        for role, name, present in shown:
            if not present:
                continue
            # Der Strich ist so lang, wie der Ring im Bild dick ist — dieselbe
            # zweite Kodierung, und sie verbindet die Legende mit dem Bild.
            swatch = QLabel(f"{'─' * LAYER_WIDTHS[role]} {name}", self)
            swatch.setStyleSheet(f"color: {ROLES[role]};")
            self._legend.addWidget(swatch)
        self._legend.addStretch(1)
