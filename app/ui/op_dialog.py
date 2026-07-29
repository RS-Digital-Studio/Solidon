"""Operation dialogs, generated from the parameter schema (Bauplan §10, §2.4).

Graded depth: the two or three values people actually change are on the front,
tolerances and resolutions sit behind "Weitere Einstellungen". Which is which
comes from ``placement`` in the schema, so a dialog cannot drift away from the
operation it belongs to.

The dialog can be opened on values instead of on the defaults, and that one
addition serves two things that look different and are the same: a clicked face
filling in where the operation goes (§18.5), and an operation of the stack being
opened again to correct it (§15.4). Both are "here are the values, ask about
them" — a second dialog for the second case would be a second place to forget a
parameter in.
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
    """One dialog for one operation, built from its schema."""

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
            # A value that was filled in belongs in front of the user even when
            # the schema files it away: it is the one that was just decided.
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
        """One editor. ``given`` wins over the schema's default where it is set."""
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
