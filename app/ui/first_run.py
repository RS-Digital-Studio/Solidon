"""Der erste Start (Bauplan §38).

Sprache, Drucker, Material, ein Blick auf die externen Programme, und der
Schlüssel für den Chat, falls es einen gibt. Vier Schritte, alle
überspringbar, alle später wieder erreichbar — ein Assistent, der zu Ende
gebracht werden muss, bevor irgendetwas geht, ist eine Wand, kein Willkommen.

Er endet dort, wo der Bauplan die ersten fünf Minuten enden lässt (§2.3): beim
ersten Import. Die letzte Seite sagt darum nicht „fertig", sie bietet an, ein
Modell zu öffnen.
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
from app.core import install, tools
from app.core.knowledge import profiles
from app.i18n import SUPPORTED_LANGUAGES, language_name, tr
from app.ui.settings import UiSettings

#: Der Zustand jedes Programms steht als Wort in der Zeile, damit sich die
#: Liste auch ohne Farbe liest (§19.1). Vorher stand dort ein Plus- und ein
#: ein Minuszeichen — beides kurz, beides zu raten. In der einzigen Liste,
#: die jemand beim allerersten Start zu lesen bekommt, ist das ein schlechter
#: Tausch für zwei gesparte Zeichen.


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
        # Der Name, nicht das Kürzel: „de" stand hier als allererste Angabe, die
        # ein neuer Benutzer zu sehen bekam.
        for entry in SUPPORTED_LANGUAGES:
            self.language.addItem(language_name(entry), entry)
        self.language.setCurrentIndex(self.language.findData(settings.language))

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

        self.install_button = QPushButton(
            f"{tr('Fehlendes installieren …')}  ·  {_missing_text()}", self
        )
        self.install_button.clicked.connect(self._install)

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
        layout.addWidget(self.install_button)
        layout.addWidget(self.open_button)
        layout.addWidget(buttons)

    # --- result -----------------------------------------------------------------

    def apply_to(self, settings: UiSettings) -> UiSettings:
        """Schreibt die Antworten zurück. Beim Annehmen aufgerufen, nie beim
        Überspringen.
        """
        settings.language = str(self.language.currentData())
        settings.printer = str(self.printer.currentData())
        settings.material = str(self.material.currentData())
        settings.first_run_done = True
        return settings

    def _install(self) -> None:
        """§36: was fehlt, lässt sich von hier holen, statt aus einem README."""
        from app.ui.install_dialog import InstallDialog

        InstallDialog(self).exec()
        self.tools.setText(_tool_text())
        self.install_button.setText(f"{tr('Fehlendes installieren …')}  ·  {_missing_text()}")

    def _open(self) -> None:
        """§2.3: die ersten fünf Minuten enden beim ersten Import, nicht bei
        „fertig".
        """
        self.apply_to(self.settings)
        self.importRequested.emit()
        self.accept()


def _select(box: QComboBox, identifier: str) -> None:
    index = box.findData(identifier)
    if index >= 0:
        box.setCurrentIndex(index)


def _missing_text() -> str:
    """Eine Zeile über das, was nicht da ist — gezeigt neben dem Knopf, der
    es holt.
    """
    absent = install.missing()
    if not absent:
        return tr("Alles Zusätzliche ist vorhanden.")
    return f"{tr('Nicht gefunden')}: " + ", ".join(str(entry.title) for entry in absent)


def _tool_text() -> str:
    """Was installiert ist und wofür es gut wäre (§38).

    Statt „nicht gefunden" steht hier der Satz, der sagt, was weiterhilft: ein
    Dienst muss laufen, ein Programm an ungewöhnlicher Stelle wird angegeben.
    Beides führt zu derselben Liste unter *Hilfe → Zusätzliche Programme*.
    """
    lines = []
    for state in tools.survey():
        marker = tr("gefunden") if state.available else tr("fehlt")
        where = str(state.path) if state.path else state.tool.address()
        if not state.available:
            where = str(state.explain())
        lines.append(f"{marker} — {state.tool.title}: {where}\n   {state.tool.what_for}")
    return "\n".join(lines)


def should_run(settings: UiSettings) -> bool:
    """Nur einmal, und nur, wenn er nicht vorher übersprungen wurde."""
    return not settings.first_run_done
