"""Operation dialogs, generated from the parameter schema (Bauplan §10, §2.4).

Graded depth: the two or three values people actually change are on the front,
tolerances and resolutions sit behind "Weitere Einstellungen". Which is which
comes from ``placement`` in the schema, so a dialog cannot drift away from the
operation it belongs to.
"""

from __future__ import annotations

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
    """One dialog for one operation, built from its schema."""

    def __init__(
        self,
        spec: OperationSpec,
        objects: list[str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.spec = spec
        self.setWindowTitle(str(spec.title))
        self.setMinimumWidth(380)
        self._editors: dict[str, QWidget] = {}

        front = QFormLayout()
        advanced = QFormLayout()
        for entry in spec.params.spec():
            editor = self._editor_for(entry, objects)
            self._editors[entry.name] = editor
            label = f"{entry.title}"
            if entry.unit:
                label = f"{label} [{entry.unit}]"
            target = front if entry.placement == "front" else advanced
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

    def _editor_for(self, entry: ParamSpec, objects: list[str]) -> QWidget:
        if entry.kind == "bool":
            editor = QCheckBox(self)
            editor.setChecked(bool(entry.default))
            return editor
        if entry.kind == "int":
            spin = QSpinBox(self)
            spin.setMinimum(int(entry.minimum) if entry.minimum is not None else -1_000_000)
            spin.setMaximum(int(entry.maximum) if entry.maximum is not None else 1_000_000)
            if entry.default is not None:
                spin.setValue(int(entry.default))
            return spin
        if entry.kind == "float":
            number = QDoubleSpinBox(self)
            number.setDecimals(2)
            number.setMinimum(entry.minimum if entry.minimum is not None else -1_000_000.0)
            number.setMaximum(entry.maximum if entry.maximum is not None else 1_000_000.0)
            if entry.default is not None:
                number.setValue(float(entry.default))
            return number
        if entry.kind == "enum" or entry.choices:
            combo = QComboBox(self)
            combo.addItems(list(entry.choices))
            if entry.default is not None and entry.default in entry.choices:
                combo.setCurrentText(str(entry.default))
            return combo
        if entry.kind in ("object", "source"):
            combo = QComboBox(self)
            combo.addItems(objects)
            combo.setEditable(True)
            return combo
        line = QLineEdit(self)
        if entry.default:
            line.setText(str(entry.default))
        return line

    def values(self) -> dict[str, Any]:
        """What the user entered, ready for the operation parameters."""
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
