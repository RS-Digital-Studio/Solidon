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

**Nachgesehen wird in einem Arbeiter.** Der Dialog brauchte gemessen 1,88
Sekunden, bis er auf dem Bildschirm stand — das Allererste, was ein Kunde von
Solidon sieht, kam fast zwei Sekunden zu spät. Vier Dinge liefen dafür im
Oberflächen-Thread: die Suche nach den vier Programmen, das Auslesen des
Slicer-Profils, die Frage an Ollama über HTTP und die Prüfung der optionalen
Pakete. Keines davon muss fertig sein, damit der Dialog erscheint; er zeigt
jetzt sofort seine Fragen und trägt die Antworten nach.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QApplication,
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
from app.i18n import language_name, set_language, tr
from app.i18n.catalog import available_languages, install_language
from app.ui.icons import icon
from app.ui.labels import by_title, deadline_date
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
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


@dataclass(frozen=True, slots=True)
class Findings:
    """Was auf diesem Rechner liegt — in einem Durchgang erhoben.

    Vier Antworten, die zusammen 1,88 Sekunden kosteten und keine davon nötig
    ist, damit der Dialog aufgeht.
    """

    tools: tuple[tools.ToolState, ...]
    missing: str
    chat: str
    printer: str


class _Survey(Worker):
    """Die Erhebung: Programme suchen, Slicer-Profil lesen, Ollama fragen.

    Kein Abbrechen — es gibt nichts zu bereuen, sie schreibt nichts. Wer den
    Dialog vorher schließt, wartet über die Halteleine auf sie.
    """

    done = Signal(object)

    def work(self) -> None:
        self.done.emit(
            Findings(
                tools=tools.survey(),
                missing=_missing_text(),
                chat=_chat_text(),
                printer=_printer_from_slicer(),
            )
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


#: Der Dialog hat sich für einen Sprachwechsel geschlossen und will neu
#: aufgebaut werden.
#:
#: Qt vergibt 0 für *Rejected* und 1 für *Accepted*; alles darüber steht dem
#: Aufrufer frei. Ein eigener Code statt eines Merkmals am Dialog, weil
#: ``exec()`` genau eine Zahl zurückgibt und der Aufrufer sonst zwei Dinge
#: fragen müsste, von denen er eines vergessen kann.
LANGUAGE_CHANGED = 2


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
        # **Und sie wirkt erst beim nächsten Start.** Der Einstellungsdialog sagt
        # das seit je, hier stand es nicht — an der Stelle, an der eine andere
        # Sprache am ehesten gewählt wird: Wer beim ersten Start „Español"
        # einstellt und danach eine deutsche Oberfläche vor sich hat, hält die
        # Einstellung für wirkungslos, nicht für aufgeschoben. Derselbe Satz und
        # derselbe Auslöser wie dort, damit beide Stellen dasselbe versprechen.
        self.language.currentIndexChanged.connect(self._language_changed)

        self.printer = QComboBox(self)
        for identifier, printer in by_title(profiles.printer_profiles()):
            self.printer.addItem(str(printer.title), identifier)
        # Was der installierte Slicer zuletzt hatte, kommt mit der Erhebung
        # nach — es liest Profildateien und gehört damit nicht hierher. Bis
        # dahin steht die Vorgabe, und nachgezogen wird nur, solange niemand
        # selbst gewählt hat (:meth:`_show`).
        self._suggested_printer = settings.printer or profiles.DEFAULT_PRINTER
        _select(self.printer, self._suggested_printer)

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
        # Bis die Erhebung antwortet, steht hier ein Satz und keine Behauptung
        # über etwas, das niemand nachgesehen hat.
        looking = QLabel(tr("Wird nachgesehen …"), self.tools)
        set_level(looking, "caption")
        self._tool_rows.addWidget(looking)

        self.install_button = QPushButton(tr("Fehlendes installieren …"), self)
        self.install_button.clicked.connect(self._install)
        self.install_button.setEnabled(False)

        self.chat_state = QLabel(tr("Wird nachgesehen …"), self)
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
        """Auf die Erhebung warten. Beim Schließen und in Tests."""
        survey = self._survey
        return survey.wait(milliseconds) if survey is not None else True

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieses Fenster außerhalb von Qt hält.

        **Ein Name für den Aufräumbefehl, auf allen Klassen, die Arbeiter
        halten.** Es waren fünf — ``release``, ``wait_for_workers``,
        ``wait_for_survey``, ``wait_for_look``, ``wait_for_setup`` —, und wer
        eine Testfixture darauf baute, sammelte sie nacheinander ein: erst
        zwei, dann drei, dann vier. Der fünfte fehlte, und der Prozess starb
        beim Abbau an einem Thread, der sein Fenster überlebt hatte.

        Der fachliche Name daneben bleibt: ``wait_for_survey`` steht in ``accept`` und
        ``reject`` und gibt
        zurück, ob die Erhebung durch ist. **An dieser Klasse fiel es auf:** Ein
        Test las die Sprachliste und schloss nie — der Erhebungsthread
        überlebte den Dialog, und der Prozess starb mit ``0xC0000409``.

        **Die Frist der fachlichen Methode bleibt ihre eigene.** Hier stand
        zuerst ``wait_for_survey(timeout_ms)`` — und damit bekam eine Erhebung, für die
        30 Sekunden vorgesehen sind, die 2 Sekunden, die für das Einsammeln
        der Leine gedacht sind. Gemessen an ``test_chat_ui``: zwei von vier
        Läufen starben danach beim Abbau, gegen null von vier davor. Der
        Parameter gilt der Leine, nicht der Sache.
        """
        self.wait_for_survey()
        self._leash.wait_all(timeout_ms)

    def _show(self, found: object) -> None:
        """Die Antworten eintragen."""
        assert isinstance(found, Findings)
        self.findings = found
        self._fill_tools(found.tools)
        self.install_button.setText(f"{tr('Fehlendes installieren …')}  ·  {found.missing}")
        self.install_button.setEnabled(True)
        self.chat_state.setText(found.chat)
        # **Nur, solange niemand selbst gewählt hat.** Eine gute Vorgabe ist
        # mehr wert als eine gute Einstellmöglichkeit (§2.4) — aber eine, die
        # eine getroffene Wahl überschreibt, ist keine Vorgabe mehr.
        if found.printer and self.printer.currentData() == self._suggested_printer:
            _select(self.printer, found.printer)
            self._suggested_printer = found.printer

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
        self.install_button.setEnabled(True)
        self.install_button.setText(tr("Fehlendes installieren …"))
        self.chat_state.setText(
            tr(
                "Beim Nachsehen ist etwas schiefgegangen. Der Chat und die "
                "zusätzlichen Programme lassen sich trotzdem einrichten."
            )
        )

    def _survey_done(self) -> None:
        survey = self._survey
        self._survey = None
        if survey is not None:
            self._leash.hold_until_done(survey)

    def reject(self) -> None:
        self.wait_for_survey()
        super().reject()

    def accept(self) -> None:
        self.wait_for_survey()
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
        self.apply_to(self.settings)
        install_language(chosen)
        set_language(chosen)
        application = QApplication.instance()
        if application is not None:
            from app.ui.app import install_qt_translations

            install_qt_translations(application, chosen)
        self.done(LANGUAGE_CHANGED)

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
                widget.deleteLater()
        for state in states:
            self._tool_rows.addWidget(ToolRow(state, self.tools))

    def _install(self) -> None:
        """§36: was fehlt, lässt sich von hier holen, statt aus einem README."""
        from app.ui.install_dialog import InstallDialog

        InstallDialog(self).exec()
        self.look()

    def _setup_chat(self) -> None:
        """§27: der Zugang für den Chat, vom ersten Start aus erreichbar.

        Derselbe Dialog wie unter *Bearbeiten → Chat einrichten* — und seit
        dieser Sitzung auch derselbe Name. Er stand hier als *Chat
        einrichten* und dort als *Zugang zum Sprachmodell*; wer den einen
        gesehen hatte, suchte den anderen nicht.
        """
        from app.ui.dialogs import KeyDialog

        KeyDialog(parent=self).exec()
        self.look()

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
