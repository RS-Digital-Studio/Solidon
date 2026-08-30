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
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME, APP_VERSION
from app.core import changes
from app.i18n import tr
from app.ui.style import NORMAL, set_level

#: Womit der Dialog aufgeht. Eine **Anfangsgröße**, kein Deckel: Der Deckel
#: saß vorher als ``setMaximumHeight`` auf dem Rollbereich, und wer das
#: Fenster größer zog, vergrößerte damit nur die Leere darüber — die Liste
#: blieb bei 420 Bildpunkten stehen (Robert, 26.08.2026, mit Bild). Was den
#: Bildschirmrand schützt, ist die Größe beim Öffnen; was der Nutzer danach
#: zieht, gehört der Liste.
INITIAL_SIZE = (640, 620)


def history_html(entries: tuple[changes.Entry, ...], current: str = APP_VERSION) -> str:
    """Der Verlauf als Auszeichnung, mit der laufenden Fassung markiert.

    Gegliedert, wie die Datei es vorgibt: je Version die Gruppen mit
    unterstrichener Überschrift, darunter ihre Punkte als Liste. Unterstrichen
    **und** halbfett — die zweite Kodierung neben der Auszeichnung ist hier
    nicht Farbe, aber dieselbe Regel: Eine Gruppenzeile muss sich von einem
    Punkt auch dann unterscheiden, wenn man nur Helligkeit sieht (Regel 18).
    Ein Abschnitt ohne Gruppen (die Fassungen vor 0.2.0) liest sich wie
    bisher: eine Liste unter der Versionszeile.

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
            title += " — " + html.escape(tr("diese Version"))
        blocks.append(f'<h3 style="margin-bottom:2px">{title}</h3>')
        blocks.append(groups_html(entry.groups))
    return "".join(blocks)


def groups_html(groups: tuple[changes.Group, ...]) -> str:
    """Ein Bündel Gruppen als Auszeichnung — Überschrift, darunter die Punkte.

    **Ausgelagert, weil zwei Fenster dasselbe zeigen.** Der Verlauf unter
    *Hilfe → Neuerungen* gliedert seit 0.2.0 so, und das Update-Fenster zeigt
    dieselben Punkte, nur für eine einzige Fassung — es holt sie über
    ``updates.Release.grouped``. Zwei Formulierungen derselben Darstellung
    wären zwei Gelegenheiten, auseinanderzulaufen; genau daran ist die
    Menütiefe schon einmal gescheitert.

    Eine Gruppe ohne Titel liest sich wie bisher: eine Liste ohne Überschrift.
    Das ist der Vorspann eines Abschnitts, der Stand vor 0.2.0 — und der
    Rückfall, wenn eine Versionsdatei gar keine Gruppen mitbringt.
    """
    blocks: list[str] = []
    for group in groups:
        if group.title:
            heading = html.escape(group.title)
            blocks.append(f'<p style="margin-top:10px;margin-bottom:0"><b><u>{heading}</u></b></p>')
        points = "".join(f"<li>{html.escape(point)}</li>" for point in group.points)
        blocks.append(f'<ul style="margin-top:4px">{points}</ul>')
    return "".join(blocks)


class ChangesDialog(QDialog):
    """Der Verlauf, je eine über das Auswahlfeld gewählte Fassung."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Neuerungen"))
        self.setMinimumWidth(560)

        self.entries = changes.history()

        self.headline = QLabel(self)
        self.headline.setWordWrap(True)
        self.headline.setText(
            tr("Was sich in {app} geändert hat. Sie benutzen {version}.").format(
                app=APP_NAME, version=APP_VERSION
            )
        )

        self.version_label = QLabel(tr("Version"), self)
        self.version_choice = QComboBox(self)
        self.version_choice.setAccessibleName(tr("Version"))
        for entry in self.entries:
            label = entry.version
            if entry.version == APP_VERSION:
                label += " — " + tr("diese Version")
            self.version_choice.addItem(label, entry.version)

        current_index = next(
            (index for index, entry in enumerate(self.entries) if entry.version == APP_VERSION),
            0,
        )
        if self.entries:
            self.version_choice.setCurrentIndex(current_index)

        self.picker = QWidget(self)
        picker_layout = QHBoxLayout(self.picker)
        picker_layout.setContentsMargins(0, 0, 0, 0)
        picker_layout.setSpacing(NORMAL)
        picker_layout.addWidget(self.version_label)
        picker_layout.addWidget(self.version_choice, 1)
        self.picker.setVisible(bool(self.entries))

        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        set_level(self.summary, "caption")
        self.summary.setVisible(bool(self.entries))

        self.body = QLabel(self)
        self.body.setWordWrap(True)
        self.body.setTextFormat(Qt.TextFormat.RichText)
        self.body.setAlignment(Qt.AlignmentFlag.AlignTop)
        # **Keine Verweise nach draußen.** Der Text trägt keine, und wenn eines
        # Tages einer hineinrutscht, soll er nicht ungefragt einen Browser
        # öffnen — dieselbe Zurückhaltung wie beim Update-Fenster.
        self.body.setOpenExternalLinks(False)
        self.body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.setText("")

        self.scroller = QScrollArea(self)
        self.scroller.setWidget(self.body)
        self.scroller.setWidgetResizable(True)
        self.scroller.setFrameShape(QScrollArea.Shape.NoFrame)

        # **Der leere Fall ist kein Fehler und bekommt trotzdem einen Satz.**
        # Er entsteht, wenn der Verlauf im Paket fehlt; ein leerer Kasten ließe
        # den Nutzer raten, ob es nichts gibt oder etwas kaputt ist.
        self.empty = QLabel(tr("Für diese Version liegt kein Verlauf bei."), self)
        self.empty.setWordWrap(True)
        self.empty.setVisible(not self.entries)
        self.scroller.setVisible(bool(self.entries))

        self.version_choice.currentIndexChanged.connect(self._show_selected)
        self._show_selected(self.version_choice.currentIndex())

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.headline)
        layout.addWidget(self.picker)
        layout.addWidget(self.summary)
        layout.addWidget(self.empty)
        # Der Rollbereich bekommt jeden gezogenen Bildpunkt (Stretch 1):
        # Überschrift und Knöpfe brauchen nicht mehr, als sie haben, und ein
        # größeres Fenster soll mehr Verlauf zeigen, nicht mehr Leere.
        layout.addWidget(self.scroller, 1)
        layout.addWidget(buttons)
        self.resize(*INITIAL_SIZE)

    def _show_selected(self, index: int) -> None:
        """Zeigt genau die gewählte Fassung und setzt den Lesebeginn zurück."""
        if index < 0:
            self.body.clear()
            self.summary.clear()
            return
        version = self.version_choice.itemData(index)
        selected = tuple(entry for entry in self.entries if entry.version == version)
        self.body.setText(history_html(selected))
        if selected:
            entry = selected[0]
            changes_count = len(entry.points)
            topics_count = len(entry.groups)
            changes_word = tr(
                "Neuerung" if changes_count == 1 else "Neuerungen",
                context="Changelog-Zähler",
            )
            topics_word = tr(
                "Thema" if topics_count == 1 else "Themen",
                context="Changelog-Zähler",
            )
            self.summary.setText(f"{changes_count} {changes_word} · {topics_count} {topics_word}")
        else:
            self.summary.clear()
        self.scroller.verticalScrollBar().setValue(0)
