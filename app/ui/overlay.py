"""Zonen, die über der Ansicht liegen statt neben ihr (Bauplan §2.5).

Das Fensterschema nennt drei Zonen — links Objektbaum, Parameter und Verlauf;
in der Mitte die Ansicht; rechts Prüfbericht oder Chat. Es sagt nicht, dass die
äußeren beiden der mittleren ihre Fläche wegnehmen müssen. Genau das taten sie:
ein Objektbaum mit einer Zeile besetzte zweihundertachtzig Pixel Breite über
die volle Höhe, und das Teil, um das es geht, bekam die Hälfte des Fensters.

Hier liegen dieselben drei Zonen als Karten **über** der Ansicht. Die Ansicht
füllt das Fenster; wo nichts steht, sieht man das Modell. Zugeklappt gibt eine
Zone ihre Fläche vollständig zurück, statt eine leere Spalte zu hinterlassen.

**Warum das mit VTK geht.** Der Kommentar am Skizzenumschalter warnt davor, Qt
über OpenGL zu legen — er meint ein Modul, das die Ansicht *ersetzt*, und für
das gilt er weiter. Ein Kind-Widget über dem Plotter ist etwas anderes: der
Vorschau-Banner tut es seit je. Neu ist nur, dass diese Karten auch Klicks
annehmen, und das wurde vor dem Umbau gemessen — Knopf, Eingabefeld und
``childAt`` an derselben Stelle.

Die Breiten sind Zahlen und keine Ziehleiste. Ein Splitter zwischen
schwebenden Karten hätte nichts zu teilen: sie nehmen einander nichts weg.
"""

from __future__ import annotations

from PySide6.QtCore import QEvent, QModelIndex, QObject, Qt
from PySide6.QtWidgets import QAbstractItemView, QTreeView, QWidget

from app.ui.style import ROOMY, SPACE
from app.ui.theme import THEMES, Theme

#: Breite der linken Zone. Breit genug für „Schraubenloch mit Senkung" in der
#: Verlaufsliste, schmal genug, dass daneben noch ein Modell steht.
LEFT_WIDTH = 260

#: Breite der rechten Zone. Ein Befund ist ein Satz, kein Absatz — schmaler
#: als links, weil hier nichts eingerückt ist.
RIGHT_WIDTH = 300

#: Abstand der Karten zum Fensterrand und zueinander.
MARGIN = ROOMY


def card_stylesheet(theme: Theme) -> str:
    """Das Aussehen einer schwebenden Karte, gespeist aus dem Thema.

    Eine Karte über der Ansicht braucht zwingend eine *deckende* Fläche: sonst
    steht ihr Text auf dem Modell, und beides ist grau. Der Rand ist keine
    Zierde, sondern die Kante, an der die Karte aufhört.

    **Wo das hingehört:** nach ``style.py``, zu den übrigen Formregeln. Es
    steht hier, weil die Karten neu sind und jene Datei gerade an anderer
    Stelle umgebaut wird; zusammengelegt wird, sobald das durch ist.
    """
    colours = THEMES[theme]
    return f"""
QWidget#overlayCard {{
    background: {colours["window"]};
    border: 1px solid {colours["line"]};
    border-radius: {ROOMY}px;
}}
"""


def rows_height(view: QAbstractItemView) -> int:
    """Wie hoch die Zeilen dieser Liste zusammen sind, mit Kopf und Rahmen.

    Qt gibt einer Liste eine Wunschhöhe, die mit ihrem Inhalt nichts zu tun hat
    — rund zweihundert Pixel, ob eine Zeile darin steht oder hundert. Neben
    einer Ansicht war das eine leere Spalte; über einer Ansicht ist es eine
    Karte, die das Modell verdeckt, um nichts zu zeigen.

    Gezählt werden die *sichtbaren* Zeilen: ein zugeklappter Ast zählt als eine
    Zeile, nicht als seine Kinder.
    """
    model = view.model()
    tree = view if isinstance(view, QTreeView) else None

    def rows_in(parent: QModelIndex) -> int:
        """Die echte Höhe der Zeilen unter ``parent``, nicht ihre Zahl.

        Gerechnet wird mit ``rowHeight`` statt mit „Zeilen mal Zeilenhöhe": ein
        umgebrochener Befund im Prüfbericht ist zwei Zeilen hoch, und eine
        Rechnung, die ihn für eine hält, schneidet ihn ab. Genau das ließ die
        Karte einen Rollbalken zeigen, wo alles hineingepasst hätte.
        """
        total = 0
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            if tree is not None:
                total += tree.rowHeight(index)
                if tree.isExpanded(index):
                    total += rows_in(index)
            else:
                total += view.sizeHintForRow(row)
        return total

    wanted = rows_in(QModelIndex())
    if wanted <= 0:
        # Eine Zeile Höhe auch dann, wenn keine da ist: eine Liste, die auf
        # null zusammenfällt, sieht aus wie ein Fehler und nicht wie eine
        # leere Liste.
        wanted = view.fontMetrics().height() + 2 * SPACE

    # Was die Liste über ihren Zeilen noch braucht — Rahmen und, beim Baum,
    # die Spaltenköpfe. Aus der Differenz gelesen und nicht aus einzelnen
    # Zahlen zusammengesetzt: das Stylesheet darf beides ändern, ohne dass
    # hier jemand nachzieht.
    viewport = view.viewport()
    if viewport is not None:
        wanted += view.height() - viewport.height()
    return wanted


