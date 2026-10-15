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

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.counterpart import PAIRS, Pair
from app.i18n import tr
from app.ui.dialogs import align_to_the_front
from app.ui.labels import LengthSpin, NumberSpin, choice_label, wheel_needs_focus
from app.ui.leash import weak_slot
from app.ui.panels import collapsible
from app.ui.style import (
    NORMAL,
    SPACE,
    WIDE,
    ContentFitIntent,
    ContentHeight,
    DialogScrollArea,
    expanded_width,
    make_primary,
    set_level,
)


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
        self._height = ContentHeight()

        self.pairs = QComboBox(self)
        wheel_needs_focus(self.pairs)
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
        self.form.setSpacing(NORMAL)
        self._back = QFormLayout()
        self._back.setSpacing(NORMAL)
        self._more: QWidget | None = None
        self._fields: dict[str, NumberSpin | QComboBox] = {}

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        self._buttons = buttons
        accept = self._accept
        accept.setText(tr("Gegenstücke setzen"))
        make_primary(accept)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        self._body = layout
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.places)
        head = self._head = QFormLayout()
        head.setSpacing(NORMAL)
        head.addRow(tr("Paar"), self.pairs)
        layout.addLayout(head)
        layout.addWidget(self.note)
        layout.addLayout(self.form)
        layout.addStretch(1)
        self._scroll = DialogScrollArea(self)
        self._scroll.setWidget(content)
        self._scroll.contentSizeChanged.connect(weak_slot(self, CounterpartDialog._fit_soon))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        outer.setSpacing(NORMAL)
        outer.addWidget(self._scroll, 1)
        outer.addWidget(buttons)

        self._rebuild()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt-Name
        super().showEvent(event)
        self._fit_soon("initial")

    def _fit_soon(self, intent: ContentFitIntent = "passive") -> None:
        QTimer.singleShot(0, self, weak_slot(self, CounterpartDialog._fit_content, intent))

    def _fit_content(self, intent: ContentFitIntent) -> None:
        """Misst auch die zugeklappte Rückseite; eine Nutzergröße bleibt erhalten."""
        self._height.fit(
            self,
            self._scroll,
            intent=intent,
            natural_width=expanded_width(self._scroll, self._head, self.form, self._back),
        )

    # --- Aufbau ---------------------------------------------------------------

    @property
    def _accept(self) -> QPushButton:
        """Der Hauptknopf, jedes Mal frisch vom Knopfkasten.

        Kein gemerkter Verweis: PySide hängt ein Widget, das eine Abfrage wie
        ``nextInFocusChain`` zurückgibt, an das befragte Widget. Fragte jemand
        das letzte Maßfeld nach seinem Nachfolger, starb der gemerkte Verweis
        auf diesen Knopf mit dem Feld beim nächsten Paarwechsel, und
        ``_rebuild`` brach vor der Tabfolge zum Knopf und vor ``valuesChanged``
        ab — die Vorschau des neuen Paares blieb aus.
        """
        button = self._buttons.button(QDialogButtonBox.StandardButton.Ok)
        assert button is not None
        return button

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
        while self._back.rowCount():
            self._back.removeRow(0)
        self._fields.clear()

        pair = self.pair()
        explanation = str(pair.doc)
        self.note.setText(explanation)
        self.pairs.setToolTip(explanation)
        self.pairs.setAccessibleDescription(explanation)
        pair_caption = self._head.labelForField(self.pairs)
        if isinstance(pair_caption, QLabel):
            pair_caption.setBuddy(self.pairs)
            pair_caption.setToolTip(explanation)
            pair_caption.setAccessibleDescription(explanation)
        spec = PARTS.get(pair.part_a)
        declared = {entry.name: entry for entry in spec.params.spec()}
        front_fields: list[QWidget] = []
        back_fields: list[QWidget] = []
        back_titles: list[str] = []
        for name in pair.shared:
            entry = declared.get(name)
            if entry is None:
                continue
            field = self._field_for(entry)
            wheel_needs_focus(field)
            self._fields[name] = field
            advanced = entry.placement == "advanced"
            form = self._back if advanced else self.form
            (back_fields if advanced else front_fields).append(field)
            if advanced:
                back_titles.append(str(entry.title))
            # Wie jede andere Formularzeile ohne Doppelpunkt (`fenster.md`, RM-342 C-N1).
            form.addRow(str(entry.title), field)
            caption = form.labelForField(field)
            if isinstance(caption, QLabel):
                caption.setBuddy(field)
                caption.setToolTip(str(entry.doc))
            # Jedes Feld meldet sich am selben Signal — der Empfänger entprellt
            # und liest die Werte über :meth:`shared`. ``valueChanged`` trägt
            # hier nur „etwas hat sich bewegt"; die Zahl in Millimetern holt
            # ``value_mm`` (siehe `oberflaeche.md`, Anzeigeeinheit).
            if isinstance(field, QComboBox):
                field.currentIndexChanged.connect(self.valuesChanged)
            else:
                field.valueChanged.connect(self.valuesChanged)
        contents = ", ".join(back_titles)
        if self._more is None and back_fields:
            rest = QWidget(self)
            rest_layout = QVBoxLayout(rest)
            rest_layout.setContentsMargins(0, 0, 0, 0)
            rest_layout.setSpacing(NORMAL)
            rest_layout.addLayout(self._back)
            self._more = collapsible(
                tr("Weitere Einstellungen"), rest, open_now=False, contents=contents
            )
            self._body.insertWidget(self._body.count() - 1, self._more)
            flap = self._more.findChild(QToolButton, "sectionHeading")
            if flap is not None:
                flap.toggled.connect(weak_slot(self, CounterpartDialog._fit_soon, "explicit"))
        focus_fields = front_fields.copy()
        if self._more is not None:
            self._more.setVisible(bool(back_fields))
            flap = self._more.findChild(QToolButton, "sectionHeading")
            if flap is not None:
                flap.setToolTip(contents)
                flap.setAccessibleDescription(contents)
                if back_fields:
                    focus_fields.append(flap)
            summary = self._more.findChild(QLabel, "sectionSummary")
            if summary is not None:
                summary.setText(contents)
        focus_fields.extend(back_fields)
        previous: QWidget = self.pairs
        for focus_field in focus_fields:
            QWidget.setTabOrder(previous, focus_field)
            previous = focus_field
        QWidget.setTabOrder(previous, self._accept)
        # Paar und Maße beginnen an einer Kante (RM-518) — nach jedem
        # Paarwechsel neu, denn die Zeilen sind dann andere.
        align_to_the_front((self._head, self.form), self._back)
        self._fit_soon()
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
            box.setAccessibleDescription(str(entry.doc))
            return box
        spin = LengthSpin(self) if entry.unit == "mm" else NumberSpin(self)
        minimum = float(entry.minimum if entry.minimum is not None else -1_000_000.0)
        maximum = float(entry.maximum if entry.maximum is not None else 1_000_000.0)
        if isinstance(spin, LengthSpin):
            spin.set_range_mm(minimum, maximum)
            spin.set_value_mm(float(entry.default))
        else:
            spin.setRange(minimum, maximum)
            spin.setDecimals(2)
            spin.setValue(float(entry.default))
        spin.setAccessibleName(str(entry.title))
        spin.setToolTip(str(entry.doc))
        spin.setAccessibleDescription(str(entry.doc))
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
