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

from typing import Protocol, runtime_checkable

from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QModelIndex,
    QObject,
    QPropertyAnimation,
    QRect,
    QRectF,
    Qt,
)
from PySide6.QtGui import QPainterPath, QRegion
from PySide6.QtWidgets import QAbstractItemView, QScrollArea, QTreeView, QWidget
from shiboken6 import isValid

from app.ui.style import ROOMY, SPACE
from app.ui.theme import THEMES, Theme


@runtime_checkable
class RoomTaker(Protocol):
    """Eine Karte, der die Überlagerung Höhe zuteilen kann.

    Wer diese beiden Methoden mitbringt, wird beim Setzen der Zonen gefragt,
    wie hoch er gern wäre, und bekommt gesagt, wie hoch er sein darf. Wer sie
    nicht mitbringt, behält seine eigene Höhe — die Parameterleiste etwa, die
    so hoch ist wie ihre Zeilen und nichts zu verteilen hat.
    """

    def height(self) -> int: ...

    def wanted_height(self) -> int:
        """Die Höhe, bei der alles zu sehen wäre."""
        ...

    def least_height(self) -> int:
        """Die Höhe, unter die die Karte nicht geht, was auch zugeteilt wird.

        Ohne diese Auskunft ist die Zuteilung eine Bitte: Die Verlaufskarte
        setzt drei Zeilen als Boden durch, meldete als Bedarf aber vier Pixel,
        und was anteilig danach verteilt wurde, ergab in der Summe mehr Höhe,
        als die Zone hatte.
        """
        ...

    def set_room(self, pixels: int) -> None:
        """Die Höhe, die zur Verfügung steht."""
        ...


#: Wie lange eine Karte für ihren Weg braucht.
#:
#: Bewegung ist hier kein Schmuck, sondern eine Auskunft: klappt ein Abschnitt
#: zu, springen die darunter an eine neue Stelle, und ohne Weg dazwischen muss
#: man raten, welcher wohin gewandert ist. Kurz genug, dass niemand darauf
#: wartet — deutlich unter der Schwelle, ab der eine Oberfläche träge wirkt.
#:
#: **Wo das hingehört:** nach ``style.py``, zu den übrigen Formregeln. Es steht
#: hier aus demselben Grund wie ``card_stylesheet``.
MOVE_MS = 160

#: Breite der linken Zone. Breit genug für „Schraubenloch mit Senkung" in der
#: Verlaufsliste, schmal genug, dass daneben noch ein Modell steht.
LEFT_WIDTH = 260

#: Breite der rechten Zone. Ein Befund ist ein Satz, kein Absatz — schmaler
#: als links, weil hier nichts eingerückt ist.
RIGHT_WIDTH = 300

#: Ab welcher Fensterbreite die Karten mitwachsen, und wie weit.
#:
#: Feste Breiten sind für 1920 gebaut und bleiben dort richtig. Auf einem
#: breiten Bildschirm werden sie zum Zwölftel des Fensters: die Maßspalte im
#: Objektbaum brach mitten in der Zahl ab — aus drei Maßen wurden zwei und ein
#: Auslassungszeichen —, während
#: daneben ein 20-mm-Würfel in zwei Metern Leere stand. Gewachsen wird
#: anteilig und mit Deckel — eine Karte, die mit dem Fenster mitwächst, wäre
#: bei 5000 Pixeln eine Wand.
GROWTH_SHARE = 0.13
LEFT_MAX = 420
RIGHT_MAX = 460

#: Abstand der Karten zum Fensterrand und zueinander.
MARGIN = ROOMY

#: Das Polster zwischen der Randlinie einer Karte und ihrem Inhalt.
#:
#: Genau ein Pixel, denn genau einen ist die Linie breit. Ohne ihn malen die
#: Kinder sie zu — Objektbaum, Verlaufsliste und die Seite des Reiters tragen
#: eigene Flächen und reichten bis an die Widgetkante. Sichtbar blieb der
#: Rahmen nur, wo zufällig ein Layout Abstand hielt: um „Objekte" lief er ganz
#: herum, ab der Kopfzeile der Liste fehlte rechts alles, ab „Verlauf" auch
#: links. Von der Kante, an der die Karte aufhört, blieb ein Haken oben links.
CARD_PADDING = 1


