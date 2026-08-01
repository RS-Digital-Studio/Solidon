"""Operationsdialoge, erzeugt aus dem Parameterschema (Bauplan §10, §2.4).

Gestufte Tiefe: die zwei bis drei Werte, die Leute wirklich ändern, stehen
vorn; Toleranzen und Auflösungen sitzen hinter „Weitere Einstellungen". Was
wohin gehört, kommt aus ``placement`` im Schema — ein Dialog kann also nicht
von der Operation abdriften, zu der er gehört.

Der Dialog lässt sich auf Werten statt auf den Vorgaben öffnen, und diese eine
Ergänzung bedient zwei Dinge, die verschieden aussehen und dasselbe sind: eine
angeklickte Fläche, die einträgt, wohin die Operation gehört (§18.5), und eine
Operation des Stapels, die zum Korrigieren wieder geöffnet wird (§15.4). Beides
ist „hier sind die Werte, frag danach" — ein zweiter Dialog für den zweiten
Fall wäre ein zweiter Ort, an dem sich ein Parameter vergessen lässt.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import OperationSpec
from app.core.types import ParamSpec
from app.i18n import tr

#: Werte unterhalb dieser Größenordnung werden feiner angezeigt. Eine Toleranz
#: von 0,075 mm wurde bei zwei Nachkommastellen beim Öffnen des Dialogs zu 0,08
#: — eine stille Änderung an einer Zahl, die jemand gemessen hat.
_FINE_BELOW = 1.0


def _decimals_for(entry: ParamSpec) -> int:
    """Wie fein ein Feld sein muss, damit sein Wertebereich hineinpasst (§11.2).

    Zwei Stellen genügen für Längen und Winkel; Toleranzen und Spiele leben
    unter einem Millimeter, und dort ist die zweite Stelle die letzte, die noch
    etwas unterscheidet.
    """
    bounds = [abs(value) for value in (entry.minimum, entry.maximum) if value]
    if bounds and max(bounds) <= _FINE_BELOW:
        return 3
    return 2


class OperationDialog(QDialog):
    """Ein Dialog für eine Operation, gebaut aus ihrem Schema."""

    def __init__(
        self,
        spec: OperationSpec,
        objects: Mapping[str, str] | Sequence[str],
        parent: QWidget | None = None,
        values: Mapping[str, Any] | None = None,
        sources: Mapping[str, str] | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setWindowTitle(str(spec.title))
        self.setMinimumWidth(380)
        self._editors: dict[str, QWidget] = {}
        given = dict(values or {})
        # Der Dialog spricht in Namen, das Dokument in Kennungen. Wer nur eine
        # Liste übergibt, bekommt die Kennungen zu sehen.
        names = dict(objects) if isinstance(objects, Mapping) else {key: key for key in objects}
        # Quellen sind keine Objekte. Sie standen hier trotzdem in derselben
        # Liste — wer „Modell laden" im Verlauf wieder öffnete, bekam eine
        # Auswahl aus Körpern angeboten, wo eine Datei gemeint war.
        self._sources = dict(sources or {})

        front = QFormLayout()
        advanced = QFormLayout()
        for entry in spec.params.spec():
            editor = self._editor_for(entry, names, given.get(entry.name))
            self._editors[entry.name] = editor
            label = f"{entry.title}"
            if entry.unit:
                label = f"{label} [{entry.unit}]"
            # Ein eingetragener Wert gehört vor den Nutzer, auch wenn das Schema ihn
            # nach hinten legt: er ist der, der gerade entschieden wurde.
            target = front if entry.placement == "front" or entry.name in given else advanced
            target.addRow(label, editor)
            if entry.doc:
                editor.setToolTip(str(entry.doc))

        layout = QVBoxLayout(self)
        if spec.doc:
            description = QLabel(str(spec.doc), self)
            description.setWordWrap(True)
            layout.addWidget(description)
        layout.addLayout(front)

        if advanced.rowCount():
            # Eine ankreuzbare Gruppe graut ihre Felder aus, statt sie
            # wegzuklappen — die gestufte Tiefe aus §2.4 war damit gedacht und
            # nicht gebaut: die hinteren Werte standen weiter da, nur grau, und
            # das Häkchen las sich wie ein Schalter, der etwas bewirkt.
            inner = QWidget(self)
            inner.setLayout(advanced)
            inner.setVisible(False)
            self.advanced = QToolButton(self)
            self.advanced.setText(tr("Weitere Einstellungen"))
            self.advanced.setCheckable(True)
            self.advanced.setAutoRaise(True)
            self.advanced.setArrowType(Qt.ArrowType.RightArrow)
            self.advanced.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)

            def unfold(open_now: bool, inner: QWidget = inner) -> None:
                inner.setVisible(open_now)
                self.advanced.setArrowType(
                    Qt.ArrowType.DownArrow if open_now else Qt.ArrowType.RightArrow
                )
                self.adjustSize()

            self.advanced.toggled.connect(unfold)
            layout.addWidget(self.advanced)
            layout.addWidget(inner)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        # Der Knopf benennt die Handlung: „Bohrung setzen" statt „OK". Was
        # gleich passiert, steht damit dort, wo entschieden wird — der
        # Fenstertitel ist beim Klicken nicht mehr im Blick.
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(str(spec.title))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _editor_for(
        self, entry: ParamSpec, objects: Mapping[str, str], given: Any = None
    ) -> QWidget:
        """Ein Editor. ``given`` schlägt die Vorgabe des Schemas, wo es gesetzt
        ist.
        """
        start = entry.default if given is None else given
        if entry.kind == "bool":
            editor = QCheckBox(self)
            editor.setChecked(bool(start))
            return editor
        if entry.kind == "int":
            spin = QSpinBox(self)
            spin.setMinimum(int(entry.minimum) if entry.minimum is not None else -1_000_000)
            spin.setMaximum(int(entry.maximum) if entry.maximum is not None else 1_000_000)
            if start is not None:
                spin.setValue(int(start))
            return spin
        if entry.kind == "float":
            number = QDoubleSpinBox(self)
            number.setDecimals(_decimals_for(entry))
            number.setMinimum(entry.minimum if entry.minimum is not None else -1_000_000.0)
            number.setMaximum(entry.maximum if entry.maximum is not None else 1_000_000.0)
            if start is not None:
                number.setValue(float(start))
            return number
        if entry.kind == "enum" or entry.choices:
            combo = QComboBox(self)
            combo.addItems(list(entry.choices))
            if start is not None and start in entry.choices:
                combo.setCurrentText(str(start))
            return combo
        if entry.kind in ("object", "source"):
            # Der Name steht da, die Kennung reist mit. Ein frei beschreibbares
            # Feld war hier ein Weg, „obj_12" falsch zu tippen — und der Baum
            # nebenan zeigt ohnehin Namen, keine Nummern.
            choices = self._sources if entry.kind == "source" else objects
            combo = QComboBox(self)
            for identifier, name in choices.items():
                combo.addItem(name, identifier)
            if start:
                index = combo.findData(str(start))
                if index < 0:
                    # Ein Wert, den die Liste nicht kennt, wird gezeigt statt
                    # ersetzt: eine Datei aus einem Projekt, dessen Quellen
                    # hier gerade nicht vorliegen, darf nicht stillschweigend
                    # zu einer anderen werden.
                    combo.addItem(str(start), str(start))
                    index = combo.count() - 1
                combo.setCurrentIndex(index)
            return combo
        line = QLineEdit(self)
        if start:
            line.setText(str(start))
        return line

    def values(self) -> dict[str, Any]:
        """Was der Nutzer eingetragen hat, fertig für die Operationsparameter."""
        collected: dict[str, Any] = {}
        for entry in self.spec.params.spec():
            editor = self._editors[entry.name]
            if isinstance(editor, QCheckBox):
                collected[entry.name] = editor.isChecked()
            elif isinstance(editor, QSpinBox):
                collected[entry.name] = editor.value()
            elif isinstance(editor, QDoubleSpinBox):
                collected[entry.name] = float(editor.value())
            elif isinstance(editor, QComboBox):
                # Objekt- und Quellenwähler tragen die Kennung als Daten, die
                # übrigen Aufklappmenüs sind ihr eigener Wert.
                data = editor.currentData()
                collected[entry.name] = editor.currentText() if data is None else str(data)
            elif isinstance(editor, QLineEdit):
                collected[entry.name] = editor.text()
        return collected
