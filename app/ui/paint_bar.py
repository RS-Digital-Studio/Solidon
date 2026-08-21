"""Die Pinselleiste (Bauplan §20, „Bemalen").

Einschalten, einen Slot und einen Radius wählen, aufs Modell klicken. Jeder
Klick ist eine Operation im Stapel — genau das macht das Malen Strich für
Strich rücknehmbar, und es hält Bild und Datei dieselbe Sache.

Per Vorgabe aus, und sie sagt das: eine Ansicht, die still malt, wenn jemand
das Modell drehen wollte, ist die Art Überraschung, die ein Undo behebt und
Vertrauen nicht übersteht.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QWidget,
)

from app.core.geom.paint import EDGE_ANGLE, MAX_SLOTS
from app.core.types import MaterialSlot
from app.i18n import tr
from app.ui.labels import LengthSpin
from app.ui.style import NORMAL, TIGHT
from app.ui.theme import slot_colour

#: Die Einheit eines Winkels — in jeder Sprache, die dieses Programm
#: mitbringt, dieselbe.
DEGREE = "°"

#: Kantenlänge des Farbfelds neben der Slotnummer.
#:
#: So groß wie eine Zeile Text, damit es neben der Nummer steht und nicht
#: darunter — und groß genug, dass man zwei Farben nebeneinander noch
#: unterscheidet, wenn sie sich ähneln.
SWATCH = 14


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
        self.slot.valueChanged.connect(self._describe_slot)

        # **Eine Nummer ist keine Farbe.** „Slot 1" sagt nicht, was auf dem Teil
        # landet — und der Pinsel legt einen Slot ohne eigene Farbe an, dessen
        # Anzeigefarbe erst die Ansicht aus der Palette nimmt. Wer sie hier
        # nicht sieht, malt und sieht sie danach: das Feld links davon zeigt
        # sie, der Name rechts nennt den Slot, wie ihn das Objekt kennt.
        # Farbe **und** Wort, denn allein die Farbe wäre keine Auskunft.
        self.swatch = QLabel(self)
        self.swatch.setFixedSize(SWATCH, SWATCH)
        self.slot_name = QLabel(self)
        self._slots: list[MaterialSlot] = []

        # Der Pinselradius ist eine Länge (§19.3); was der Kern bekommt, sind
        # Millimeter — der Ring in der Szene zeichnet daraus sein Weltmaß.
        self.radius = LengthSpin(self)
        self.radius.set_range_mm(0.1, 500.0)
        self.radius.set_value_mm(10.0)

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
        layout.addWidget(self.swatch)
        layout.addWidget(self.slot_name)
        layout.addWidget(QLabel(tr("Radius"), self))
        layout.addWidget(self.radius)
        layout.addWidget(QLabel(tr("Kantenwinkel"), self))
        layout.addWidget(self.edge)
        layout.addStretch(1)

        # Von Hand, denn ``valueChanged`` kommt erst bei einer Änderung: ohne
        # diesen Aufruf stünde die Leiste beim Öffnen ohne Farbfeld da.
        self._describe_slot()

    @property
    def painting(self) -> bool:
        return bool(self.active.isChecked())

    def values(self) -> dict[str, float | int]:
        """Woraus ein Strich besteht."""
        return {
            "slot": int(self.slot.value()),
            "radius": self.radius.value_mm(),
            "edge_angle": float(self.edge.value()),
        }

    def set_slots(self, slots: Sequence[MaterialSlot]) -> None:
        """Die Slots des gewählten Körpers — sie bestimmen Name und Farbe.

        Aufgerufen bei jedem Auswahlwechsel und nach jeder Auswertung: Ein
        Strich legt einen Slot an, und die Leiste soll ihn danach kennen.
        """
        self._slots = list(slots)
        self._describe_slot()

    def _describe_slot(self) -> None:
        """Farbfeld und Name auf den gewählten Slot bringen."""
        index = int(self.slot.value())
        known = {entry.index: entry for entry in self._slots}
        entry = known.get(index)
        if index == 0:
            # Slot 0 ist das unbemalte Teil. Ein Farbfeld dafür wäre eine
            # Behauptung über eine Farbe, die vom Thema kommt.
            self.swatch.clear()
            self.slot_name.setText(tr("unbemalt"))
            self.slot_name.setToolTip(tr("Slot 0 nimmt die Farbe zurück, die das Teil selbst hat."))
            return
        colour = _hex_of(entry.colour) if entry is not None and entry.colour else slot_colour(index)
        self.swatch.setPixmap(_swatch(colour or "#000000"))
        if entry is None:
            self.slot_name.setText(tr("neu"))
            self.slot_name.setToolTip(tr("Diesen Slot gibt es am gewählten Körper noch nicht."))
            return
        self.slot_name.setText(entry.name)
        self.slot_name.setToolTip(
            tr("Die Farbe ist die der Ansicht. Gedruckt wird, was im Slot eingelegt ist.")
        )

    def stop(self) -> None:
        """Ausschalten — benutzt, wenn sich die Szene unter dem Pinsel ändert."""
        if self.active.isChecked():
            self.active.setChecked(False)


def _hex_of(colour: tuple[float, float, float]) -> str:
    """Eine Farbe aus dem Dokument als #RRGGBB."""
    return "#" + "".join(f"{max(0, min(255, round(channel * 255))):02x}" for channel in colour)


def _swatch(colour: str) -> QPixmap:
    """Ein Farbfeld mit Rand.

    Der Rand ist nicht Zierde: ein Feld in der Farbe des Hintergrunds wäre
    sonst kein Feld, und Weiß im hellen Thema ist genau dieser Fall.
    """
    pixmap = QPixmap(QSize(SWATCH, SWATCH))
    pixmap.fill(QColor(colour))
    painter = QPainter(pixmap)
    painter.setPen(QColor(0, 0, 0, 90))
    painter.drawRect(0, 0, SWATCH - 1, SWATCH - 1)
    painter.end()
    return pixmap
