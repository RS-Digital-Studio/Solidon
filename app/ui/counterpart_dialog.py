"""Gegenstücke setzen: ein Paar, ein Satz Maße, zwei Stellen (RM-147 E1).

Der Dialog zu :mod:`app.core.counterpart`. Er fragt genau drei Dinge, und das
ist die ganze Bedienung: **welches Paar**, **wie groß**, und wo — wobei das Wo
schon feststeht, wenn er aufgeht: Es sind die beiden Stellen, die im Objektbaum
markiert sind.

**Die Maße kommen aus dem Bausteinschema** und nicht aus einer zweiten Liste
hier: Titel, Einheit, Grenzen und Vorgabe stehen im Register (§10), und eine
Kopie davon liefe am Tag der nächsten Änderung daneben. Was der Dialog dazutut,
ist die Auswahl, welche davon **gemeinsam** sind — und das steht im Paar.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.counterpart import PAIRS, Pair
from app.i18n import tr
from app.ui.labels import LengthSpin, NumberSpin, choice_label
from app.ui.style import TIGHT, make_primary, set_level


class CounterpartDialog(QDialog):
    """Welches Gegenstück, und mit welchen Maßen."""

    #: Paar oder Maß haben sich geändert — das Fenster rechnet die Vorschau neu
    #: (§18.7). Der Dialog rechnet nichts selbst: Was entstünde, weiß der Kern
    #: (``counterpart.drafts_for``), und gerechnet wird es im Arbeiter.
    valuesChanged = Signal()

    def __init__(
        self,
        first_place: str,
        second_place: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Gegenstücke setzen"))
        self.setMinimumWidth(420)

        self.pairs = QComboBox(self)
        for entry in PAIRS:
            self.pairs.addItem(str(entry.title), entry.key)
        self.pairs.setAccessibleName(tr("Paar"))
        self.pairs.currentIndexChanged.connect(self._rebuild)

        # **Was wohin kommt, steht da, bevor geklickt wird.** „Erstes" und
        # „zweites Teil" sind ohne die Namen der Stellen eine Frage an das
        # Gedächtnis — und die Reihenfolge entscheidet, welche Hälfte wo landet.
        self.places = QLabel("", self)
        self.places.setWordWrap(True)
        self.places.setText(
            tr("Erstes Teil: {first}\nZweites Teil: {second}").format(
                first=first_place, second=second_place
            )
        )

        self.note = QLabel("", self)
        self.note.setWordWrap(True)
        set_level(self.note, "caption")

        self.form = QFormLayout()
        self._fields: dict[str, NumberSpin | QComboBox] = {}

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        accept = buttons.button(QDialogButtonBox.StandardButton.Ok)
        accept.setText(tr("Gegenstücke setzen"))
        make_primary(accept)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setSpacing(TIGHT)
        layout.addWidget(self.places)
        head = QFormLayout()
        head.addRow(tr("Paar:"), self.pairs)
        layout.addLayout(head)
        layout.addWidget(self.note)
        layout.addLayout(self.form)
        layout.addWidget(buttons)

        self._rebuild()

    # --- Aufbau ---------------------------------------------------------------

    def pair(self) -> Pair:
        """Das gewählte Paar."""
        from app.core.counterpart import pair_named

        return pair_named(str(self.pairs.currentData()))

    def _rebuild(self) -> None:
        """Die gemeinsamen Maße des gewählten Paares, aus dem Bausteinschema.

        Ein Paarwechsel tauscht die Felder vollständig: Der Passstift hat
        Durchmesser und Länge, Schraube und Mutter haben eine Größe. Was
        stehenbliebe, verspräche eine Wirkung, die die andere Hälfte nicht
        kennt (§2.4).
        """
        from app.core.knowledge.parts.registry import PARTS

        while self.form.rowCount():
            self.form.removeRow(0)
        self._fields.clear()

        pair = self.pair()
        self.note.setText(str(pair.doc))
        spec = PARTS.get(pair.part_a)
        declared = {entry.name: entry for entry in spec.params.spec()}
        for name in pair.shared:
            entry = declared.get(name)
            if entry is None:
                continue
            field = self._field_for(entry)
            self._fields[name] = field
            self.form.addRow(f"{entry.title}:", field)
            # Jedes Feld meldet sich am selben Signal — der Empfänger entprellt
            # und liest die Werte über :meth:`shared`. ``valueChanged`` trägt
            # hier nur „etwas hat sich bewegt"; die Zahl in Millimetern holt
            # ``value_mm`` (siehe `oberflaeche.md`, Anzeigeeinheit).
            if isinstance(field, QComboBox):
                field.currentIndexChanged.connect(self.valuesChanged)
            else:
                field.valueChanged.connect(self.valuesChanged)
        self.valuesChanged.emit()

    def _field_for(self, entry: Any) -> NumberSpin | QComboBox:
        """Ein Feld nach der Art des Parameters — dieselben Grenzen wie im Register."""
        if entry.choices:
            box = QComboBox(self)
            for value in entry.choices:
                box.addItem(choice_label(value), value)
            box.setCurrentIndex(max(0, box.findData(entry.default)))
            box.setAccessibleName(str(entry.title))
            box.setToolTip(str(entry.doc))
            return box
        spin = LengthSpin(self) if entry.unit == "mm" else NumberSpin(self)
        spin.setRange(
            float(entry.minimum if entry.minimum is not None else -1_000_000.0),
            float(entry.maximum if entry.maximum is not None else 1_000_000.0),
        )
        spin.setDecimals(2)
        spin.setValue(float(entry.default))
        spin.setAccessibleName(str(entry.title))
        spin.setToolTip(str(entry.doc))
        return spin

    # --- Ergebnis -------------------------------------------------------------

    def shared(self) -> dict[str, Any]:
        """Die eingestellten gemeinsamen Maße, fertig für den Ablauf.

        Eine Länge kommt in **Millimetern** heraus, gleich was die Anzeige
        zeigt: ``LengthSpin.value_mm`` ist der Weg, den der Kern erwartet
        (§11.1, §19.3).
        """
        values: dict[str, Any] = {}
        for name, field in self._fields.items():
            if isinstance(field, QComboBox):
                values[name] = str(field.currentData())
            elif isinstance(field, LengthSpin):
                values[name] = field.value_mm()
            else:
                values[name] = float(field.value())
        return values