def living[T: QWidget](zone: QWidget, wanted: type[T]) -> list[T]:
    """Die Kinder dieser Art, deren C++-Seite noch lebt.

    **Die Python-Hülle überlebt die C++-Seite.** Nimmt ein Qt-Elternteil sein
    Kind mit, bleibt der Wrapper stehen — und die erste Frage an ihn, sei es
    ``isVisibleTo`` oder ``sizeHint``, ist dann die Zugriffsverletzung. Kein
    Absturz mit Zeile, sondern

        RuntimeError: Error calling Python override of QWidget::eventFilter():
        libshiboken: Internal C++ object (ObjectTree) already deleted.

    Gesehen im Belegslauf vom 23.08.2026 in zwei von vier Durchgängen, jedes
    Mal im Teardown und jedes Mal **nach** 257 bestandenen Tests: Der
    ``eventFilter`` dieser Datei läuft, während die Ereignisschleife ein
    letztes Mal angehalten wird, und geht dabei über Kinder, die der Abbau
    schon halb weggeräumt hat. Dasselbe passiert dem Kunden beim Schließen des
    Fensters — dort landet die Ausnahme auf stderr, wo sie niemand liest.

    An **einer** Stelle und nicht an fünf: `findChildren` steht in dieser Datei
    fünfmal, und eine Wache, die man je Aufrufstelle wiederholt, fehlt beim
    sechsten Mal. Die Fixture der Suite macht dasselbe für die obersten
    Fenster (``tests/conftest.py``); für die Kinder machte es niemand.

    **Was diese Funktion allein nicht leistet, und das gehört dazu:** Qt nimmt
    ein zerstörtes Kind selbst aus der Liste — nachgemessen, sowohl nach
    ``shiboken6.delete`` als auch nach ``deleteLater`` samt zugestelltem
    ``DeferredDelete``. Eine tote Hülle bekommt man hier also selten zu sehen.
    Der Absturz aus dem Belegslauf entsteht **zwischen** dem Sammeln und dem
    Zugriff: Der Speicherbereiniger läuft in dem Thread, dessen Allokation
    gerade die Schwelle reißt, und das kann jeder sein. Deshalb steht
    ``isValid`` zusätzlich dort, wo der Wert wirklich angefasst wird — die
    Liste allein schließt das Fenster nicht.
    """
    return [child for child in zone.findChildren(wanted) if isValid(child)]


def card_width(base: int, cap: int, window: int) -> int:
    """Wie breit eine Karte in einem Fenster dieser Breite sein soll.

    Unter etwa 2000 Pixeln kommt der Grundwert heraus — dort ändert sich
    nichts. Darüber wächst die Karte anteilig, bis sie den Deckel erreicht.
    """
    return int(min(max(base, window * GROWTH_SHARE), cap))


def card_stylesheet(theme: Theme) -> str:
    """Das Aussehen einer schwebenden Karte, gespeist aus dem Thema.

    Eine Karte über der Ansicht braucht zwingend eine *deckende* Fläche: sonst
    steht ihr Text auf dem Modell, und beides ist grau. Der Rand ist keine
    Zierde, sondern die Kante, an der die Karte aufhört.

    **Er trägt den Akzent, nicht die Trennfarbe.** Ein grauer Rand über einem
    grauen Modell in einem grauen Raum ist die Kante, die man sucht statt
    sieht — und das Fenster hatte, solange nichts ausgewählt war, keinen
    einzigen farbigen Punkt. Dass der Akzent damit an mehr als einer Stelle
    zugleich steht, ist der Preis dafür und war eine bewusste Entscheidung.

    **Wo das hingehört:** nach ``style.py``, zu den übrigen Formregeln. Es
    steht hier, weil die Karten neu sind und jene Datei gerade an anderer
    Stelle umgebaut wird; zusammengelegt wird, sobald das durch ist.

    **Der Rand braucht seinen eigenen Pixel.** Ohne das Polster darunter malen
    die Kinder ihn zu: Objektbaum, Verlaufsliste und die Seite des Reiters
    tragen eigene Flächen, und die reichten bis an die Widgetkante. Sichtbar
    blieb der Rahmen nur dort, wo zufällig ein Layout Abstand hielt — um
    „Objekte" lief er ganz herum, ab der Kopfzeile der Liste fehlte rechts
    alles, ab „Verlauf" auch links. Von einer Kante, an der die Karte aufhört,
    blieb ein Haken oben links.

    Das Reiterfeld bekommt es hier, weil ``::pane`` ein eigenes Subcontrol ist;
    die anderen Zonen bekommen es als Rand ihres Layouts (:data:`CARD_PADDING`).
    Ein ``padding`` im Stilblatt wäre der kürzere Weg und wirkt nicht: Qt
    verkleinert damit die Fläche eines schlichten ``QWidget`` nicht, und das
    Layout darin legt seine Kinder weiter auf die Randlinie.
    """
    colours = THEMES[theme]
    return f"""
QWidget#overlayCard {{
    background: {colours["window"]};
    border: 1px solid {colours["accent_line"]};
    border-radius: {ROOMY}px;
}}

QTabWidget#overlayCard::pane {{
    border: none;
    background: transparent;
    margin: 0px {CARD_PADDING}px {CARD_PADDING}px {CARD_PADDING}px;
}}
"""


