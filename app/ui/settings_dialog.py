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

from collections.abc import Mapping

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.knowledge import profiles
from app.core.units import DISPLAY_UNITS
from app.i18n import TranslatableText, _, language_name, tr
from app.i18n.catalog import available_languages
from app.ui.ai_disclosure import clear_disclosure
from app.ui.labels import TrackSlider, by_title
from app.ui.palette import DIFF_PALETTES
from app.ui.panels import align_forms
from app.ui.settings import UiSettings
from app.ui.shortcut_schemes import SCHEMES
from app.ui.style import make_primary

# **Diese drei Listen standen mit ``tr()`` da, und das übersetzt sofort.**
# Auf Modulebene heißt „sofort": beim Import, in der Sprache, die dann gerade
# gilt — und das ist beim Start noch keine. ``app.py`` holt ``MainWindow`` in
# Zeile 152, ``main_window.py`` zieht diesen Dialog auf Modulebene nach, und
# ``install_language`` läuft erst siebzehn Zeilen später. Ein Kunde mit
# portugiesischer Oberfläche fand deshalb in den Einstellungen „Dunkel",
# „Wie in Cura — links wählt, rechts dreht" und „Blau und Orange (Vorgabe)"
# vor, während alles andere um sie herum portugiesisch war. Die Texte waren
# übersetzt; sie wurden nur zu früh abgeholt.
#
# ``_()`` gibt stattdessen einen ``TranslatableText``, der seine Sprache erst
# beim Anzeigen sucht — ``_choices`` ruft ohnehin ``str()`` darauf.

#: Die Bezeichnungen der Navigationsschemata (§2.9).
NAVIGATION = {
    "slicer": _("Wie in Cura — links wählt, rechts dreht"),
    "orbit": _("Wie in Bambu Studio, Orca und PrusaSlicer — links dreht"),
    "cad": _("Wie im CAD — mittlere Taste dreht, rechts zoomt"),
    "blender": _("Wie in Blender — links wählt, mittlere Taste dreht"),
}

#: Die Bezeichnungen der Themen.
THEMES = {"dark": _("Dunkel"), "light": _("Hell")}

#: Wie die Differenzansicht ihre Farben nennt (§19.1).
DIFF_LABELS = {
    "blue_orange": _("Blau und Orange (Vorgabe)"),
    "red_green": _("Rot und Grün"),
    "greyscale": _("Graustufen"),
}


