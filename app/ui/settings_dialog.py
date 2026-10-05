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
from itertools import pairwise
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core import discover
from app.core.errors import CANCEL, RETRY, FileWriteError
from app.core.knowledge import profiles
from app.core.log import get_logger
from app.core.types import PrinterProfile
from app.core.units import DISPLAY_UNITS
from app.i18n import TranslatableText, _, language_name, tr
from app.i18n.catalog import available_languages
from app.ui.ai_disclosure import clear_disclosure
from app.ui.dialogs import align_to_the_front
from app.ui.first_run import (
    LANGUAGE_CHANGED,
    PrinterChoices,
    PrinterComboBox,
    _PrinterSurvey,
    add_printer_choices,
    allowed_printers,
    choose_slicer_file,
    preferred_printer,
    select_program,
    valid_printer_choice,
)
from app.ui.icons import icon
from app.ui.labels import TrackSlider, by_title, slicer_title, wheel_needs_focus
from app.ui.leash import WAIT_TIMEOUT_MS, WorkerLeash
from app.ui.palette import DIFF_PALETTES
from app.ui.panels import collapsible, open_section
from app.ui.print_settings_dialog import _SlicerWorker
from app.ui.settings import UiSettings
from app.ui.shortcut_schemes import SCHEMES
from app.ui.style import (
    NORMAL,
    SPACE,
    WIDE,
    ContentHeight,
    DialogScrollArea,
    expanded_width,
    make_primary,
    select_data,
)

_log = get_logger(__name__)

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
    "solidon": _("Solidon — links verschiebt, rechts dreht, WASD fliegt"),
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


def option_titles() -> dict[str, str]:
    """Jede Einzeloption des Dialogs mit ihrem Namen, in der Folge des Formulars.

    **Eine Quelle für Formular und Befehlspalette** (RM-491): Seit die Hälfte
    hinter „Weitere Einstellungen" liegt, findet man Tastenbelegung und
    Fernsteuerung über die Palette — unter genau dem Namen, den die Zeile
    trägt. Die Schlüssel sind die Attributnamen der Felder
    (:meth:`SettingsDialog.show_option`).
    """
    return {
        "language": tr("Sprache"),
        "unit": tr("Anzeigeeinheit"),
        "theme": tr("Thema"),
        "updates": tr("Beim Start nach einer neuen Version sehen"),
        "slicer": tr("Slicer"),
        "navigation": tr("Navigation"),
        "spacemouse": tr("3D-Maus (SpaceMouse) benutzen"),
        "spacemouse_speed": tr("Geschwindigkeit der 3D-Maus"),
        "spacemouse_invert": tr("Richtung umkehren"),
        "shortcuts": tr("Tastenbelegung"),
        "diff_palette": tr("Differenzansicht"),
        "auto_accept": tr("Umkehrbare Chat-Vorschläge ohne Nachfrage übernehmen"),
        "ai_disclosure_reset": tr("KI-Hinweis erneut anzeigen"),
        "remote": tr("Fernsteuerung durch andere Programme zulassen (MCP)"),
        "remote_port": tr("Port der Fernsteuerung"),
        "printer": tr("Drucker"),
        "material": tr("Material"),
    }


#: Die Zeilen der 3D-Maus — sichtbar erst ab dem ersten gesehenen Gerät.
SPACEMOUSE_OPTIONS = ("spacemouse", "spacemouse_speed", "spacemouse_invert")

#: Welcher Haken eine Zeile freigibt, solange sie gesperrt ist.
_GATES = {
    "remote_port": "remote",
    "spacemouse_speed": "spacemouse",
    "spacemouse_invert": "spacemouse",
}


def searchable_options(settings: UiSettings) -> dict[str, str]:
    """Was die Befehlspalette aus diesem Dialog anbietet — nur sichtbare Zeilen.

    „Richtung umkehren" allein sagt in der Palette nicht, wessen Richtung;
    dort steht die 3D-Maus davor.
    """
    titles = option_titles()
    if not settings.spacemouse_seen:
        for key in SPACEMOUSE_OPTIONS:
            titles.pop(key)
    else:
        titles["spacemouse_invert"] = tr(
            "{name}: {value}", name=tr("3D-Maus"), value=titles["spacemouse_invert"]
        )
    return titles


