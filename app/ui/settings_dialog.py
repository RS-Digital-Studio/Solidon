"""Die Einstellungen an einem Ort (Bauplan §19.3, §38).

Es gab keinen solchen Ort. Thema und Navigation lagen unter *Ansicht*, Sprache,
Drucker und Material unter *Hilfe → Erste Schritte* — wer den Drucker unter
„Hilfe" sucht, hat geraten. Drei erklärte Einstellungen waren deshalb tot:
die Anzeigeeinheit hatte keinen Leser, die Differenzpalette wurde gespeichert
und nie geladen, und die Updateprüfung ließ sich nur durch Handbearbeitung der
Datei einschalten.

Zwei Sorten stehen hier nebeneinander, und der Dialog sagt, welche welche ist:
was die **Anwendung** betrifft (Sprache, Thema, Einheit) und was für **neue
Projekte** gilt (Drucker, Material). Den Drucker des offenen Projekts ändert
man nicht hier, sondern dort, wo er wirkt — er ist eine Änderung am Dokument
und gehört in den Verlauf (§15.5).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.knowledge import profiles
from app.core.units import DISPLAY_UNITS
from app.i18n import SUPPORTED_LANGUAGES, language_name, tr
from app.ui.palette import DIFF_PALETTES
from app.ui.settings import UiSettings
from app.ui.shortcut_schemes import SCHEMES

#: Die Bezeichnungen der Navigationsschemata (§2.9).
NAVIGATION = {
    "slicer": tr("Wie in Cura — links wählt, rechts dreht"),
    "orbit": tr("Wie in Bambu Studio, Orca und PrusaSlicer — links dreht"),
    "cad": tr("Wie im CAD — mittlere Taste dreht"),
    "blender": tr("Wie in Blender"),
}

#: Die Bezeichnungen der Themen.
THEMES = {"dark": tr("Dunkel"), "light": tr("Hell")}

#: Wie die Differenzansicht ihre Farben nennt (§19.1).
DIFF_LABELS = {
    "blue_orange": tr("Blau und Orange (Vorgabe)"),
    "red_green": tr("Rot und Grün"),
    "greyscale": tr("Graustufen"),
}


class SettingsDialog(QDialog):
    """Was die Anwendung sich merkt, an einer Stelle."""

    def __init__(self, settings: UiSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("Einstellungen"))
        self.setMinimumWidth(460)

        self.language = _choices(self, {key: language_name(key) for key in SUPPORTED_LANGUAGES})
        _select(self.language, settings.language)
        self.language_note = QLabel(tr("Eine andere Sprache erscheint beim nächsten Start."), self)
        self.language_note.setWordWrap(True)
        self.language_note.setVisible(False)
        self.language.currentIndexChanged.connect(self._language_changed)

        self.unit = _choices(self, {key: key for key in DISPLAY_UNITS})
        _select(self.unit, settings.display_unit)

        self.theme = _choices(self, THEMES)
        _select(self.theme, settings.theme)

        self.navigation = _choices(self, NAVIGATION)
        _select(self.navigation, settings.navigation)

        self.diff_palette = _choices(
            self, {key: DIFF_LABELS.get(key, key) for key in DIFF_PALETTES}
        )
        _select(self.diff_palette, settings.diff_palette)

        # Konzept P15, E7: wer aus Fusion kommt, hat E und F in den Fingern.
        # Die Vorgabe bleibt die des Registers; das hier legt einzelne Tasten
        # darüber und wirkt beim nächsten Start, weil die Menüs beim Bau
        # gesetzt werden.
        self.shortcuts = _choices(
            self, {key: str(label) for key, (label, _table) in SCHEMES.items()}
        )
        _select(self.shortcuts, settings.shortcut_scheme)
        self.shortcuts.setToolTip(
            tr("Welche Tasten die Operationen führen. Wirkt beim nächsten Start.")
        )

        self.updates = QCheckBox(tr("Beim Start nach einer neuen Fassung sehen"), self)
        self.updates.setChecked(settings.check_for_updates)
        self.updates.setToolTip(
            tr("Ein Hinweis mit einem Link. Es wird nichts geladen und nichts ersetzt.")
        )

        # Konzept P15 §7 Etappe 9: aus, bis jemand sie einschaltet. Der
        # Hinweis daneben nennt Adresse und Port, denn ohne die kann niemand
        # sie eintragen — und wer sie liest, sieht zugleich, dass sie diesen
        # Rechner nicht verlässt.
        self.remote = QCheckBox(tr("Fernsteuerung über MCP zulassen"), self)
        self.remote.setChecked(settings.remote_enabled)
        self.remote_port = QSpinBox(self)
        self.remote_port.setRange(1024, 65535)
        self.remote_port.setValue(settings.remote_port)
        self.remote.setToolTip(
            tr(
                "Ein anderes Programm auf diesem Rechner darf dieselben "
                "Operationen aufrufen wie die Menüs. Nur über 127.0.0.1, und "
                "jeder Aufruf ist eine Transaktion, die ein Strg+Z zurücknimmt."
            )
        )

        self.printer = _choices(
            self,
            {key: str(entry.title) for key, entry in sorted(profiles.printer_profiles().items())},
        )
        _select(self.printer, settings.printer or profiles.DEFAULT_PRINTER)
        self.material = _choices(
            self,
            {key: str(entry.title) for key, entry in sorted(profiles.material_profiles().items())},
        )
        _select(self.material, settings.material or profiles.DEFAULT_MATERIAL)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._application_group())
        layout.addWidget(self._project_group())
        layout.addWidget(buttons)

    def _application_group(self) -> QWidget:
        box = QGroupBox(tr("Anwendung"), self)
        form = QFormLayout(box)
        form.addRow(tr("Sprache"), self.language)
        form.addRow("", self.language_note)
        form.addRow(tr("Anzeigeeinheit"), self.unit)
        form.addRow(tr("Thema"), self.theme)
        form.addRow(tr("Navigation"), self.navigation)
        form.addRow(tr("Differenzansicht"), self.diff_palette)
        form.addRow(tr("Tastenbelegung"), self.shortcuts)
        form.addRow("", self.updates)
        form.addRow("", self.remote)
        form.addRow(tr("Port der Fernsteuerung"), self.remote_port)
        return box

    def _project_group(self) -> QWidget:
        box = QGroupBox(tr("Vorgaben für neue Projekte"), self)
        form = QFormLayout(box)
        note = QLabel(
            tr(
                "Diese Werte gelten für das nächste neue Projekt. Drucker und Material "
                "eines offenen Projekts ändert die Druckvorbereitung."
            ),
            box,
        )
        note.setWordWrap(True)
        form.addRow(note)
        form.addRow(tr("Drucker"), self.printer)
        form.addRow(tr("Material"), self.material)
        return box

    def _language_changed(self) -> None:
        """§38: eine Änderung, die erst nach dem Neustart wirkt, sagt das.

        Der Sprachkatalog wird beim Start installiert; die Texte, die schon
        auf dem Bildschirm stehen, wechseln nicht mit. Das stillschweigend zu
        übergehen hieß, dass die Einstellung aussieht, als hätte sie nicht
        gewirkt.
        """
        self.language_note.setVisible(str(self.language.currentData()) != self.settings.language)

    def apply_to(self, settings: UiSettings) -> UiSettings:
        """Schreibt die Antworten zurück. Nur beim Annehmen aufgerufen."""
        settings.language = str(self.language.currentData())
        settings.display_unit = str(self.unit.currentData())
        settings.theme = str(self.theme.currentData())
        settings.navigation = str(self.navigation.currentData())
        settings.diff_palette = str(self.diff_palette.currentData())
        settings.shortcut_scheme = str(self.shortcuts.currentData())
        settings.check_for_updates = self.updates.isChecked()
        settings.remote_enabled = self.remote.isChecked()
        settings.remote_port = int(self.remote_port.value())
        settings.printer = str(self.printer.currentData())
        settings.material = str(self.material.currentData())
        return settings


def _choices(parent: QWidget, entries: dict[str, str]) -> QComboBox:
    """Ein Aufklappmenü, das Namen zeigt und Kennungen weitergibt."""
    box = QComboBox(parent)
    for key, label in entries.items():
        box.addItem(str(label), key)
    return box


def _select(box: QComboBox, identifier: str) -> None:
    index = box.findData(identifier)
    if index >= 0:
        box.setCurrentIndex(index)
