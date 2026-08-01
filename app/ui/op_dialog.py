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

from collections.abc import Mapping
from typing import Any

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.registry import OperationSpec
from app.core.types import ParamSpec
from app.i18n import tr


class OperationDialog(QDialog):
    """Ein Dialog für eine Operation, gebaut aus ihrem Schema."""

    def __init__(
        self,
        spec: OperationSpec,
        objects: list[str],
        parent: QWidget | None = None,
        values: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setWindowTitle(str(spec.title))
        self.setMinimumWidth(380)
        self._editors: dict[str, QWidget] = {}
        given = dict(values or {})

        front = QFormLayout()
        advanced = QFormLayout()
        for entry in spec.params.spec():
            editor = self._editor_for(entry, objects, given.get(entry.name))
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
            box = QGroupBox(tr("Weitere Einstellungen"), self)
            box.setCheckable(True)
            box.setChecked(False)
            box.setLayout(advanced)
            layout.addWidget(box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _editor_for(self, entry: ParamSpec, objects: list[str], given: Any = None) -> QWidget:
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
            number.setDecimals(2)
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
            combo = QComboBox(self)
            combo.addItems(objects)
            combo.setEditable(True)
            if start:
                combo.setCurrentText(str(start))
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
                collected[entry.name] = editor.currentText()
            elif isinstance(editor, QLineEdit):
                collected[entry.name] = editor.text()
        return collected
