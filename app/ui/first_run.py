"""Der erste Start (Bauplan §38).

Sprache, Slicer, dessen Drucker, ein Blick auf die externen Programme und der
Zugang für den Chat. Die Filamente folgen im Filamentlager. Alles überspringbar, alles
später wieder erreichbar — ein Assistent, der zu Ende gebracht werden muss,
bevor irgendetwas geht, ist eine Wand, kein Willkommen.

Der Chat steht mit im Dialog, weil er das Versprechen ist, mit dem die
Anwendung antritt — und weil ein neuer Nutzer weder einen Schlüssel noch ein
laufendes Ollama mitbringt. Der einzige andere Weg dorthin ist ein Knopf in
einem Panel, das er noch nie gesehen hat.

Er endet dort, wo der Bauplan die ersten fünf Minuten enden lässt (§2.3): beim
ersten Import. Die letzte Seite sagt darum nicht „fertig", sie bietet an, ein
Modell zu öffnen.

**Nachgesehen wird in einem Arbeiter.** Der Dialog brauchte gemessen 1,88
Sekunden, bis er auf dem Bildschirm stand — das Allererste, was ein Kunde von
Solidon sieht, kam fast zwei Sekunden zu spät. Vier Dinge liefen dafür im
Oberflächen-Thread: die Suche nach den vier Programmen, das Auslesen des
Slicer-Profils, die Frage an Ollama über HTTP und die Prüfung der optionalen
Pakete. Keines davon muss fertig sein, damit der Dialog erscheint; er zeigt
jetzt sofort seine Fragen und trägt die Antworten nach.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import QCoreApplication, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QStandardItemModel
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME
from app.core import activation, discover, tools
from app.core.activation import TRIAL_DAYS
from app.core.backends import llm
from app.core.errors import AppError
from app.core.export import slicer_profiles
from app.core.export.handover import detect
from app.core.knowledge import profiles
from app.core.log import get_logger
from app.core.types import PrinterProfile, PrintTechnology
from app.i18n import format_decimal, language_name, set_language, tr
from app.i18n.catalog import available_languages, install_language
from app.ui.icons import icon
from app.ui.labels import NumberSpin, by_title, deadline_date
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.settings import UiSettings
from app.ui.style import NORMAL, ROOMY, TIGHT, WIDE, make_primary, set_level

_log = get_logger(__name__)

#: Der Zustand jedes Programms steht als Wort in der Zeile, damit sich die
#: Liste auch ohne Farbe liest (§19.1). Vorher stand dort ein Plus- und ein
#: ein Minuszeichen — beides kurz, beides zu raten. In der einzigen Liste,
#: die jemand beim allerersten Start zu lesen bekommt, ist das ein schlechter
#: Tausch für zwei gesparte Zeichen.
#:
#: Das Wort ist geblieben, und ein Zeichen steht jetzt daneben — nicht statt
#: seiner. Beides zusammen ist, was Regel 18 verlangt: die Form trägt die
#: Bedeutung mit, das Wort bleibt lesbar.


@dataclass(frozen=True, slots=True)
class Findings:
    """Was auf diesem Rechner liegt — in einem Durchgang erhoben.

    Programme und Chat-Zugang sind für den sofortigen Dialogaufbau nicht nötig.
    Druckervorgaben gehören zur anschließenden, ausdrücklichen Slicerwahl.
    """

    tools: tuple[tools.ToolState, ...]
    chat: str
    slicers: tuple[Path, ...] = ()


class _Survey(Worker):
    """Die Erhebung: Programme suchen und den Chat-Zugang prüfen.

    Kein Abbrechen — es gibt nichts zu bereuen, sie schreibt nichts. Wer den
    Dialog vorher schließt, wartet über die Halteleine auf sie.
    """

    done = Signal(object)

    def work(self) -> None:
        self.done.emit(
            Findings(
                tools=tools.survey(),
                chat=_chat_text(),
                slicers=discover.find_programs("slicer", tools.SLICERS),
            )
        )


@dataclass(frozen=True, slots=True)
class CustomPrinterDraft:
    """Ein noch ungespeicherter eigener Drucker, wie er beim Sprachwechsel
    von einem Dialog in den nächsten reist.

    Die Verfahrensfelder reisen beide mit, gleich welches gewählt ist: Wer
    zwischen FDM und Resin hin- und herschaltet, findet seine Zahlen wieder.
    """

    identifier: str
    name: str
    dimensions: tuple[float, float, float]
    technology: PrintTechnology
    nozzle: float
    nozzles: int
    pixel_size: float
    minimum_wall: float
    layer_height: float = 0.0
    """Die eingetragene Schichthöhe; null heißt abgeleitet."""


#: Woran ein Gruppenkopf in der Druckerliste zu erkennen ist — kein Drucker,
#: nicht wählbar, nur die Überschrift des Verfahrens darunter.
_GROUP_HEADER = "__group__"

#: Die Reihenfolge der Gruppen. FDM zuerst, weil es die häufigere Wahl ist;
#: ein Resin-Kunde findet seine Gruppe darunter.
_TECHNOLOGY_ORDER: tuple[PrintTechnology, ...] = ("fdm", "resin")


def _group_title(technology: PrintTechnology) -> str:
    """Der Kopf über einer Gruppe — derselbe Satz wie in der Verfahrenswahl."""
    return tr("Resin — Harz") if technology == "resin" else tr("FDM — Filament")


@dataclass(frozen=True, slots=True)
class PrinterChoices:
    """Die belegten Drucker eines bestimmten Slicers."""

    executable: Path
    identifiers: tuple[str, ...]
    suggested: str
    translated: bool = True
    """Ob Solidon die Profile dieses Programms überhaupt liest. Ein
    Programm ohne Familie (``other``) nennt keine Drucker — nicht, weil dort
    keine wären, sondern weil Solidon seinen Bestand nicht kennt."""


class _PrinterSurvey(Worker):
    """Liest die Druckerprofile außerhalb des Oberflächen-Threads."""

    done = Signal(object)

    def __init__(self, executable: Path) -> None:
        super().__init__()
        self.executable = executable

    def work(self) -> None:
        flavour = detect(self.executable).flavour
        known = profiles.printer_profiles()
        names = slicer_profiles.known_printers(flavour, self.executable)
        identifiers = tuple(
            sorted(
                {
                    identifier
                    for name in names
                    if (identifier := slicer_profiles.printer_for(name, known))
                }
                | set(profiles.user_printer_profiles())
            )
        )
        suggested = slicer_profiles.printer_for(
            slicer_profiles.chosen_machine(flavour, self.executable), known
        )
        self.done.emit(
            PrinterChoices(self.executable, identifiers, suggested, translated=flavour != "other")
        )


class ToolRow(QWidget):
    """Ein externes Programm: Zeichen, Zustand, Name, wofür es gut ist.

    Vorher war die ganze Liste **ein** mehrzeiliges Label — zwanzig Zeilen
    Fließtext mit vollständigen Installationspfaden, als Erstes, was ein neuer
    Nutzer von der Anwendung zu lesen bekam. Der Pfad beantwortet keine Frage,
    die beim ersten Start jemand hat; er steht jetzt im Hinweis darüber, wo er
    denjenigen erreicht, der ihn sucht.
    """

    def __init__(self, state: tools.ToolState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        symbol = QLabel(self)
        name = "done" if state.available else "severity-info"
        symbol.setPixmap(icon(name, self).pixmap(16, 16))

        if state.available:
            status = tr("bereit") if state.tool.kind == "service" else tr("gefunden")
        elif state.installed:
            status = tr("installiert")
        else:
            status = tr("nicht eingerichtet")
        word = QLabel(status, self)
        set_level(word, "caption")

        what = QLabel(f"{state.tool.title} — {state.tool.what_for}", self)
        what.setWordWrap(True)

        # Der Pfad, oder der Satz, der sagt, was weiterhilft: ein Dienst muss
        # laufen, ein Programm an ungewöhnlicher Stelle wird angegeben.
        where = str(state.path) if state.available else str(state.explain())
        self.setToolTip(where)

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(NORMAL)
        row.addWidget(symbol)
        row.addWidget(word)
        row.addWidget(what, stretch=1)


#: Der Dialog hat sich für einen Sprachwechsel geschlossen und will neu
#: aufgebaut werden.
#:
#: Qt vergibt 0 für *Rejected* und 1 für *Accepted*; alles darüber steht dem
#: Aufrufer frei. Ein eigener Code statt eines Merkmals am Dialog, weil
#: ``exec()`` genau eine Zahl zurückgibt und der Aufrufer sonst zwei Dinge
#: fragen müsste, von denen er eines vergessen kann.
LANGUAGE_CHANGED = 2


class FirstRunDialog(QDialog):
    """Eine Seite mit den zwei Grundlagen und den optionalen Erweiterungen."""

    importRequested = Signal()
    inventoryRequested = Signal()

    def __init__(self, settings: UiSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("Erste Schritte"))
        self.setMinimumWidth(680)

        # Der Testlauf steht hier in einem Satz und mehr nicht: die
        # Ersteinrichtung fragt nach keinem Schlüssel — das wäre eine Hürde
        # vor dem ersten Blick (Konzept V4b). In der Demo steht dort der
        # Stichtag, aus demselben Grund in einem Satz.
        #
        # **Und eine beschädigte Installation verspricht keine freien Tage**
        # (H4). Der Satz stand hier unabhängig vom Zustand: „Die ersten 14 Tage
        # ist alles frei", während ``unlocked`` schon in der ersten Sekunde
        # falsch war und jede Änderung absagte. Ein Virenscanner in Quarantäne
        # reicht dafür, und dann ist das der erste Satz, den ein neuer Kunde
        # liest. Der Wortlaut kommt aus derselben Quelle wie im Freischalt- und
        # im Über-Dialog (``InstallationDamaged``) — hier lokal geholt, weil
        # ``app.ui.dialogs`` ``app.core.scene`` nachzieht und dieser Dialog beim
        # Start gefragt wird.
        state = activation.state()
        if state.damaged:
            from app.ui.dialogs import damaged_line

            terms = damaged_line()
        elif state.in_demo:
            terms = tr(
                "Diese Demo läuft vollständig und ohne Schlüssel bis zum {date}; "
                "danach lässt sie sich nicht mehr starten. Ihre Projekte bleiben "
                "erhalten."
            ).format(date=deadline_date(state))
        elif state.sale_without_trial:
            terms = tr(
                "Diese Verkaufsversion startet ohne Testphase. Öffnen, Ansehen und "
                "Messen bleiben ohne Schlüssel möglich; zum Ändern und Ausgeben "
                "brauchen Sie einen Lizenzschlüssel und die einmalige Geräteaktivierung."
            )
        else:
            terms = tr(
                "Die ersten {days} Tage ist alles frei; danach bleiben Öffnen, "
                "Ansehen und Messen es."
            ).format(days=TRIAL_DAYS)
        title = QLabel(tr("Willkommen bei {app}").format(app=APP_NAME), self)
        set_level(title, "title")
        self.greeting = QLabel(
            tr(
                "Wählen Sie zuerst Ihren Slicer und danach Ihren Drucker. "
                "Ihre Filamente können Sie anschließend im Filamentlager einrichten."
            ),
            self,
        )
        self.greeting.setWordWrap(True)
        self.terms = QLabel(terms, self)
        self.terms.setWordWrap(True)
        set_level(self.terms, "caption")

        self.language = QComboBox(self)
        # Der Name, nicht das Kürzel: „de" stand hier als allererste Angabe, die
        # ein neuer Benutzer zu sehen bekam.
        for entry in available_languages():
            self.language.addItem(language_name(entry), entry)
        self.language.setCurrentIndex(self.language.findData(settings.language))
        # **Und sie wirkt erst beim nächsten Start.** Der Einstellungsdialog sagt
        # das seit je, hier stand es nicht — an der Stelle, an der eine andere
        # Sprache am ehesten gewählt wird: Wer beim ersten Start „Español"
        # einstellt und danach eine deutsche Oberfläche vor sich hat, hält die
        # Einstellung für wirkungslos, nicht für aufgeschoben. Derselbe Satz und
        # derselbe Auslöser wie dort, damit beide Stellen dasselbe versprechen.
        self.language.currentIndexChanged.connect(self._language_changed)

        self.slicer = QComboBox(self)
        self.slicer.addItem(tr("Später auswählen"), "")
        remembered = discover.remembered_path("slicer")
        if remembered:
            self.slicer.addItem(Path(remembered).stem, remembered)
            self.slicer.setCurrentIndex(1)
        self.slicer.setAccessibleName(tr("Slicer"))
        self.slicer.currentIndexChanged.connect(self._slicer_changed)
        self.slicer_file = QPushButton(tr("Benutzerdefiniert …"), self)
        self.slicer_file.setIcon(icon("open", self.slicer_file))
        self.slicer_file.setToolTip(tr("Slicer-Programm auswählen"))
        self.slicer_file.clicked.connect(self._choose_slicer_file)
        slicer_row = QHBoxLayout()
        slicer_row.addWidget(self.slicer, 1)
        slicer_row.addWidget(self.slicer_file)
        self.printer_state = QLabel("", self)
        self.printer_state.setWordWrap(True)
        set_level(self.printer_state, "caption")
        self._printer_survey: _PrinterSurvey | None = None

        self.printer = QComboBox(self)
        for identifier, printer in by_title(profiles.printer_profiles()):
            self._insert_printer_choice(str(printer.title), identifier)
        self._insert_printer_choice(tr("Benutzerdefiniert …"), "__custom__")
        self._group_printers()
        # Erst die Slicerwahl startet das Lesen seiner Druckerprofile. Bis
        # dahin bleibt die gespeicherte Vorgabe stehen; fremde Installationen
        # liefern weder einen Drucker noch ein Material für diese Auswahl.
        self._suggested_printer = settings.printer or profiles.DEFAULT_PRINTER
        _select(self.printer, self._suggested_printer)
        self.printer.currentIndexChanged.connect(self._printer_changed)
        self._custom_identifier = "user-" + uuid4().hex
        self.custom_printer = QWidget(self)
        custom_form = QFormLayout(self.custom_printer)
        custom_form.setContentsMargins(0, 0, 0, 0)
        self.printer_name = QLineEdit(self.custom_printer)
        self.printer_name.setPlaceholderText(tr("Name Ihres Druckers"))
        custom_form.addRow(tr("Name"), self.printer_name)
        # Das Verfahren entscheidet, welche Maße darunter gefragt werden:
        # Düse und Düsenzahl bei FDM, Pixelgröße und Mindestwand bei Resin
        # (Resin-Konzept §4). Ein Feld, das für das gewählte Verfahren
        # nichts bedeutet, steht nicht da.
        self.printer_technology = QComboBox(self.custom_printer)
        self.printer_technology.addItem(tr("FDM — Filament"), userData="fdm")
        self.printer_technology.addItem(tr("Resin — Harz"), userData="resin")
        self.printer_technology.currentIndexChanged.connect(self._technology_changed)
        custom_form.addRow(tr("Verfahren"), self.printer_technology)
        self.printer_dimensions: list[NumberSpin] = []
        dimensions = QHBoxLayout()
        template = profiles.printer(profiles.DEFAULT_PRINTER)
        resin_template = profiles.printer(profiles.DEFAULT_RESIN_PRINTER)
        for label, value in zip(
            (tr("Breite"), tr("Tiefe"), tr("Höhe")), template.build_volume, strict=True
        ):
            field = NumberSpin(self.custom_printer)
            field.setRange(1, 100_000)
            field.setDecimals(2)
            field.setSuffix(" " + tr("mm"))
            field.setValue(value)
            field.setAccessibleName(label)
            dimensions.addWidget(QLabel(label, self.custom_printer))
            dimensions.addWidget(field)
            self.printer_dimensions.append(field)
        custom_form.addRow(tr("Bauraum"), dimensions)
        self.printer_nozzle = NumberSpin(self.custom_printer)
        self.printer_nozzle.setRange(0.05, 10)
        self.printer_nozzle.setDecimals(2)
        self.printer_nozzle.setSingleStep(0.1)
        self.printer_nozzle.setSuffix(" " + tr("mm"))
        self.printer_nozzle.setValue(template.nozzle_diameter)
        custom_form.addRow(tr("Düse"), self.printer_nozzle)
        # Wie viele davon: Eine Düse mit Wechselstation spült bei jedem
        # Filamentwechsel, und danach richtet sich, ob Filamente auf eigene
        # Platten kommen. Der Druckdialog führt dasselbe Feld.
        self.printer_nozzles = QSpinBox(self.custom_printer)
        self.printer_nozzles.setRange(1, 8)
        self.printer_nozzles.setValue(template.nozzles)
        self.printer_nozzles.setToolTip(
            tr(
                "Wie viele Düsen der Drucker zugleich führt. Eine Wechselstation zählt "
                "nicht dazu — sie spült bei jedem Filamentwechsel."
            )
        )
        custom_form.addRow(tr("Düsen"), self.printer_nozzles)
        self.printer_pixel = NumberSpin(self.custom_printer)
        self.printer_pixel.setRange(0.005, 1.0)
        self.printer_pixel.setDecimals(3)
        self.printer_pixel.setSingleStep(0.005)
        self.printer_pixel.setSuffix(" " + tr("mm"))
        self.printer_pixel.setValue(resin_template.pixel_size)
        self.printer_pixel.setToolTip(
            tr("Die Kantenlänge eines Bildpunkts — das kleinste Detail, das der Drucker abbildet.")
        )
        custom_form.addRow(tr("Pixelgröße"), self.printer_pixel)
        self.printer_wall = NumberSpin(self.custom_printer)
        self.printer_wall.setRange(0.05, 10.0)
        self.printer_wall.setDecimals(2)
        self.printer_wall.setSingleStep(0.1)
        self.printer_wall.setSuffix(" " + tr("mm"))
        self.printer_wall.setValue(resin_template.minimum_wall)
        self.printer_wall.setToolTip(
            tr("Die dünnste Wand, die dieses Harz nach Waschen und Härten stehen lässt.")
        )
        custom_form.addRow(tr("Mindestwand"), self.printer_wall)
        # **Die Schichthöhe, die die Website verspricht.** „Gebraucht werden
        # Bauraum und Schichthöhe" steht in den Fragen auf der Startseite, und
        # das Formular hatte kein Feld dafür: FDM leitete sie aus der Düse ab,
        # Resin nahm die Vorlage. Leer bleibt genau das — und das Feld nennt
        # den abgeleiteten Wert, statt leer zu schweigen.
        self.printer_layer = NumberSpin(self.custom_printer)
        self.printer_layer.setRange(0.0, 1.0)
        self.printer_layer.setDecimals(3)
        self.printer_layer.setSingleStep(0.01)
        self.printer_layer.setSuffix(" " + tr("mm"))
        self.printer_layer.setValue(0.0)
        self.printer_layer.setToolTip(
            tr(
                "Leer lassen, dann gilt der gezeigte Wert. Bei Filament wählen die "
                "Druckeinstellungen die Schichthöhe je Qualitätsstufe."
            )
        )
        self.printer_layer.setAccessibleName(tr("Schichthöhe"))
        self.printer_layer.setAccessibleDescription(self.printer_layer.toolTip())
        self.printer_nozzle.valueChanged.connect(self._name_derived_layer)
        custom_form.addRow(tr("Schichthöhe"), self.printer_layer)
        self._technology_rows = {
            "fdm": (self.printer_nozzle, self.printer_nozzles),
            "resin": (self.printer_pixel, self.printer_wall),
        }
        self._technology_changed()
        self.custom_printer.hide()

        basics = QGroupBox(tr("Grundlagen"), self)
        form = QFormLayout(basics)
        form.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        basics_hint = QLabel(
            tr("Diese Vorgaben gelten für neue Projekte und lassen sich jederzeit ändern."),
            basics,
        )
        basics_hint.setWordWrap(True)
        set_level(basics_hint, "caption")
        form.addRow(basics_hint)
        form.addRow(tr("Sprache"), self.language)
        form.addRow(tr("Slicer"), slicer_row)
        form.addRow(tr("Drucker"), self.printer)
        form.addRow(self.custom_printer)
        form.addRow(self.printer_state)
        # **Der Ausweg für alle, die ihr Gerät nicht finden.** Die Liste nennt
        # die verbreiteten Maschinen; wer einen Artillery oder Qidi hat, stand
        # vorher vor der Frage, ob der allgemeine Eintrag für ihn gilt — und
        # riet. Er gilt, und was ihn vom eigenen Gerät unterscheidet, sind zwei
        # Werte, die sich ändern lassen (§2.4: eine gute Vorgabe schlägt eine
        # Einstellmöglichkeit, aber nur, wenn man ihr trauen kann).
        #
        # „Maße" und nicht „Bauraum und Düse": Ein eigener Resin-Drucker fragt
        # Pixelgröße und Mindestwand, eine Düse hat er nicht (RM-071).
        printer_hint = QLabel(
            tr(
                "Ihr Drucker ist nicht dabei? Wählen Sie „Benutzerdefiniert“ "
                "und tragen Sie seinen Namen und seine Maße ein."
            ),
            basics,
        )
        printer_hint.setWordWrap(True)
        set_level(printer_hint, "caption")
        form.addRow(printer_hint)
        self.inventory_button = QPushButton(tr("Filamentlager öffnen …"), basics)
        self.inventory_button.setIcon(icon("open", self.inventory_button))
        self.inventory_button.clicked.connect(self._open_inventory)
        form.addRow(tr("Filamente"), self.inventory_button)

        optional = QGroupBox(tr("Optionale Erweiterungen"), self)
        optional_layout = QVBoxLayout(optional)
        optional_layout.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        optional_layout.setSpacing(NORMAL)
        optional_hint = QLabel(
            tr(
                "Slicer, Bildgenerierung und Chat erweitern Solidon. Zum Konstruieren "
                "und Bearbeiten brauchen Sie nichts davon. Filamentprofile aus Ihrem "
                "Slicer können Sie später im Filamentlager als eigene Spulen übernehmen."
            ),
            optional,
        )
        optional_hint.setWordWrap(True)
        set_level(optional_hint, "caption")
        optional_layout.addWidget(optional_hint)

        self.tools = QWidget(optional)
        self._tool_rows = QVBoxLayout(self.tools)
        self._tool_rows.setContentsMargins(0, 0, 0, 0)
        self._tool_rows.setSpacing(TIGHT)
        # **Der Platzhalter nennt, worauf er wartet.** Bis die Erhebung
        # antwortet, steht hier ein Satz und keine Behauptung über etwas, das
        # niemand nachgesehen hat — aber dreimal „Wird nachgesehen …"
        # untereinander sagte nicht, *was* nachgesehen wird. Der Name steht
        # sofort, nur der Zustand wandert nach.
        looking = QLabel(tr("Zusatzprogramme — wird nachgesehen …"), self.tools)
        set_level(looking, "caption")
        self._tool_rows.addWidget(looking)

        # **Diese Zeile trägt nur noch den Ausnahmefall.** Sie fasste zusammen,
        # was die Programmzeilen darüber einzeln nennen („Optional nicht
        # eingerichtet: ComfyUI" über einer Zeile „nicht eingerichtet ·
        # ComfyUI — …"); zweimal dasselbe liest sich wie zwei Auskünfte. Bleibt
        # sie leer, bleibt sie unsichtbar — sichtbar wird sie, wenn die
        # Erhebung scheitert und die Zeilen deshalb nichts zeigen können.
        self.extras_state = QLabel("", optional)
        self.extras_state.setWordWrap(True)
        set_level(self.extras_state, "caption")
        self.extras_state.hide()

        # **Gesperrt, bis die Erhebung antwortet — aber nicht mehr wortlos.**
        # Ein gesperrter Knopf ohne Grund daneben ist eine Frage an den Kunden,
        # die er nicht beantworten kann; er stand knapp drei Sekunden so da.
        # Der Grund steht jetzt in der Zeile darüber („Zusatzprogramme — wird
        # nachgesehen …"), und damit bleibt die Entscheidung von
        # ``test_the_dialog_is_there_before_the_answers_are`` gültig: kein
        # Knopf auf eine Vermutung.
        self.install_button = QPushButton(tr("Zusatzprogramme verwalten …"), optional)
        self.install_button.clicked.connect(self._install)
        # Gesperrt, bis die Erhebung antwortet — und der Grund steht am Knopf
        # und nicht nur in der Zeile darunter. Derselbe Satz, den der
        # Chat-Einrichtungsdialog für dieselbe Lage benutzt.
        self._say_why_locked(str(tr("Wird nachgesehen …")))

        self.chat_state = QLabel(tr("Chat — wird nachgesehen …"), optional)
        self.chat_state.setWordWrap(True)
        set_level(self.chat_state, "caption")

        self.chat_button = QPushButton(tr("Chat einrichten …"), optional)
        self.chat_button.clicked.connect(self._setup_chat)

        optional_layout.addWidget(self.tools)
        optional_layout.addWidget(self.extras_state)
        optional_layout.addWidget(self.chat_state)
        optional_actions = QHBoxLayout()
        optional_actions.setSpacing(NORMAL)
        optional_actions.addWidget(self.install_button)
        optional_actions.addWidget(self.chat_button)
        optional_actions.addStretch(1)
        optional_layout.addLayout(optional_actions)

        self.open_button = QPushButton(tr("Eigenes Modell öffnen …"), self)
        self.open_button.clicked.connect(self._open)

        # Nach der Handlung benannt, wie der Dialog *Ungesicherte Änderungen*
        # es vormacht. „Übernehmen" neben „Überspringen" ließ offen, was der
        # Unterschied ist — beide schließen den Dialog, beide fragen nie
        # wieder, und nur einer merkt sich die getroffene Auswahl. Wer sie
        # geändert und dann „Überspringen" gedrückt hätte, hätte sie verloren.
        buttons = QDialogButtonBox(self)
        buttons.addButton(self.open_button, QDialogButtonBox.ButtonRole.ActionRole)
        start = buttons.addButton(
            tr("Speichern und starten"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        make_primary(start)
        buttons.addButton(tr("Später einstellen"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(WIDE)
        layout.addWidget(title)
        layout.addWidget(self.greeting)
        layout.addWidget(self.terms)
        layout.addWidget(basics)
        layout.addWidget(optional)
        layout.addWidget(buttons)

        self._survey: _Survey | None = None
        self._leash = WorkerLeash(self)
        """Hält den ausgelaufenen Arbeiter, bis Qt mit ihm durch ist — das
        Warum steht in :mod:`app.ui.leash`."""
        self.look()

    # --- nachsehen --------------------------------------------------------------

    def look(self) -> None:
        """Die Erhebung starten. Beim Aufbau und nach jeder Einrichtung."""
        if self._survey is not None and self._survey.isRunning():
            return
        survey = _Survey()
        survey.done.connect(self._show)
        survey.crashed.connect(self._crashed)
        survey.finished.connect(self._survey_done)
        self._survey = survey
        # Über die Leine gestartet: Sie hält ihn ab diesem Moment, nicht erst
        # ab seinem Ende — ein Dialog, der vorher weggeräumt wird, nähme sonst
        # die letzte Referenz auf einen laufenden Thread mit.
        self._leash.start(survey)

    def wait_for_survey(self, milliseconds: int = 30_000) -> bool:
        """Auf die Erhebung warten. Beim Aufräumen (:meth:`release`) und in Tests —
        das Schließen wartet nicht mehr."""
        survey = self._survey
        finished = survey.wait(milliseconds) if survey is not None else True
        QCoreApplication.processEvents()
        printer_survey = self._printer_survey
        if printer_survey is not None:
            finished = printer_survey.wait(milliseconds) and finished
        QCoreApplication.processEvents()
        return finished

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieses Fenster außerhalb von Qt hält.

        Warum der Name, warum die eigene Frist: :mod:`app.ui.leash`.
        """
        self.wait_for_survey()
        self._leash.wait_all(timeout_ms)

    def _grow_to_content(self) -> None:
        """Der Dialog wächst mit den nachgereichten Zeilen — von selbst tut
        er es nicht.

        Die Erhebung tauscht „Wird nachgesehen …" gegen drei Programmzeilen
        und die Chat-Auskunft; das Intro-Label darüber bricht um und meldet
        der Layoutrechnung nur eine Zeile Mindesthöhe. Das Fenster blieb
        deshalb auf seiner Aufmachgröße stehen, und der Fehlbetrag wurde aus
        den Auswahlfeldern gepresst: Sprache und Drucker standen mit 16 von
        28 Punkten Höhe da, die Schrift oben und unten
        abgeschnitten (Robert, 26.08.2026, mit Bild).

        Gerufen wird über ``QTimer.singleShot(0, self, …)``, nicht direkt:
        Unmittelbar nach dem Zeilentausch meldet ``sizeHint`` noch den alten
        Stand (die weggeräumten Zeilen leben bis zum nächsten
        Ereignisdurchlauf), und ein ``max`` mit einer veralteten Zahl wächst
        nicht. Mit ``self`` als Empfänger verfällt der Ruf, wenn der Dialog
        vorher weggeräumt wird — ein Rückruf in ein zerstörtes C++-Objekt
        ist der Absturz ohne Zeile.
        """
        # Erst die Lügen festnageln, dann messen: **Jedes** umbrochene Label
        # meldet der Layoutrechnung nur eine Zeile Mindesthöhe — das Intro,
        # die drei Programmzeilen, die Chat-Auskunft. Die Reste summieren
        # sich; offscreen (null Schriftfamilien) fehlten am Ende noch Pixel,
        # obwohl das Intro schon gepinnt war. ``heightForWidth`` über der
        # wirklich gelegten Breite ist je Label die ehrliche Zahl (die Bauart
        # von ``panels.fit_wrapped``, hier über den ganzen Dialog). Der Dialog
        # wird nicht von Hand verbreitert, die gepinnten Mindesthöhen können
        # also nicht zu groß zurückbleiben.
        for label in self.findChildren(QLabel):
            if label.wordWrap() and label.width() > 0:
                label.setMinimumHeight(label.heightForWidth(label.width()))
        self.resize(self.width(), max(self.height(), self.sizeHint().height()))

    def _grow_soon(self) -> None:
        QTimer.singleShot(0, self, self._grow_to_content)

    def _say_why_locked(self, why: str) -> None:
        """Den Programme-Knopf sperren und sagen, warum — oder ihn freigeben.

        Ein leerer Grund gibt frei. Alle drei Kanäle (Regel 18): Der Tooltip
        allein erreicht nicht, wer den Knopf mit der Tastatur anfährt.
        """
        self.install_button.setEnabled(not why)
        self.install_button.setToolTip(why)
        self.install_button.setStatusTip(why)
        self.install_button.setAccessibleDescription(why)

    def _show(self, found: object) -> None:
        """Die Antworten eintragen."""
        assert isinstance(found, Findings)
        self.findings = found
        self._fill_tools(found.tools)
        self._say_why_locked("")
        self.chat_state.setText(found.chat)
        self._fill_slicers(found.slicers)
        self._grow_soon()

    def _crashed(self, detail: str) -> None:
        """Womit niemand gerechnet hat — und keine Zeile bleibt auf „wird
        nachgesehen" stehen.

        Der erste Blick auf Solidon ist nicht der Ort für einen Dialog, der
        stillsteht. Was hier fehlschlägt, kostet nichts: Die Liste der
        Programme ist ein Blick, keine Bedingung — der Weg zum ersten Modell
        führt daran vorbei.
        """
        _log.warning("first run survey crashed: %s", detail)
        self._fill_tools(())
        self._say_why_locked("")
        self.extras_state.show()
        self.extras_state.setText(
            tr(
                "Der Zustand der Zusatzprogramme konnte nicht geprüft werden. Sie "
                "können sie trotzdem verwalten."
            )
        )
        self.chat_state.setText(
            tr(
                "Beim Nachsehen ist etwas schiefgegangen. Der Chat und die "
                "zusätzlichen Programme lassen sich trotzdem einrichten."
            )
        )
        self._grow_soon()

    def _survey_done(self) -> None:
        survey = self._survey
        self._survey = None
        if survey is not None:
            self._leash.hold_until_done(survey)

    # **Schließen wartet nicht auf die Erhebung.** Hier stand vor jedem
    # Schließen ``wait_for_survey()`` — bis zu dreißig Sekunden im
    # Oberflächen-Thread, gemessen rund drei, ohne Wartezeiger; wer den
    # Dialog gleich zu Beginn übernahm oder überging, sah ein Fenster, das
    # nicht antwortet. Nötig ist das Warten nicht: Die Halteleine hält den
    # Arbeiter über das Fenster hinaus (:mod:`app.ui.leash`), und seine späte
    # Antwort trifft einen Dialog, dessen Werte schon übernommen sind.

    def accept(self) -> None:
        if not self._save_custom_printer():
            return
        super().accept()

    def _language_changed(self) -> None:
        """Die Sprache wechselt sofort — auch im Dialog selbst.

        **Ein Hinweis stand hier und war das Falsche.** „Die Oberfläche stellt
        sich gleich darauf um" kündigte an, was erst nach dem Bestätigen
        geschah; der Dialog blieb deutsch. Wer die Sprache wechselt, tut das
        aber meistens, **weil er den Text nicht lesen kann** — und dem nützt
        eine Ankündigung in genau dieser Sprache nichts. Entschieden von
        Robert am 26.08.2026.

        **Neu gebaut statt übersetzt**, aus demselben Grund wie beim
        Hauptfenster (:func:`app.ui.app.rebuild_for_language`): ``tr()``
        übersetzt beim Setzen, und was einmal in einem Widget steht, bleibt
        dort stehen. Neunzehn Texte einzeln nachzuziehen hieße, beim
        zwanzigsten einen zu vergessen — und eine vergessene Zeile fällt nur
        in einer Sprache auf. Der Dialog schließt sich deshalb mit
        :data:`LANGUAGE_CHANGED`, und der Aufrufer öffnet ihn neu.

        **Die Antworten reisen mit.** Vor dem Schließen wandert der ganze Stand
        in die Einstellungen, aus denen der neue Dialog seine Vorbelegung holt
        — wer schon einen Drucker gewählt hat, findet ihn wieder. Dass damit
        auch ein „Später einstellen" danach die Wahl behält, ist gewollt: Was
        sichtbar gewirkt hat, wird nicht heimlich zurückgenommen.
        """
        chosen = str(self.language.currentData())
        if not chosen or chosen == self.settings.language:
            return
        self._carry_over(self.settings)
        install_language(chosen)
        set_language(chosen)
        application = QApplication.instance()
        if application is not None:
            from app.ui.app import install_qt_translations

            install_qt_translations(application, chosen)
        self.done(LANGUAGE_CHANGED)

    # --- result -----------------------------------------------------------------

    def apply_to(self, settings: UiSettings) -> UiSettings:
        """Übernimmt die Antworten und markiert die angenommene Einrichtung als beendet."""
        if not self._save_custom_printer():
            return settings
        self._carry_over(settings)
        settings.first_run_done = True
        return settings

    def _carry_over(self, settings: UiSettings) -> None:
        """Bewahrt Antworten beim Sprachwechsel, ohne die Einrichtung abzuschließen."""
        settings.language = str(self.language.currentData())
        if self.printer.currentData() != "__custom__":
            settings.printer = str(self.printer.currentData())
        chosen = str(self.slicer.currentData() or "")
        if chosen:
            discover.remember_path("slicer", chosen)
        # Keine Frage mehr, aber weiterhin ein vollständiger Projektvorgabensatz:
        # Bis ein Filamentprofil seinen Typ liefert, gilt die dokumentierte
        # Kernvorgabe — die des Verfahrens: Ein Resin-Drucker beginnt mit Harz
        # und nicht mit PLA, und wer das Verfahren wechselt, wechselt sie mit.
        settings.material = profiles.material_for(settings.printer, settings.material)

    def _fill_tools(self, states: tuple[tools.ToolState, ...]) -> None:
        """Eine Zeile je Programm, neu gebaut statt neu beschriftet.

        Was installiert wurde, ändert die Zeichen und die Hinweise; eine Zeile
        einzeln nachzuziehen hieße, dieselbe Zuordnung zweimal zu schreiben.

        Die Zustände kommen von außen und werden hier nicht erhoben: Die Suche
        kostet Sekunden und läuft im Arbeiter (:class:`_Survey`).
        """
        while self._tool_rows.count():
            item = self._tool_rows.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        for state in states:
            self._tool_rows.addWidget(ToolRow(state, self.tools))

    def _install(self) -> None:
        """§36: was fehlt, lässt sich von hier holen, statt aus einem README."""
        from app.ui.install_dialog import InstallDialog

        InstallDialog(self, settings=self.settings).exec()
        self.look()

    def _setup_chat(self) -> None:
        """§27: der Zugang für den Chat, vom ersten Start aus erreichbar.

        Derselbe Dialog wie unter *Bearbeiten → Chat einrichten* — und seit
        dieser Sitzung auch derselbe Name. Er stand hier als *Chat
        einrichten* und dort als *Zugang zum Sprachmodell*; wer den einen
        gesehen hatte, suchte den anderen nicht.
        """
        from app.ui.dialogs import KeyDialog

        KeyDialog(parent=self, settings=self.settings).exec()
        self.look()

    def _open(self) -> None:
        """§2.3: die ersten fünf Minuten enden beim ersten Import, nicht bei
        „fertig".
        """
        if not self._save_custom_printer():
            return
        self.apply_to(self.settings)
        self.importRequested.emit()
        self.accept()

    def _open_inventory(self) -> None:
        """Die Einrichtung übernehmen und danach das Filamentlager öffnen."""
        if not self._save_custom_printer():
            return
        self.apply_to(self.settings)
        self.accept()
        self.inventoryRequested.emit()

    def _technology_changed(self) -> None:
        """Nur die Maße des gewählten Verfahrens stehen im Formular.

        Ein Formular ist ein ``QFormLayout``: Die Beschriftung hängt an
        ihrem Feld, und ``setRowVisible`` nimmt beide zusammen aus dem Bild.
        """
        chosen = self.custom_technology()
        form = self.custom_printer.layout()
        assert isinstance(form, QFormLayout)
        for technology, fields in self._technology_rows.items():
            for field in fields:
                form.setRowVisible(field, technology == chosen)
        self._name_derived_layer()
        self._grow_soon()

    def _derived_layer_height(self) -> float:
        """Die Schichthöhe, die gilt, wenn das Feld leer bleibt.

        Dieselbe Rechnung wie beim Speichern: FDM aus der Düse, höchstens die
        Vorlage; Resin die Vorlage des allgemeinen Resin-Druckers.
        """
        if self.custom_technology() == "resin":
            return profiles.printer(profiles.DEFAULT_RESIN_PRINTER).layer_height
        template = profiles.printer(profiles.DEFAULT_PRINTER)
        return min(template.layer_height, self.printer_nozzle.value() / 2)

    def _name_derived_layer(self) -> None:
        """Das leere Feld nennt den Wert, der dann gilt."""
        self.printer_layer.setSpecialValueText(
            str(tr("automatisch · {value} mm")).format(
                value=format_decimal(round(self._derived_layer_height(), 3))
            )
        )

    def _chosen_layer_height(self) -> float:
        """Die eingetragene Schichthöhe, oder die abgeleitete, wenn leer."""
        entered = self.printer_layer.value()
        return entered if entered > self.printer_layer.minimum() else self._derived_layer_height()

    def custom_technology(self) -> PrintTechnology:
        """Das Verfahren des eigenen Druckers, wie es gerade gewählt ist."""
        return "resin" if self.printer_technology.currentData() == "resin" else "fdm"

    def _printer_changed(self) -> None:
        """Eigene Druckerdaten stehen direkt unter der entsprechenden Auswahl."""
        custom = self.printer.currentData() == "__custom__"
        self.custom_printer.setVisible(custom)
        if not custom and self.sender() is self.printer:
            self.printer_state.clear()
        self._grow_soon()

    def _save_custom_printer(self) -> bool:
        """Eigene Maße werden erst bei ausdrücklicher Übernahme gespeichert."""
        if self.printer.currentData() != "__custom__":
            return True
        name = self.printer_name.text().strip()
        if not name:
            self.printer_state.setText(tr("Geben Sie Ihrem Drucker einen Namen."))
            self.printer_name.setFocus()
            return False
        width, depth, height = (field.value() for field in self.printer_dimensions)
        if self.custom_technology() == "resin":
            # Vom allgemeinen Resin-Gerät abgeleitet: Verfahren, Schichthöhe
            # und die Nullen für Düse und Bahn kommen von dort.
            entry = replace(
                profiles.printer(profiles.DEFAULT_RESIN_PRINTER),
                id=self._custom_identifier,
                title=name,
                build_volume=(width, depth, height),
                pixel_size=self.printer_pixel.value(),
                minimum_wall=self.printer_wall.value(),
                layer_height=self._chosen_layer_height(),
            )
        else:
            template = profiles.printer(profiles.DEFAULT_PRINTER)
            nozzle = self.printer_nozzle.value()
            entry = replace(
                template,
                id=self._custom_identifier,
                title=name,
                build_volume=(width, depth, height),
                nozzle_diameter=nozzle,
                nozzles=self.printer_nozzles.value(),
                layer_height=self._chosen_layer_height(),
                extrusion_width=nozzle * template.extrusion_width / template.nozzle_diameter,
            )
        try:
            profiles.save_printer(entry)
        except (AppError, OSError) as problem:
            _log.warning("custom printer could not be saved: %s", problem)
            self.printer_state.setText(
                tr(
                    "Der Drucker konnte nicht gespeichert werden. Prüfen Sie den "
                    "Speicherplatz und versuchen Sie es erneut."
                )
            )
            return False
        self._insert_printer_choice(name, entry.id)
        _select(self.printer, entry.id)
        self._suggested_printer = entry.id
        return True

    def custom_printer_draft(self) -> CustomPrinterDraft | None:
        """Noch ungespeicherte eigene Druckerdaten reisen beim Sprachwechsel mit."""
        if self.printer.currentData() != "__custom__":
            return None
        width, depth, height = (field.value() for field in self.printer_dimensions)
        return CustomPrinterDraft(
            identifier=self._custom_identifier,
            name=self.printer_name.text(),
            dimensions=(width, depth, height),
            technology=self.custom_technology(),
            nozzle=self.printer_nozzle.value(),
            nozzles=self.printer_nozzles.value(),
            pixel_size=self.printer_pixel.value(),
            minimum_wall=self.printer_wall.value(),
            layer_height=self.printer_layer.value(),
        )

    def restore_custom_printer_draft(self, draft: CustomPrinterDraft | None) -> None:
        """Stellt den Entwurf im neu übersetzten Dialog wieder her."""
        if draft is None:
            return
        self._custom_identifier = draft.identifier
        self.printer_name.setText(draft.name)
        for field, value in zip(self.printer_dimensions, draft.dimensions, strict=True):
            field.setValue(value)
        _select(self.printer_technology, draft.technology)
        self.printer_nozzle.setValue(draft.nozzle)
        self.printer_nozzles.setValue(draft.nozzles)
        self.printer_pixel.setValue(draft.pixel_size)
        self.printer_wall.setValue(draft.minimum_wall)
        self.printer_layer.setValue(draft.layer_height)
        _select(self.printer, "__custom__")

    def _fill_slicers(self, found: tuple[Path, ...]) -> None:
        """Nachgereichte Programme erhalten die bereits getroffene Auswahl."""
        chosen = str(self.slicer.currentData() or "")
        paths = list(dict.fromkeys((*found, *((Path(chosen),) if chosen else ()))))
        with QSignalBlocker(self.slicer):
            self.slicer.clear()
            self.slicer.addItem(tr("Später auswählen"), "")
            for path in paths:
                self.slicer.addItem(path.stem, str(path))
                self.slicer.setItemData(
                    self.slicer.count() - 1, str(path), Qt.ItemDataRole.ToolTipRole
                )
            _select(self.slicer, chosen)
        if chosen:
            self._slicer_changed()

    def _choose_slicer_file(self) -> None:
        """Portable Slicer und abweichende Installationspfade lassen sich ausdrücklich wählen."""
        filename, _ = QFileDialog.getOpenFileName(self, tr("Slicer-Programm auswählen"))
        if not filename:
            return
        if self.slicer.findData(filename) < 0:
            self.slicer.addItem(Path(filename).stem, filename)
        _select(self.slicer, filename)

    def _slicer_changed(self) -> None:
        """Jede Auswahl bekommt eine eigene, gegen späte Antworten geschützte Suche."""
        self._printer_survey = None
        chosen = str(self.slicer.currentData() or "")
        if not chosen:
            self._fill_printers(tuple(profiles.printer_profiles()))
            self.printer_state.clear()
            return
        self.printer.setEnabled(False)
        self.printer_state.setText(tr("Drucker des gewählten Slicers werden gesucht …"))
        worker = _PrinterSurvey(Path(chosen))
        worker.done.connect(self._printers_found)
        worker.crashed.connect(self._printers_failed)
        self._printer_survey = worker
        self._leash.start(worker)

    def _insert_printer_choice(self, title: str, identifier: str) -> None:
        """Jeder Eintrag steht in der Gruppe seines Verfahrens nach sichtbarem
        Titel sortiert, auch ein eigener Drucker; „Benutzerdefiniert …" am Ende.

        Die Gruppenköpfe setzt :meth:`_group_printers` danach — hier wird nur
        einsortiert, und zwar hinter alle Drucker des Verfahrens davor.
        """
        order = list(_TECHNOLOGY_ORDER)
        rank = len(order) if identifier == "__custom__" else order.index(_technology_of(identifier))

        def rank_of(index: int) -> int:
            data = str(self.printer.itemData(index) or "")
            if data == "__custom__":
                return len(order)
            found = _technology_of(data)
            return order.index(found) if found in order else len(order)

        position = next(
            (
                index
                for index in range(self.printer.count())
                if str(self.printer.itemData(index) or "") != _GROUP_HEADER
                and (
                    rank_of(index) > rank
                    or (
                        rank_of(index) == rank
                        and self.printer.itemText(index).casefold() > title.casefold()
                    )
                )
            ),
            self.printer.count(),
        )
        with QSignalBlocker(self.printer):
            self.printer.insertItem(position, title, userData=identifier)
        self._group_printers()

    def _group_printers(self) -> None:
        """Ein Kopf je Verfahren über seiner Gruppe — :func:`group_printer_choices`."""
        group_printer_choices(self.printer)

    def _fill_printers(self, identifiers: tuple[str, ...], suggested: str = "") -> None:
        """Nur passende Drucker anbieten und eine weiterhin passende Wahl erhalten."""
        chosen = str(self.printer.currentData() or "")
        # Die Resin-Drucker hängen an keinem FDM-Slicer: Ein Slicer, der
        # seine Drucker nennt, filtert die FDM-Liste — und lässt die andere
        # Gruppe stehen, denn sie kommt aus dem eigenen Bestand.
        allowed = (
            set(identifiers)
            | {profiles.DEFAULT_PRINTER}
            | {name for name, entry in profiles.printer_profiles().items() if entry.is_resin}
        )
        preferred = chosen
        if suggested and (
            chosen == self._suggested_printer or (chosen not in allowed and chosen != "__custom__")
        ):
            preferred = suggested
        if preferred not in allowed and preferred != "__custom__":
            preferred = profiles.DEFAULT_PRINTER
        with QSignalBlocker(self.printer):
            self.printer.clear()
            for identifier, printer in by_title(profiles.printer_profiles()):
                if identifier in allowed:
                    self._insert_printer_choice(str(printer.title), identifier)
            self._insert_printer_choice(tr("Benutzerdefiniert …"), "__custom__")
            _select(self.printer, preferred)
        if preferred == suggested:
            self._suggested_printer = suggested
        self.printer.setEnabled(True)
        self._printer_changed()

    def _printers_found(self, found: object) -> None:
        """Ein früherer Slicer darf die aktuelle Druckerauswahl nicht verändern."""
        if self.sender() is not self._printer_survey:
            return
        assert isinstance(found, PrinterChoices)
        if str(found.executable) != self.slicer.currentData():
            return
        self._fill_printers(found.identifiers, found.suggested)
        if found.translated:
            self.printer_state.clear()
        else:
            # Kein Fehler und kein leerer Satz: Das Programm ist da, nur seine
            # Drucker kennt Solidon nicht — der Kunde wählt seinen aus der
            # Liste oder legt ihn an (Regel 17).
            self.printer_state.setText(
                tr(
                    "Die Drucker dieses Programms kennt Solidon nicht. Wählen Sie Ihren "
                    "Drucker aus der Liste oder richten Sie ihn selbst ein."
                )
            )
        self._grow_soon()

    def _printers_failed(self, detail: str) -> None:
        """Die eigene Druckerwahl bleibt auch ohne lesbaren Profilbestand erreichbar."""
        if self.sender() is not self._printer_survey:
            return
        _log.warning("first run printer survey crashed: %s", detail)
        self._fill_printers(tuple(profiles.user_printer_profiles()))
        self.printer_state.setText(
            tr(
                "Drucker konnten nicht gelesen werden. Wählen Sie einen anderen "
                "Slicer oder richten Sie Ihren Drucker selbst ein."
            )
        )


