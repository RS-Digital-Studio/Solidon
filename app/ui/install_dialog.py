"""Was fehlt, und ein Knopf, der es holt (Bauplan §36, §38).

Eine Zeile je Sache, die Solidon benutzen kann, mit dem Zweck und dem
Zustand. Wo sich etwas von hier installieren lässt, hat die Zeile einen Knopf;
wo nicht, den Grund und die offizielle Seite.

Nichts installiert sich selbst. Die Liste wird bei der Erstinbetriebnahme
gezeigt und lässt sich aus dem Hilfe-Menü wieder öffnen — installiert wird,
wenn jemand einen Knopf drückt, und das ist der ganze Unterschied zwischen
einer hilfreichen Anwendung und einer, die sich selbst hilft.

**Die Zeile sagt auch, wo etwas liegt.** „Vorhanden" ohne Pfad ist eine
Behauptung; mit Pfad ist es eine Angabe, die jemand nachsehen kann. Und wo
nichts gefunden wurde, steht der Weg daneben, der immer funktioniert: den Ort
selbst angeben. Eine portable Installation auf einem zweiten Laufwerk findet
kein Suchverfahren der Welt, und daran soll niemand hängenbleiben.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import install, tools
from app.core.log import get_logger
from app.i18n import tr
from app.ui.leash import WorkerLeash
from app.ui.style import TIGHT

_log = get_logger(__name__)

#: Markierungen, damit der Zustand auch ohne Farbe lesbar ist (§19.1).
PRESENT = "+"
ABSENT = "-"


class _Worker(QThread):
    """Eine Installation, abseits des Oberflächen-Threads — ein Download
    braucht Minuten.
    """

    done = Signal(object)
    line = Signal(str)

    def __init__(self, requirement: install.Requirement) -> None:
        super().__init__()
        self._requirement = requirement

    def run(self) -> None:
        self.done.emit(install.install(self._requirement, self.line.emit))


class _Row(QWidget):
    """Eine Anforderung: Zustand, Zweck, Fundort und was sich tun lässt."""

    startRequested = Signal(object)

    def __init__(self, requirement: install.Requirement, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.requirement = requirement
        self.tool = tools.by_id(requirement.id)
        self.state = QLabel(self)
        self.state.setFixedWidth(16)

        title = QLabel(f"{requirement.title} — {requirement.what_for}", self)
        title.setWordWrap(True)

        #: Wo es liegt, oder der Satz, der sagt, was als Nächstes hilft.
        self.where = QLabel(self)
        self.where.setWordWrap(True)
        self.where.setEnabled(False)
        self.where.setTextFormat(Qt.TextFormat.PlainText)

        self.action = QPushButton(tr("Installieren"), self)
        self.action.clicked.connect(lambda: self.startRequested.emit(requirement))
        self.locate = QPushButton(tr("Ort angeben …"), self)
        self.locate.clicked.connect(self._choose_location)
        self.locate.setVisible(self.tool is not None)
        self.page = QPushButton(tr("Seite öffnen"), self)
        self.page.clicked.connect(self._open_page)
        self.page.setVisible(bool(requirement.url))

        head = QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self.state)
        head.addWidget(title, stretch=1)
        head.addWidget(self.action)
        head.addWidget(self.locate)
        head.addWidget(self.page)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(TIGHT)
        layout.addLayout(head)
        layout.addWidget(self.where)
        self.refresh()

    def refresh(self) -> None:
        """Den Zustand neu lesen — nach einer Installation und beim Öffnen."""
        here = install.present(self.requirement)
        self.state.setText(PRESENT if here else ABSENT)
        self.action.setVisible(not here)
        self.action.setEnabled(not here and install.installable(self.requirement))
        if not here and not install.installable(self.requirement):
            self.action.setToolTip(str(install.why_not(self.requirement)))
            self.action.setVisible(True)
        self.where.setText(self._where_text())
        self.setToolTip(self._explanation(here))

    def _where_text(self) -> str:
        """Der Fundort, wenn es einen gibt — sonst der Satz, der weiterhilft."""
        if self.tool is None:
            return ""
        state = tools.state_of(self.tool)
        if state.path is not None:
            return str(state.path)
        if state.available and self.tool.address():
            return self.tool.address()
        return str(state.explain())

    def _explanation(self, here: bool) -> str:
        if self.tool is not None:
            return str(tools.state_of(self.tool).explain())
        if here:
            return tr("Vorhanden")
        if install.installable(self.requirement):
            return tr("Kann von hier installiert werden.")
        return str(install.why_not(self.requirement))

    def _choose_location(self) -> None:
        """Den Ort selbst angeben: eine Datei bei Programmen, eine Adresse bei Diensten."""
        if self.tool is None:
            return
        if self.tool.kind == "service":
            self._choose_address()
        else:
            self._choose_file()
        self.refresh()

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

        self.rows = [_Row(entry, self) for entry in install.REQUIREMENTS]
        for row in self.rows:
            row.startRequested.connect(self._start)

        self.state = QLabel(self)
        self.state.setWordWrap(True)
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        for row in self.rows:
            layout.addWidget(row)
        layout.addWidget(self.progress)
        layout.addWidget(self.state)
        layout.addWidget(buttons)

    # --- running ----------------------------------------------------------------

    def _start(self, requirement: install.Requirement) -> None:
        if self._worker is not None and self._worker.isRunning():
            return
        self._busy(True)
        self.state.setText(f"{tr('Wird installiert')}: {requirement.title}")

        worker = _Worker(requirement)
        worker.done.connect(self._finished)
        worker.line.connect(self.state.setText)
        worker.finished.connect(self._thread_done)
        self._worker = worker
        worker.start()

    def _finished(self, result: object) -> None:
        assert isinstance(result, install.InstallResult)
        self._busy(False)
        for row in self.rows:
            row.refresh()
        if result.installed:
            self.state.setText(f"{result.requirement.title}: {tr('fertig')}")
            return
        reason = str(result.reason) if result.reason else tr("Das hat nicht geklappt.")
        self.state.setText(f"{result.requirement.title}: {reason}")
        _log.info("install of %s did not finish: %s", result.requirement.id, reason)

    def _thread_done(self) -> None:
        # `finished` heißt „`run` ist zurück", nicht „das Objekt darf weg" —
        # das Loslassen übernimmt die Halteleine.
        worker = self._worker
        self._worker = None
        if worker is not None:
            self._leash.hold_until_done(worker)

    def _busy(self, running: bool) -> None:
        self.progress.setVisible(running)
        for row in self.rows:
            row.action.setEnabled(not running and install.installable(row.requirement))

    def reject(self) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            # Eine laufende Installation läuft weiter; eine Paketverwaltung auf
            # halbem Weg abzuwürgen lässt eine Maschine in einem Zustand zurück,
            # den niemand lesen kann.
            worker.wait(50)
        super().reject()
