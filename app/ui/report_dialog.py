"""Der Fehlerbericht-Dialog (Bauplan §37.2, §33.1).

Gezeigt, wenn etwas schiefgeht, das nicht der Nutzer verursacht hat — ein
``InternalError`` (§33.1). Ein Programmfehler darf nie wie ein Fehler des
Nutzers aussehen, und das hier ist die andere Hälfte dieser Regel: er sieht
anders aus, und er bietet etwas an, das man dagegen tun kann.

Gesendet wird nichts. Der Dialog schreibt einen Ordner, sagt wo er liegt und
bietet an, ihn zu öffnen; ob irgendetwas irgendwohin geht, ist die Entscheidung
des Nutzers — und deshalb geht der Ordner auch nicht von selbst auf. Das Angebot,
das Projekt anzuhängen, sagt klar, dass die Geometrie mitreist — denn genau das
muss jemand wissen, bevor er eine Datei einem Fremden gibt.
"""

from __future__ import annotations

import traceback
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
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

        # **Wohin es gelegt wurde, ist die halbe Auskunft.** Die Kopfzeile
        # darüber bittet, „den abgelegten Ordner" zu schicken — welcher das ist,
        # stand nirgends: Der Pfad ging in die Vorschau und im gleichen Atemzug
        # kam ``accept()``, also war er weg, bevor ihn jemand lesen konnte. Er
        # steht jetzt in einer eigenen Zeile, auswählbar, und bleibt stehen.
        self.location = QLabel(self)
        self.location.setWordWrap(True)
        self.location.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.location.hide()

        buttons = QDialogButtonBox(self)
        self.write_button = buttons.addButton(
            tr("Bericht ablegen"), QDialogButtonBox.ButtonRole.AcceptRole
        )
        # ``ActionRole`` löst weder ``accepted`` noch ``rejected`` aus — der
        # Knopf soll den Dialog ja gerade **nicht** schließen, sonst wäre der
        # Pfad wieder weg. Verbunden wird deshalb sein eigenes ``clicked``.
        self.reveal_button = buttons.addButton(
            tr("Ordner öffnen"), QDialogButtonBox.ButtonRole.ActionRole
        )
        self.reveal_button.clicked.connect(self._reveal)
        self.reveal_button.hide()
        buttons.addButton(tr("Schließen"), QDialogButtonBox.ButtonRole.RejectRole)
        buttons.accepted.connect(self._write)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(headline)
        layout.addWidget(self.preview, stretch=1)
        layout.addWidget(self.with_log)
        layout.addWidget(self.with_project)
        layout.addWidget(self.location)
        layout.addWidget(buttons)

        self.written: Path | None = None

    def _refresh(self) -> None:
        self.report.include_log = self.with_log.isChecked()
        self.report.include_project = self.with_project.isChecked()
        self.preview.setPlainText(reports.as_text(self.report))

    def _write(self) -> None:
        """Ablegen — und offen bleiben, damit man den Ort noch lesen kann.

        Hier stand ``accept()``, direkt hinter der Zeile, die den Pfad in die
        Vorschau schrieb: Der Dialog nannte den Ordner und verschwand im
        gleichen Augenblick. Wer danach die Bitte aus der Kopfzeile erfüllen
        wollte — „senden Sie den abgelegten Ordner an …" —, musste den
        Ablageort erraten.

        Ein zweiter Druck auf „Bericht ablegen" würde einen zweiten Ordner
        anlegen; der Knopf ist danach also fertig, nicht bloß gedrückt.
        """
        self._refresh()
        self.written = reports.write(self.report, self.project)
        self.location.setText(f"{tr('Abgelegt unter')}: {self.written}")
        self.location.show()
        self.reveal_button.show()
        self.write_button.setEnabled(False)
        _log.info("error report prepared in %s", self.written)

    def _reveal(self) -> None:
        """Den abgelegten Ordner im Dateiverwalter zeigen.

        Von Hand und nicht von selbst: Ein Fenster, das sich nach einem Absturz
        ungefragt über die Anwendung legt, ist ein zweiter Schreck.
        """
        if self.written is None:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self.written)))