def _select(box: QComboBox, identifier: str) -> None:
    index = box.findData(identifier)
    if index >= 0:
        box.setCurrentIndex(index)


def group_printer_choices(box: QComboBox) -> None:
    """Ein Kopf je Verfahren über seiner Gruppe — nicht wählbar, nur gelesen.

    Der Kunde wählt seine Maschine aus derselben Liste wie alle anderen,
    schaltet nichts um und muss nichts wissen (Resin-Konzept §4): Der Kopf
    sagt, welches Verfahren die Drucker darunter haben, und ist über seine
    Rolle als Kopf hinaus nichts — kein Eintrag, keine Antwort. Die Liste muss
    dafür schon nach Verfahren geordnet sein (:func:`add_printer_choices`).

    **Halbfett, nicht nur grau.** Grau trägt jeder gesperrte Eintrag; ein Kopf,
    der sich allein darüber abhebt, liest sich wie ein Drucker, den man nicht
    wählen darf (Regel 18).

    **An allen drei Druckerlisten**, nicht nur im Erststart: Einstellungen und
    Druckvorbereitung nennen dieselben Drucker, und dort stand der
    Resin-Drucker flach zwischen den FDM-Geräten.
    """
    model = box.model()
    assert isinstance(model, QStandardItemModel)
    with QSignalBlocker(box):
        for index in reversed(range(box.count())):
            if str(box.itemData(index) or "") == _GROUP_HEADER:
                box.removeItem(index)
        present = {
            _technology_of(str(box.itemData(index) or ""))
            for index in range(box.count())
            if str(box.itemData(index) or "") != "__custom__"
        }
        if len(present) < 2:
            # Eine einzige Gruppe braucht keinen Kopf: Ein Slicer, der
            # nur FDM-Drucker kennt, zeigt sie wie bisher.
            return
        heading = QFont(box.font())
        heading.setBold(True)
        for technology in _TECHNOLOGY_ORDER:
            first = next(
                (
                    index
                    for index in range(box.count())
                    if str(box.itemData(index) or "") not in {"__custom__", ""}
                    and _technology_of(str(box.itemData(index))) == technology
                ),
                None,
            )
            if first is None:
                continue
            box.insertItem(first, _group_title(technology), userData=_GROUP_HEADER)
            item = model.item(first)
            if item is not None:
                item.setFlags(Qt.ItemFlag.NoItemFlags)
                item.setFont(heading)


