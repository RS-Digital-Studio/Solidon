"""Was fehlt, und ein Knopf, der es holt (Bauplan §36, §38).

Eine Zeile je Sache, die Solidon benutzen kann, mit dem Zweck und dem
Zustand. Wo sich etwas von hier installieren lässt, hat die Zeile einen Knopf;
wo nicht, den Grund, den Befehl zum Abschreiben und die offizielle Seite.

Nichts installiert sich selbst. Die Liste wird bei der Erstinbetriebnahme
gezeigt und lässt sich aus dem Hilfe-Menü wieder öffnen — installiert wird,
wenn jemand einen Knopf drückt, und das ist der ganze Unterschied zwischen
einer hilfreichen Anwendung und einer, die sich selbst hilft.

**Die Zeile sagt auch, wo etwas liegt.** „Vorhanden" ohne Pfad ist eine
Behauptung; mit Pfad ist es eine Angabe, die jemand nachsehen kann. Und wo
nichts gefunden wurde, steht der Weg daneben, der immer funktioniert: den Ort
selbst angeben. Eine portable Installation auf einem zweiten Laufwerk findet
kein Suchverfahren der Welt, und daran soll niemand hängenbleiben.

**Gesucht wird in einem Arbeiter.** Gemessen kostete das Öffnen 2,97 Sekunden
und jede Auffrischung weitere 2,10 — im Oberflächen-Thread, ohne ein Zeichen
dafür, dass etwas läuft. Der Grund war nicht die Suche, sondern ihre Anzahl:
Jede Zeile fragte dreimal dasselbe, und bei den beiden Diensten hing an jeder
Frage eine Socket-Probe. Erhoben wird jetzt einmal je Zeile
(:func:`install.statuses`) und nicht im Hauptthread — §38 verlangt beides.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Final

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import discover, install, tools
from app.core.log import get_logger
from app.i18n import tr
from app.ui.labels import UNEXPECTED_CRASH
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.style import TIGHT, make_primary

_log = get_logger(__name__)

#: Markierungen, damit der Zustand auch ohne Farbe lesbar ist (§19.1).
PRESENT = "+"
ABSENT = "-"

#: Solange gesucht wird. Ohne dieses dritte Zeichen behauptete die Zeile
#: „fehlt", bevor jemand nachgesehen hatte — und das ist keine Auskunft,
#: sondern eine Vermutung mit Knopf daneben.
PENDING = "?"

#: Wie oft die Laufzeit einer Installation nachgezogen wird.
#:
#: **Das Lebenszeichen, das fehlte.** Eine Installation dauert Minuten, und der
#: Balken davor ist unbestimmt — nichts an ihm unterscheidet „lädt" von
#: „hängt". Die rohe Ausgabe gehört weiterhin hinter „Details"; was hier steht,
#: ist die Zeit, und die sagt genau das, was jemand wissen will.
TICK_MS = 1000

#: Ab wann ein Start lange genug dauert, um die Erwartung mitzusagen.
#: `wartezeit.md` nennt zehn Sekunden als Grenze, ab der eine Schätzung
#: dazugehört — darunter ist die laufende Zahl selbst die Auskunft.
SLOW_START_SECONDS: Final = 30.0


class _Survey(Worker):
    """Die Erhebung: Registry, Installationsordner, Ports.

    Sekunden, nicht Millisekunden, und deshalb nicht im Oberflächen-Thread
    (§38). Kein Abbrechen: Es gibt nichts zu bereuen — die Suche schreibt
    nichts, und wer den Dialog schließt, wartet auf sie über die Halteleine.
    """

    done = Signal(object)

    def work(self) -> None:
        self.done.emit(install.statuses())


class _Worker(Worker):
    """Eine Installation, abseits des Oberflächen-Threads — ein Download
    braucht Minuten.
    """

    done = Signal(object)
    line = Signal(str)

    def __init__(self, requirement: install.Requirement) -> None:
        super().__init__()
        self._requirement = requirement

    def work(self) -> None:
        self.done.emit(install.install(self._requirement, self.line.emit))


class _LaunchWorker(Worker):
    """Einen gefundenen Dienst öffnen und abseits der Oberfläche auf ihn warten.

    **Abbrechbar**, weil das Warten Minuten dauern kann: ComfyUI Desktop
    antwortet erst nach gut zwei Minuten, und ein Dialog, der so lange keinen
    Ausstieg hat, ist eine Sackgasse (§2.1, `wartezeit.md`). Abgebrochen wird
    dabei das Warten und nicht der Dienst — er gehört Solidon nicht.
    """

    done = Signal(object)

    def __init__(self, requirement: install.Requirement, tool: tools.ExternalTool) -> None:
        super().__init__()
        self._requirement = requirement
        self._tool = tool
        self._stopped = False

    def stop_waiting(self) -> None:
        """Aus dem Qt-Thread heraus: nicht mehr warten.

        Ein einfaches Merkmal genügt — gelesen wird es im Arbeiter, gesetzt in
        der Oberfläche, und beide Richtungen sind für einen Wahrheitswert
        atomar. Ein Schloss hier wäre Aufwand ohne Gewinn.
        """
        self._stopped = True

    def work(self) -> None:
        # Der Absender reist mit: Nach einem Abbruch gibt der Dialog die
        # Knöpfe sofort frei, während dieser Arbeiter noch bis zum nächsten
        # Poll lebt. Startet der Kunde inzwischen etwas anderes, träfe seine
        # Meldung einen fremden Lauf (`wartezeit.md`, ``Session._outdated``).
        self.done.emit(
            (
                self._requirement,
                tools.start_detailed(self._tool, cancelled=lambda: self._stopped),
                self,
            )
        )


class _Row(QWidget):
    """Eine Anforderung: Zustand, Zweck, Fundort und was sich tun lässt.

    Die Zeile sucht nichts selbst. Sie bekommt einen :class:`install.Status`
    und zeigt ihn — vorher steht sie auf :data:`PENDING`.
    """

    startRequested = Signal(object)
    followUpRequested = Signal(object)
    toolStartRequested = Signal(object)
    locationChanged = Signal()

    def __init__(self, requirement: install.Requirement, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.requirement = requirement
        self.tool = tools.by_id(requirement.id)
        self.status: install.Status | None = None
        self.state = QLabel(PENDING, self)
        self.state.setFixedWidth(16)

        title = QLabel(f"{requirement.title} — {requirement.what_for}", self)
        title.setWordWrap(True)

        #: Wo es liegt, oder der Satz, der sagt, was als Nächstes hilft.
        # **Leer, solange die Erhebung läuft.** Hier stand „Wird gesucht …",
        # je Zeile einmal — im offenen Dialog gemessen siebenmal derselbe
        # Satz, dazu sechs Fragezeichen als Zustandszeichen. Dass gesucht
        # wird, sagen der laufende Balken und die Zeile darunter **einmal**
        # für alle; hier gehört hin, was diese eine Zeile herausgefunden hat,
        # und bis dahin nichts.
        self.where = QLabel("", self)
        self.where.setWordWrap(True)
        self.where.setEnabled(False)
        self.where.setTextFormat(Qt.TextFormat.PlainText)

        self.action = QPushButton(tr("Installieren"), self)
        # Gebundene Methoden, keine Lambdas: Ein Lambda, das ``self`` fängt,
        # an einem Knopf, der Kind von ``self`` ist, schließt den Ring aus
        # ``wartezeit.md`` — die Zeile lebte dann bis zum Prozessende. Das
        # Requirement steht als Feld, die Methoden lesen es dort.
        self.action.clicked.connect(self._request_start)
        self.action.setVisible(False)
        # **Der zweite Schritt.** Ollama installiert bringt kein Modell mit,
        # ComfyUI installiert kennt die Knoten nicht — beides stand in einem
        # Satz, und der eine nannte einen Befehl, den ein Kunde nicht ausführen
        # kann. Wo das Requirement einen ``follow_up`` trägt, steht hier der
        # Knopf dafür, sobald das Programm da ist.
        self.follow = QPushButton(str(requirement.follow_up_title), self)
        self.follow.clicked.connect(self._request_follow_up)
        self.follow.setVisible(False)
        self.launch = QPushButton(tr("Lokal starten"), self)
        self.launch.clicked.connect(self._request_tool_start)
        self.launch.setToolTip(
            tr("Öffnet die lokale Anwendung und verbindet Solidon mit ihrem Backend.")
        )
        self.launch.setVisible(False)
        self.locate = QPushButton(tr("Ort angeben …"), self)
        self.locate.setToolTip(
            tr("Lokale Anwendung auswählen oder eine Web-/Netzadresse verwenden.")
        )
        if self.tool is not None and self.tool.kind == "service" and self.tool.startable:
            location_menu = QMenu(self.locate)
            local_action = location_menu.addAction(tr("Lokale App auswählen …"))
            local_action.triggered.connect(self._choose_file)
            address_action = location_menu.addAction(tr("Web-/Netzadresse verwenden …"))
            address_action.triggered.connect(self._choose_address)
            self.locate.setMenu(location_menu)
        else:
            self.locate.clicked.connect(self._choose_location)
        self.locate.setVisible(self.tool is not None)
        self.copy = QPushButton(tr("Befehl kopieren"), self)
        self.copy.clicked.connect(self._copy_command)
        self.copy.setVisible(False)
        self.page = QPushButton(tr("Seite öffnen"), self)
        self.page.clicked.connect(self._open_page)
        self.page.setVisible(bool(requirement.url))

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self.state)
        head.addWidget(title, stretch=1)
        head.addWidget(self.action)
        head.addWidget(self.launch)
        head.addWidget(self.follow)
        head.addWidget(self.locate)
        head.addWidget(self.copy)
        head.addWidget(self.page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        layout.addLayout(head)
        layout.addWidget(self.where)

    def _request_start(self) -> None:
        self.startRequested.emit(self.requirement)

    def _request_follow_up(self) -> None:
        self.followUpRequested.emit(self.requirement)

    def _request_tool_start(self) -> None:
        self.toolStartRequested.emit(self.requirement)

    def show_status(self, status: install.Status) -> None:
        """Den erhobenen Zustand zeigen. Der einzige Weg, diese Zeile zu füllen."""
        self.status = status
        here = status.present
        self.state.setText(PRESENT if here else ABSENT)
        self.action.setVisible(not here)
        self.action.setEnabled(not here and status.installable)
        if not here and not status.installable:
            self.action.setToolTip(str(status.reason))
        # Der zweite Schritt erscheint, sobald der erste getan ist — vorher
        # wäre er ein Angebot, etwas einzurichten, das es nicht gibt.
        self.follow.setVisible(here and bool(self.requirement.follow_up))
        self.launch.setVisible(status.startable and not status.running)
        self.page.setVisible(not here and bool(self.requirement.url))
        # **Der Befehl zum Abschreiben.** „Auf diesem System geht es nicht" ist
        # eine Auskunft, mit der niemand weiterkommt; die Zeile, die es täte,
        # kennt Solidon — sie steht in ``install.MANAGERS``.
        self.copy.setVisible(bool(status.by_hand))
        self.copy.setToolTip(status.by_hand)
        self.where.setText(self._where_text(status))
        self.setToolTip(self._explanation(status))

    def set_busy(self, running: bool) -> None:
        """Während irgendetwas installiert wird, drückt hier niemand etwas."""
        self.action.setEnabled(not running and self.status is not None and self.status.installable)
        self.launch.setEnabled(not running)
        self.follow.setEnabled(not running)
        self.locate.setEnabled(not running)

    def _where_text(self, status: install.Status) -> str:
        """Der Fundort, wenn es einen gibt — sonst der Satz, der weiterhilft.

        Steht ein Befehl daneben, wird er genannt: Er ist die vollständige
        Antwort auf „und wie dann?", und ein Knopf „Befehl kopieren" ohne den
        Befehl im Blick wäre eine Zumutung.
        """
        if status.present:
            if self.tool is not None and self.tool.kind == "service":
                if status.running and status.using_remote_address:
                    detail = tr("Aktiv: Web-/Netzadresse {adresse} — erreichbar.").format(
                        adresse=status.address
                    )
                elif status.running:
                    detail = tr("Aktiv: lokales Backend {adresse} — erreichbar.").format(
                        adresse=status.address
                    )
                # **Der Satz nennt den Knopf nur, wenn es ihn gibt.** Beide
                # Zweige darunter verwiesen auf „Lokal starten", ohne dessen
                # Bedingung zu teilen: Der Knopf hängt an ``startable``, und das
                # verlangt zusätzlich ein gefundenes Startprogramm. Wer einen
                # Dienst eingetragen hat, dessen Startprogramm fehlt, las den
                # Verweis auf einen Knopf, der nicht dastand (gemessen an beiden
                # Diensten, 30.08.2026). Dieselbe Familie wie ein Knopf, dessen
                # Freigabe und Ausführung Verschiedenes prüfen — hier zwischen
                # Text und Knopf statt zwischen Knopf und Handlung.
                elif status.using_remote_address and status.startable:
                    detail = tr(
                        "Die Web-/Netzadresse {adresse} antwortet nicht. Mit „Lokal starten“ "
                        "wechseln Sie zum lokalen Backend."
                    ).format(adresse=status.address)
                elif status.using_remote_address:
                    detail = tr(
                        "Die Web-/Netzadresse {adresse} antwortet nicht, und ein lokales "
                        "Startprogramm ist nicht eingerichtet."
                    ).format(adresse=status.address)
                elif status.startable:
                    detail = tr(
                        "Lokales Backend {adresse} antwortet noch nicht — mit „Lokal "
                        "starten“ öffnen."
                    ).format(adresse=status.address)
                else:
                    detail = tr(
                        "Lokales Backend {adresse} antwortet noch nicht, und ein "
                        "Startprogramm ist nicht eingerichtet."
                    ).format(adresse=status.address)
                return f"{status.location}\n{detail}"
            return status.location
        if status.by_hand:
            return f"{status.reason}\n{status.by_hand}"
        return str(status.reason) or status.location

    def _explanation(self, status: install.Status) -> str:
        if self.tool is not None and not status.present:
            return str(tools.state_of(self.tool).explain())
        if status.present:
            return tr("Vorhanden")
        if status.installable:
            return tr("Kann von hier installiert werden.")
        return str(status.reason)

    def _copy_command(self) -> None:
        """Den Befehl in die Ablage — für ein Terminal, das wir nicht öffnen."""
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None and self.status is not None:
            clipboard.setText(self.status.by_hand)

    def _choose_location(self) -> None:
        """Den Ort selbst angeben: eine Datei bei Programmen, eine Adresse bei Diensten."""
        if self.tool is None:
            return
        if self.tool.kind == "service":
            self._choose_address()
        else:
            self._choose_file()

    def _address_question(self, problem: str = "") -> str:
        """Die Frage über dem Feld — mit einem Beispiel, und im zweiten Anlauf
        mit dem Grund.

        **Bis zum 24.08.2026 stand hier ein Satz und sonst nichts:** „Adresse,
        unter der es erreichbar ist." Wer noch nie eine Dienstadresse
        eingetragen hat, weiß daraus weder, wie eine aussieht, noch woher er
        sie bekommt — ein Kunde trug den Ordner seiner Modelle ein und suchte
        den Fehler danach drei Stunden an anderer Stelle.

        Das Beispiel kommt aus dem Werkzeug selbst (``ExternalTool.url``) und
        nicht aus einer Zeichenkette hier: Es ist genau die Adresse, unter der
        Solidon den Dienst ohne Zutun sucht, und bleibt damit richtig, wenn sich
        die Vorgabe ändert.
        """
        example = self.tool.url if self.tool else ""
        if self.tool is not None and self.tool.startable:
            sentence = tr(
                "Adresse, unter der der Dienst antwortet — zum Beispiel {beispiel}\n\n"
                "Hier gehört die Webadresse eines bereits laufenden ComfyUI oder "
                "Ollama hin, auch auf einem anderen Rechner — kein Ordner und keine "
                "Programmdatei. Für eine lokale App wählen Sie stattdessen „Lokale "
                "App auswählen …“.\n"
                "Leer lassen heißt: wieder die Vorgabe benutzen."
            ).format(beispiel=example)
        else:
            sentence = tr(
                "Adresse, unter der der Dienst antwortet — zum Beispiel {beispiel}\n\n"
                "Solidon spricht über das Netz mit ihm. Hier gehört deshalb kein "
                "Ordner und keine Programmdatei hin, sondern die Adresse, die das "
                "Programm beim Start selbst nennt.\n"
                "Leer lassen heißt: wieder die Vorgabe benutzen."
            ).format(beispiel=example)
        return f"{problem}\n\n{sentence}" if problem else sentence

    def _choose_address(self) -> None:
        """Fragt, bis die Antwort eine Adresse ist — oder der Nutzer abbricht.

        Eine Schleife und kein zweiter Dialog: Der Grund steht über demselben
        Feld, die getippte Eingabe bleibt stehen, und wer abbricht, bricht ab.
        Ein Fehlerfenster dazwischen wäre ein Klick mehr für dieselbe Auskunft.
        """
        if self.tool is None:
            return
        problem = ""
        entered = self.tool.remote_address() or self.tool.url
        while True:
            entered, accepted = QInputDialog.getText(
                self,
                str(self.tool.title),
                self._address_question(problem),
                text=entered,
            )
            if not accepted:
                return
            trouble = discover.unusable_address(entered)
            if trouble is None:
                tools.set_address(self.tool.id, entered.strip())
                self.locationChanged.emit()
                return
            problem = str(trouble)

    def _choose_file(self) -> None:
        assert self.tool is not None
        current = self.tool.path()
        chosen, _filter = QFileDialog.getOpenFileName(
            self,
            tr("Programm auswählen"),
            str(current.parent) if current is not None else "",
            tr("Programme und Apps (*.exe *.com *.AppImage *.app);;Alle Dateien (*)"),
        )
        if chosen:
            tools.set_program(self.tool.id, str(Path(chosen)))
            self.locationChanged.emit()

    def _open_page(self) -> None:
        QDesktopServices.openUrl(QUrl(self.requirement.url))


class InstallDialog(QDialog):
    """Die Liste dessen, was Solidon benutzen kann, und was davon da ist."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Zusätzliche Programme"))
        self.setMinimumWidth(760)
        self._worker: _Worker | None = None
        self._launcher: _LaunchWorker | None = None
        self._expected_seconds = tools.START_TIMEOUT_SECONDS
        """Wie lange der laufende Start haben darf — bestimmt, ob die
        Erwartung im Satz steht."""
        self._survey: _Survey | None = None
        self._queue: list[install.Requirement] = []
        """Was „Alles Fehlende installieren" noch vor sich hat."""
        self._running_title = ""
        """Was gerade installiert wird — für die Zeile mit der Laufzeit."""
        self._running_action = "install"
        """Ob die Laufzeitzeile eine Installation oder einen Start beschreibt."""
        self._started_at = 0.0
        self._tick = QTimer(self)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._show_elapsed)
        self._broke = False
        """Ein Arbeiter ist zerbrochen. Dann wird **nicht** neu erhoben: Die
        Erhebung überschriebe die Meldung eine Sekunde später mit ihrer
        Zusammenfassung, und der Kunde hätte den Satz gesehen und nicht
        gelesen."""
        self._leash = WorkerLeash(self)
        """Hält den ausgelaufenen Arbeiter, bis Qt mit ihm durch ist — das
        Warum steht in :mod:`app.ui.leash`."""

        intro = QLabel(
            tr(
                "Keines davon ist Pflicht — ohne sie fehlen einzelne Funktionen, "
                "der Rest von Solidon arbeitet unverändert."
            ),
            self,
        )
        intro.setWordWrap(True)

        self.rows = [_Row(entry, self) for entry in install.shown()]
        for row in self.rows:
            row.startRequested.connect(self._start)
            row.followUpRequested.connect(self._follow_up)
            row.toolStartRequested.connect(self._start_tool)
            row.locationChanged.connect(self.refresh)

        self.state = QLabel(self)
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        # **Die rohe Ausgabe gehört hinter einen Knopf, nicht in die Zeile.**
        # Das Statuslabel hing an ``worker.line`` und zeigte damit die
        # Befehlszeile und jede Zeile, die pip oder winget von sich geben —
        # gefolgt von „Das hat nicht geklappt.". Wer das liest, weiß danach
        # weniger als vorher. Der Satz sagt jetzt, was möglich ist; das
        # Protokoll steht daneben für den, der es weitergeben will.
        self._details = ""
        self.details_button = QPushButton(tr("Details anzeigen"), self)
        self.details_button.setVisible(False)
        self.details_button.clicked.connect(self._show_details)
        # **Ein Knopf für alles Fehlende.** Sieben Zeilen einzeln zu drücken
        # und je Zeile Minuten zu warten, ist die Arbeit, die diese Liste
        # abnehmen sollte. Er installiert nichts, was nicht dasteht: Was er
        # tut, ist die Reihenfolge — die Entscheidung bleibt der eine Druck.
        self.all_button = QPushButton(tr("Alles Fehlende installieren"), self)
        self.all_button.setVisible(False)
        self.all_button.clicked.connect(self._start_all)
        # **Den Akzent trug bisher eine Listenzeile, und zwar die oberste.**
        # Qt gibt den Default beim ersten ``show()`` an den ersten Knopf mit
        # ``autoDefault``; in diesem Dialog sind das vierzig Stück, und Nummer
        # eins ist das „Installieren" der ersten Zeile. Sechs Zeilen tragen
        # denselben Text, eine davon stand hervorgehoben da — der Kunde liest
        # das als Empfehlung, welches Programm zuerst dran ist, und es war die
        # Reihenfolge im Layout. Der Hauptknopf ist der, der alles auf einmal
        # tut; ein ausdrücklicher Default nimmt Nummer eins den ihren ab.
        make_primary(self.all_button)
        # **Keine Zahl im Balken.** Sie steht mittig, und der Rand der
        # Füllung wandert darunter hindurch: bei 45 % lag sie halb auf
        # Bernstein und halb auf der Spur, ab 60 % ganz auf Bernstein — mit
        # 1,69 Kontrast, also unlesbar. Eine Farbe, die auf beiden Gründen
        # trägt, gibt es nicht; eine dunklere Füllung nähme dem Balken den
        # Akzent (gerechnet: 4,5 Schriftkontrast kostet die Hälfte des
        # Flächenkontrasts). Der Prozentwert steht deshalb in der Zeile
        # daneben, wo ein ruhiger Grund ist.
        self.progress = QProgressBar(self)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 0)
        self.progress.setVisible(True)

        # **Abbrechen gehört zu jeder Wartezeit über zwei Sekunden**
        # (`wartezeit.md`). Solange nur zwanzig Sekunden gewartet wurde, fiel
        # das nicht auf; bei einem Dienst, der zwei Minuten hochfährt, ist ein
        # Dialog ohne Ausstieg eine Sackgasse (§2.1). Abgebrochen wird das
        # **Warten**, nicht der Dienst: Er gehört Solidon nicht und wird von
        # ihm nie beendet — der Satz danach sagt genau das.
        self.stop_waiting = QPushButton(tr("Nicht mehr warten"), self)
        self.stop_waiting.setVisible(False)
        self.stop_waiting.clicked.connect(self._stop_waiting)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        for row in self.rows:
            layout.addWidget(row)
        layout.addWidget(self.progress)
        layout.addWidget(self.state)
        layout.addWidget(self.stop_waiting, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.all_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.details_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(buttons)

        self.state.setText(tr("Wird gesucht …"))
        self.refresh()

    # --- suchen -----------------------------------------------------------------

    def refresh(self) -> None:
        """Neu nachsehen — beim Öffnen und nach jeder Installation.

        Im Arbeiter, weil die Suche Sekunden kostet: Registry, zwei Ebenen
        Installationsordner, und für jeden Dienst eine Socket-Probe.
        """
        if self._survey is not None and self._survey.isRunning():
            return
        self._broke = False
        survey = _Survey()
        survey.done.connect(self._surveyed)
        survey.crashed.connect(self._crashed)
        survey.finished.connect(self._survey_done)
        self._survey = survey
        self.progress.setVisible(True)
        # Über die Leine gestartet — siehe :meth:`WorkerLeash.start`.
        self._leash.start(survey)

    def wait_for_survey(self, milliseconds: int = 30_000) -> bool:
        """Auf die Erhebung warten. Beim Schließen und in Tests.

        Ein Dialog, der mit laufender Suche zugeht, lässt einen Thread auf ein
        gelöschtes C++-Objekt zeigen — dasselbe Warum wie bei der Halteleine.
        """
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

        Der fachliche Name daneben bleibt: ``wait_for_survey``, wie beim Erstlauf-Dialog —
        dieselbe Erhebung,
        derselbe fachliche Name.

        **Die Frist der fachlichen Methode bleibt ihre eigene.** Hier stand
        zuerst ``wait_for_survey(timeout_ms)`` — und damit bekam eine Erhebung, für die
        30 Sekunden vorgesehen sind, die 2 Sekunden, die für das Einsammeln
        der Leine gedacht sind. Gemessen an ``test_chat_ui``: zwei von vier
        Läufen starben danach beim Abbau, gegen null von vier davor. Der
        Parameter gilt der Leine, nicht der Sache.
        """
        self.wait_for_survey()
        self._leash.wait_all(timeout_ms)

    def _surveyed(self, found: object) -> None:
        assert isinstance(found, tuple)
        by_id = {status.requirement.id: status for status in found}
        for row in self.rows:
            status = by_id.get(row.requirement.id)
            if status is not None:
                row.show_status(status)
        absent = [
            status.requirement for status in found if not status.present and status.installable
        ]
        # Der Sammelknopf erscheint erst, wenn es zwei zu holen gibt — bei
        # einem einzigen stünde er neben dem Knopf, der dasselbe tut.
        self.all_button.setVisible(len(absent) > 1)
        if not self._busy_installing():
            self.progress.setVisible(False)
            self.state.setText(self._summary(found))

    def _summary(self, found: tuple[install.Status, ...]) -> str:
        """Eine Zeile über das Ganze — sie ersetzt „Wird gesucht …"."""
        absent = [status for status in found if not status.present]
        if not absent:
            if any(status.startable for status in found):
                return tr(
                    "Alle Zusatzprogramme sind installiert. Lokale Dienste starten Sie "
                    "direkt in ihrer Zeile."
                )
            return tr("Alles Zusätzliche ist bereit.")
        names = ", ".join(str(status.requirement.title) for status in absent)
        return f"{tr('Nicht gefunden')}: {names}"

    def _crashed(self, detail: str) -> None:
        """Womit niemand gerechnet hat — und der Weg aus dem Wartezustand.

        Ohne das blieben die Zeilen auf „?" stehen und der Balken lief weiter:
        Ein ``run``, das eine Ausnahme durchlässt, sendet sein Ergebnissignal
        nie.
        """
        self._tick.stop()
        self._busy(False)
        self.progress.setVisible(False)
        self._queue.clear()
        self._broke = True
        _log.warning("install dialog worker crashed: %s", detail)
        self.state.setText(str(UNEXPECTED_CRASH))
        self._details = f"{self._details}\n{detail}" if self._details else detail
        self.details_button.setVisible(True)

    def _survey_done(self) -> None:
        survey = self._survey
        self._survey = None
        if survey is not None:
            self._leash.hold_until_done(survey)

    # --- der zweite Schritt -----------------------------------------------------

    def _follow_up(self, requirement: install.Requirement) -> None:
        """Was nach dem Installieren noch nötig ist — und wer es tut.

        Die Zuordnung steht hier und nicht im Kern: Der Kern benennt den
        Schritt (``Requirement.follow_up``), die Oberfläche weiß, welcher
        Dialog ihn führt.
        """
        if requirement.follow_up == "comfyui":
            from app.ui.comfy_dialog import ComfySetupDialog

            ComfySetupDialog(self).exec()
        elif requirement.follow_up == "chat":
            from app.ui.dialogs import KeyDialog

            KeyDialog(parent=self).exec()
        else:
            return
        self.refresh()

    # --- installieren -----------------------------------------------------------

    def _start_tool(self, requirement: install.Requirement) -> None:
        """Einen lokalen Dienst öffnen; die Portprüfung läuft im Arbeiter."""
        if self._busy_working():
            return
        # **Was zum vorigen Lauf gehört, gehört nicht zu diesem** — und zwar
        # vor jedem Rückweg, nicht nur vor dem gelingenden. Der
        # Installationszweig räumt hier auf, der Startzweig tat es nicht: Wer
        # erst installierte und dann startete, fand unter *Details anzeigen*
        # noch die Ausgabe der Paketverwaltung. Auch die Absage „kein lokales
        # Startprogramm" darunter ist ein neuer Vorgang; ihr die Ausgabe des
        # alten beizulegen wäre dieselbe Verwechslung. Dieselbe Familie wie die
        # Ergebniszeile, die einen Slicer-Wechsel überlebte.
        self._details = ""
        self.details_button.setVisible(False)
        self._broke = False
        tool = tools.by_id(requirement.id)
        if tool is None or tool.start_command() is None:
            self.state.setText(
                tr("Kein lokales Startprogramm gefunden — geben Sie die App oder die Adresse an.")
            )
            return
        self._busy(True)
        self._running_title = str(requirement.title)
        self._running_action = "start"
        self._started_at = time.monotonic()
        self._expected_seconds = tool.start_seconds
        self._show_elapsed()
        self._tick.start()
        self.stop_waiting.setVisible(True)

        worker = _LaunchWorker(requirement, tool)
        worker.done.connect(self._tool_started)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(self._launch_thread_done)
        self._launcher = worker
        self._leash.start(worker)

    def _start_all(self) -> None:
        """Alles Fehlende, eines nach dem anderen."""
        self._queue = [
            row.requirement
            for row in self.rows
            if row.status is not None and not row.status.present and row.status.installable
        ]
        self._next_in_queue()

    def _next_in_queue(self) -> None:
        while self._queue:
            requirement = self._queue.pop(0)
            if not install.present(requirement):
                self._start(requirement)
                return
        self.refresh()

    def _start(self, requirement: install.Requirement) -> None:
        if self._busy_working():
            return
        self._busy(True)
        self._running_title = str(requirement.title)
        self._running_action = "install"
        self._started_at = time.monotonic()
        self._show_elapsed()
        self._tick.start()
        self._details = ""
        self.details_button.setVisible(False)

        worker = _Worker(requirement)
        worker.done.connect(self._finished)
        worker.line.connect(self._note_line)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(self._thread_done)
        self._worker = worker
        self._leash.start(worker)

    def _show_elapsed(self) -> None:
        """„Wird installiert: OrcaSlicer (45 s)" — dasselbe Muster wie beim
        Erzeugen eines Modells (``mesh.py``).

        **Und bei einem Dienst, der lange braucht, die Erwartung dazu — vom
        ersten Tick an, nicht erst nach einer Weile.** `wartezeit.md` verlangt
        über zehn Sekunden eine Schätzung „wenn möglich"; die Schätzung hier
        ist aber nicht die verstrichene Zeit, sondern die **erwartete**, und
        die steht schon beim Drücken fest (:attr:`ExternalTool.start_seconds`).

        Sie später einzublenden wäre die schlechtere Bedienung: Wer den Knopf
        drückt und sofort liest, dass es ein bis zwei Minuten dauert, wartet
        ruhig. Wer es erst nach dreißig Sekunden erfährt, hat dreißig Sekunden
        lang gerätselt, ob etwas kaputt ist — und genau daran hat der
        Startknopf für ComfyUI seinen schlechten Ruf verdient.

        Bei Ollama bleibt der Satz weg: Es antwortet in Sekunden, und ein
        Hinweis auf zwei Minuten wäre dort schlicht falsch.
        """
        seconds = time.monotonic() - self._started_at
        action = tr("Wird gestartet") if self._running_action == "start" else tr("Wird installiert")
        line = f"{action}: {self._running_title} ({seconds:.0f} s)"
        if self._running_action == "start" and self._expected_seconds > SLOW_START_SECONDS:
            line += " — " + tr("das dauert beim ersten Mal ein bis zwei Minuten")
        self.state.setText(line)

    def _stop_waiting(self) -> None:
        """Nicht mehr auf den Dienst warten — er läuft weiter.

        Abgebrochen wird das **Warten** und nicht der Dienst: Ein gestarteter
        Prozess gehört Solidon nicht und wird von ihm nie beendet
        (:func:`app.core.tools.start_detailed`). Der Satz sagt genau das,
        damit niemand glaubt, der Start sei zurückgenommen — und er nennt den
        Weg zurück, statt in einer Sackgasse zu enden (§2.1).
        """
        if self._launcher is not None:
            self._launcher.stop_waiting()
        self._tick.stop()
        self.stop_waiting.setVisible(False)
        self._busy(False)
        self.state.setText(
            tr(
                "{name} startet weiter im Hintergrund — Solidon beendet es nicht. "
                "Beim nächsten Öffnen von „Modell erzeugen“ wird nachgesehen, "
                "ob es inzwischen antwortet."
            ).format(name=self._running_title)
        )

    def _busy_installing(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _busy_working(self) -> bool:
        return self._busy_installing() or (
            self._launcher is not None and self._launcher.isRunning()
        )

    def _browsable(self, address: str) -> str:
        """Eine Adresse, die man im Browser öffnen kann — sonst nichts.

        ComfyUI horcht auf ``http://127.0.0.1:8188`` und zeigt dort seine
        Oberfläche. Ollamas Adresse ist ``http://localhost:11434/api/chat``,
        ein Endpunkt, der auf einen Browseraufruf mit einem Fehler antwortet —
        wer den Kunden dorthin schickt, zeigt ihm eine Fehlerseite und lässt
        ihn glauben, der Dienst sei kaputt.

        Unterschieden wird **am Pfad und nicht am Dienst**: Was keinen hat, ist
        eine Seite. Das kommt ohne Wissen über das jeweilige Programm aus und
        gilt damit auch für das nächste, das dazukommt.
        """
        rest = address.partition("://")[2]
        return "" if "/" in rest.rstrip("/") else address

    def _tool_started(self, result: object) -> None:
        """Die verständliche Antwort auf den Startversuch zeigen.

        **Nur, wenn sie zum laufenden Versuch gehört.** Ein abgebrochener
        Arbeiter lebt bis zu seinem nächsten Poll weiter; seine Meldung darf
        den Zustandstext eines inzwischen gestarteten Laufs nicht übermalen.
        Dasselbe Muster wie ``Session._outdated`` — verglichen wird der
        Absender, nicht der Inhalt.
        """
        assert isinstance(result, tuple) and len(result) in (2, 3)
        requirement, start_result = result[0], result[1]
        # Ohne Absender gilt die Meldung als aktuell — dieselbe Regel wie in
        # ``Session._outdated``: Tests rufen den Slot direkt, und ein Aufruf
        # ohne Arbeiter ist dort keine Nachzüglermeldung, sondern der Normalfall.
        sender = result[2] if len(result) == 3 else None
        assert isinstance(requirement, install.Requirement)
        assert isinstance(start_result, tools.StartResult)
        if sender is not None and sender is not self._launcher:
            return
        self._tick.stop()
        self.stop_waiting.setVisible(False)
        self._busy(False)
        if start_result.running:
            self.state.setText(f"{requirement.title}: {tr('Lokales Backend läuft jetzt.')}")
            return
        if start_result.stopped:
            # Der Kunde hat das Warten beendet. Sein Satz steht schon da; ihn
            # jetzt mit „antwortet nicht" zu überschreiben hieße, seine eigene
            # Handlung als Fehlschlag zu melden.
            #
            # **Am Ergebnis abgelesen und nicht an einem Merkmal des Fensters.**
            # Als Merkmal blieb es stehen, wenn der Dienst das Rennen gegen den
            # Abbruch gewann: Der running-Zweig darüber kehrt vorher zurück,
            # das Merkmal blieb wahr, und der nächste **echte** Fehlschlag
            # verschwand wortlos — Balken weg, kein Satz, kein Grund.
            return
        self._broke = True
        if not start_result.launched:
            reason = start_result.reason or tr("Unbekannter Grund")
            self.state.setText(
                f"{requirement.title}: "
                + tr(
                    "Das lokale Programm konnte nicht geöffnet werden: {grund}. "
                    "Prüfen Sie den gespeicherten Ort oder wählen Sie die App erneut aus."
                ).format(grund=reason)
            )
            return
        if requirement.id == "comfyui":
            program_name = (
                discover.plain_name(start_result.program.name)
                if start_result.program is not None
                else ""
            )
            if program_name == "comfy":
                reason = tr(
                    "Die ComfyUI-Kommandozeile wurde gestartet, aber das Backend antwortet "
                    "noch nicht. Prüfen Sie die ComfyUI-Protokolle und versuchen Sie es erneut."
                )
            else:
                # **Nach der vollen Wartezeit, nicht nach zwanzig Sekunden.**
                # Solange gewartet wird, steht der laufende Zustand da; dieser
                # Satz gilt erst, wenn die am Dienst kalibrierte Zeit um ist —
                # und dann gehört die Zahl hinein, sonst liest er sich wie die
                # alte Fehlmeldung nach einem Augenblick (Regel 17: warum).
                reason = tr(
                    "ComfyUI ist geöffnet, hat aber in {minuten} Minuten nicht geantwortet. "
                    "Es läuft weiter — öffnen Sie dort die lokale Installation, oder sehen "
                    "Sie in den ComfyUI-Protokollen nach, woran es hängt."
                ).format(minuten=f"{self._expected_seconds / 60:.0f}")
        else:
            reason = tr(
                "Das Programm wurde gestartet, aber der Dienst antwortet noch nicht. "
                "Prüfen Sie die lokale Anwendung und versuchen Sie es dann erneut."
            )
        # **Die Adresse lag die ganze Zeit vor und stand nirgends.** „Sehen Sie
        # in den Protokollen nach" schickt den Kunden an einen Ort, den er
        # nicht kennt; ein Aufruf im Browser beantwortet dieselbe Frage in zwei
        # Sekunden — läuft der Dienst oder nicht. ``StartResult`` trägt sie
        # seit je, und niemand hat gefragt, warum sie nicht zu sehen ist.
        # **Was Solidon versucht hat, gehört in die Einzelheiten** (§33.2).
        # Der Startweg hatte den Knopf nie gefüllt, obwohl der Befehl im
        # Ergebnis steht: Wer meldet „es startet nicht", kann ihn kopieren und
        # selbst ausführen — und sieht dann in einer Zeile, was das Programm
        # dazu sagt. Ohne ihn bleibt einem Fehlerbericht nur „ging nicht".
        self._note_start_attempt(start_result)
        page = self._browsable(start_result.address)
        if page:
            reason = f"{reason} " + str(
                tr("Ob es inzwischen antwortet, sehen Sie unter {adresse}.")
            ).format(adresse=page)
        self.state.setText(f"{requirement.title}: {reason}")

    def _note_start_attempt(self, start_result: tools.StartResult) -> None:
        """Den Startversuch für die Einzelheiten festhalten.

        Nur bei einem Fehlschlag und nur, wenn es etwas zu sagen gibt: Ein
        gelungener Start braucht keine Nachschau, und ein leerer Kasten hinter
        einem Knopf ist schlechter als kein Knopf.
        """
        lines = []
        if start_result.command:
            lines.append(f"{tr('Aufruf')}: {' '.join(start_result.command)}")
        if start_result.address:
            lines.append(f"{tr('Adresse')}: {start_result.address}")
        if not lines:
            return
        self._details = "\n".join(lines)
        self.details_button.setVisible(True)

    def _launch_thread_done(self) -> None:
        worker = self._launcher
        self._launcher = None
        if worker is not None:
            self._leash.hold_until_done(worker)
        if not self._broke:
            self.refresh()

    def _note_line(self, line: str) -> None:
        """Eine Zeile der Paketverwaltung — gesammelt, nicht gezeigt."""
        self._details = f"{self._details}\n{line}" if self._details else line

    def _show_details(self) -> None:
        """Das Protokoll, für den der es weitergeben will (§33.2)."""
        box = QMessageBox(self)
        box.setWindowTitle(tr("Einzelheiten"))
        box.setText(tr("Was die Paketverwaltung gemeldet hat:"))
        box.setDetailedText(self._details)
        box.exec()

    def _finished(self, result: object) -> None:
        assert isinstance(result, install.InstallResult)
        self._tick.stop()
        self._busy(False)
        if result.installed:
            self.state.setText(f"{result.requirement.title}: {tr('fertig')}")
        else:
            reason = str(result.reason) if result.reason else tr("Das hat nicht geklappt.")
            self.state.setText(f"{result.requirement.title}: {reason}")
            if result.output:
                self._details = (
                    f"{self._details}\n{result.output}" if self._details else result.output
                )
            self.details_button.setVisible(bool(self._details))
            _log.info("install of %s did not finish: %s", result.requirement.id, reason)

    def _thread_done(self) -> None:
        # `finished` heißt „`run` ist zurück", nicht „das Objekt darf weg" —
        # das Loslassen übernimmt die Halteleine.
        worker = self._worker
        self._worker = None
        if worker is not None:
            self._leash.hold_until_done(worker)
        # **Und erst hier geht die Reihe weiter.** Angestoßen aus ``_finished``
        # verschluckte sie einen Eintrag: ``done`` kommt, während der Arbeiter
        # noch läuft, ``_start`` sieht ihn als beschäftigt und kehrt um — der
        # Eintrag war aber schon aus der Warteschlange genommen. Von vier
        # fehlenden Programmen wurden so drei installiert, ohne ein Wort dazu.
        if self._queue:
            self._next_in_queue()
        elif not self._broke:
            self.refresh()

    def _busy(self, running: bool) -> None:
        self.progress.setVisible(running)
        self.all_button.setEnabled(not running)
        for row in self.rows:
            row.set_busy(running)

    def reject(self) -> None:
        self._queue.clear()
        worker = self._worker
        if worker is not None and worker.isRunning():
            # Eine laufende Installation läuft weiter; eine Paketverwaltung auf
            # halbem Weg abzuwürgen lässt eine Maschine in einem Zustand zurück,
            # den niemand lesen kann.
            worker.wait(50)
        launcher = self._launcher
        if launcher is not None and launcher.isRunning():
            launcher.wait(50)
        # Die Suche dagegen ist in Millisekunden bis Sekunden durch, und sie
        # schreibt nichts — auf sie wird gewartet, statt sie zu verwaisen.
        self.wait_for_survey()
        super().reject()
