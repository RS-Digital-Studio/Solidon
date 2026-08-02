"""Der Fehlerbericht-Dialog (Bauplan §37.2, §33.1).

Gezeigt, wenn etwas schiefgeht, das nicht der Nutzer verursacht hat — ein
``InternalError`` (§33.1). Ein Programmfehler darf nie wie ein Fehler des
Nutzers aussehen, und das hier ist die andere Hälfte dieser Regel: er sieht
anders aus, und er bietet etwas an, das man dagegen tun kann.

Gesendet wird nichts. Der Dialog schreibt einen Ordner und öffnet ihn; ob
irgendetwas irgendwohin geht, ist die Entscheidung des Nutzers. Das Angebot,
das Projekt anzuhängen, sagt klar, dass die Geometrie mitreist — denn genau das
muss jemand wissen, bevor er eine Datei einem Fremden gibt.
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

from app.branding import SUPPORT_ADDRESS
from app.core import report as reports
from app.core.log import get_logger
from app.i18n import tr

_log = get_logger(__name__)


class ErrorReportDialog(QDialog):
    """Was passiert ist, was angehängt wird, und wohin es gelegt wurde."""

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
                "Hier wird ein Bericht zusammengestellt — verschickt wird nichts. "
                "Wenn Sie möchten, senden Sie den abgelegten Ordner an {address}."
            ).replace("{address}", SUPPORT_ADDRESS),
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
