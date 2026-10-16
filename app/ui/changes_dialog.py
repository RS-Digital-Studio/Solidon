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

from app import branding
from app.branding import APP_NAME, website_page_url
from app.core import changes
from app.core.markup import inline
from app.i18n import get_language, native_text, tr
from app.ui.scroll_areas import ReadingScrollArea
from app.ui.style import NORMAL, WIDE, no_primary, set_level

#: Womit der Dialog aufgeht. Eine **Anfangsgröße**, kein Deckel: Der Deckel
#: saß vorher als ``setMaximumHeight`` auf dem Rollbereich, und wer das
#: Fenster größer zog, vergrößerte damit nur die Leere darüber — die Liste
#: blieb bei 420 Bildpunkten stehen (Robert, 26.08.2026, mit Bild). Was den
#: Bildschirmrand schützt, ist die Größe beim Öffnen; was der Nutzer danach
#: zieht, gehört der Liste.
INITIAL_SIZE = (640, 620)


#: Der Objektname des Vorspann-Kastens; das Stylesheet hebt ihn darüber hervor
#: (``style.stylesheet``, Akzentkante und Fläche, dazu Stufe ``section``).
LEAD_BOX = "changesLead"


def lead_box(parent: QWidget) -> QLabel:
    """Der Kasten für die Meldung, die jedem Nutzer gilt — über allen Gruppen.

    **Ein eigenes Label und keine Zeile im Text darunter**, weil nur das
    Stylesheet die Farben des Themas kennt und beim Themenwechsel nachzieht;
    Rich Text bekäme sie als feste Werte. Hervorgehoben wird zweifach
    (Regel 18): Die Akzentkante samt Fläche trägt die Farbe, die größere und
    halbfette Schrift (Stufe ``section``) und die Kante als Form tragen es
    auch ohne Farbsehen.

    Dieselbe Zurückhaltung wie in der Liste: kein Verweis wirkt, markieren
    geht. Der Inhalt kommt im Update-Fenster vom Server und ist maskiert.
    """
    box = QLabel(parent)
    box.setObjectName(LEAD_BOX)
    box.setWordWrap(True)
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setOpenExternalLinks(False)
    box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    set_level(box, "section")
    box.setVisible(False)
    return box


def lead_html(points: tuple[str, ...]) -> str:
    """Die Punkte eines Vorspanns als Absätze, ausgezeichnet wie die Liste."""
    language = get_language()
    return "".join(
        f'<p style="margin:0">{inline(native_text(point, language))}</p>' for point in points
    )


def history_html(
    entries: tuple[changes.Entry, ...],
    current: str = branding.APP_VERSION,
    *,
    lead_apart: bool = False,
) -> str:
    """Der Verlauf als Auszeichnung, mit der laufenden Fassung markiert.

    Gegliedert, wie die Datei es vorgibt: je Version die Gruppen mit
    unterstrichener Überschrift, darunter ihre Punkte als Liste. Unterstrichen
    **und** halbfett — die zweite Kodierung neben der Auszeichnung ist hier
    nicht Farbe, aber dieselbe Regel: Eine Gruppenzeile muss sich von einem
    Punkt auch dann unterscheiden, wenn man nur Helligkeit sieht (Regel 18).
    Ein Abschnitt ohne Gruppen (die Fassungen vor 0.2.0) liest sich wie
    bisher: eine Liste unter der Versionszeile.

    Jeder Punkt geht maskiert durch ``markup.inline`` (``groups_html``), obwohl
    der Text aus dem eigenen Paket kommt und nicht von einem Server: Ein Punkt,
    der ein ``<`` enthält — „Wände
    unter 2 Extrusionsbreiten" ließe sich so schreiben —, verschwände sonst
    samt allem bis zum nächsten ``>``. Das ist kein Angriff, nur ein Satz, der
    dann fehlt.

    ``lead_apart`` lässt den Vorspann weg, weil der Aufrufer ihn in seinem
    eigenen Kasten zeigt (:func:`lead_box`); ohne den Schalter steht er wie
    bisher als Liste ohne Überschrift vorn.
    """
    blocks: list[str] = []
    for entry in entries:
        title = html.escape(entry.version)
        if entry.version == current:
            title += " — " + html.escape(tr("diese Version"))
        blocks.append(f'<h3 style="margin-bottom:2px">{title}</h3>')
        blocks.append(groups_html(entry.topics if lead_apart else entry.groups))
    return "".join(blocks)


