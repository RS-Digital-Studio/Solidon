"""Die Leiste, die einen gezogenen Langlochzug bestätigt (§18.11, §21.1).

Ein Zug am Langlochgriff (:mod:`app.ui.slot_handle`) endete bis zum
10.09.2026 unmittelbar in einem Schritt des Verlaufs. Das ist bei einer
Bewegung richtig — dort ist die Stelle, an der man loslässt, die Aussage —,
bei einer **Form** aber nicht: Länge und Richtung sind zwei Zahlen, und wer
sie auf den Millimeter meint, trifft sie mit der Maus nicht (Robert,
10.09.2026: „beim ziehen die maße, nach dem ziehen nochmal die eingabe bei
den maßen und dann bestätigen").

Diese Leiste ist die dritte Stufe: Nach dem Loslassen bleibt der Umriss im
Bild stehen, hier stehen seine zwei Maße als Felder, und erst *Übernehmen*
macht daraus eine Operation. Dieselbe Bauart und derselbe Ort wie die Leiste
der Flächenplatzierung — unten mittig über der Werkzeugzeile, denn dorthin
sieht beim Zeichnen ohnehin jeder.

**Sie rechnet nichts.** Was sie meldet, sind zwei Zahlen; die Vorschau zeichnet
der Griff, und das Ergebnis entsteht in ``slot_hole`` (Regel 2).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QPushButton, QWidget

from app.core.units import DEGREE_UNIT
from app.i18n import tr
from app.ui.labels import LengthSpin, NumberSpin
from app.ui.style import NORMAL, ROOMY, TIGHT, make_primary
from app.ui.theme import THEMES

#: Wie kurz und wie lang ein Langloch über diese Felder werden darf.
#:
#: Die Untergrenze ist eine Zahl, keine Bedingung: Ob die Länge **wirklich**
#: reicht, hängt am Durchmesser des Lochs, und das weiß der Kern
#: (``prepare.SLOT_TOO_SHORT``). Hier steht nur, was ein Zahlenfeld überhaupt
#: annehmen darf; die Leiste setzt ihre eigene Untergrenze beim Öffnen auf den
#: gemessenen Durchmesser.
LENGTH_RANGE = (0.2, 5000.0)

#: Der Bereich des Richtungsfeldes — derselbe, den der Parameter führt.
ANGLE_RANGE = (-180.0, 180.0)

#: Wie viel Platz über der unteren Kante der Werkzeugzeile gehört.
#:
#: Die Leiste der Flächenplatzierung rechnet ihn aus den belegten Zonen der
#: Überlagerung; hier genügt ein Maß, weil die Werkzeugzeile die einzige Zone
#: unter der Ansicht ist. Wächst dort etwas, wächst diese Zahl mit.
TOOLS_ROOM = 56

__all__ = ["ANGLE_RANGE", "LENGTH_RANGE", "TOOLS_ROOM", "SlotBar"]


class SlotBar(QFrame):
    """Länge und Richtung eines gezogenen Langlochs, zum Nachbessern.

    ``valuesChanged`` meldet jede Änderung — dafür ist die Vorschau da;
    ``accepted`` das Übernehmen, ``cancelled`` den Abbruch. Wer eines der
    beiden bekommt, räumt die Leiste ab: Sie gehört dem Zug und nicht dem
    Dokument.
    """

    valuesChanged = Signal(float, float)
    accepted = Signal(float, float)
    cancelled = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("slotBar")

        layout = QGridLayout(self)
        layout.setContentsMargins(ROOMY, TIGHT, ROOMY, TIGHT)
        layout.setSpacing(NORMAL)

        self.title = QLabel(tr("Langloch"), self)
        layout.addWidget(self.title, 0, 0)

        self.length = LengthSpin(self)
        self.length.setObjectName("slotBarLength")
        self.length.set_range_mm(*LENGTH_RANGE)
        self.length.setAccessibleName(tr("Länge des Langlochs"))
        length_label = QLabel(tr("Länge"), self)
        length_label.setBuddy(self.length)
        layout.addWidget(length_label, 0, 1)
        layout.addWidget(self.length, 0, 2)

        self.angle = NumberSpin(self)
        self.angle.setObjectName("slotBarAngle")
        self.angle.setRange(*ANGLE_RANGE)
        self.angle.setDecimals(1)
        self.angle.setSuffix(f" {DEGREE_UNIT}")
        self.angle.setAccessibleName(tr("Richtung des Langlochs"))
        angle_label = QLabel(tr("Richtung"), self)
        angle_label.setBuddy(self.angle)
        layout.addWidget(angle_label, 0, 3)
        layout.addWidget(self.angle, 0, 4)

        self.cancel = QPushButton(tr("Abbrechen"), self)
        self.cancel.clicked.connect(self._on_cancel)
        layout.addWidget(self.cancel, 0, 5)

        self.apply = QPushButton(tr("Übernehmen"), self)
        make_primary(self.apply)
        self.apply.clicked.connect(self._on_apply)
        layout.addWidget(self.apply, 0, 6)
        self._items: tuple[QWidget, ...] = (
            self.title,
            length_label,
            self.length,
            angle_label,
            self.angle,
            self.cancel,
            self.apply,
        )

        self.active = False
        """Ob die Leiste gerade einen Zug hält.

        **Ein eigener Zustand und nicht ``isVisible()``**: Qt beantwortet die
        Sichtbarkeit falsch, solange das Fenster nie gezeigt wurde — offscreen
        also immer, und damit in jedem Test. Wer daran eine Bedingung hängt,
        prüft die Testumgebung statt der Sache (``.claude/rules/tests.md``)."""
        self._quiet = False
        """Ob die Leiste gerade selbst schreibt — dann meldet sie nichts.

        Ohne diese Wache meldete das Setzen der Werte beim Öffnen sofort eine
        Änderung, und die Vorschau rechnete gegen sich selbst."""
        self.length.valueChangedMm.connect(self._report)
        self.angle.valueChanged.connect(self._report)
        self.set_theme("dark")
        self.hide()

    # --- Zustand ---------------------------------------------------------------------

    def begin(self, length_mm: float, angle: float, *, shortest_mm: float) -> None:
        """Zeigt die Leiste mit den Werten, die der Zug hinterlassen hat.

        ``shortest_mm`` ist die kürzeste Länge, die dieses Loch tragen kann; sie
        kommt aus :func:`app.core.geom.prepare.shortest_slot` und ist gemessen —
        darunter erkennt niemand mehr ein Langloch, auch die Merkmalserkennung
        nicht. Das Feld nimmt weniger nicht an; eine Zahl, die in einer Absage
        endet, ist keine Eingabe (Regel 17).
        """
        self._quiet = True
        try:
            self.length.set_range_mm(max(shortest_mm, LENGTH_RANGE[0]), LENGTH_RANGE[1])
            self.length.set_value_mm(float(length_mm))
            self.angle.setValue(float(angle))
        finally:
            self._quiet = False
        self.active = True
        self.show()
        self.adjustSize()
        self.place()
        # Der Fokus steht auf der Länge: Sie ist die Zahl, die man nachbessert,
        # und wer sofort tippt, überschreibt sie statt sie zu suchen.
        self.length.setFocus(Qt.FocusReason.OtherFocusReason)
        self.length.selectAll()

    def values(self) -> tuple[float, float]:
        """Länge in Millimetern und Richtung in Grad — so, wie sie dastehen."""
        return (float(self.length.value_mm()), float(self.angle.value()))

    def dismiss(self) -> None:
        """Weg damit — ohne zu melden. Für den Aufrufer, der schon weiß, dass
        Schluss ist (eine neue Auswahl, eine neue Szene, ein Undo)."""
        self.active = False
        if self.isVisible():
            self.hide()

    def place(self) -> None:
        """Unten mittig über der Werkzeugzeile — dieselbe Stelle wie die Leiste
        der Flächenplatzierung.

        Zwei Leisten, die dasselbe tun, gehören an denselben Ort; wer eine davon
        kennt, sucht die andere nicht.
        """
        parent = self.parentWidget()
        if parent is None:
            return
        area = parent.rect().adjusted(ROOMY, ROOMY, -ROOMY, -ROOMY)
        layout = self.layout()
        assert isinstance(layout, QGridLayout)
        wide = sum(widget.sizeHint().width() for widget in self._items) + 6 * NORMAL + 2 * ROOMY
        for widget in self._items:
            layout.removeWidget(widget)
        if wide <= area.width():
            for column, widget in enumerate(self._items):
                layout.addWidget(widget, 0, column)
        else:
            layout.addWidget(self.title, 0, 0, 1, 2)
            for index, widget in enumerate(self._items[1:]):
                layout.addWidget(widget, 1 + index // 2, index % 2)
        self.setMaximumWidth(max(0, area.width()))
        self.adjustSize()
        self.move(
            area.left() + max(0, (area.width() - self.width()) // 2),
            max(area.top(), area.bottom() - self.height() - TOOLS_ROOM),
        )
        self.raise_()

    def set_theme(self, theme: str) -> None:
        """Dieselbe Zeichnung wie die Zahlenleiste des Zugs — beide sagen
        etwas über einen Zwischenstand, nicht über das Ergebnis."""
        colours = THEMES["light" if theme == "light" else "dark"]
        self.setStyleSheet(
            f"#slotBar {{ background: {colours['window']};"
            f" border: 1px dashed {colours['disabled']}; border-radius: 4px; }}"
            f"#slotBar QLabel {{ color: {colours['text']}; background: transparent; }}"
        )

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt-Schnittstelle
        """Eingabetaste übernimmt, Escape verwirft — hier und nicht anderswo.

        **Die Leiste beantwortet ihre Tasten selbst.** Der Ereignisfilter der
        Ansicht sitzt auf der Grafikfläche und auf dem Feld der Zahlenleiste;
        die Leiste hier steht daneben, und ihr Fokus liegt beim Öffnen im
        Längenfeld. Gemessen am gezeigten Fenster (10.09.2026): Return und
        Escape kamen dort nirgends an — Escape lief auf den Fenster-Kurzbefehl
        und ging eine Auswahlstufe zurück, was die Leiste stehen ließ.

        Drei Stellen sagen diese Zusage zu (Docstring, Karte, Regeldatei); an
        einem eigenen Widget hält sie nur, wenn das Widget sie selbst einlöst.
        """
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._on_apply()
            return
        if key == Qt.Key.Key_Escape:
            self._on_cancel()
            return
        super().keyPressEvent(event)

    # --- Meldungen -------------------------------------------------------------------

    def _report(self, *_ignored: object) -> None:
        if self._quiet:
            return
        length, angle = self.values()
        self.valuesChanged.emit(length, angle)

    def _on_apply(self, _checked: bool = False) -> None:
        length, angle = self.values()
        self.active = False
        self.hide()
        self.accepted.emit(length, angle)

    def _on_cancel(self, _checked: bool = False) -> None:
        self.active = False
        self.hide()
        self.cancelled.emit()
