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

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import install, tools
from app.core.log import get_logger
from app.i18n import tr
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.style import TIGHT

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


class _Row(QWidget):
    """Eine Anforderung: Zustand, Zweck, Fundort und was sich tun lässt.

    Die Zeile sucht nichts selbst. Sie bekommt einen :class:`install.Status`
    und zeigt ihn — vorher steht sie auf :data:`PENDING`.
    """

    startRequested = Signal(object)
    followUpRequested = Signal(object)

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
        self.where = QLabel(tr("Wird gesucht …"), self)
        self.where.setWordWrap(True)
        self.where.setEnabled(False)
        self.where.setTextFormat(Qt.TextFormat.PlainText)

        self.action = QPushButton(tr("Installieren"), self)
        self.action.clicked.connect(lambda: self.startRequested.emit(requirement))
        self.action.setVisible(False)
        # **Der zweite Schritt.** Ollama installiert bringt kein Modell mit,
        # ComfyUI installiert kennt die Knoten nicht — beides stand in einem
        # Satz, und der eine nannte einen Befehl, den ein Kunde nicht ausführen
        # kann. Wo das Requirement einen ``follow_up`` trägt, steht hier der
        # Knopf dafür, sobald das Programm da ist.
        self.follow = QPushButton(str(requirement.follow_up_title), self)
        self.follow.clicked.connect(lambda: self.followUpRequested.emit(requirement))
        self.follow.setVisible(False)
        self.locate = QPushButton(tr("Ort angeben …"), self)
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
        head.addWidget(self.follow)
        head.addWidget(self.locate)
        head.addWidget(self.copy)
        head.addWidget(self.page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        layout.addLayout(head)
        layout.addWidget(self.where)

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

    def _where_text(self, status: install.Status) -> str:
        """Der Fundort, wenn es einen gibt — sonst der Satz, der weiterhilft.

        Steht ein Befehl daneben, wird er genannt: Er ist die vollständige
        Antwort auf „und wie dann?", und ein Knopf „Befehl kopieren" ohne den
        Befehl im Blick wäre eine Zumutung.
        """
        if status.present:
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
        self.show_status(install.status_of(self.requirement))

    def _choose_address(self) -> None:
        address, accepted = QInputDialog.getText(
            self,
            str(self.tool.title) if self.tool else "",
            tr("Adresse, unter der es erreichbar ist:"),
            text=self.tool.address() if self.tool else "",
        )
        if accepted and self.tool is not None:
            tools.set_location(self.tool.id, address.strip())

    def _choose_file(self) -> None:
        assert self.tool is not None
        current = self.tool.path()
        chosen, _filter = QFileDialog.getOpenFileName(
            self,
            tr("Programm auswählen"),
            str(current.parent) if current is not None else "",
            tr("Programme (*.exe);;Alle Dateien (*)"),
        )
        if chosen:
            tools.set_location(self.tool.id, str(Path(chosen)))

    def _open_page(self) -> None:
        QDesktopServices.openUrl(QUrl(self.requirement.url))


class InstallDialog(QDialog):
    """Die Liste dessen, was Solidon benutzen kann, und was davon da ist."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Zusätzliche Programme"))
        self.setMinimumWidth(640)
        self._worker: _Worker | None = None
        self._survey: _Survey | None = None
        self._queue: list[install.Requirement] = []
        """Was „Alles Fehlende installieren" noch vor sich hat."""
        self._running_title = ""
        """Was gerade installiert wird — für die Zeile mit der Laufzeit."""
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

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        for row in self.rows:
            layout.addWidget(row)
        layout.addWidget(self.progress)
        layout.addWidget(self.state)
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
            return tr("Alles Zusätzliche ist vorhanden.")
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
        self.state.setText(tr("Dabei ist etwas schiefgegangen, womit hier niemand gerechnet hat."))
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
        if self._busy_installing():
            return
        self._busy(True)
        self._running_title = str(requirement.title)
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
        """
        seconds = time.monotonic() - self._started_at
        self.state.setText(f"{tr('Wird installiert')}: {self._running_title} ({seconds:.0f} s)")

    def _busy_installing(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

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
        # Die Suche dagegen ist in Millisekunden bis Sekunden durch, und sie
        # schreibt nichts — auf sie wird gewartet, statt sie zu verwaisen.
        self.wait_for_survey()
        super().reject()
