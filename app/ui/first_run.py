"""Der erste Start (Bauplan §38).

Sprache, Drucker, Material, ein Blick auf die externen Programme, und der
Zugang für den Chat. Vier Schritte, alle überspringbar, alle später wieder
erreichbar — ein Assistent, der zu Ende gebracht werden muss, bevor
irgendetwas geht, ist eine Wand, kein Willkommen.

Der Chat steht mit im Dialog, weil er das Versprechen ist, mit dem die
Anwendung antritt — und weil ein neuer Nutzer weder einen Schlüssel noch ein
laufendes Ollama mitbringt. Der einzige andere Weg dorthin ist ein Knopf in
einem Panel, das er noch nie gesehen hat.

Er endet dort, wo der Bauplan die ersten fünf Minuten enden lässt (§2.3): beim
ersten Import. Die letzte Seite sagt darum nicht „fertig", sie bietet an, ein
Modell zu öffnen.
"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME
from app.core import activation, install, tools
from app.core.activation import TRIAL_DAYS
from app.core.backends import llm
from app.core.export import slicer_keys, slicer_profiles
from app.core.knowledge import profiles
from app.core.log import get_logger
from app.i18n import language_name, tr
from app.i18n.catalog import available_languages
from app.ui.icons import icon
from app.ui.labels import by_title, deadline_date
from app.ui.settings import UiSettings
from app.ui.style import NORMAL, TIGHT, set_level

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

        word = QLabel(tr("gefunden") if state.available else tr("fehlt"), self)
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


class FirstRunDialog(QDialog):
    """Eine Seite, vier Fragen, alles überspringbar."""

    importRequested = Signal()

    def __init__(self, settings: UiSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setWindowTitle(tr("Erste Schritte"))
        self.setMinimumWidth(520)

        # Der Testlauf steht hier in einem Satz und mehr nicht: die
        # Ersteinrichtung fragt nach keinem Schlüssel — das wäre eine Hürde
        # vor dem ersten Blick (Konzept V4b). In der Demo steht dort der
        # Stichtag, aus demselben Grund in einem Satz.
        state = activation.state()
        if state.in_demo:
            terms = tr(
                "Diese Demo läuft vollständig und ohne Schlüssel bis zum {date}; "
                "danach lässt sie sich nicht mehr starten. Ihre Projekte bleiben "
                "erhalten."
            ).format(date=deadline_date(state))
        else:
            terms = tr(
                "Die ersten {days} Tage ist alles frei; danach bleiben Öffnen, "
                "Ansehen und Messen es."
            ).format(days=TRIAL_DAYS)
        self.greeting = QLabel(
            f"{APP_NAME} — "
            + tr(
                "Konstruieren, erzeugen und anpassen für den 3D-Druck. Diese Angaben "
                "stehen später unter Bearbeiten, Einstellungen; überspringen geht auch."
            )
            + " "
            + terms,
            self,
        )
        self.greeting.setWordWrap(True)

        self.language = QComboBox(self)
        # Der Name, nicht das Kürzel: „de" stand hier als allererste Angabe, die
        # ein neuer Benutzer zu sehen bekam.
        for entry in available_languages():
            self.language.addItem(language_name(entry), entry)
        self.language.setCurrentIndex(self.language.findData(settings.language))

        self.printer = QComboBox(self)
        for identifier, printer in by_title(profiles.printer_profiles()):
            self.printer.addItem(str(printer.title), identifier)
        chosen = settings.printer or _printer_from_slicer() or profiles.DEFAULT_PRINTER
        _select(self.printer, chosen)

        self.material = QComboBox(self)
        for identifier, material in by_title(profiles.material_profiles()):
            self.material.addItem(str(material.title), identifier)
        _select(self.material, settings.material or profiles.DEFAULT_MATERIAL)

        form = QFormLayout()
        form.addRow(tr("Sprache"), self.language)
        form.addRow(tr("Drucker"), self.printer)
        form.addRow(tr("Material"), self.material)

        self.tools = QWidget(self)
        self._tool_rows = QVBoxLayout(self.tools)
        self._tool_rows.setContentsMargins(0, 0, 0, 0)
        self._tool_rows.setSpacing(TIGHT)
        self._fill_tools()

        self.install_button = QPushButton(
            f"{tr('Fehlendes installieren …')}  ·  {_missing_text()}", self
        )
        self.install_button.clicked.connect(self._install)

        self.chat_state = QLabel(_chat_text(), self)
        self.chat_state.setWordWrap(True)

        self.chat_button = QPushButton(tr("Chat einrichten …"), self)
        self.chat_button.clicked.connect(self._setup_chat)

        self.open_button = QPushButton(tr("Modell öffnen …"), self)
        self.open_button.clicked.connect(self._open)

        # Nach der Handlung benannt, wie der Dialog *Ungesicherte Änderungen*
        # es vormacht. „Übernehmen" neben „Überspringen" ließ offen, was der
        # Unterschied ist — beide schließen den Dialog, beide fragen nie
        # wieder, und nur einer merkt sich die getroffene Auswahl. Wer sie
        # geändert und dann „Überspringen" gedrückt hätte, hätte sie verloren.
        buttons = QDialogButtonBox(self)
        buttons.addButton(tr("Los geht's"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(tr("Später einstellen"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.greeting)
        layout.addLayout(form)
        layout.addWidget(QLabel(tr("Externe Programme — keines davon ist Pflicht:"), self))
        layout.addWidget(self.tools)
        layout.addWidget(self.install_button)
        layout.addWidget(self.chat_state)
        layout.addWidget(self.chat_button)
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

    def _fill_tools(self) -> None:
        """Eine Zeile je Programm, neu gebaut statt neu beschriftet.

        Was installiert wurde, ändert die Zeichen und die Hinweise; eine Zeile
        einzeln nachzuziehen hieße, dieselbe Zuordnung zweimal zu schreiben.
        """
        while self._tool_rows.count():
            item = self._tool_rows.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        for state in tools.survey():
            self._tool_rows.addWidget(ToolRow(state, self.tools))

    def _install(self) -> None:
        """§36: was fehlt, lässt sich von hier holen, statt aus einem README."""
        from app.ui.install_dialog import InstallDialog

        InstallDialog(self).exec()
        self._fill_tools()
        self.install_button.setText(f"{tr('Fehlendes installieren …')}  ·  {_missing_text()}")
        self.chat_state.setText(_chat_text())

    def _setup_chat(self) -> None:
        """§27: der Zugang für den Chat, vom ersten Start aus erreichbar.

        Derselbe Dialog wie unter *Bearbeiten → Chat einrichten* — und seit
        dieser Sitzung auch derselbe Name. Er stand hier als *Chat
        einrichten* und dort als *Zugang zum Sprachmodell*; wer den einen
        gesehen hatte, suchte den anderen nicht.
        """
        from app.ui.dialogs import KeyDialog

        KeyDialog(parent=self).exec()
        self.chat_state.setText(_chat_text())

    def _open(self) -> None:
        """§2.3: die ersten fünf Minuten enden beim ersten Import, nicht bei
        „fertig".
        """
        self.apply_to(self.settings)
        self.importRequested.emit()
        self.accept()


def _printer_from_slicer() -> str:
    """Welchen Drucker der installierte Slicer zuletzt hatte (§2.3, §29).

    Der Dialog meldet in derselben Zeile „Slicer gefunden" und schlug daneben
    den allgemeinen 220er vor, während der Bestand des Slicers den richtigen
    Drucker kannte — samt der Maschine, die dort zuletzt eingestellt war. Eine
    gute Vorgabe ist mehr wert als eine gute Einstellmöglichkeit (§2.4).

    Findet sich nichts, bleibt es bei der Vorgabe: eine falsche Vorauswahl
    sähe aus wie eine Entscheidung.
    """
    slicer = tools.by_id("slicer")
    found = slicer.path() if slicer is not None else None
    if found is None:
        return ""
    try:
        flavour = slicer_keys.flavour_of(found.name)
        if flavour is None:
            return ""
        machine = slicer_profiles.chosen_machine(flavour, found)
        return slicer_profiles.printer_for(machine, profiles.printer_profiles())
    except OSError as problem:
        _log.debug("could not ask the slicer which printer it has: %s", problem)
        return ""


def _select(box: QComboBox, identifier: str) -> None:
    index = box.findData(identifier)
    if index >= 0:
        box.setCurrentIndex(index)


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


def _missing_text() -> str:
    """Eine Zeile über das, was nicht da ist — gezeigt neben dem Knopf, der
    es holt.
    """
    absent = install.missing()
    if not absent:
        return tr("Alles Zusätzliche ist vorhanden.")
    return f"{tr('Nicht gefunden')}: " + ", ".join(str(entry.title) for entry in absent)


def should_run(settings: UiSettings) -> bool:
    """Nur einmal, und nur, wenn er nicht vorher übersprungen wurde."""
    return not settings.first_run_done