def _round_corners(zone: QWidget) -> None:
    """Die vier Zwickel neben den runden Ecken freistellen.

    Das Stylesheet rundet die Karte, aber das Widget bleibt ein Rechteck —
    außerhalb der Rundung malt Qt den Elternhintergrund, und der ist hier das
    OpenGL-Fenster. Dort standen schwarze Zipfel, wo die Ansicht durchscheinen
    sollte.

    Über eine Maske und nicht über ``WA_TranslucentBackground``: das nimmt dem
    Widget auch das Löschen seiner Fläche, und dann steht jede Beschriftung
    doppelt übereinander — ausprobiert, sah schlimmer aus als die Zipfel.

    Der Preis ist eine harte Kante an der Rundung: eine Maske kennt nur ganz
    oder gar nicht. Bei zwölf Pixeln Radius fällt das weniger auf als vier
    schwarze Ecken auf hellem Modell.
    """
    if zone.width() <= 0 or zone.height() <= 0:
        return
    shape = QPainterPath()
    shape.addRoundedRect(QRectF(zone.rect()), float(ROOMY), float(ROOMY))
    zone.setMask(QRegion(shape.toFillPolygon().toPolygon()))


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
    if model is None:
        # Die Stubs behaupten, das könne nicht sein — eine Liste, die gerade
        # aufgebaut wird, hat aber keines. Eine Höhe von null ließe die Karte
        # zusammenfallen; dieselbe Antwort wie für eine leere Liste.
        return int(view.fontMetrics().height() + 2 * SPACE)  # type: ignore[unreachable]
    tree = view if isinstance(view, QTreeView) else None

    def rows_in(parent: QModelIndex) -> int:
        """Die echte Höhe der Zeilen unter ``parent``, nicht ihre Zahl.

        Gerechnet wird mit ``rowHeight`` statt mit „Zeilen mal Zeilenhöhe": ein
        umgebrochener Befund im Prüfbericht ist zwei Zeilen hoch, und eine
        Rechnung, die ihn für eine hält, schneidet ihn ab. Genau das ließ die
        Karte einen Rollbalken zeigen, wo alles hineingepasst hätte.

        Bei einer Liste ist die Quelle ``visualRect`` und **nicht**
        ``sizeHintForRow``. Der zweite kennt den Wortumbruch nicht: für die
        fünf Befunde, mit denen das Beispielprojekt öffnet, meldet er
        fünfmal 34 Pixel, während die Zeilen 58, 34, 42, 58 und 42 hoch
        sind — 170 gegen 234. Die Karte bekam die 170, und bei fünf
        Befunden stand ein Rollbalken in einer Spalte, neben der
        achthundert Pixel frei blieben.

        ``visualRect`` kennt die Wahrheit erst, wenn die Liste einmal
        gelegt wurde; solange sie das nicht ist, ist die Schätzung besser
        als eine Null. Deshalb der größere der beiden Werte.
        """
        total = 0
        for row in range(model.rowCount(parent)):
            index = model.index(row, 0, parent)
            if tree is not None:
                total += tree.rowHeight(index)
                if tree.isExpanded(index):
                    total += rows_in(index)
            else:
                total += max(view.visualRect(index).height(), view.sizeHintForRow(row))
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
    for view in living(zone, QAbstractItemView):
        if not view.isVisibleTo(zone):
            continue
        # Eine gesetzte Mindesthöhe ist eine Aussage über den Zweck und nicht
        # über den Inhalt: der Gesprächsverlauf des Chats ist ein
        # Arbeitsbereich, und leer bleibt er es. Ohne dieses ``max`` zog die
        # Zeilenrechnung ihn auf eine Zeile zurück, und die Karte stand auf
        # hundertsiebzig Pixeln neben tausendzweihundert freien.
        needs = max(rows_height(view), view.minimumHeight())
        # Abgezogen wird, was die Liste zu ``zone.sizeHint()`` beigetragen
        # hat — und das ist nicht ihre rohe Wunschhöhe: das Layout klemmt sie
        # zwischen Mindest- und Höchsthöhe. Die Listen der linken Spalte sind
        # per ``fit_to_rows`` auf feste Höhen gesetzt, meist deutlich unter
        # Qts pauschalen 192 Pixeln — die rohe Zahl abzuziehen rechnete die
        # Zone um gut hundert Pixel je Liste zu kurz, und Parameter und
        # Verlauf hingen unterhalb der Kartenkante.
        contributed = min(max(view.sizeHint().height(), view.minimumHeight()), view.maximumHeight())
        wanted += needs - contributed
    for area in living(zone, QScrollArea):
        if isinstance(area, QAbstractItemView) or not area.isVisibleTo(zone):
            continue
        inner = area.widget()
        viewport = area.viewport()
        if inner is None or viewport is None:
            continue
        # Ein Rollbereich meldet eine Wunschhöhe, die mit dem, was in ihm
        # steht, nichts zu tun hat — er ist ja dafür gebaut, weniger zu zeigen
        # als er hat. In der Tour hieß das: jeder Schritt endete auf „…", auf
        # dreizehn fehlenden Pixeln, während neben der Karte achthundert frei
        # blieben. Gefragt wird deshalb das Widget darin, und zwar nach seiner
        # tatsächlichen Höhe: bei umbrechendem Text steht die im Layout, nicht
        # im ``sizeHint``.
        needs = max(inner.height(), inner.sizeHint().height())
        wanted += max(needs - viewport.height(), 0)
    return max(wanted, 0)


