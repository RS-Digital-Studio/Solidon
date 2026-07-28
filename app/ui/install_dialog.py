"""What is missing, and a button that fetches it (Bauplan §36, §38).

One row per thing Formwerk can use, with what it is for and whether it is
there. Where it can be installed from here, the row has a button; where it
cannot, it has the reason and the official page.

Nothing installs itself. The list is shown on the first run and can be opened
again from the help menu — installing is somebody pressing a button, which is
the whole difference between a helpful application and one that helps itself.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core import install
from app.core.log import get_logger
from app.i18n import tr

_log = get_logger(__name__)

#: Markers, so the state reads without colour as well (§19.1).
PRESENT = "+"
ABSENT = "-"


class _Worker(QThread):
    """One install, off the interface thread — a download takes minutes."""

    done = Signal(object)
    line = Signal(str)

    def __init__(self, requirement: install.Requirement) -> None:
        super().__init__()
        self._requirement = requirement

    def run(self) -> None:
        self.done.emit(install.install(self._requirement, self.line.emit))


class _Row(QWidget):
    """One requirement: state, what it is for, and what can be done about it."""

    startRequested = Signal(object)

    def __init__(self, requirement: install.Requirement, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.requirement = requirement
        self.state = QLabel(self)
        self.state.setFixedWidth(16)

        title = QLabel(f"{requirement.title} — {requirement.what_for}", self)
        title.setWordWrap(True)

        self.action = QPushButton(tr("Installieren"), self)
        self.action.clicked.connect(lambda: self.startRequested.emit(requirement))
        self.page = QPushButton(tr("Seite öffnen"), self)
        self.page.clicked.connect(self._open_page)
        self.page.setVisible(bool(requirement.url))

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.state)
        layout.addWidget(title, stretch=1)
        layout.addWidget(self.action)
        layout.addWidget(self.page)
        self.refresh()

    def refresh(self) -> None:
        """Read the state again — after an install, and when the dialog opens."""
        here = install.present(self.requirement)
        self.state.setText(PRESENT if here else ABSENT)
        self.action.setVisible(not here)
        self.action.setEnabled(not here and install.installable(self.requirement))
        if not here and not install.installable(self.requirement):
            self.action.setToolTip(str(install.why_not(self.requirement)))
            self.action.setVisible(True)
        self.setToolTip(self._explanation(here))

    def _explanation(self, here: bool) -> str:
        if here:
            return tr("Vorhanden")
        if install.installable(self.requirement):
            return tr("Kann von hier installiert werden.")
        return str(install.why_not(self.requirement))

    def _open_page(self) -> None:
        QDesktopServices.openUrl(QUrl(self.requirement.url))


class InstallDialog(QDialog):
    """The list of what Formwerk can use, and what of it is here."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Zusätzliche Programme"))
        self.setMinimumWidth(640)
        self._worker: _Worker | None = None

        intro = QLabel(
            tr(
                "Keines davon ist Pflicht — ohne sie fehlen einzelne Funktionen, "
                "der Rest von Formwerk arbeitet unverändert."
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
        self._worker = None

    def _busy(self, running: bool) -> None:
        self.progress.setVisible(running)
        for row in self.rows:
            row.action.setEnabled(not running and install.installable(row.requirement))

    def reject(self) -> None:
        worker = self._worker
        if worker is not None and worker.isRunning():
            # An install that is running keeps running; killing a package
            # manager halfway leaves a machine in a state nobody can read.
            worker.wait(50)
        super().reject()
