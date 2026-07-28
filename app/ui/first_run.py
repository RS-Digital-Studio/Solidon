"""The first run (Bauplan §38).

Language, printer, material, a look at the external programs, and the key for
the chat if there is one. Four steps, all of them skippable, all of them
reachable again later — a wizard that has to be finished before anything can be
done is a wall, not a welcome.

It ends where the plan says the first five minutes end (§2.3): at the first
import. So the last page does not say "done", it offers to open a model.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME
from app.core import tools
from app.core.knowledge import profiles
from app.i18n import SUPPORTED_LANGUAGES, tr
from app.ui.settings import UiSettings

#: Marker per state, so the list reads without colour as well (§19.1).
FOUND = "+"
MISSING = "-"


class FirstRunDialog(QDialog):
    """One page, four questions, everything skippable."""

    importRequested = Signal()

    def __init__(self, settings: UiSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("Erste Schritte"))
        self.setMinimumWidth(520)

        greeting = QLabel(
            f"{APP_NAME} — "
            + tr(
                "Konstruieren, erzeugen und anpassen für den 3D-Druck. Diese Angaben "
                "lassen sich jederzeit ändern; überspringen geht auch."
            ),
            self,
        )
        greeting.setWordWrap(True)

        self.language = QComboBox(self)
        for entry in SUPPORTED_LANGUAGES:
            self.language.addItem(entry, entry)
        self.language.setCurrentText(settings.language)

        self.printer = QComboBox(self)
        for identifier, printer in sorted(profiles.printer_profiles().items()):
            self.printer.addItem(str(printer.title), identifier)
        _select(self.printer, settings.printer or profiles.DEFAULT_PRINTER)

        self.material = QComboBox(self)
        for identifier, material in sorted(profiles.material_profiles().items()):
            self.material.addItem(str(material.title), identifier)
        _select(self.material, settings.material or profiles.DEFAULT_MATERIAL)

        form = QFormLayout()
        form.addRow(tr("Sprache"), self.language)
        form.addRow(tr("Drucker"), self.printer)
        form.addRow(tr("Material"), self.material)

        self.tools = QLabel(_tool_text(), self)
        self.tools.setWordWrap(True)
        self.tools.setTextFormat(Qt.TextFormat.PlainText)

        self.open_button = QPushButton(tr("Modell öffnen …"), self)
        self.open_button.clicked.connect(self._open)

        buttons = QDialogButtonBox(self)
        buttons.addButton(tr("Übernehmen"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(tr("Überspringen"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(greeting)
        layout.addLayout(form)
        layout.addWidget(QLabel(tr("Externe Programme — keines davon ist Pflicht:"), self))
        layout.addWidget(self.tools)
        layout.addWidget(self.open_button)
        layout.addWidget(buttons)

    # --- result -----------------------------------------------------------------

    def apply_to(self, settings: UiSettings) -> UiSettings:
        """Write the answers back. Called on accept, never on skip."""
        settings.language = str(self.language.currentData())
        settings.printer = str(self.printer.currentData())
        settings.material = str(self.material.currentData())
        settings.first_run_done = True
        return settings

    def _open(self) -> None:
        """§2.3: the first five minutes end at the first import, not at "done"."""
        self.apply_to(self.settings)
        self.importRequested.emit()
        self.accept()


def _select(box: QComboBox, identifier: str) -> None:
    index = box.findData(identifier)
    if index >= 0:
        box.setCurrentIndex(index)


def _tool_text() -> str:
    """What is installed and what each one would be for (§38)."""
    lines = []
    for state in tools.survey():
        marker = FOUND if state.available else MISSING
        where = str(state.path) if state.path else tr("nicht gefunden")
        lines.append(f"{marker} {state.tool.title}: {where}\n   {state.tool.what_for}")
    return "\n".join(lines)


def should_run(settings: UiSettings) -> bool:
    """Only once, and only if it was not skipped before."""
    return not settings.first_run_done