def extra_height(zone: QWidget) -> int:
    """Was in der Zone Platz braucht und keiner Karte gehört.

    Abschnittsköpfe, die Parameterleiste, die Abstände des Layouts. Wer das
    nicht abzieht, verteilt mehr Höhe, als die Zone hat: bei zwanzig
    aufgeklappten Körpern auf 1366x768 bekam der Objektbaum 500 Pixel in einem
    Abschnitt, der 121 hoch war. Die 379 dazwischen schnitt das Elternwidget
    weg — und der Rollbalken wusste nichts davon, also waren die Zeilen nicht
    abgeschnitten, sondern unerreichbar.

    **Gerechnet wird strukturell und nie über die gesetzten Höhen.** Das ist
    die Bedingung dafür, dass die Spalte stillsteht (siehe
    ``OverlayHost._share_room``): ``natural_height`` taugt hier nicht, sie liest
    für ihre Rollbereiche die gelegten Höhen und schwankte zwischen 389 und
    1275 Pixeln, je nachdem was zuletzt zugeteilt wurde. Diese Rechnung nimmt je
    Posten den Unterschied zwischen dem, was er als Ganzes wünscht, und dem, was
    die Karten darin wünschen — beide Wünsche wandern gemeinsam, der Unterschied
    bleibt der Kopf. Gemessen über Zuteilungen von 60 bis 900 Pixeln: 217, jedes
    Mal.
    """
    layout = zone.layout()
    if layout is None:
        return 0
    margins = layout.contentsMargins()
    total = margins.top() + margins.bottom() + max(layout.count() - 1, 0) * layout.spacing()
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget() if item is not None else None
        if widget is None or not widget.isVisibleTo(zone):
            continue
        takers = [
            child
            for child in living(widget, QWidget)
            # ``isValid`` ein zweites Mal, und das ist kein Versehen: Zwischen
            # dem Sammeln und dieser Zeile kann der Speicherbereiniger
            # zuschlagen — er läuft in dem Thread, dessen Allokation gerade die
            # Schwelle reißt, nicht zwangsläufig in diesem. Die Prüfung gehört
            # deshalb an den Zugriff und nicht nur an die Liste.
            if isinstance(child, RoomTaker) and isValid(child) and child.isVisibleTo(zone)
        ]
        if not takers:
            total += widget.sizeHint().height()
            continue
        inside = sum(child.sizeHint().height() for child in takers if isValid(child))
        total += max(widget.sizeHint().height() - inside, 0)
    return total


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
        self.veil: QWidget | None = None
        self._moves: dict[int, QPropertyAnimation] = {}
        """Die laufende Bewegung je Zone — festgehalten, weil eine Animation,
        die niemand hält, mitten im Weg eingesammelt wird."""
        self._placing = False
        """Ob gerade gesetzt wird — siehe ``_place``."""

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
            # Die vier Zwickel neben den runden Ecken gehören der Ansicht
            # dahinter, nicht dem Elternhintergrund — sonst stehen dort
            # schwarze Zipfel. Gelöst wird das mit einer Maske in ``_move``
            # und **nicht** mit ``WA_TranslucentBackground``: das nimmt dem
            # Widget auch das Löschen seiner Fläche, und dann steht jede
            # Beschriftung doppelt übereinander.
        self.left, self.right, self.bottom = left, right, bottom
        # Eine zugeklappte Zone soll ihre Fläche zurückgeben. Qt meldet die
        # neue Wunschhöhe erst, wenn jemand danach fragt — also fragen wir bei
        # jeder Änderung an einem Kind nach.
        #
        # **Und zwar an jedem Kind, nicht nur an der Zone selbst.** Eine
        # Werkzeugleiste wird auf zwei Wegen sichtbar: über den Umschalter der
        # Zeile und über ``show_for``, das die Ansicht selbst aufruft, wenn
        # eine Szene mehrere Körper bekommt. Der zweite Weg meldete sich
        # nirgends — die untere Zone blieb auf der Höhe der Knopfreihe, und
        # die Explosionsleiste lag über den Umschaltern. Auf einem
        # Bildschirmfoto fürs Handbuch war es zu sehen, im Fenster daneben
        # ebenso.
        for zone in (left, right, bottom):
            self._watch(zone)
        self._place()

    def set_veil(self, veil: QWidget) -> None:
        """Eine Fläche, die die Ansicht verdeckt, solange sie nichts zeigt.

        Sie liegt über der Ansicht und **unter** den drei Karten. Über den
        Karten wäre sie ein modaler Vorhang: das Menü bliebe erreichbar, die
        Werkzeugzeile nicht, und wer den Ladevorgang vom Startbildschirm aus
        angestoßen hat, säße bis zum Ende fest. Verdeckt wird nur, was
        ohnehin leer ist.

        Sie bekommt **keinen** Ereignisfilter wie die Zonen: sie hat keine
        Wunschhöhe, die sich ändern könnte, und ein ``Resize``, das nach
        ``_place`` zurückruft, wäre nur der Weg in den eigenen Stapel.
        """
        veil.setParent(self)
        # Die Reihenfolge macht die Stapelung: erst den Schleier nach ganz
        # unten, dann die Ansicht unter ihn. Was oben steht, sind die Karten.
        veil.lower()
        self.view.lower()
        self.veil = veil
        self._place()

    def _watch(self, zone: QWidget) -> None:
        """Auf diese Zone und alles darin hören."""
        zone.installEventFilter(self)
        for child in living(zone, QWidget):
            child.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        """Ändert sich eine Zone, wird neu gerechnet, nicht nur neu gezeichnet.

        ``LayoutRequest`` ist dabei der wichtigste Fall: Qt schickt ihn, wenn
        eine Liste darin Zeilen bekommt oder verliert. Ohne ihn bliebe eine
        Karte so hoch, wie sie beim Aufbau war — und der Objektbaum wäre nach
        dem Öffnen eines Projekts genauso leer aussehend wie davor.

        **Wer stirbt, wird nicht weiter beobachtet.** Ein Filter wird am
        überwachten Objekt installiert und bleibt dort, bis eine Seite ihn
        entfernt — ``_watch`` tat das nie. Solange kein Fenster starb, fiel es
        nicht auf; seit sie sterben können (`acb0dd5`), läuft der Filter in den
        Abbau hinein und fragt halb abgeräumte Widgets nach ihrer Geometrie.
        Qt schickt ``Destroy``, **bevor** die C++-Seite weg ist: der letzte
        Takt, in dem das Abbestellen noch möglich ist.

        Gemessen an ``tests/test_first_run.py``, je sechs Läufe: **vier von
        sechs** mit einem Teardown-Fehler ohne diese drei Zeilen, **null von
        sechs** mit ihnen.

        Zwei Wachen am Eingang von ``_place`` — auf ``isValid`` von Wirt,
        Ansicht und Zonen — standen hier zuerst und sind wieder weg: Sie
        senkten die Quote nicht (drei bis vier von sechs blieben rot), denn
        eine Prüfung am Eingang gewinnt keinen Wettlauf, der **während**
        ``_lay_out`` entschieden wird. Das Abbestellen dagegen sorgt dafür,
        dass ``_lay_out`` gar nicht erst gerufen wird.
        """
        if event.type() == QEvent.Type.Destroy:
            watched.removeEventFilter(self)
            return False
        if event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Hide,
            QEvent.Type.LayoutRequest,
        ):
            self._place(moving=True)
        return super().eventFilter(watched, event)

    def reflow(self) -> None:
        """Die Zonen neu setzen, weil eine von ihnen anders hoch sein will.

        Für den Fall, dass es niemand von selbst meldet: eine Zone, die von
        außen ihre Geometrie bekommt, rechnet ihre Wunschhöhe nicht mehr
        selbst durch, und das ``LayoutRequest`` ihres Layouts kommt entweder
        gar nicht oder einen Takt zu spät. Wer weiß, dass sich etwas geändert
        hat, sagt es hier — das ist ehrlicher als ein Ereignis, auf dessen
        Zustellung man hofft.
        """
        self._place(moving=False)

    def resizeEvent(self, event: object) -> None:  # noqa: N802 — Qt-Name
        """Das Fenster zu ziehen ist keine Gelegenheit für Bewegung.

        Wer am Rand zieht, erwartet, dass alles folgt — nicht, dass es
        hinterherläuft. Animiert wird nur, was der Nutzer *ausgelöst* hat: eine
        Zone zuklappen, ein Ergebnis, das Zeilen bringt.
        """
        super().resizeEvent(event)  # type: ignore[arg-type]
        self._place(moving=False)

    def _move(self, zone: QWidget, target: QRect, moving: bool) -> None:
        """Eine Zone an ihren Platz — sofort oder auf einem Weg dorthin.

        Nicht animiert wird, was ohnehin schon stimmt, was gerade unsichtbar
        ist (ein Weg, den niemand sieht, ist verlorene Zeit) und was aus einem
        Fenster-Resize kommt. Eine laufende Bewegung wird abgebrochen und nicht
        gestapelt: zwei Animationen auf derselben Geometrie streiten sich um
        jedes Bild.
        """
        running = self._moves.get(id(zone))
        if running is not None and running.endValue() == target:
            # Schon auf dem Weg genau dorthin. Sie abzubrechen und neu zu
            # starten hieße, bei jedem eingehenden ``LayoutRequest`` wieder
            # von vorn zu beginnen — die Karte käme nie an, und weil sie
            # unterwegs ist, stimmt ihre Geometrie auch nie mit dem Ziel
            # überein, was den nächsten Neustart auslöst.
            return
        running = self._moves.pop(id(zone), None)
        if running is not None:
            running.stop()

        if zone.geometry() == target:
            return
        if not moving or MOVE_MS <= 0 or not zone.isVisible():
            zone.setGeometry(target)
            _round_corners(zone)
            return

        move = QPropertyAnimation(zone, b"geometry", self)
        move.setDuration(MOVE_MS)
        # Schnell anfangen, sanft ankommen: eine Bewegung, die am Ziel abbremst,
        # liest sich als „dorthin", eine gleichförmige als „irgendwohin".
        move.setEasingCurve(QEasingCurve.Type.OutCubic)
        move.setStartValue(zone.geometry())
        move.setEndValue(target)
        move.finished.connect(lambda: self._moves.pop(id(zone), None))
        # Die Maske wächst mit, nicht erst am Ziel: eine wachsende Zone unter
        # der alten Maske zeigt ihren neuen Teil sonst erst nach 160 ms — und
        # gar nicht, wenn eine neue Bewegung diese hier unterwegs ersetzt,
        # denn ``stop()`` sendet kein ``finished``.
        move.valueChanged.connect(lambda _value, zone=zone: _round_corners(zone))
        move.finished.connect(lambda: _round_corners(zone))
        self._moves[id(zone)] = move
        move.start()

    def _place(self, moving: bool = False) -> None:
        """Ansicht auf die ganze Fläche, Karten an ihre Ränder.

        **Läuft nie in sich selbst.** ``_move`` setzt eine Geometrie, sobald
        nicht animiert wird — und ``setGeometry`` stellt sein ``Resize`` sofort
        zu, nicht über die Warteschlange. Der Filter oben fängt es und ruft
        hierher zurück, mitten in den Aufruf, aus dem es stammt.

        Die Bremse dafür war ``zone.geometry() == target`` in ``_move``: beim
        zweiten Mal steht die Zone schon richtig, also passiert nichts mehr.
        Sie trägt nur, solange das Ziel dasselbe bleibt — und das tut es nicht.
        ``natural_height`` misst die Listen in der Zone über ihre *aktuelle*
        Höhe, und die hat sich durch das ``setGeometry`` gerade geändert. Zwei
        Werte, die sich abwechseln, reichen: dann ist das Ziel jedes Mal ein
        anderes, die Bremse greift nie, und der Stapel läuft über.

        Wer während des Setzens noch einmal setzen will, will nichts Neues —
        die Werte, die er läse, entstehen gerade erst. Ein späteres, echtes
        ``LayoutRequest`` kommt danach durch wie zuvor.
        """
        if self._placing:
            return
        self._placing = True
        try:
            self._lay_out(moving)
        finally:
            self._placing = False

    def _lay_out(self, moving: bool) -> None:
        """Das eigentliche Setzen. Nur aus ``_place``, nie von außen."""
        self.view.setGeometry(0, 0, self.width(), self.height())
        # Vor dem Zonen-Zweig: der Schleier deckt die Ansicht, und die gibt es
        # auch dann, wenn noch keine Karte angemeldet ist.
        if self.veil is not None:
            self.veil.setGeometry(0, 0, self.width(), self.height())
        if self.left is None or self.right is None or self.bottom is None:
            return

        height = self.height()
        width = self.width()

        # Links und rechts hängen oben und wachsen nur so weit nach unten, wie
        # ihr Inhalt reicht — höchstens bis kurz vors untere Ende, damit die
        # Werkzeugzeile frei bleibt.
        room = max(height - 2 * MARGIN - self._bottom_room(), 0)

        if self.left.isVisibleTo(self):
            self._share_room(self.left, room)
            wanted = min(natural_height(self.left), room)
            card = card_width(LEFT_WIDTH, LEFT_MAX, width)
            self._move(self.left, QRect(MARGIN, MARGIN, card, wanted), moving)

        if self.right.isVisibleTo(self):
            self._share_room(self.right, room)
            wanted = min(natural_height(self.right), room)
            card = card_width(RIGHT_WIDTH, RIGHT_MAX, width)
            self._move(
                self.right,
                QRect(width - card - MARGIN, MARGIN, card, wanted),
                moving,
            )

        # Die Werkzeugzeile sitzt mittig unten und ist so breit, wie sie sein
        # muss — nicht so breit wie das Fenster.
        if self.bottom.isVisibleTo(self):
            size = self.bottom.sizeHint()
            wanted = min(size.width(), width - 2 * MARGIN)
            self._move(
                self.bottom,
                QRect(
                    (width - wanted) // 2, height - size.height() - MARGIN, wanted, size.height()
                ),
                moving,
            )

        self._tell_the_view_about_the_zones()

    def _tell_the_view_about_the_zones(self) -> None:
        """Die Ansicht darf sagen, dass sie den Zonen ausweichen will.

        Für den Viewport ist das Übereinanderliegen richtig: man sieht das
        Modell hinter den Karten, und das ist der Sinn der Anordnung. Für eine
        Ansicht mit eigener Werkzeugleiste ist es falsch — im Skizzenmodus lagen
        die **ersten** Werkzeuge unter der linken Karte, also Linie und
        Rechteck, und die Bedingungsliste unter der rechten. Bei 1296 Pixeln
        Breite ebenso wie bei 1900: kein Platzproblem, sondern die
        Stapelreihenfolge.

        Wer ausweichen will, bringt ``set_zone_margins`` mit; wer nichts
        mitbringt, bekommt weiterhin die ganze Fläche.

        **Derzeit bringt es niemand mit, und der Absatz darüber ist
        Vergangenheit.** Seit dem Schnitt in §30.1 (P4) ersetzt der
        Skizzenmodus die Ansicht nicht mehr — er sitzt als Leiste unter ihr,
        und die Karten weichen *ihr* aus (``_bottom_room``) statt umgekehrt.
        Im Stapel liegt seither nur noch der Viewport, und für den ist das
        Übereinanderliegen richtig.

        Die Stelle bleibt, weil sie eine Frage beantwortet, die wieder
        auftreten kann: Eine Ansicht mit eigener Werkzeugleiste gehört nicht
        unter die Karten. ``tests/test_overlay.py`` hält sie mit einer eigenen
        Attrappe fest — ohne die wäre sie eine Zusage, die niemand mehr
        prüft.

        **Gemeldet wird die Breite, die die Karte wirklich bekommt**, also
        dieselbe Rechnung wie in ``_lay_out``. Vorher standen hier die
        Grundwerte, und die gelten nur bis etwa 2000 Pixel Fensterbreite:
        Im Vollbild war die linke Karte 332 statt 260 Pixel breit, der Rand
        also 72 Pixel zu schmal — und genau dort, bei x = 284, lag die
        Ebenenwahl des Skizzeneditors unter der Karte. Ausweichen, das die
        eigene Breite nicht kennt, weicht am Ende nicht aus.
        """
        inner = getattr(self.view, "currentWidget", None)
        target = inner() if callable(inner) else self.view
        setter = getattr(target, "set_zone_margins", None)
        if not callable(setter):
            return
        showing_left = self.left is not None and self.left.isVisibleTo(self)
        showing_right = self.right is not None and self.right.isVisibleTo(self)
        width = self.width()
        setter(
            card_width(LEFT_WIDTH, LEFT_MAX, width) + 2 * MARGIN if showing_left else 0,
            card_width(RIGHT_WIDTH, RIGHT_MAX, width) + 2 * MARGIN if showing_right else 0,
        )

    def _share_room(self, zone: QWidget, room: int) -> None:
        """Den Karten einer Zone sagen, wie hoch sie werden dürfen.

        Sie können es nicht selbst wissen. Eine Karte kennt ihren Inhalt,
        aber nicht das Fenster und nicht die anderen Karten, die sich die
        Spalte mit ihr teilen — und wer das nicht weiß, kann nur eine
        Konstante nehmen. Genau die stand hier: zwölf Zeilen, ob das Fenster
        achthundert Pixel hoch war oder vierzehnhundert. Im Vollbild rollte
        der Objektbaum bei dreißig Zeilen, während unter ihm dreihundert
        Pixel leer blieben.

        Passt alles, bekommt jede Karte ihren vollen Bedarf und der Deckel
        ist wirkungslos. Passt es nicht, wird nach Bedarf geteilt: eine Karte
        mit dreißig Zeilen bekommt mehr als eine mit dreien, aber keine
        bekommt alles.
        """
        takers: list[RoomTaker] = [
            child
            for child in living(zone, QWidget)
            if isinstance(child, RoomTaker) and child.isVisibleTo(zone)
        ]
        if not takers:
            return

        # Gerechnet wird ausschließlich mit ``room`` und dem Bedarf — beide
        # hängen **nicht** an der aktuellen Höhe der Karten. Das ist keine
        # Feinheit, sondern die ganze Bedingung dafür, dass die Spalte
        # stillsteht: eine Zuteilung, die die Höhen liest, die sie gerade
        # selbst gesetzt hat, bekommt beim nächsten Durchlauf andere Zahlen,
        # setzt wieder, und die Karte läuft auf und ab. Bei einem einzigen
        # Aufklappen waren es neunhundertfünf Geometriewechsel.
        #
        # **Abgezogen wird, was nicht den Karten gehört.** Hier stand, das sei
        # der Preis der Stillstandsbedingung: Abschnittsköpfe und
        # Parameterleiste blieben in ``room`` stehen, und bei Überfüllung rolle
        # eine Karte „ein paar Zeilen früher als nötig". Der Satz beschrieb den
        # Fehler in die falsche Richtung. Ungekürzt ist ``room`` **größer** als
        # der Platz, den es gibt: Bei „gehaeuse-mit-bausteinen" auf 1366x768,
        # einmal auf den Aufklapppfeil des Gehäusebodens geklickt, verteilte es
        # 592 Pixel auf Baum (411) und Verlauf (180) — die drei Köpfe (3 mal 24),
        # die Parameterleiste (96) und die Layoutabstände waren nicht dabei.
        # Der Abschnitt „Objekte" hatte 234 Pixel, der Baum stand auf 411; 177
        # Pixel lagen außerhalb der Karte und wurden weggeschnitten, der
        # Rollbalken meldete dazu max=2. Zehn Zeilen waren damit nicht
        # abgeschnitten, sondern **unerreichbar** — darunter der zweite Körper.
        #
        # Die Stillstandsbedingung bleibt gewahrt, denn beide Summanden hängen
        # am Inhalt und nicht an der Zuteilung: ``natural_height`` ersetzt den
        # Beitrag jeder Liste durch das, was ihre Zeilen brauchen, und
        # ``wanted_height`` ist dasselbe Maß. Was übrig bleibt, ist genau das
        # Beiwerk — und das ist so hoch, wie es ist.
        floors = [child.least_height() for child in takers]
        wants = [
            max(child.wanted_height(), floor) for child, floor in zip(takers, floors, strict=True)
        ]
        budget = max(room - extra_height(zone), sum(floors))
        if sum(wants) <= budget:
            for child, want in zip(takers, wants, strict=True):
                child.set_room(want)
            return
        # **Erst die Böden, dann der Rest nach Bedarf.** Anteilig an den ganzen
        # Wünschen zu teilen war die zweite Hälfte des Fehlers: Der leere
        # Verlauf wünschte vier Pixel und bekam anteilig drei — durchgesetzt
        # wurden aber seine hundertzwölf, und die fehlten oben. Verteilt wird
        # deshalb nur, was über den Böden liegt.
        spare = budget - sum(floors)
        appetite = [want - floor for want, floor in zip(wants, floors, strict=True)]
        hunger = sum(appetite)
        for child, floor, share in zip(takers, floors, appetite, strict=True):
            child.set_room(floor + (spare * share // hunger if hunger else 0))

    def _bottom_room(self) -> int:
        """Wie viel Höhe die Werkzeugzeile unten für sich braucht."""
        if self.bottom is None or not self.bottom.isVisibleTo(self):
            return 0
        return self.bottom.sizeHint().height() + MARGIN