class SettingsDialog(QDialog):
    """Was die Anwendung sich merkt, an einer Stelle."""

    def __init__(self, settings: UiSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("Einstellungen"))
        self.setMinimumWidth(460)

        self.language = _choices(self, {key: language_name(key) for key in available_languages()})
        _select(self.language, settings.language)
        self.language_note = QLabel(tr("Die Oberfläche stellt sich gleich darauf um."), self)
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
            self, {key: str(DIFF_LABELS.get(key, key)) for key in DIFF_PALETTES}
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

        self.updates = QCheckBox(tr("Beim Start nach einer neuen Version sehen"), self)
        self.updates.setChecked(settings.check_for_updates)
        # **Die Zusage stimmt seit ``download()`` und ``start_installer()``
        # nicht mehr.** Hier stand, es werde nichts geladen und nichts ersetzt;
        # das war richtig, als der Weg wirklich nur ein Link war. Die Zusage
        # aus §37.2 ist eine andere und eine genauere: Die Grenze liegt beim
        # Auslöser, nicht beim Vorgang — geladen wird auf Klick, gestartet nach
        # dem Schließen. Eine Zusage in die freundliche Richtung ist auch dann
        # falsch, wenn sie falsch ist.
        self.updates.setToolTip(
            tr(
                "Fragt beim Start bei solidon3d.de nach. Geladen und installiert "
                "wird erst auf Ihre Bestätigung."
            )
        )

        # §26.5: die automatische Übernahme ist die Vorgabe — Regel 19 kennt
        # keine Bestätigung vor rücknehmbaren Handlungen. Abschaltbar, weil
        # sie das gefühlte Verhalten des Chats ändert.
        self.auto_accept = QCheckBox(
            tr("Umkehrbare Chat-Vorschläge ohne Nachfrage übernehmen"), self
        )
        self.auto_accept.setChecked(settings.auto_accept_reversible)
        self.auto_accept.setToolTip(
            tr(
                "Nur wenn jede Operation des Vorschlags umkehrbar ist, keine "
                "Warnung entstand und keine Rückfrage offen war. Ein Undo "
                "nimmt alles zurück."
            )
        )

        self._reset_ai_disclosure = False
        self.ai_disclosure_reset = QPushButton(tr("KI-Hinweis erneut anzeigen"), self)
        self.ai_disclosure_reset.setAccessibleName(self.ai_disclosure_reset.text())
        self.ai_disclosure_reset.setAccessibleDescription(
            tr(
                "Löscht nur den lokalen Anzeigenachweis. Vor der nächsten "
                "Chatnachricht erscheint der KI-Hinweis erneut."
            )
        )
        self.ai_disclosure_reset.setToolTip(self.ai_disclosure_reset.accessibleDescription())
        has_disclosure = bool(
            settings.ai_disclosure_version
            or settings.ai_disclosure_backend
            or settings.ai_disclosure_target
            or settings.ai_disclosure_at_utc
        )
        self.ai_disclosure_reset.setEnabled(has_disclosure)
        self.ai_disclosure_reset.clicked.connect(self._reset_disclosure)

        # Konzept P15 §7 Etappe 9: aus, bis jemand sie einschaltet. Der
        # Hinweis daneben nennt Adresse und Port, denn ohne die kann niemand
        # sie eintragen — und wer sie liest, sieht zugleich, dass sie diesen
        # Rechner nicht verlässt.
        #
        # „Fernsteuerung über MCP zulassen" stand hier und war der dritte von
        # drei Namen für scheinbar Benachbartes — *Chat einrichten* im Menü
        # daneben, und „Fern-" klingt danach, als ginge etwas hinaus. Es kommt
        # aber etwas herein. „über MCP" nannte das Protokoll; wer hier steuert,
        # stand nur im Tooltip. „durch andere Programme" nennt es.
        #
        # Das Wort *Fernsteuerung* bleibt vorn stehen, und das ist Absicht: Die
        # Zeile darunter heißt „Port der Fernsteuerung", das Handbuch hat ein
        # Kapitel *Fernsteuerung*. Wer hier ein anderes Wort setzt, behebt
        # einen Namensbruch und legt einen zweiten an. Die ausführliche
        # Version („Solidon von anderen Programmen auf diesem Rechner
        # fernsteuern lassen") sagte nicht mehr und zog den Dialog auf
        # Französisch von 566 auf 768 Bildpunkte — gemessen, dann verworfen.
        self.remote = QCheckBox(tr("Fernsteuerung durch andere Programme zulassen (MCP)"), self)
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
        # Die Portnummer gehört zur Fernsteuerung und nicht neben sie: Sie
        # stand bedienbar da, während der Haken aus war — eine Einstellung für
        # etwas, das nicht läuft. Derselbe Tooltip, damit die Erklärung auch
        # den erreicht, der zuerst auf das Feld zeigt.
        self.remote_port.setEnabled(self.remote.isChecked())
        self.remote_port.setToolTip(self.remote.toolTip())
        self.remote.toggled.connect(self.remote_port.setEnabled)

        # Konzept 3D-Maus, Abschnitt 6: eine Zeile, drei Felder — An/Aus, ein
        # Regler, Richtung. Sichtbar erst ab dem ersten gesehenen Gerät, und
        # ab dann dauerhaft: Wer das Gerät abzieht, findet die Einstellung
        # sonst nicht wieder, und die Handbuchbilder sähen sie nie.
        self.spacemouse = QCheckBox(tr("3D-Maus (SpaceMouse) benutzen"), self)
        self.spacemouse.setChecked(settings.spacemouse_enabled)
        self.spacemouse.setToolTip(
            tr(
                "Die Kappe ist das Teil: Schieben verschiebt, Drehen dreht, "
                "zu sich ziehen holt es näher. Jede Gerätetaste passt alles ein."
            )
        )
        self.spacemouse_speed = TrackSlider(Qt.Orientation.Horizontal, self)
        self.spacemouse_speed.setRange(1, 10)
        self.spacemouse_speed.setValue(settings.spacemouse_speed)
        self.spacemouse_speed.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.spacemouse_speed.setTickInterval(1)
        self.spacemouse_speed.setAccessibleName(tr("Geschwindigkeit der 3D-Maus"))
        self.spacemouse_speed.setToolTip(
            tr("Wie weit ein Schub die Ansicht bewegt. Links fein, rechts flott.")
        )
        self.spacemouse_invert = QCheckBox(tr("Richtung umkehren"), self)
        self.spacemouse_invert.setChecked(settings.spacemouse_invert)
        self.spacemouse_invert.setToolTip(
            tr(
                "Dann ist die Kappe die Kamera statt des Teils — für alle, die "
                "es aus ihrem CAD so gewohnt sind."
            )
        )
        self.spacemouse_speed.setEnabled(self.spacemouse.isChecked())
        self.spacemouse_invert.setEnabled(self.spacemouse.isChecked())
        self.spacemouse.toggled.connect(self.spacemouse_speed.setEnabled)
        self.spacemouse.toggled.connect(self.spacemouse_invert.setEnabled)

        self.printer = _choices(
            self,
            {key: str(entry.title) for key, entry in by_title(profiles.printer_profiles())},
        )
        _select(self.printer, settings.printer or profiles.DEFAULT_PRINTER)
        self.material = _choices(
            self,
            {key: str(entry.title) for key, entry in by_title(profiles.material_profiles())},
        )
        _select(self.material, settings.material or profiles.DEFAULT_MATERIAL)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        # Speichern ist die Handlung dieses Fensters, also trägt sie den
        # Akzent — ausdrücklich. Qt gab ihn beim ersten ``show()`` ohnehin an
        # denselben Knopf, aber ohne die halbfette Schrift daneben, und Farbe
        # allein ist keine zweite Kodierung (Regel 18).
        save = buttons.button(QDialogButtonBox.StandardButton.Save)
        if save is not None:
            make_primary(save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self._application_group())
        layout.addWidget(self._project_group())
        layout.addWidget(buttons)
        # Zwei Gruppen, zwei Formulare — und jedes rechnete seine
        # Beschriftungsspalte für sich: Die Felder begannen oben bei 148 und
        # unten bei 70 Punkten, gemessen am gebauten Dialog (Befund B11).
        align_forms(self)

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
        form.addRow("", self.auto_accept)
        form.addRow(tr("KI-Hinweis"), self.ai_disclosure_reset)
        form.addRow("", self.remote)
        form.addRow(tr("Port der Fernsteuerung"), self.remote_port)
        form.addRow("", self.spacemouse)
        form.addRow(tr("Geschwindigkeit der 3D-Maus"), self.spacemouse_speed)
        form.addRow("", self.spacemouse_invert)
        for row in (self.spacemouse, self.spacemouse_speed, self.spacemouse_invert):
            form.setRowVisible(row, self.settings.spacemouse_seen)
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
        settings.auto_accept_reversible = self.auto_accept.isChecked()
        if self._reset_ai_disclosure:
            clear_disclosure(settings)
        settings.remote_enabled = self.remote.isChecked()
        settings.remote_port = int(self.remote_port.value())
        settings.spacemouse_enabled = self.spacemouse.isChecked()
        settings.spacemouse_speed = int(self.spacemouse_speed.value())
        settings.spacemouse_invert = self.spacemouse_invert.isChecked()
        settings.printer = str(self.printer.currentData())
        settings.material = str(self.material.currentData())
        return settings

    def _reset_disclosure(self) -> None:
        """Merkt die Wahl bis zum Speichern; Abbrechen verändert noch nichts."""

        self._reset_ai_disclosure = True
        self.ai_disclosure_reset.setEnabled(False)
        self.ai_disclosure_reset.setText(tr("Wird vor der nächsten Nachricht angezeigt"))
        self.ai_disclosure_reset.setAccessibleName(self.ai_disclosure_reset.text())


def _choices(parent: QWidget, entries: Mapping[str, str | TranslatableText]) -> QComboBox:
    """Ein Aufklappmenü, das Namen zeigt und Kennungen weitergibt.

    Nimmt beides an: eine fertige Zeichenkette und einen ``TranslatableText``,
    der seine Sprache erst hier sucht. Die Listen über dem Dialog sind lazy,
    weil sie beim Import noch keine Sprache haben (siehe dort).
    """
    box = QComboBox(parent)
    for key, label in entries.items():
        box.addItem(str(label), key)
    return box


def _select(box: QComboBox, identifier: str) -> None:
    index = box.findData(identifier)
    if index >= 0:
        box.setCurrentIndex(index)