def add_printer_choices(box: QComboBox, entries: Mapping[str, PrinterProfile]) -> None:
    """Die Drucker nach Verfahren und darin nach sichtbarem Titel, mit Köpfen.

    Dieselbe Ordnung wie im Erststart: FDM zuerst, dann Resin, jede Gruppe
    nach dem Titel, den der Kunde liest (:func:`app.ui.labels.by_title`).
    """

    def rank(pair: tuple[str, PrinterProfile]) -> tuple[int, str]:
        technology = pair[1].technology
        order = _TECHNOLOGY_ORDER.index(technology) if technology in _TECHNOLOGY_ORDER else 99
        return order, str(pair[1].title).casefold()

    with QSignalBlocker(box):
        for identifier, printer in sorted(entries.items(), key=rank):
            box.addItem(str(printer.title), identifier)
    group_printer_choices(box)


def _technology_of(identifier: str) -> PrintTechnology:
    """Das Verfahren eines Druckers aus dem Bestand; ein Unbekannter ist FDM —
    so rechnet die Szene ohne ihn auch."""
    known = profiles.printer_profiles().get(identifier)
    return known.technology if known is not None else "fdm"


def _chat_text() -> str:
    """Ob der Chat einen Zugang hat (§27) — als Satz, nicht als Symbol.

    Ein bereites Backend wird beim Namen genannt; ohne eines steht hier, was
    fehlt und dass alles andere davon unberührt bleibt.
    """
    backend = llm.first_available()
    if backend is not None:
        return f"{tr('Der Chat ist bereit')} — {backend.id}: {backend.model}"
    return tr(
        "Der Chat braucht einen Zugang zu einem Sprachmodell — ein eigener "
        "Schlüssel oder ein lokales Modell über Ollama. Alles andere "
        "funktioniert ohne."
    )


def should_run(settings: UiSettings) -> bool:
    """Nur einmal, und nur, wenn er nicht vorher übersprungen wurde."""
    return not settings.first_run_done