class SettingsDialog(QDialog):
    """Was die Anwendung sich merkt, an einer Stelle."""

    def __init__(
        self,
        settings: UiSettings,
        parent: QWidget | None = None,
        *,
        slicer_path: str | None = None,
        discovered_printers: Mapping[str, PrinterProfile] | None = None,
        printer_query: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self._height = ContentHeight()
        self._closed = False
        self._leash = WorkerLeash(self)
        self._slicer_worker: _SlicerWorker | None = None
        self._printer_survey: _PrinterSurvey | None = None
        self._suggested_printer = profiles.DEFAULT_PRINTER
        self._discovered_printers = dict(discovered_printers or {})
        self.setWindowTitle(tr("Einstellungen"))
        self.setMinimumWidth(460)
        titles = option_titles()
        self._shown_option: QWidget | None = None

        self.language = _choices(self, {key: language_name(key) for key in available_languages()})
        select_data(self.language, settings.language)
        self.language.currentIndexChanged.connect(self._language_changed)

        self.unit = _choices(self, {key: key for key in DISPLAY_UNITS})
        select_data(self.unit, settings.display_unit)

        self.theme = _choices(self, THEMES)
        select_data(self.theme, settings.theme)

        self.navigation = _choices(self, NAVIGATION)
        self.navigation.setMinimumContentsLength(36)
        select_data(self.navigation, settings.navigation)
        self.navigation.setToolTip(self.navigation.currentText())
        self.navigation.currentTextChanged.connect(self.navigation.setToolTip)

        self.diff_palette = _choices(
            self, {key: str(DIFF_LABELS.get(key, key)) for key in DIFF_PALETTES}
        )
        select_data(self.diff_palette, settings.diff_palette)

        # Konzept P15, E7: wer aus Fusion kommt, hat E und F in den Fingern.
        # Die Vorgabe bleibt die des Registers; das hier legt einzelne Tasten
        # darüber und wirkt beim nächsten Start, weil die Menüs beim Bau
        # gesetzt werden.
        self.shortcuts = _choices(
            self, {key: str(label) for key, (label, _table) in SCHEMES.items()}
        )
        select_data(self.shortcuts, settings.shortcut_scheme)
        self.shortcuts.setToolTip(
            tr("Welche Tasten die Operationen führen. Wirkt beim nächsten Start.")
        )

        self.updates = QCheckBox(titles["updates"], self)
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
        self.auto_accept = QCheckBox(titles["auto_accept"], self)
        self.auto_accept.setChecked(settings.auto_accept_reversible)
        self.auto_accept.setToolTip(
            tr(
                "Nur wenn jede Operation des Vorschlags umkehrbar ist, keine "
                "Warnung entstand und keine Rückfrage offen war. Ein Undo "
                "nimmt alles zurück."
            )
        )

        self._reset_ai_disclosure = False
        self.ai_disclosure_reset = QPushButton(titles["ai_disclosure_reset"], self)
        self.ai_disclosure_reset.setAccessibleName(self.ai_disclosure_reset.text())
        has_disclosure = bool(
            settings.ai_disclosure_version
            or settings.ai_disclosure_backend
            or settings.ai_disclosure_target
            or settings.ai_disclosure_at_utc
            or settings.generation_disclosure_version
            or settings.generation_disclosure_target
            or settings.generation_disclosure_data
            or settings.generation_disclosure_at_utc
        )
        # **Gesperrt heißt: der Grund steht dort, wo sonst der Zweck steht.**
        # Der Knopf trug seine Beschreibung unabhängig vom Zustand, und die
        # sagt, was er *täte* — auf einem Rechner, der den Hinweis nie gesehen
        # hat, ist das die Antwort auf eine Frage, die niemand gestellt hat.
        # Wer den grauen Knopf anfasst, will wissen, warum er grau ist.
        note = (
            tr(
                "Löscht nur die lokalen Anzeigenachweise. Vor der nächsten "
                "KI-Anfrage erscheint der passende Hinweis erneut."
            )
            if has_disclosure
            else tr(
                "Der KI-Hinweis wurde auf diesem Rechner noch nicht bestätigt "
                "— es gibt nichts zurückzusetzen."
            )
        )
        self.ai_disclosure_reset.setAccessibleDescription(note)
        self.ai_disclosure_reset.setToolTip(note)
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
        self.remote = QCheckBox(titles["remote"], self)
        self.remote.setChecked(settings.remote_enabled)
        self.remote_port = QSpinBox(self)
        self.remote_port.setRange(1024, 65535)
        self.remote_port.setValue(settings.remote_port)
        self.remote.setToolTip(
            tr(
                "Ein anderes Programm auf diesem Rechner darf dieselben "
                "Operationen aufrufen wie die Menüs. Nur über 127.0.0.1, und "
                "jeden Aufruf nimmt ein Strg+Z zurück."
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
        self.spacemouse = QCheckBox(titles["spacemouse"], self)
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
        self.spacemouse_speed.setAccessibleName(titles["spacemouse_speed"])
        self.spacemouse_speed.setToolTip(
            tr("Wie weit ein Schub die Ansicht bewegt. Links fein, rechts flott.")
        )
        self.spacemouse_invert = QCheckBox(titles["spacemouse_invert"], self)
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

        self.slicer = QComboBox(self)
        self.slicer.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.slicer.setMinimumContentsLength(20)
        self.slicer.addItem(tr("Später auswählen"), "")
        self._stored_slicer_path = discover.remembered_path("slicer")
        selected_slicer = self._stored_slicer_path if slicer_path is None else slicer_path
        if selected_slicer:
            self.slicer.addItem(slicer_title(Path(selected_slicer)), selected_slicer)
            self.slicer.setItemData(1, selected_slicer, Qt.ItemDataRole.ToolTipRole)
            self.slicer.setCurrentIndex(1)
        self.slicer.setAccessibleName(titles["slicer"])
        self.slicer.currentIndexChanged.connect(self._slicer_changed)
        self.slicer_file = QPushButton(tr("Benutzerdefiniert …"), self)
        self.slicer_file.setIcon(icon("open", self.slicer_file))
        self.slicer_file.setToolTip(tr("Slicer-Programm auswählen"))
        self.slicer_file.clicked.connect(self._choose_slicer_file)
        self.search_again = QPushButton(tr("Erneut prüfen"), self)
        self.search_again.setIcon(icon("refresh", self.search_again))
        self.search_again.clicked.connect(self._slicer_changed)
        self.search_again.hide()
        self.slicer_state = QLabel(tr("Die Slicer werden gesucht …"), self)
        self.slicer_state.setWordWrap(True)
        self.printer_state = QLabel(self)
        self.printer_state.setWordWrap(True)
        self.printer_choice_state = QLabel(self)
        self.printer_choice_state.setWordWrap(True)
        self.search_progress = QProgressBar(self)
        self.search_progress.setRange(0, 0)
        self.search_progress.setTextVisible(False)
        # Eine Anzeige je Suche, jede bei dem, was gesucht wird: Die Slicersuche
        # lief unter dem Drucker an, zwei Zeilen unter ihrem Satz.
        self.slicer_progress = QProgressBar(self)
        self.slicer_progress.setRange(0, 0)
        self.slicer_progress.setTextVisible(False)

        # Nach Verfahren gruppiert wie im Erststart — dieselben Drucker, dieselbe
        # Ordnung (RM-071).
        self.printer = PrinterComboBox(self)
        if printer_query is not None:
            self.printer.search_field.setText(printer_query)
        self.printer.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.printer.setMinimumContentsLength(20)
        add_printer_choices(self.printer, self._known_printers())
        select_data(self.printer, settings.printer or profiles.DEFAULT_PRINTER)
        self.printer.setToolTip(self.printer.currentText())
        self.printer.currentTextChanged.connect(self.printer.setToolTip)
        # Die Materialliste folgt dem Verfahren des Druckers: Ein Harzdrucker
        # bietet Harze an, ein Filamentdrucker Filamente — PLA in einem
        # Harzbad wäre eine Vorgabe, die kein Projekt je drucken kann (RM-071).
        self.material = QComboBox(self)
        self._fill_materials(settings.material or profiles.DEFAULT_MATERIAL)
        self.printer.currentIndexChanged.connect(
            lambda _index: self._fill_materials(str(self.material.currentData() or ""))
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel, self
        )
        button_layout = buttons.layout()
        assert button_layout is not None
        button_layout.setSpacing(SPACE)
        # Speichern ist die Handlung dieses Fensters, also trägt sie den
        # Akzent — ausdrücklich. Qt gab ihn beim ersten ``show()`` ohnehin an
        # denselben Knopf, aber ohne die halbfette Schrift daneben, und Farbe
        # allein ist keine zweite Kodierung (Regel 18).
        self.save = buttons.button(QDialogButtonBox.StandardButton.Save)
        assert self.save is not None
        make_primary(self.save)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        content = QWidget(self)
        form_layout = QVBoxLayout(content)
        form_layout.setContentsMargins(0, 0, 0, 0)
        form_layout.setSpacing(WIDE)
        form_layout.addWidget(self._application_group(titles))
        form_layout.addWidget(self._project_group(titles))
        form_layout.addStretch(1)
        self._scroll = DialogScrollArea(self)
        self._scroll.setWidget(content)
        self._scroll.contentSizeChanged.connect(self._fit_soon)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        layout.addWidget(self._scroll, 1)
        layout.addWidget(buttons)
        for choice in self.findChildren(QComboBox) + self.findChildren(QSpinBox):
            wheel_needs_focus(choice)
        # Zwei Abschnitte, drei Formulare — und jedes rechnete seine
        # Beschriftungsspalte für sich: Die Felder begannen oben bei 148 und
        # unten bei 70 Punkten, gemessen am gebauten Dialog (Befund B11). Die
        # Spalte setzen die Zeilen, die offen dastehen; hinter „Weitere
        # Einstellungen“ bricht eine längere Beschriftung um (RM-518).
        align_to_the_front((self._application_form, self._project_form), self._advanced_form)
        self._natural_advanced_width = self._reserve_advanced_width()
        heading = self.advanced.findChild(QToolButton)
        assert heading is not None
        heading.toggled.connect(self._fit_explicit_soon)
        tab_order = (
            self.language,
            self.unit,
            self.theme,
            self.updates,
            self.slicer,
            self.slicer_file,
            heading,
            self.navigation,
            self.spacemouse,
            self.spacemouse_speed,
            self.spacemouse_invert,
            self.shortcuts,
            self.diff_palette,
            self.auto_accept,
            self.ai_disclosure_reset,
            self.remote,
            self.remote_port,
            self.printer,
            self.search_again,
            self.material,
        )
        for before, after in pairwise(tab_order):
            QWidget.setTabOrder(before, after)
        for form in self.findChildren(QFormLayout):
            for row in range(form.rowCount()):
                field_item = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
                editor = field_item.widget() if field_item is not None else None
                label = label_item.widget() if label_item is not None else None
                if editor is not None and isinstance(label, QLabel) and label.text():
                    label.setBuddy(editor)
                    if not editor.accessibleName():
                        editor.setAccessibleName(label.text())
        self.printer.currentIndexChanged.connect(self._printer_choice_changed)
        self._slicer_changed()
        self._find_slicers()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt-Name
        super().showEvent(event)
        self._fit_initial_soon()
        if self._shown_option is not None:
            QTimer.singleShot(0, self, self._reach_the_shown_option)

    def show_option(self, key: str) -> None:
        """Öffnet den Dialog bei einer Zeile — der Weg aus der Befehlspalette.

        Liegt sie hinter „Weitere Einstellungen", klappt der Bereich auf; das
        Feld bekommt den Fokus und wird nach dem Anzeigen ins Bild gerollt.
        Ist es gesperrt, weil ein Haken darüber aus ist (der Port ohne
        Fernsteuerung), bekommt dieser Haken den Fokus — er ist der Weg.
        """
        widget = getattr(self, key, None) if key in option_titles() else None
        if not isinstance(widget, QWidget):
            return
        more = self._advanced_form.parentWidget()
        if more is not None and more.isAncestorOf(widget):
            open_section(more)
        gate = _GATES.get(key)
        if not widget.isEnabled() and gate is not None:
            widget = getattr(self, gate)
        self._shown_option = widget
        widget.setFocus(Qt.FocusReason.OtherFocusReason)
        if self.isVisible():
            QTimer.singleShot(0, self, self._reach_the_shown_option)

    def _reach_the_shown_option(self) -> None:
        if self._shown_option is not None:
            self._scroll.ensureWidgetVisible(self._shown_option)
            self._shown_option.setFocus(Qt.FocusReason.OtherFocusReason)

    def _fit_soon(self) -> None:
        QTimer.singleShot(0, self, self._fit_content)

    def _fit_initial_soon(self) -> None:
        QTimer.singleShot(0, self, self._fit_initial_content)

    def _fit_explicit_soon(self) -> None:
        QTimer.singleShot(0, self, self._fit_explicit_content)

    def _fit_content(self) -> None:
        """Nachgereichte Inhalte vergrößern den Rahmen höchstens, nie zurück (RM-487)."""
        self._height.fit(self, self._scroll, intent="passive")

    def _fit_initial_content(self) -> None:
        """Misst den Dialog einmal mit der breitesten eingeklappten Zeile."""
        self._natural_advanced_width = self._reserve_advanced_width()
        self._height.fit(
            self,
            self._scroll,
            grow_width=True,
            intent="initial",
            natural_width=self._natural_advanced_width,
        )

    def _fit_explicit_content(self) -> None:
        """Die Klappe darf nur bei einer automatischen Größe Höhe ändern."""
        self._height.fit(self, self._scroll, intent="explicit")

    def _reserve_advanced_width(self) -> int:
        """Die natürliche Fensterbreite samt der zugeklappten Zusatzzeilen."""
        return max(
            self.sizeHint().width(),
            self.minimumWidth(),
            expanded_width(self._scroll, self._advanced_form),
        )

    def _application_group(self, titles: Mapping[str, str]) -> QWidget:
        # **Eine Abschnittsform in allen Dialogen** (RM-518): die flache
        # Überschrift der Druckeinstellungen statt eines gerahmten Kastens.
        box = QWidget(self)
        form = QFormLayout(box)
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(NORMAL)
        form.setHorizontalSpacing(NORMAL)
        # **Eine Zeilenform für alle Zeilen.** Mit ``WrapLongRows`` stand die
        # Beschriftung von „Slicer" und „Navigation" über ihrem Feld, die der
        # übrigen daneben — zwei Formen in einem Dialog. Der Dialog wird dafür
        # so breit, wie seine breiteste Zeile es verlangt.
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        form.addRow(titles["language"], self.language)
        form.addRow(titles["unit"], self.unit)
        form.addRow(titles["theme"], self.theme)
        form.addRow("", self.updates)
        # **Der Slicer gilt der Anwendung, nicht dem nächsten Projekt**: Er
        # rechnet jede Druckdatei, auch die des offenen Projekts. Er steht
        # zuletzt in dieser Gruppe und damit unmittelbar vor den Druckern, die
        # aus ihm kommen.
        slicer_row = QWidget(box)
        slicer_layout = QHBoxLayout(slicer_row)
        slicer_layout.setContentsMargins(0, 0, 0, 0)
        slicer_layout.setSpacing(NORMAL)
        slicer_layout.addWidget(self.slicer, 1)
        slicer_layout.addWidget(self.slicer_file)
        form.addRow(titles["slicer"], slicer_row)
        form.addRow(self.slicer_state)
        form.addRow(self.slicer_progress)
        more = QWidget(box)
        details = QFormLayout(more)
        details.setContentsMargins(0, 0, 0, 0)
        details.setVerticalSpacing(NORMAL)
        details.setHorizontalSpacing(NORMAL)
        details.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        # Was zusammengehört, steht beisammen: erst die Kamera (Navigation,
        # 3D-Maus), dann die Tasten, das Bild, der Chat, die Fernsteuerung.
        details.addRow(titles["navigation"], self.navigation)
        details.addRow("", self.spacemouse)
        details.addRow(titles["spacemouse_speed"], self.spacemouse_speed)
        details.addRow("", self.spacemouse_invert)
        details.addRow(titles["shortcuts"], self.shortcuts)
        details.addRow(titles["diff_palette"], self.diff_palette)
        details.addRow("", self.auto_accept)
        details.addRow(tr("KI-Hinweis"), self.ai_disclosure_reset)
        details.addRow("", self.remote)
        details.addRow(titles["remote_port"], self.remote_port)
        for row in (self.spacemouse, self.spacemouse_speed, self.spacemouse_invert):
            details.setRowVisible(row, self.settings.spacemouse_seen)
        # Zugeklappt nennt der Bereich, was in ihm steht, und er merkt sich,
        # wie der Kunde ihn verließ (RM-491).
        contents = (
            tr(
                "Navigation, 3D-Maus, Tastenbelegung, Differenzansicht, Chat, "
                "KI-Hinweis, Fernsteuerung"
            )
            if self.settings.spacemouse_seen
            else tr("Navigation, Tastenbelegung, Differenzansicht, Chat, KI-Hinweis, Fernsteuerung")
        )
        self.advanced = collapsible(
            tr("Weitere Einstellungen"),
            more,
            open_now=False,
            contents=contents,
            remember="settings.more",
        )
        self._advanced_form = details
        self._application_form = form
        form.addRow(self.advanced)
        return collapsible(tr("Anwendung"), box)

    def _project_group(self, titles: Mapping[str, str]) -> QWidget:
        box = QWidget(self)
        form = QFormLayout(box)
        form.setContentsMargins(0, 0, 0, 0)
        form.setVerticalSpacing(NORMAL)
        form.setHorizontalSpacing(NORMAL)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.DontWrapRows)
        note = QLabel(
            tr(
                "Diese Werte gelten für das nächste neue Projekt. Drucker und Material "
                "eines offenen Projekts ändert die Druckvorbereitung."
            ),
            box,
        )
        note.setWordWrap(True)
        form.addRow(note)
        form.addRow(titles["printer"], self.printer)
        form.addRow(self.printer_choice_state)
        form.addRow(self.printer_state)
        form.addRow(self.search_progress)
        form.addRow(self.search_again)
        form.addRow(titles["material"], self.material)
        self._project_form = form
        return collapsible(tr("Vorgaben für neue Projekte"), box)

    @property
    def slicer_path(self) -> str:
        """Noch ungespeicherte Wahl; auch beim Sprachwechsel bleibt sie im Entwurf."""
        return str(self.slicer.currentData() or "")

    @property
    def discovered_printers(self) -> Mapping[str, PrinterProfile]:
        """Ungespeicherte Slicerprofile für den nächsten Sprach-Entwurf."""
        return self._discovered_printers

    @property
    def printer_query(self) -> str | None:
        """Die getrennte Suche reist beim Sprachwechsel mit der bestätigten Wahl."""
        return self.printer.search_field.text() or None

    def _known_printers(self) -> dict[str, PrinterProfile]:
        return dict(profiles.printer_profiles()) | self._discovered_printers

    def save_external_choices(self) -> None:
        """Nur Speichern übernimmt das gewählte fremde Profil und den Programmpfad."""
        chosen = str(self.printer.currentData() or "")
        profile = self._discovered_printers.get(chosen)
        try:
            if profile is not None and profiles.printer_profiles().get(chosen) != profile:
                profiles.save_printer(profile)
            if not discover.same_program(discover.remembered_path("slicer"), self.slicer_path):
                discover.remember_path("slicer", self.slicer_path)
        except OSError as problem:
            raise FileWriteError(detail=str(problem), suggestions=(RETRY, CANCEL)) from problem

    def _find_slicers(self) -> None:
        worker = _SlicerWorker()
        worker.done.connect(self._slicers_found)
        worker.crashed.connect(self._slicers_failed)
        self._slicer_worker = worker
        self._leash.start(worker)
        self._search_state()

    def _slicers_found(self, found: object) -> None:
        if self._closed or self.sender() is not self._slicer_worker:
            return
        self._slicer_worker = None
        chosen = discover.program_path(self.slicer_path)
        discovered = tuple(found) if isinstance(found, tuple | list) else ()
        paths = dict.fromkeys((*discovered, *((Path(chosen),) if chosen else ())))
        with QSignalBlocker(self.slicer):
            self.slicer.clear()
            self.slicer.addItem(tr("Später auswählen"), "")
            for path in paths:
                self.slicer.addItem(slicer_title(Path(path)), str(path))
                self.slicer.setItemData(
                    self.slicer.count() - 1, str(path), Qt.ItemDataRole.ToolTipRole
                )
            select_program(self.slicer, chosen)
        self.slicer_state.setText(
            ""
            if paths
            else tr(
                "Kein Slicer gefunden. Wählen Sie über „Benutzerdefiniert …“ "
                "das installierte Programm aus."
            )
        )
        self._search_state()
        self._fit_soon()

    def _slicers_failed(self, detail: str) -> None:
        if self._closed or self.sender() is not self._slicer_worker:
            return
        _log.warning("settings slicer search crashed: %s", detail)
        self._slicers_found(())

    def _choose_slicer_file(self) -> None:
        choose_slicer_file(self, self.slicer)

    def _slicer_changed(self) -> None:
        self._printer_survey = None
        self.search_again.hide()
        if not self.slicer_path:
            self._fill_printers(tuple(profiles.printer_profiles()))
            self.printer_state.clear()
        else:
            self.printer.setEnabled(False)
            self.material.setEnabled(False)
            self.printer_state.setText(tr("Drucker des gewählten Slicers werden gesucht …"))
            worker = _PrinterSurvey(Path(self.slicer_path))
            worker.done.connect(self._printers_found)
            worker.crashed.connect(self._printers_failed)
            self._printer_survey = worker
            self._leash.start(worker)
        self._search_state()
        self._fit_soon()

    def _search_state(self) -> None:
        pending = self._printer_survey is not None
        valid = valid_printer_choice(self.printer)
        choice_reason = tr("Wählen Sie einen Drucker aus der Liste.") if not valid else ""
        self.printer_choice_state.setText(choice_reason)
        self.printer_choice_state.setVisible(not pending and bool(choice_reason))
        reason = self.printer_state.text() if pending else choice_reason
        self.save.setEnabled(not pending and valid)
        self.save.setToolTip(reason)
        self.save.setAccessibleDescription(reason)
        self.search_progress.setVisible(pending)
        self.search_progress.setAccessibleName(reason or self.printer_state.text())
        self.slicer_progress.setVisible(self._slicer_worker is not None)
        self.slicer_progress.setAccessibleName(self.slicer_state.text())
        self.slicer_state.setVisible(bool(self.slicer_state.text()))
        self.printer_state.setVisible(bool(self.printer_state.text()))

    def _printer_choice_changed(self) -> None:
        if self._closed:
            return
        self._fill_materials(str(self.material.currentData() or ""))
        self._search_state()
        self._fit_soon()

    def _fill_printers(self, identifiers: tuple[str, ...], suggested: str = "") -> None:
        known = self._known_printers()
        allowed = allowed_printers(identifiers, known)
        preferred, self._suggested_printer = preferred_printer(
            str(self.printer.currentData() or ""), suggested, self._suggested_printer, allowed
        )
        with QSignalBlocker(self.printer):
            self.printer.clear()
            add_printer_choices(
                self.printer, {name: entry for name, entry in known.items() if name in allowed}
            )
            select_data(self.printer, preferred)
        self.printer.setEnabled(True)
        self.printer.setToolTip(self.printer.currentText())
        self.material.setEnabled(True)
        self._fill_materials(str(self.material.currentData() or ""))

    def _printers_found(self, found: object) -> None:
        if self._closed or self.sender() is not self._printer_survey:
            return
        assert isinstance(found, PrinterChoices)
        if not discover.same_program(str(found.executable), self.slicer_path):
            # Nie still verwerfen: Eine Suche ohne Antwort sperrt „Speichern“
            # für immer (RM-335).
            self._slicer_changed()
            return
        self._printer_survey = None
        self._discovered_printers = {profile.id: profile for profile in found.profiles}
        self._fill_printers(found.identifiers, found.suggested)
        self.printer_state.setText(
            ""
            if found.translated and found.profiles
            else tr(
                "Keine passenden Druckerprofile gefunden. Prüfen Sie die Drucker im Slicer "
                "oder wählen Sie einen anderen Slicer."
            )
        )
        self._search_state()
        self.search_again.setVisible(not found.profiles)
        self._fit_soon()

    def _printers_failed(self, detail: str) -> None:
        if self._closed or self.sender() is not self._printer_survey:
            return
        _log.warning("settings printer survey crashed: %s", detail)
        self._printer_survey = None
        self._fill_printers(tuple(profiles.user_printer_profiles()))
        self.printer_state.setText(
            tr(
                "Drucker konnten nicht gelesen werden. Wählen Sie einen anderen Slicer "
                "oder versuchen Sie es erneut."
            )
        )
        self._search_state()
        self.search_again.show()
        self._fit_soon()

    def accept(self) -> None:
        """Speichern übernimmt erst die sichtbare, fertig gelesene Druckerwahl."""
        if self._printer_survey is None and valid_printer_choice(self.printer):
            super().accept()

    def done(self, result: int) -> None:
        self._closed = True
        super().done(result)

    def wait_for_survey(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> bool:
        """Die Erhebung zustellen, ohne beim normalen Schließen darauf zu warten."""
        self._leash.wait_all(timeout_ms)
        QCoreApplication.processEvents()
        return self._slicer_worker is None and self._printer_survey is None

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        self._closed = True
        self._leash.wait_all(timeout_ms)

    def _language_changed(self) -> None:
        """Fordert den Neuaufbau mit den ungespeicherten Antworten in der neuen Sprache an."""
        chosen = str(self.language.currentData())
        if chosen and chosen != self.settings.language:
            self.done(LANGUAGE_CHANGED)

    def apply_to(self, settings: UiSettings) -> UiSettings:
        """Schreibt die Antworten zurück. Nur beim Annehmen aufgerufen."""
        settings.language = str(self.language.currentData())
        settings.display_unit = str(self.unit.currentData())
        settings.theme = str(self.theme.currentData())
        settings.navigation = str(self.navigation.currentData())
        settings.diff_palette = str(self.diff_palette.currentData())
        settings.shortcut_scheme = str(self.shortcuts.currentData())
        chosen_slicer = self.slicer_path
        if forgets_slicer_profiles(
            self._stored_slicer_path, chosen_slicer, settings.slicer_profile_slicer
        ):
            settings.slicer_machine_profile = ""
            settings.slicer_base_process = ""
            settings.slicer_base_filament = ""
            settings.slicer_bed_plate = ""
            settings.slicer_profile_printer = ""
            settings.slicer_filament_per_material.clear()
            settings.slicer_profile_slicer = chosen_slicer
        settings.check_for_updates = self.updates.isChecked()
        settings.auto_accept_reversible = self.auto_accept.isChecked()
        if self._reset_ai_disclosure:
            clear_disclosure(settings)
        settings.remote_enabled = self.remote.isChecked()
        settings.remote_port = int(self.remote_port.value())
        settings.spacemouse_enabled = self.spacemouse.isChecked()
        settings.spacemouse_speed = int(self.spacemouse_speed.value())
        settings.spacemouse_invert = self.spacemouse_invert.isChecked()
        settings.printer = (
            str(self.printer.currentData()) if valid_printer_choice(self.printer) else ""
        )
        if settings.printer:
            settings.material = profiles.material_for(
                settings.printer, str(self.material.currentData())
            )
        return settings

    def _fill_materials(self, wanted: str) -> None:
        """Nur die Materialien des gewählten Verfahrens, das bisherige gewählt,
        wo es passt — sonst die Vorgabe des Verfahrens."""
        if not valid_printer_choice(self.printer):
            self.material.setEnabled(False)
            return
        self.material.setEnabled(self._printer_survey is None)
        printer_id = str(self.printer.currentData() or "")
        printer = self._known_printers().get(printer_id)
        with QSignalBlocker(self.material):
            self.material.clear()
            for key, entry in by_title(profiles.material_profiles()):
                if printer is None or entry.fits(printer):
                    self.material.addItem(str(entry.title), key)
            material_printer = (
                profiles.DEFAULT_RESIN_PRINTER
                if printer is not None and printer.is_resin
                else profiles.DEFAULT_PRINTER
            )
            select_data(self.material, profiles.material_for(material_printer, wanted))

    def _reset_disclosure(self) -> None:
        """Merkt die Wahl bis zum Speichern; Abbrechen verändert noch nichts."""

        self._reset_ai_disclosure = True
        self.ai_disclosure_reset.setEnabled(False)
        self.ai_disclosure_reset.setText(tr("Wird vor der nächsten KI-Anfrage angezeigt"))
        self.ai_disclosure_reset.setAccessibleName(self.ai_disclosure_reset.text())


def forgets_slicer_profiles(stored: str, chosen: str, profile_slicer: str) -> bool:
    """Ob Speichern die gemerkten Slicerprofile verwirft.

    Nur wenn in diesem Dialog ein anderer Slicer gewählt wurde als der, für den
    die Profile gelten. Der Druckdialog merkt Profile auch für einen nur
    gefundenen, nie gespeicherten Slicer; wer danach allein das Thema änderte
    oder genau diesen Slicer wählte, verlor sie (RM-337).
    """
    if discover.same_program(stored, chosen):
        return False
    return not profile_slicer or not discover.same_program(profile_slicer, chosen)


def _choices(parent: QWidget, entries: Mapping[str, str | TranslatableText]) -> QComboBox:
    """Ein Aufklappmenü, das Namen zeigt und Kennungen weitergibt.

    Nimmt beides an: eine fertige Zeichenkette und einen ``TranslatableText``,
    der seine Sprache erst hier sucht. Die Listen über dem Dialog sind lazy,
    weil sie beim Import noch keine Sprache haben (siehe dort).
    """
    box = QComboBox(parent)
    box.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    box.setMinimumContentsLength(20)
    for key, label in entries.items():
        box.addItem(str(label), key)
    return box