def natural_height(zone: QWidget) -> int:
    """Die Höhe, bei der der Inhalt einer Zone genau hineinpasst.

    Qts eigene Wunschhöhe taugt dafür nicht, weil die Listen darin ihre
    beisteuern (siehe ``rows_height``). Gerechnet wird deshalb: was die Zone
    ohne ihre Listen bräuchte, plus das, was die Listen wirklich brauchen.
    """
    wanted = zone.sizeHint().height()
    for view in zone.findChildren(QAbstractItemView):
        if not view.isVisibleTo(zone):
            continue
        wanted += rows_height(view) - view.sizeHint().height()
    return max(wanted, 0)


class OverlayHost(QWidget):
    """Die Ansicht füllt die Fläche, die Zonen liegen darüber.

    Positioniert wird in ``resizeEvent`` und nicht über ein Layout: ein Layout
    teilt Fläche auf, und genau das soll hier niemand tun. Die Karten bekommen
    ihre Geometrie zugewiesen, die Ansicht bekommt alles.
    """

    def __init__(self, view: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Vor ``setParent``: das Umhängen löst sofort ein Resize aus, und
        # ``_place`` fragt dort nach den drei Zonen. Stünden sie erst danach,
        # stürbe das Fenster beim Bauen.
        self.left: QWidget | None = None
        self.right: QWidget | None = None
        self.bottom: QWidget | None = None

        self.view = view
        view.setParent(self)

    def set_zones(self, left: QWidget, right: QWidget, bottom: QWidget) -> None:
        """Die drei Zonen anmelden. Reihenfolge legt fest, was oben liegt."""
        for zone in (left, right, bottom):
            zone.setParent(self)
            zone.raise_()
            # Ohne das malt Qt den Elternhintergrund unter die Karte, und der
            # ist hier das OpenGL-Fenster — die Karte bekäme ein schwarzes
            # Rechteck statt der Ansicht hinter ihren runden Ecken.
            zone.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.left, self.right, self.bottom = left, right, bottom
        # Eine zugeklappte Zone soll ihre Fläche zurückgeben. Qt meldet die
        # neue Wunschhöhe erst, wenn jemand danach fragt — also fragen wir bei
        # jeder Änderung an einem Kind nach.
        for zone in (left, right, bottom):
            zone.installEventFilter(self)
        self._place()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        """Ändert sich eine Zone, wird neu gerechnet, nicht nur neu gezeichnet.

        ``LayoutRequest`` ist dabei der wichtigste Fall: Qt schickt ihn, wenn
        eine Liste darin Zeilen bekommt oder verliert. Ohne ihn bliebe eine
        Karte so hoch, wie sie beim Aufbau war — und der Objektbaum wäre nach
        dem Öffnen eines Projekts genauso leer aussehend wie davor.
        """
        if event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Hide,
            QEvent.Type.LayoutRequest,
        ):
            self._place()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: object) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._place()

    def _place(self) -> None:
        """Ansicht auf die ganze Fläche, Karten an ihre Ränder."""
        self.view.setGeometry(0, 0, self.width(), self.height())
        if self.left is None or self.right is None or self.bottom is None:
            return

        height = self.height()
        width = self.width()

        # Links und rechts hängen oben und wachsen nur so weit nach unten, wie
        # ihr Inhalt reicht — höchstens bis kurz vors untere Ende, damit die
        # Werkzeugzeile frei bleibt.
        room = max(height - 2 * MARGIN - self._bottom_room(), 0)

        if self.left.isVisibleTo(self):
            wanted = min(natural_height(self.left), room)
            self.left.setGeometry(MARGIN, MARGIN, LEFT_WIDTH, wanted)

        if self.right.isVisibleTo(self):
            wanted = min(natural_height(self.right), room)
            self.right.setGeometry(width - RIGHT_WIDTH - MARGIN, MARGIN, RIGHT_WIDTH, wanted)

        # Die Werkzeugzeile sitzt mittig unten und ist so breit, wie sie sein
        # muss — nicht so breit wie das Fenster.
        if self.bottom.isVisibleTo(self):
            size = self.bottom.sizeHint()
            wanted = min(size.width(), width - 2 * MARGIN)
            self.bottom.setGeometry(
                (width - wanted) // 2, height - size.height() - MARGIN, wanted, size.height()
            )

    def _bottom_room(self) -> int:
        """Wie viel Höhe die Werkzeugzeile unten für sich braucht."""
        if self.bottom is None or not self.bottom.isVisibleTo(self):
            return 0
        return self.bottom.sizeHint().height() + MARGIN