def groups_html(groups: tuple[changes.Group, ...]) -> str:
    """Ein Bündel Gruppen als Auszeichnung — Überschrift, darunter die Punkte.

    **Ausgelagert, weil zwei Fenster dasselbe zeigen.** Der Verlauf unter
    *Hilfe → Neuerungen* gliedert seit 0.2.0 so, und das Update-Fenster zeigt
    dieselben Punkte, nur für eine einzige Fassung — es holt sie über
    ``updates.Release.grouped``. Zwei Formulierungen derselben Darstellung
    wären zwei Gelegenheiten, auseinanderzulaufen; genau daran ist die
    Menütiefe schon einmal gescheitert.

    Eine Gruppe ohne Titel liest sich als Liste ohne Überschrift: der Stand
    vor 0.2.0 und der Rückfall einer Versionsdatei ohne Gruppen. Einen
    Vorspann (``changes.lead_of``) nehmen die Aufrufer vorher heraus.
    """
    blocks: list[str] = []
    # Die Punkte kommen aus einer Datei, nicht durch ``tr``: Ihre Kürzel
    # schreibt erst diese Stelle so, wie die Tastatur sie beschriftet (⌘Z),
    # in der Sprache des Fensters, aus deren Datei sie stammen.
    language = get_language()
    for group in groups:
        if group.title:
            heading = html.escape(native_text(group.title, language))
            blocks.append(f'<p style="margin-top:10px;margin-bottom:0"><b><u>{heading}</u></b></p>')
        # ``inline`` und nicht nur maskieren: Die Punkte heben Handlungen wie
        # *Druckoptimal ausrichten* hervor, und maskiert standen die Sternchen
        # im Text. Maskiert wird darin trotzdem alles andere.
        points = "".join(
            f"<li>{inline(native_text(point, language))}</li>" for point in group.points
        )
        blocks.append(f'<ul style="margin-top:4px">{points}</ul>')
    return "".join(blocks)


