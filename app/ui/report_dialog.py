"""The error report dialog (Bauplan §37.2, §33.1).

Shown when something goes wrong that is not the user's doing — an
``InternalError`` (§33.1). A program fault must never look like a mistake by the
user, and this is the other half of that rule: it looks different, and it offers
something to do about it.

Nothing is sent. The dialog writes a folder and opens it; whether anything goes
anywhere is the user's decision. The offer to attach the project says plainly
that the geometry travels along, because that is exactly what someone needs to
know before they hand a file to a stranger.
"""

from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.core import report as reports
from app.core.log import get_logger
from app.i18n import tr

_log = get_logger(__name__)


class ErrorReportDialog(QDialog):
    """What happened, what will be attached, and where it was put."""

    def __init__(
        self,
        summary: str,
        detail: str = "",
        error: BaseException | None = None,
        project: Path | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.project = project
        self.setWindowTitle(tr("Fehlerbericht"))
        self.setMinimumWidth(560)

        self.report = reports.ErrorReport(
            summary=summary,
            detail=detail,
            traceback="".join(traceback.format_exception(error)) if error else "",
        )

        headline = QLabel(
            tr(
                "Das war ein Programmfehler, nicht Ihre Schuld. "
                "Hier wird ein Bericht zusammengestellt — verschickt wird nichts."
            ),
            self,
        )
        headline.setWordWrap(True)

        self.preview = QTextBrowser(self)
        self.preview.setPlainText(reports.as_text(self.report))

        self.with_log = QCheckBox(tr("Protokoll anhängen"), self)
        self.with_log.setChecked(True)
        self.with_log.toggled.connect(self._refresh)

        self.with_project = QCheckBox(
            tr("Projektdatei anhängen — sie enthält die Geometrie des Modells"), self
        )
        self.with_project.setEnabled(project is not None and project.is_file())
        self.with_project.toggled.connect(self._refresh)

        buttons = QDialogButtonBox(self)
        buttons.addButton(tr("Bericht ablegen"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.addButton(tr("Schließen"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._write)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(headline)
        layout.addWidget(self.preview, stretch=1)
        layout.addWidget(self.with_log)
        layout.addWidget(self.with_project)
        layout.addWidget(buttons)

        self.written: Path | None = None

    def _refresh(self) -> None:
        self.report.include_log = self.with_log.isChecked()
        self.report.include_project = self.with_project.isChecked()
        self.preview.setPlainText(reports.as_text(self.report))

    def _write(self) -> None:
        self._refresh()
        self.written = reports.write(self.report, self.project)
        self.preview.setPlainText(
            f"{reports.as_text(self.report)}\n\n{tr('Abgelegt unter')}: {self.written}"
        )
        _log.info("error report prepared in %s", self.written)
        self.accept()
