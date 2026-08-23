"""Was neu ist — der Verlauf, jederzeit nachlesbar (Bauplan §37.2).

**Warum es diesen Dialog gibt.** Die Punkte einer Fassung standen bis 0.1.3 an
genau einer Stelle: im Update-Fenster, und das erscheint nur, wenn es etwas
Neueres gibt. Wer wissen wollte, was die Fassung gebracht hat, die er gerade
benutzt, fand es nirgends — und wer den Hinweis einmal weggeklickt hatte, kam
nicht mehr an ihn heran.

Der Verlauf reist deshalb im Paket mit (``core.changes``) und steht unter
*Hilfe → Neuerungen*. Kein Netz, kein Server, keine Frage nach draußen: Das
hier ist das, was in der eigenen Installation ohnehin schon liegt.

Ein Dialog und kein Fenster, anders als beim Handbuch: Man liest ihn einmal
durch und arbeitet weiter. Das Handbuch bleibt daneben offen, weil man darin
nachschlägt, während man etwas tut.
"""

from __future__ import annotations

import html

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME, APP_VERSION
from app.core import changes
from app.i18n import tr
from app.ui.style import NORMAL

#: Wie hoch der Rollbereich höchstens wird. Derselbe Grund wie im
#: Update-Fenster: Ein Dialog, der über den Bildschirmrand wächst, verliert
#: seine Knöpfe nach unten — und der Verlauf wird mit jeder Fassung länger.
HISTORY_MAX_HEIGHT = 420


def history_html(entries: tuple[changes.Entry, ...], current: str = APP_VERSION) -> str:
    """Der Verlauf als Auszeichnung, mit der laufenden Fassung markiert.

    ``html.escape`` auf jedem Punkt, obwohl der Text aus dem eigenen Paket
    kommt und nicht von einem Server: Ein Punkt, der ein ``<`` enthält — „Wände
    unter 2 Extrusionsbreiten" ließe sich so schreiben —, verschwände sonst
    samt allem bis zum nächsten ``>``. Das ist kein Angriff, nur ein Satz, der
    dann fehlt.
    """
    blocks: list[str] = []
    for entry in entries:
        title = html.escape(entry.version)
        if entry.version == current:
            title += " — " + html.escape(tr("diese Fassung"))
        points = "".join(f"<li>{html.escape(point)}</li>" for point in entry.points)
        blocks.append(f"<p><b>{title}</b></p><ul>{points}</ul>")
    return "".join(blocks)


class ChangesDialog(QDialog):
    """Der Verlauf, von der neuesten Fassung abwärts."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Neuerungen"))
        self.setMinimumWidth(560)

        entries = changes.history()

        self.headline = QLabel(self)
        self.headline.setWordWrap(True)
        self.headline.setText(
            tr("Was sich in {app} geändert hat. Sie benutzen {version}.").format(
                app=APP_NAME, version=APP_VERSION
            )
        )

        self.body = QLabel(self)
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        # **Keine Verweise nach draußen.** Der Text trägt keine, und wenn eines
        # Tages einer hineinrutscht, soll er nicht ungefragt einen Browser
        # öffnen — dieselbe Zurückhaltung wie beim Update-Fenster.
        self.body.setOpenExternalLinks(False)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.setText(history_html(entries))

        self.scroller = QScrollArea(self)
        self.scroller.setWidget(self.body)
        self.scroller.setWidgetResizable(True)
        self.scroller.setFrameShape(QScrollArea.Shape.NoFrame)
        self.scroller.setMaximumHeight(HISTORY_MAX_HEIGHT)

        # **Der leere Fall ist kein Fehler und bekommt trotzdem einen Satz.**
        # Er entsteht, wenn der Verlauf im Paket fehlt; ein leerer Kasten ließe
        # den Nutzer raten, ob es nichts gibt oder etwas kaputt ist.
        self.empty = QLabel(tr("Für diese Fassung liegt kein Verlauf bei."), self)
        self.empty.setWordWrap(True)
        self.empty.setVisible(not entries)
        self.scroller.setVisible(bool(entries))

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.headline)
        layout.addWidget(self.empty)
        layout.addWidget(self.scroller)
        layout.addWidget(buttons)