class ChangesDialog(QDialog):
    """Der Verlauf, je eine über das Auswahlfeld gewählte Fassung."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Neuerungen"))
        self.setMinimumWidth(560)

        # **Die letzten drei und nicht alle** (Entscheidung Robert,
        # 09.09.2026). Die Begründung steht bei :func:`changes.recent`; hier
        # zählt die Folge: Was der Dialog weglässt, muss er nennen — sonst
        # sähen die drei Einträge aus wie der ganze Verlauf, und wer eine
        # Fassung übersprungen hat, suchte sie vergeblich.
        self.entries = changes.recent()

        self.headline = QLabel(self)
        self.headline.setWordWrap(True)
        self.headline.setText(
            tr("Was sich in {app} geändert hat. Sie benutzen {version}.").format(
                app=APP_NAME, version=branding.APP_VERSION
            )
        )

        self.version_label = QLabel(tr("Version"), self)
        self.version_choice = QComboBox(self)
        self.version_choice.setAccessibleName(tr("Version"))
        for entry in self.entries:
            label = entry.version
            if entry.version == branding.APP_VERSION:
                label += " — " + tr("diese Version")
            self.version_choice.addItem(label, entry.version)

        current_index = next(
            (
                index
                for index, entry in enumerate(self.entries)
                if entry.version == branding.APP_VERSION
            ),
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

        # **Der Vorspann der gewählten Fassung** — die Meldung, die jedem gilt,
        # über den Gebieten und nicht als erster Punkt darin (Entscheidung
        # Robert). Gefüllt in ``_show_selected``; ohne Vorspann bleibt er weg.
        self.lead = lead_box(self)

        # **Hier darf ein Verweis wirken**, anders als in der Liste darunter:
        # Der Satz ist unser eigener und die Adresse baut die Anwendung aus
        # ihrer Sprache — es kommt nichts von außen hinein. Dieselbe Abwägung
        # trifft das Update-Fenster für seinen gekürzten Auszug.
        self.older = QLabel(self)
        self.older.setWordWrap(True)
        self.older.setTextFormat(Qt.TextFormat.RichText)
        # **Auch mit der Tastatur erreichbar.** Ohne
        # ``LinksAccessibleByKeyboard`` ist ein QLabel-Verweis nur mit der Maus
        # zu haben und für einen Bildschirmleser stumm — der Skizzeneditor hat
        # denselben Satz aufgeschrieben. Hier wiegt es schwerer als dort: Seit
        # der Dialog nur noch drei Fassungen zeigt, ist dieser Verweis der
        # einzige Weg zu den übrigen.
        self.older.setTextInteractionFlags(
            Qt.TextInteractionFlag.LinksAccessibleByMouse
            | Qt.TextInteractionFlag.LinksAccessibleByKeyboard
            | Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.older.setOpenExternalLinks(True)
        set_level(self.older, "caption")
        # ``html.escape`` auf dem Linktext, obwohl er aus dem eigenen Katalog
        # kommt: Dieselbe Zurückhaltung wie bei jedem Punkt darunter, und eine
        # Übersetzung mit einem ``&`` darin bräche sonst die Auszeichnung.
        self.older.setText(
            tr("Gezeigt sind die letzten {count} Versionen.").format(count=len(self.entries))
            + ' <a href="'
            + html.escape(website_page_url("changelog.html", get_language()), quote=True)
            + f'">{html.escape(tr("Vollständiger Verlauf auf der Website"))}</a>'
        )
        # Sichtbar nur, wenn wirklich etwas fehlt: In einem Paket mit drei
        # Fassungen oder weniger wäre der Satz eine Auskunft über nichts.
        self.older.setVisible(len(changes.history()) > len(self.entries))

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

        self.scroller = ReadingScrollArea(
            tr("Neuerungen"), tr("Mit Pfeil- und Bildtasten blättern."), self
        )
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
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        layout.addWidget(self.headline)
        layout.addWidget(self.picker)
        layout.addWidget(self.summary)
        layout.addWidget(self.empty)
        layout.addWidget(self.lead)
        # Der Rollbereich bekommt jeden gezogenen Bildpunkt (Stretch 1):
        # Überschrift und Knöpfe brauchen nicht mehr, als sie haben, und ein
        # größeres Fenster soll mehr Verlauf zeigen, nicht mehr Leere.
        layout.addWidget(self.scroller, 1)
        # Unter der Liste und nicht über ihr: Der Hinweis gilt dem, was der
        # Leser **nicht** findet, und danach sucht er erst, wenn er die drei
        # gelesen hat.
        layout.addWidget(self.older)
        layout.addWidget(buttons)
        # **„Schließen" ist nie ein Hauptknopf**, und genau der stand hier im
        # Akzent: Qt macht beim ersten ``show()`` den ersten autoDefault-Knopf
        # zum Default, und in einem Fenster, das nur „Schließen" hat, trifft es
        # ihn. Das Änderungsfenster zeigt, was neu ist; es verlangt nichts.
        no_primary(self)
        self.resize(*INITIAL_SIZE)

    def _show_selected(self, index: int) -> None:
        """Zeigt genau die gewählte Fassung und setzt den Lesebeginn zurück."""
        if index < 0:
            self.body.clear()
            self.summary.clear()
            self.lead.clear()
            self.lead.setVisible(False)
            return
        version = self.version_choice.itemData(index)
        selected = tuple(entry for entry in self.entries if entry.version == version)
        self.body.setText(history_html(selected, lead_apart=True))
        lead = selected[0].lead if selected else None
        self.lead.setText(lead_html(lead.points) if lead is not None else "")
        self.lead.setVisible(lead is not None)
        if selected:
            entry = selected[0]
            changes_count = len(entry.points)
            # Der Vorspann ist kein Thema: Er gehört keinem Gebiet an.
            topics_count = len(entry.topics)
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
