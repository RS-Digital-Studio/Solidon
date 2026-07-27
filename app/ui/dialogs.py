"""Questions and errors as the plan describes them (Bauplan §2.7, §21.3).

An error names, in this order, what did not work, why, and what is possible now —
as buttons, not prose. The stack trace goes to the log, never into the dialog.
"""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QMessageBox,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import Action, AppError
from app.i18n import tr


class AskDialog(QDialog):
    """Ambiguity stops and asks — over ``ctx.ask``, never from inside the core."""

    def __init__(self, question: str, choices: list[str], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Rückfrage"))
        self.setMinimumWidth(360)

        prompt = QLabel(question, self)
        prompt.setWordWrap(True)
        self.list = QListWidget(self)
        self.list.addItems(choices)
        self.list.setCurrentRow(0)
        self.list.itemDoubleClicked.connect(lambda _item: self.accept())

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(prompt)
        layout.addWidget(self.list)
        layout.addWidget(buttons)

    def chosen(self) -> str | None:
        item = self.list.currentItem()
        return item.text() if item is not None else None


def show_error(error: AppError, parent: QWidget | None = None) -> Action | None:
    """Show an error as a suggestion and return the action the user picked."""
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(tr("Das hat so nicht funktioniert"))
    box.setText(str(error.title))
    if error.detail:
        box.setInformativeText(str(error.detail))

    buttons: dict[Any, Action] = {}
    for action in error.suggestions:
        role = (
            QMessageBox.ButtonRole.AcceptRole
            if action.primary
            else QMessageBox.ButtonRole.ActionRole
        )
        buttons[box.addButton(str(action.label), role)] = action

    box.exec()
    return buttons.get(box.clickedButton())


def confirm_discard(count: int, parent: QWidget | None = None) -> bool:
    """The one question that is worth asking: throwing away more than one step (§15.4)."""
    if count <= 1:
        return True
    answer = QMessageBox.question(
        parent,
        tr("Abgeschnittene Schritte verwerfen?"),
        tr("Diese Änderung verwirft {count} zurückgenommene Schritte.").replace(
            "{count}", str(count)
        ),
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.Yes,
    )
    return answer == QMessageBox.StandardButton.Yes
