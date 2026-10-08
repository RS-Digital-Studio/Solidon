"""Zonen, die über der Ansicht liegen statt neben ihr (Bauplan §2.5).

Das Fensterschema nennt drei Zonen — links Objektbaum, Parameter und Verlauf;
in der Mitte die Ansicht; rechts Prüfbericht oder Chat. Es sagt nicht, dass die
äußeren beiden der mittleren ihre Fläche wegnehmen müssen. Genau das taten sie:
ein Objektbaum mit einer Zeile besetzte zweihundertachtzig Pixel Breite über
die volle Höhe, und das Teil, um das es geht, bekam die Hälfte des Fensters.

Hier liegen dieselben drei Zonen als Karten **über** der Ansicht. Die Ansicht
füllt das Fenster; wo nichts steht, sieht man das Modell. Zugeklappt gibt eine
Zone ihre Fläche vollständig zurück, statt eine leere Spalte zu hinterlassen.

**Warum das über einem nativen Renderfenster geht.** Der Kommentar am
Skizzenumschalter warnt davor, Qt über die Grafikfläche des Renderers zu
legen — er meint ein Modul, das die Ansicht *ersetzt*, und für das gilt er
weiter. Ein Kind-Widget über dem Renderfenster ist etwas anderes: der
Vorschau-Banner tut es seit je. Neu ist nur, dass diese Karten auch Klicks
annehmen, und das wurde vor dem Umbau gemessen — Knopf, Eingabefeld und
``childAt`` an derselben Stelle.

Die Breiten sind Zahlen und keine Ziehleiste. Ein Splitter zwischen
schwebenden Karten hätte nichts zu teilen: sie nehmen einander nichts weg.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Final, Protocol, TypeGuard, override

from PySide6.QtCore import (
    QAbstractItemModel,
    QChildEvent,
    QEasingCurve,
    QEvent,
    QModelIndex,
    QObject,
    QPoint,
    QPropertyAnimation,
    QRect,
    QRectF,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import (
    QContextMenuEvent,
    QFocusEvent,
    QKeyEvent,
    QMouseEvent,
    QPainterPath,
    QRegion,
    QResizeEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTabWidget,
    QToolButton,
    QTreeView,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from app.i18n import tr
from app.ui.cursors import cursor
from app.ui.icons import icon
from app.ui.leash import stop_watching_the_dying
from app.ui.style import ROOMY, SPACE
from app.ui.theme import THEMES, Theme


class RoomTaker(Protocol):
    """Eine Karte, der die Überlagerung Höhe zuteilen kann.

    Wer diese beiden Methoden mitbringt, wird beim Setzen der Zonen gefragt,
    wie hoch er gern wäre, und bekommt gesagt, wie hoch er sein darf. Wer sie
    nicht mitbringt, behält seine eigene Höhe — die Parameterleiste etwa, die
    so hoch ist wie ihre Zeilen und nichts zu verteilen hat.
    """

    def height(self) -> int: ...

    def isVisibleTo(self, ancestor: QWidget) -> bool: ...  # noqa: N802 — Qt-Name

    def sizeHint(self) -> QSize: ...  # noqa: N802 — Qt-Name

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


#: Je Widget-Typ einmal beantwortet, ob er den Raumvertrag erfüllt.
#:
#: Die Frage ist strukturell — vier Methoden am Typ —, und sie wurde je Kind
#: und je Durchlauf neu gestellt: 84 435 Mal beim Start, vier ``getattr`` je
#: Kind (Review Leistung B4, 21.09.2026). Der Typ ändert sich nicht.
_ROOM_TAKERS: dict[type, bool] = {}


def is_room_taker(value: object) -> TypeGuard[RoomTaker]:
    """Qt-Widgets mit dem Raumvertrag ohne Laufzeitprüfung von ``Protocol``.

    ``typing`` ermittelt bei ``isinstance(widget, RoomTaker)`` die MRO des
    Shiboken-Typs. Während echter Sprachwechsel lieferte Qt dort vorübergehend
    eine Liste statt eines Iterators; der Resize brach sichtbar ab. Vier
    benannte, aufrufbare Methoden beantworten dieselbe strukturelle Frage ohne
    Introspektion in Qt-internen Typdaten — und je Typ nur einmal.
    """
    kind = type(value)
    known = _ROOM_TAKERS.get(kind)
    if known is None:
        known = all(
            callable(getattr(kind, name, None))
            for name in ("height", "wanted_height", "least_height", "set_room")
        )
        _ROOM_TAKERS[kind] = known
    return known


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

#: Breite der linken Zone auf Full HD. Breit genug für Maße, Parameter und
#: „Schraubenloch mit Senkung" in der Verlaufsliste, schmal genug, dass
#: daneben noch ein Modell steht.
#:
#: **Hier stand einen halben Tag lang 272, und die Messung dahinter war ein
#: Phantom.** Ein Wächter maß die Parameterkarte auf 270 und damit über der
#: Zone — offscreen. Dort hat Qt aber gar keine Schrift:
#: ``QFontInfo(app.font()).family()`` gibt eine leere Zeichenkette, die
#: Punktgröße ist negativ, und **jede** angeforderte Familie liefert dieselbe
#: synthetische Metrik. Derselbe Text misst dort 228 Punkte und unter Segoe UI
#: 111 — offscreen rechnet rund doppelt so breit wie jeder echte Bildschirm.
#:
#: Gemessen unter echter Plattform ist die Karte **166** breit, mit Stylesheet
#: wie ohne, und in allen sechs Sprachen gleich; eine um ein Viertel größere
#: Systemschrift bringt sie auf 183. Sie hat nie gesprengt, auf keinem Fenster.
#:
#: Wer diese Zahl ändern will, misst deshalb unter **echter** Plattform.
#: Offscreen sagt über Schriftmetrik nichts — auch dann nicht, wenn man die
#: Familie ausdrücklich setzt.
LEFT_WIDTH = 300

#: Breite der rechten Zone. Ein Befund ist ein Satz, kein Absatz — schmaler
#: als eine klassische Seitenleiste, aber deutlich breiter als links, weil hier
#: vollständige Handlungssätze, die Auswahlhandlungen und der Chat stehen.
#:
#: Zweimal heraufgesetzt am 07.09.2026, beide Male von Robert: erst 320 auf
#: 360, weil sich seit den Auswahlhandlungen zwei Karten die Breite teilen und
#: ein Satz wie „Bohrung verschließen" darin umbrach — dann auf 450, weil bei
#: einem gewählten Körper „fast die Hälfte fehlte" (Robert). 510 waren ein
#: Zwischenstand und sind zurückgenommen: Sie überschritten auf einem 1200
#: breiten Fenster die Enge-Schranke, und die hält die Mitte als Griff frei.
#:
#: **Und wieder ein Stück zurück am 11.09.2026**, von Robert („das panel mit
#: prüfbericht/chat/Tour können wir auch ein bisschen schmaler machen"): Die
#: Handlungen an der Auswahl wohnen seit dem 11.09.2026 im Auswahl-Dock
#: rechts daneben, die Spalte trägt nur noch Prüfbericht, Chat und Tour — die
#: Breite für zwei Karten stand vor einer. 400 ist ein Satz breit und lässt
#: dem Bild, was die zweite Karte nicht mehr braucht.
#:
#: **Seit RM-511 wieder eine Karte für alles rechts** — Auswahl, Prüfbericht
#: und Chat als Reiter, das Dock daneben ist weg. Robert, 05.10.2026: „bisschen
#: breiter machen, wo wir mehr Platz haben“. Die Grundbreite trägt eine
#: Koordinatenzeile X, Y, Z nebeneinander; darüber wächst die Karte mit ihrem
#: eigenen Anteil (:data:`RIGHT_SHARE`).
RIGHT_WIDTH = 400

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

#: Der Anteil der rechten Karte. Größer als links, weil sie seit RM-511 auch
#: die Felder der Auswahl trägt: Auf Full HD sind das 480 Punkte, ab 2160
#: Punkten Fensterbreite der Deckel. Robert, 05.10.2026: „ein bisschen
#: schmaler“ als die 518 von RM-511 — die Ansicht bekommt den Platz zurück.
RIGHT_SHARE = 0.25
RIGHT_MAX = 540

#: In einem schmalen Fenster dürfen die beiden Karten einander nicht
#: überdecken. Jede bekommt höchstens diesen Anteil; der Rest bleibt als
#: sichtbare Mitte und als Griff auf die Ansicht. Bei 640 Punkten sind das 268
#: je Karte statt einer Überlappung. Auf Full HD greift die Grenze nicht.
NARROW_CARD_SHARE = 0.42

#: Abstand der Karten zueinander und zur Werkzeugzeile unten.
MARGIN = ROOMY

#: Abstand der Karten links und rechts zum Fensterrand: keiner. Robert,
#: 05.10.2026: „Die ganzen Panels rechts und links sollen keinen Abstand mehr
#: zum Rand haben.“ Sie liegen bündig an der Seite und unter der Leiste; frei
#: und rund bleibt nur ihre innere untere Ecke (:func:`_round_corners`, die
#: Regeln ``[dock=…]`` in :func:`card_stylesheet`).
EDGE = 0

#: Die Seite, an der eine Zone anliegt — als Eigenschaft ``dock`` an der Zone
#: und ihren Karten, damit Stilblatt und Maske dieselbe Antwort lesen.
DOCK_PROPERTY = "dock"

#: Der Objektname, an dem das Stilblatt eine schwebende Karte erkennt.
CARD = "overlayCard"

#: Die Karte der Maßgruppe über dem Bild (``placement_flow``) — gerahmt und
#: gerundet wie die Karten am Rand (RM-516).
MEASURE_CARD = "placement_measure_fields"

#: Die beiden Seitenkarten, benannt nach dem Rand, an dem sie von Haus aus
#: liegen: ``left`` trägt Objekte, Parameter und Verlauf, ``right`` die Reiter
#: Auswahl, Prüfbericht und Chat. Seit dem 06.10.2026 lassen sie sich
#: verschieben (Entscheidung Robert nach dem Fragebogen zu 0.5.3, „Bewegliche
#: Menüs?“); der Name bleibt der des Stammplatzes.
SIDE_CARDS: Final = ("left", "right")

#: Wie nah an einem Fensterrand eine losgelassene Karte einrastet, in
#: Logikpunkten — weit genug, dass man den Rand nicht genau treffen muss.
SNAP_TO_EDGE = 32

#: Wie hoch eine schwebende Karte mindestens bleibt, bevor sie nach oben
#: rückt (:func:`floating_top`) — Kopfzeile und einige Zeilen. Darüber hinaus
#: rollt ihr Inhalt, statt dass die Oberkante wandert.
FLOATING_LEAST = 200

#: Wie weit eine Pfeiltaste am Griff die Karte schiebt, mit Umschalt weiter.
NUDGE = 24
NUDGE_FAR = 96

#: Wie dick der Umriss ist, der beim Ziehen am Zeiger hängt.
CARD_OUTLINE_WIDTH = 2

#: Der Objektname der vier Umrisslinien, an dem das Stilblatt sie färbt.
OUTLINE = "cardOutline"

#: Das Polster zwischen der Randlinie einer Karte und ihrem Inhalt.
#:
#: Genau ein Pixel, denn genau einen ist die Linie breit. Ohne ihn malen die
#: Kinder sie zu — Objektbaum, Verlaufsliste und die Seite des Reiters tragen
#: eigene Flächen und reichten bis an die Widgetkante. Sichtbar blieb der
#: Rahmen nur, wo zufällig ein Layout Abstand hielt: um „Objekte" lief er ganz
#: herum, ab der Kopfzeile der Liste fehlte rechts alles, ab „Verlauf" auch
#: links. Von der Kante, an der die Karte aufhört, blieb ein Haken oben links.
CARD_PADDING = 1


def keep_widgets_alien() -> None:
    """Ein natives Fenster steckt seine Geschwister nicht an.

    Die Grafikfläche des Renderers ist ein natives Fenster
    (``present_method="screen"``). Ohne diese Regel macht Qt dann jede Ebene
    darüber nativ **samt allen ihren Geschwistern**, und ein Elternteil, in das
    ein natives Widget umzieht, zwingt jedes spätere Kind dazu. Am Wabenhalter
    standen so 140 von 854 Widgets als eigene Windows-Fenster da, darunter die
    ganze Andockleiste mit Merkmalfenster und Auswahlhandlungen. Das
    Merkmalfenster entstand als Kind des Hauptfensters und nahm die Nativität
    beim Umzug mit. Ein Bohrungsklick legte dadurch 30 Fenster an, und jedes
    ``setVisible`` kostete 1,3 ms mit sofortigem Malen. Gemessen am 25.09.2026
    am echten Fenster (RM-232): Bohrung zu Bohrung 346 → 146 ms am Wabenhalter,
    382 → 177 ms an der dichten Platte.

    Was über der Fläche liegen muss, wird ausdrücklich nativ
    (:func:`hold_above_the_view`). Gesetzt wird die Regel dort, wo die Fläche
    entsteht, vor ihrem Aufbau; sie gilt für den ganzen Prozess, und ein
    zweiter Aufruf ändert nichts.
    """
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings)


def hold_above_the_view(event: QChildEvent) -> None:
    """Ein direktes Kind über der Grafikfläche bekommt ein eigenes natives Fenster.

    Für ``childEvent`` der Ansicht und des :class:`OverlayHost`. Ein
    Kind ohne natives Fenster malt Qt in die Fläche seines Elternteils, und die
    liegt **unter** dem nativen Fenster des Renderers. Eine Karte, ein Banner
    oder die Maßgruppe wären dort unsichtbar. Die Kinder dieser Kinder bleiben
    ohne eigenes Fenster und malen in das ihres Elternteils.

    Gesetzt wird beim Polieren (``ChildPolished``), also vor dem ersten
    Zeigen. Das trifft auch Kinder, die später entstehen oder umziehen. Zu
    ``ChildAdded`` ist ein Kind unter Umständen noch nicht fertig gebaut.
    Eigene Fenster wie Menüs und Dialoge bleiben, was sie sind.
    """
    if event.type() != QEvent.Type.ChildPolished:
        return
    child = event.child()
    if isinstance(child, QWidget) and not child.isWindow():
        child.setAttribute(Qt.WidgetAttribute.WA_NativeWindow)


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


def card_width(base: int, cap: int, window: int, share: float = GROWTH_SHARE) -> int:
    """Wie breit eine Karte in einem Fenster dieser Breite sein soll.

    Mindestens der Grundwert ``base``.
    Darüber, wo das Fenster mehr hergibt, wächst die Karte mit ``share``
    anteilig, bis sie den Deckel erreicht: links ab etwa 2300 Punkten, rechts
    mit :data:`RIGHT_SHARE` schon auf Full HD. Darunter darf sie nicht so breit bleiben,
    dass beide Seiten einander überdecken: Die schmale Grenze erhält zwischen
    ihnen einen sichtbaren Griff auf den Viewport.
    """
    grown = min(max(base, window * share), cap)
    narrow = max(window * NARROW_CARD_SHARE, 0)
    return int(min(grown, narrow))


@dataclass(frozen=True, slots=True)
class CardPlace:
    """Wo eine Seitenkarte liegt: an einem Rand oder frei über der Ansicht.

    ``edge`` ist ``"left"``, ``"right"`` oder leer für eine schwebende Karte;
    dann sagen ``across`` und ``down`` als Anteil zwischen null und eins, wo
    sie im Spielraum steht. **Anteile, keine Punkte:** Dieselbe Anordnung gilt
    auf jedem Bildschirm und kann den Fensterrand rechnerisch nicht verlassen.
    """

    edge: str
    across: float = 0.0
    down: float = 0.0

    def text(self) -> str:
        """Die Form in den Einstellungen: ``left``, ``right`` oder ``float:0.4:0.2``."""
        if self.edge:
            return self.edge
        # Gespeichert, nicht angezeigt: der Punkt ist hier Teil der Form.
        return f"float:{round(self.across, 4)!r}:{round(self.down, 4)!r}"

    @staticmethod
    def read(text: object, home: str) -> CardPlace:
        """Aus den Einstellungen — und bei allem, was nicht passt, der Stammplatz."""
        if text in ("left", "right"):
            return CardPlace(str(text))
        if not isinstance(text, str) or not text.startswith("float:"):
            return CardPlace(home)
        parts = text.split(":")
        try:
            across, down = float(parts[1]), float(parts[2])
        except IndexError, ValueError:
            return CardPlace(home)
        if len(parts) != 3 or not (0.0 <= across <= 1.0 and 0.0 <= down <= 1.0):
            return CardPlace(home)
        return CardPlace("", across, down)


def _share(offset: int, span: int) -> float:
    """Ein Versatz als Anteil am Spielraum, zwischen null und eins."""
    return min(max(offset / max(span, 1), 0.0), 1.0)


def card_rect(place: CardPlace, width: int, room: int, size: QSize) -> QRect:
    """Wo eine Karte dieser Größe an diesem Platz steht.

    ``room`` ist die Unterkante, über die keine Seitenkarte reicht — die
    Werkzeugzeile darunter bleibt frei. Eine Karte am Rand liegt bündig oben
    (:data:`EDGE`), eine schwebende hält :data:`MARGIN` zu allen Rändern.

    **Die Oberkante einer schwebenden Karte steht fest**, gleich wie hoch sie
    gerade ist (:func:`floating_top`): Sonst lief, wer eine Kopfzeile auf- oder
    zuklappte, unter dem Zeiger weg. Wächst sie bis an die Unterkante, wird sie
    dort begrenzt, und ihr Inhalt rollt.
    """
    breadth = min(size.width(), width)
    if place.edge == "left":
        return QRect(EDGE, EDGE, breadth, max(min(size.height(), room), 0))
    if place.edge == "right":
        return QRect(width - breadth - EDGE, EDGE, breadth, max(min(size.height(), room), 0))
    top = floating_top(place, room, size.height())
    left = MARGIN + round(place.across * max(width - breadth - 2 * MARGIN, 0))
    return QRect(left, top, breadth, max(min(size.height(), room - top), 0))


def floating_top(place: CardPlace, room: int, wanted: int = FLOATING_LEAST) -> int:
    """Die Oberkante einer schwebenden Karte, die ``wanted`` hoch sein will.

    ``down`` ist ein Anteil an der Höhe zwischen den Rändern, nicht am
    Spielraum unter der Karte, also hängt die Oberkante nicht an ihrer Höhe.
    Nach oben rückt sie nur, wo unter ihr weniger als :data:`FLOATING_LEAST`
    bliebe — in einem kleineren Fenster, nicht weil eine Liste wächst.
    """
    anchored = MARGIN + round(place.down * max(room - 2 * MARGIN, 0))
    return max(min(anchored, room - min(wanted, FLOATING_LEAST)), MARGIN)


def dropped_place(rect: QRect, width: int, room: int, snap: int = SNAP_TO_EDGE) -> CardPlace:
    """Wohin eine Karte kommt, deren Umriss hier losgelassen wird.

    Bis ``snap`` Punkte vor einem Fensterrand rastet sie dort ein; die Tastatur
    schiebt mit ``snap=0``, sonst käme eine Karte mit dem ersten Pfeil nie
    vom Rand los.
    """
    if rect.left() - EDGE <= snap:
        return CardPlace("left")
    if width - EDGE - (rect.left() + rect.width()) <= snap:
        return CardPlace("right")
    return CardPlace(
        "",
        _share(rect.left() - MARGIN, width - rect.width() - 2 * MARGIN),
        # Spiegelbildlich zu :func:`card_rect`: die Oberkante, nicht der Rest darunter.
        _share(rect.top() - MARGIN, room - 2 * MARGIN),
    )


def _opposite(edge: str) -> str:
    return "right" if edge == "left" else "left"


def settled_places(
    moved: str,
    wanted: CardPlace,
    places: Mapping[str, CardPlace],
    sizes: Mapping[str, QSize],
    width: int,
    room: int,
) -> dict[str, CardPlace] | None:
    """Die Plätze beider Karten, wenn ``moved`` nach ``wanted`` soll — oder ``None``.

    **Ein Rand trägt eine Karte:** Wer an den Rand der anderen will, tauscht
    mit ihr; sie geht an den Rand, den die gezogene verlässt, und schwebte die,
    an den gegenüberliegenden. **Überdecken sich die beiden, bekommt die
    gezogene den Platz**, und die andere rückt waagrecht neben sie, wenn sie
    schwebt. Liegt die andere am Rand oder passt sie nirgends hin, rückt die
    gezogene neben die andere, sofern sie schwebt. Geht beides nicht, ist die
    Antwort ``None``, und alles bleibt, wie es war — der Aufrufer sagt warum.
    ``sizes`` nennt die Größe jeder sichtbaren Karte; eine unsichtbare
    überdeckt nichts.
    """
    result = dict(places)
    result[moved] = wanted
    other = next(key for key in result if key != moved)
    if wanted.edge and result[other].edge == wanted.edge:
        result[other] = CardPlace(places[moved].edge or _opposite(wanted.edge))
    if moved not in sizes or other not in sizes:
        return result
    mine = card_rect(result[moved], width, room, sizes[moved])
    theirs = card_rect(result[other], width, room, sizes[other])
    if not mine.intersects(theirs):
        return result
    turns = [(key, rect) for key, rect in ((other, mine), (moved, theirs)) if not result[key].edge]
    for shifting, fixed in turns:
        size = sizes[shifting]
        for left in (fixed.left() + fixed.width() + MARGIN, fixed.left() - MARGIN - size.width()):
            if MARGIN <= left <= width - size.width() - MARGIN:
                beside = CardPlace(
                    "",
                    _share(left - MARGIN, width - size.width() - 2 * MARGIN),
                    result[shifting].down,
                )
                if not card_rect(beside, width, room, size).intersects(fixed):
                    result[shifting] = beside
                    return result
    return None


def free_span(width: int, rects: Iterable[QRect]) -> tuple[int, int]:
    """Der breiteste freie Streifen zwischen den Seitenkarten, als Rand links und rechts.

    Jede Karte sperrt ihren waagrechten Bereich über die volle Höhe, samt
    :data:`MARGIN` Abstand; bei Gleichstand gewinnt der linke Streifen. In der
    Stammlage sind das dieselben Zahlen wie vor den verschiebbaren Karten:
    links die Breite der linken Karte plus Abstand, rechts die der rechten.
    """
    blocked = sorted(
        (max(rect.left() - MARGIN, 0), min(rect.left() + rect.width() + MARGIN, width))
        for rect in rects
    )
    gaps: list[tuple[int, int]] = []
    start = 0
    for left, right in blocked:
        if left > start:
            gaps.append((start, left))
        start = max(start, right)
    if start < width:
        gaps.append((start, width))
    if not gaps:
        return 0, 0
    best = max(gaps, key=lambda gap: (gap[1] - gap[0], -gap[0]))
    return best[0], width - best[1]


def card_stylesheet(theme: Theme) -> str:
    """Das Aussehen einer schwebenden Karte, gespeist aus dem Thema.

    Eine Karte über der Ansicht braucht zwingend eine *deckende* Fläche: sonst
    steht ihr Text auf dem Modell, und beides ist grau. Der Rand ist keine
    Zierde, sondern die Kante, an der die Karte aufhört.

    **Er trägt die Linienfarbe, nicht den Akzent** (RM-512). Drei Karten mit
    Bernsteinkante, dazu der aktive Reiter, leuchteten im Ruhezustand neben dem
    einen Hauptknopf — vier Linien und eine Fläche in derselben Signalfarbe,
    und keine davon wollte etwas vom Kunden. Die Kante sagt, wo die Karte
    aufhört; dafür reicht die Trennfarbe des Themas, die auch Felder und
    Listen umrandet. Der Akzent bleibt dem, was zu tun ist
    (``tests/test_resting_state.py``).

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
QWidget#{CARD}, QFrame#{MEASURE_CARD} {{
    background: {colours["window"]};
    border: 1px solid {colours["line"]};
    border-radius: {ROOMY}px;
}}

QTabWidget#{CARD}::pane {{
    border: none;
    background: transparent;
    margin: 0px {CARD_PADDING}px {CARD_PADDING}px {CARD_PADDING}px;
}}

QWidget#{CARD}[{DOCK_PROPERTY}="left"] {{
    border-top: none;
    border-left: none;
    border-top-left-radius: 0px;
    border-top-right-radius: 0px;
    border-bottom-left-radius: 0px;
}}

QWidget#{CARD}[{DOCK_PROPERTY}="right"] {{
    border-top: none;
    border-right: none;
    border-top-left-radius: 0px;
    border-top-right-radius: 0px;
    border-bottom-right-radius: 0px;
}}

QWidget#{OUTLINE} {{
    background: {colours["accent_line"]};
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

    **Eine anliegende Karte ist nur an ihrer freien Ecke rund** — der inneren
    unteren (:data:`EDGE`). An Fensterrand und Leiste wäre eine Rundung ein
    Zwickel, durch den das Modell zwischen Karte und Rand blitzt.
    """
    if zone.width() <= 0 or zone.height() <= 0:
        return
    rects = zone.card_rects() if isinstance(zone, CardColumn) else [zone.rect()]
    dock = zone.property(DOCK_PROPERTY)
    mask = QRegion()
    for rect in rects:
        shape = QPainterPath()
        shape.addRoundedRect(QRectF(rect), float(ROOMY), float(ROOMY))
        mask = mask.united(QRegion(shape.toFillPolygon().toPolygon()))
        if dock in ("left", "right"):
            # Oben über die ganze Breite und die anliegende Seite über die
            # ganze Höhe eckig — es bleibt die Rundung unten innen.
            mask = mask.united(
                QRegion(QRect(rect.left(), rect.top(), rect.width(), rect.height() - ROOMY))
            )
            side = rect.left() if dock == "left" else rect.left() + ROOMY
            mask = mask.united(
                QRegion(QRect(side, rect.top(), rect.width() - ROOMY, rect.height()))
            )
    zone.setMask(mask)


class CardColumn(QWidget):
    """Eine Zone aus mehreren Karten übereinander, jede mit eigenem Abschluss.

    Die rechte Spalte trägt seit dem 07.09.2026 zwei Karten (Entscheidung
    Robert): oben Prüfbericht und Chat, darunter — mit demselben Abstand wie
    zum Fensterrand — die Handlungen an der Auswahl. Für den ``OverlayHost``
    bleibt sie **eine** Zone: eine Geometrie, ein Ein- und Ausblenden über F9,
    eine Höhenverteilung; nur die Fläche zwischen den Karten gehört der
    Ansicht dahinter.

    Genau dafür ist die Klasse da. Die Maske einer Zone ist sonst ihr eigenes
    gerundetes Rechteck, und eine Spalte, die zwei Karten hält, zeigte in der
    Lücke dazwischen dann den schwarzen Elternhintergrund (siehe
    :func:`_round_corners`). Hier wird die Maske aus den sichtbaren Karten
    gebaut und immer dann erneuert, wenn eine von ihnen ihre Lage, Größe oder
    Sichtbarkeit ändert — das Layout legt sie neu, sobald eine Karte kommt oder
    geht, und der Host erfährt davon erst über sein eigenes ``LayoutRequest``.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("cardColumn")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(MARGIN)

    def add_card(self, card: QWidget, stretch: int = 0) -> None:
        """Eine Karte unten anfügen; sie bekommt Stil und Deckfläche der Zonen."""
        card.setObjectName(CARD)
        card.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        card.installEventFilter(self)
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        layout.addWidget(card, stretch)

    def card_rects(self) -> list[QRect]:
        """Die Flächen der sichtbaren Karten, in den Koordinaten der Spalte."""
        layout = self.layout()
        assert isinstance(layout, QVBoxLayout)
        rects = []
        for index in range(layout.count()):
            item = layout.itemAt(index)
            card = item.widget() if item is not None else None
            if card is not None and card.isVisibleTo(self):
                rects.append(card.geometry())
        return rects

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        if stop_watching_the_dying(self, watched, event):
            return False
        if event.type() in (
            QEvent.Type.Move,
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Hide,
        ):
            _round_corners(self)
        return super().eventFilter(watched, event)

    def resizeEvent(self, event: object) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)  # type: ignore[arg-type]
        _round_corners(self)


def _dock(zone: QWidget, side: str) -> None:
    """Zone und ihre Karten wissen, an welcher Seite sie anliegen (:data:`EDGE`)."""
    for widget in (zone, *living(zone, QWidget)):
        if widget is zone or widget.objectName() == CARD:
            widget.setProperty(DOCK_PROPERTY, side)
            # Eine Eigenschaft im Selektor wirkt erst nach neuem Polieren.
            style = widget.style()
            style.unpolish(widget)
            style.polish(widget)


def tell_the_zone(widget: QWidget) -> None:
    """Ein Inhalt ist gewachsen: Jede Ebene bis zur Zone fragt ihren Wunsch neu.

    Qt reicht ein geändertes Wunschmaß je Ereignisrunde nur eine Ebene
    weiter, über Reiter und Rollbereich als nachgereichtes ``LayoutRequest``,
    und das Layout der Zone merkt sich den Wunsch ihrer Karte, bis die Karte
    selbst ``updateGeometry`` ruft. Die Zone rechnete deshalb zuerst mit dem
    alten Wunsch: Nach dem Aufklappen der Befundliste stand die rechte Karte
    fünf Runden lang eine Zeile zu kurz, die Liste rollte neben freiem Platz,
    dann glitt die Karte ein zweites Mal (Durchsicht 0.5.3). Hier fragt jede
    Ebene von ``widget`` bis zur Zone sofort neu; wer danach misst
    (``OverlayHost.reflow``), liest den neuen Wunsch.
    """
    current: QWidget | None = widget
    while current is not None:
        current.updateGeometry()
        parent = current.parentWidget()
        if parent is None or isinstance(parent, OverlayHost):
            return
        current = parent


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
    if not isinstance(model, QAbstractItemModel):
        # **Zwei Fälle, eine Antwort.** Die Stubs behaupten, ein fehlendes
        # Modell könne es nicht geben — eine Liste, die gerade aufgebaut wird,
        # hat aber keines. Und im Abbau kommt der zweite dazu: shiboken kann
        # unter einem recycelten Zeiger einen **fremden Wrapper** liefern, und
        # der ist kein totes Objekt, sondern ein lebendiges vom falschen Typ.
        # ``isValid`` sagt dazu ja; nur die Frage nach der Art trifft es.
        #
        # Belegt am 30.08.2026 in zwei Torläufen, beide Male dieselbe Zeile:
        #
        #     AttributeError: 'QWidgetItem' object has no attribute 'rowCount'
        #
        # Erreicht über ``LayoutRequest`` → ``eventFilter`` → ``_place``, also
        # über eine Zone, die noch lebt, hin zu einer Ansicht, die schon geht.
        # Das ``Destroy``-Abbestellen deckt das **nicht** ab — es stand zu
        # beiden Zeitpunkten bereits in dieser Datei. Wer abbestellt, hört auf,
        # ein sterbendes Objekt zu beobachten; wer über seine Nachbarn rechnet,
        # muss zusätzlich fragen, was er da vor sich hat.
        #
        # Eine Höhe von null ließe die Karte zusammenfallen; dieselbe Antwort
        # wie für eine leere Liste.
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

    # Was die Liste über ihren Zeilen noch braucht — Rahmen, beim Baum die
    # Spaltenköpfe und ein **sichtbarer waagrechter Balken**. Gelesen aus der
    # Differenz, wo die Liste angezeigt ist: das Stylesheet darf alles davon
    # ändern, ohne dass hier jemand nachzieht. Vor dem Anzeigen ist die
    # Differenz eine Zahl aus dem Bau (eine Liste von null Punkten über einem
    # Sichtfeld von 28 ergab -28, RM-489); dann gilt die Summe der Teile, und
    # sie bleibt auch danach der Boden, damit ein Balken, der gerade erst
    # erschienen ist, nicht eine Zeile verdeckt.
    chrome = 2 * view.frameWidth()
    if tree is not None and not tree.isHeaderHidden():
        head = tree.header()
        chrome += head.sizeHint().height() if head is not None else 0
    bar = view.horizontalScrollBar()
    policy = view.horizontalScrollBarPolicy()
    if bar is not None and (
        policy == Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        or (policy == Qt.ScrollBarPolicy.ScrollBarAsNeeded and bar.isVisibleTo(view))
    ):
        chrome += bar.sizeHint().height()
    viewport = view.viewport()
    if viewport is not None and view.isVisible():
        chrome = max(chrome, view.height() - viewport.height())
    return wanted + chrome


class CurrentPageTabs(QTabWidget):
    """Ein Reiterwidget, das so hoch sein will wie die Seite, die vorn steht.

    Qt misst einen Reiterstapel an seiner größten Seite: ``QStackedLayout``
    nimmt für Wunschhöhe **und** Breitenhöhe das Maximum aller Seiten. Seit
    RM-511 teilen sich Auswahl, Prüfbericht und Chat die rechte Karte, und ein
    Bericht ohne Befunde stand in der Höhe des Chats — gemessen am echten
    Fenster bei Full HD rund 530 Punkte Karte für 225 Punkte Inhalt.

    Gerechnet wird der Rahmen (Reiterleiste, Rand) als Unterschied zwischen
    Qts Wunsch für das Ganze und dem für den Stapel, und dazu die vordere
    Seite. Die Breitenhöhe meldet es immer, weil die Karte darüber ihre Höhe
    aus ihr liest; eine Seite ohne eigene nimmt ihre Wunschhöhe.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.currentChanged.connect(self._page_changed)

    def _page_changed(self, _index: int) -> None:
        self.updateGeometry()

    def _stack(self) -> QStackedWidget | None:
        return self.findChild(QStackedWidget, "qt_tabwidget_stackedwidget")

    def _chrome_height(self, whole: QSize, stack: QStackedWidget) -> int:
        return max(whole.height() - stack.sizeHint().height(), 0)

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        whole = super().sizeHint()
        page, stack = self.currentWidget(), self._stack()
        if page is None or stack is None:
            return whole
        return QSize(whole.width(), self._chrome_height(whole, stack) + page.sizeHint().height())

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        """Das Mindestmaß der vorderen Seite samt Rahmen, in beiden Richtungen.

        Auch in der Breite: Die Karte darüber wird so breit wie ihre vordere
        Seite mindestens verlangt (``OverlayHost._right_width``, RM-488). Der
        Stapel verlangte die breiteste aller Seiten, und die Karte hätte für
        den Prüfbericht auch dann Platz gemacht, wenn die Auswahl vorn steht.
        """
        least = super().minimumSizeHint()
        page, stack = self.currentWidget(), self._stack()
        if page is None or stack is None:
            return least
        chrome = max(least.height() - stack.minimumSizeHint().height(), 0)
        # Qt nimmt die breitere von Stapel und Reiterleiste (mit Rollknöpfen
        # höchstens 200) und legt den Rahmen darum; dieselbe Rechnung mit der
        # vorderen Seite statt des Stapels.
        bar = self.tabBar().minimumSizeHint().width() if not self.tabBar().isHidden() else 0
        if self.usesScrollButtons():
            bar = min(bar, 200)
        frame = max(least.width() - max(stack.minimumSizeHint().width(), bar), 0)
        width = max(page.minimumSizeHint().width(), bar) + frame
        return QSize(width, chrome + page.minimumSizeHint().height())

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt-Name
        return self.currentWidget() is not None or super().hasHeightForWidth()

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt-Name
        page, stack = self.currentWidget(), self._stack()
        if page is None or stack is None:
            return super().heightForWidth(width)
        # Der Rand links und rechts, wie er gerade gelegt ist; vor dem ersten
        # Legen der des Rahmens, den das Stilblatt zeichnet.
        side = self.width() - stack.width() if 0 < stack.width() <= self.width() else 2
        inner = page.heightForWidth(max(width - side, 0)) if page.hasHeightForWidth() else -1
        if inner < 0:
            inner = page.sizeHint().height()
        return self._chrome_height(super().sizeHint(), stack) + inner


class ContentScroller(QScrollArea):
    """Ein Rollbereich, der seinen ganzen Inhalt wünscht; legen darf Qt ihn selbst.

    Anders als :class:`FittedScroller` setzt Qt die Größe des Inhalts hier
    selbst (``widgetResizable``); geändert ist nur der Wunsch. Die Karte, in
    der er steht, misst ihre Höhe daran, und ``natural_height`` zählt ihn
    deshalb nicht ein zweites Mal. Mit Qts eigenem Wunsch — der Höhe, die der
    Inhalt beim Einsetzen hatte — rechnete ``natural_height`` den Rest über die
    gerade gelegte Sichthöhe nach, und das rastete in der Mitte ein: an einer
    Bohrung bei Full HD 597 von 810 Punkten, obwohl Platz war (RM-511, am
    echten Fenster gemessen).
    """

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt-Name
        hint = super().sizeHint()
        content = self.widget()
        if content is None:
            return hint
        width = self.viewport().width()
        if content.hasHeightForWidth() and width > 0:
            height = content.heightForWidth(width)
        else:
            height = content.sizeHint().height()
        height = max(height, content.minimumSizeHint().height())
        return QSize(hint.width(), height + 2 * self.frameWidth())


class FittedScroller(QScrollArea):
    """Ein Rollbereich, der seinen ganzen Inhalt wünscht und erst rollt, wenn die Zone knapp ist.

    Für eine Karte aus vielen festen Zeilen, deren Höhe die Überlagerung
    zuteilt, nicht ein Layout: Der Prüfbericht trägt Prüfumfang, Übergabe,
    Nachbau, Filter, Liste, Befundkontext und Handlungen untereinander und
    braucht an seiner Breite mindestens 718 Punkte; im Fenster von
    1024 x 720 bekam er 425. Qt staucht dann jede Zeile unter ihre
    Mindesthöhe, und *An den Slicer übergeben …* lag über *Modell
    nachbauen*, das Suchfeld über der Liste.
    Hier rollt stattdessen der Inhalt; wo Platz ist, sieht man keinen
    Unterschied, denn der Wunsch ist der des Inhalts.

    Der Wunsch wird bei jeder Frage neu gelesen (``QScrollArea`` merkt sich
    den ersten, siehe ``selection_operations._ListScroller``), und jede
    Layoutänderung des Inhalts meldet ihn weiter. ``natural_height`` zählt
    diesen Rollbereich deshalb nicht ein zweites Mal.

    **Erst gibt nach, was nachgeben kann, dann wird gerollt.** Die Höhe des
    Inhalts setzt :meth:`_fit_content` selbst: so hoch wie der Ausschnitt,
    mindestens aber ``minimumHeightForWidth`` an der echten Breite — die Liste
    auf ihrer Mindesthöhe, umbrechender Text mit allen Zeilen. Qts eigene
    Größenwahl (``widgetResizable``) gibt einem umbrechenden Inhalt seine
    Wunschhöhe und rollte deshalb auch im hohen Fenster.
    """

    def __init__(self, content: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(False)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # **Die Breite gehört der Spalte.** Ohne waagrechten Balken schnitt die
        # Karte einen Inhalt in seiner Mindestbreite rechts ab (326 statt 226
        # Punkte breit); gestaucht wird quer wie ohne Rollbereich.
        content.setSizePolicy(QSizePolicy.Policy.Ignored, content.sizePolicy().verticalPolicy())
        self.setWidget(content)

    def _least_height(self, content: QWidget, width: int) -> int:
        """Die kleinste Höhe, in der der Inhalt bei dieser Breite nichts staucht."""
        layout = content.layout()
        if layout is not None and layout.hasHeightForWidth():
            return layout.minimumHeightForWidth(width)
        return content.minimumSizeHint().height()

    def _fit_content(self) -> None:
        """Breite des Ausschnitts, Höhe des Ausschnitts oder mehr — dann mit Balken.

        Entschieden wird an der Breite ohne Balken; braucht der Inhalt dort
        mehr Höhe, als da ist, gilt die Breite mit Balken. So entscheidet
        die Breite nie über den Balken, der sie ändert.
        """
        content = self.widget()
        if content is None:
            return
        frame = 2 * self.frameWidth()
        width = max(self.width() - frame, 0)
        height = max(self.height() - frame, 0)
        least = self._least_height(content, width)
        if least > height:
            width = max(width - self.verticalScrollBar().sizeHint().width(), 0)
            least = self._least_height(content, width)
        wanted = QSize(width, max(height, least))
        if content.size() != wanted:
            content.resize(wanted)

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_content()

    @override
    def sizeHint(self) -> QSize:
        content = self.widget()
        if content is None:
            return super().sizeHint()
        frame = 2 * self.frameWidth()
        return content.sizeHint() + QSize(frame, frame)

    @override
    def minimumSizeHint(self) -> QSize:
        # Die Mindesthöhe des Inhalts, wie ohne Rollbereich. Unterschreitet die
        # Zone sie, staucht das Layout den Rollbereich trotzdem — dann rollt
        # der Inhalt, statt sich zu stauchen.
        content = self.widget()
        if content is None:
            return super().minimumSizeHint()
        frame = 2 * self.frameWidth()
        return content.minimumSizeHint() + QSize(frame, frame)

    @override
    def hasHeightForWidth(self) -> bool:
        # **Der Wunsch der Karte reist über Höhe-für-Breite.** Der Reiter rechts
        # steht senkrecht auf ``Ignored``; sein ``sizeHint`` zählt in der Karte
        # nicht, ``QLayout.totalSizeHint`` fragt aber ``heightForWidth``, wenn
        # ein Kind sie hat. Ein ``QScrollArea`` hat keine — ohne diese beiden
        # Methoden fiel der Wunsch der rechten Spalte von 741 auf 122 Punkte.
        content = self.widget()
        return content is not None and content.hasHeightForWidth()

    @override
    def heightForWidth(self, width: int) -> int:
        content = self.widget()
        if content is None or not content.hasHeightForWidth():
            return super().heightForWidth(width)
        frame = 2 * self.frameWidth()
        return content.heightForWidth(width - frame) + frame

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        # ``setWidget`` trägt den Rollbereich als Filter am Inhalt ein; ein neu
        # gelegter Inhalt heißt ein neuer Wunsch.
        if watched is self.widget() and event.type() == QEvent.Type.LayoutRequest:
            self.updateGeometry()
            self._fit_content()
        return super().eventFilter(watched, event)


def natural_height(zone: QWidget, width: int | None = None) -> int:
    """Die Höhe, bei der der Inhalt einer Zone genau hineinpasst.

    Qts eigene Wunschhöhe taugt dafür nicht, weil die Listen darin ihre
    beisteuern (siehe ``rows_height``). Gerechnet wird deshalb: was die Zone
    ohne ihre Listen bräuchte, plus das, was die Listen wirklich brauchen.

    ``width`` ist die Breite, auf die die Zone gleich gesetzt wird. Qt rechnet
    umbrechenden Text im ``sizeHint`` an der Wunschbreite; in der schmaleren
    Karte bricht er in mehr Zeilen um. Der Prüfbericht verlangte so 654 Punkte
    statt der 718, die er an seiner Breite mindestens braucht, und rollte auch
    im hohen Fenster.
    """
    wanted = zone.sizeHint().height()
    if width is not None and zone.hasHeightForWidth():
        wanted = max(wanted, zone.heightForWidth(width))
    # Ein direkt gemessener Reiter reserviert den größten Seitenwunsch.
    # Ein ``CurrentPageTabs`` misst schon selbst nur die Seite, die vorn steht;
    # dort darf dieselbe Differenz nicht noch einmal abgezogen werden.
    tabs = [zone] if isinstance(zone, QTabWidget) and not isinstance(zone, CurrentPageTabs) else []
    for tab in tabs:
        current = tab.currentWidget()
        if current is None or not tab.isVisibleTo(zone):
            continue
        tallest = max(
            (
                page.sizeHint().height()
                for index in range(tab.count())
                if (page := tab.widget(index)) is not None
            ),
            default=0,
        )
        current_height = current.sizeHint().height()
        if current.hasHeightForWidth():
            current_height = max(current_height, current.heightForWidth(current.width()))
        wanted += current_height - tallest
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
        # Ein ``FittedScroller`` wünscht schon seinen ganzen Inhalt; der steht
        # damit in ``zone.sizeHint()`` und zählte hier ein zweites Mal.
        if isinstance(area, (QAbstractItemView, FittedScroller, ContentScroller)) or (
            not area.isVisibleTo(zone)
        ):
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
        needs = min(max(inner.height(), inner.sizeHint().height()), area.maximumHeight())
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
            if is_room_taker(child) and isValid(child) and child.isVisibleTo(zone)
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

    placesChanged = Signal(object)
    """Die Plätze der Seitenkarten haben sich geändert — als ``{Karte: Text}``
    (:meth:`CardPlace.text`), zum Merken in den Einstellungen."""
    dragHint = Signal(str)
    """Was das Loslassen gerade täte, als Satz — leer, wenn nicht gezogen wird.
    Die zweite Kodierung neben dem Umriss (Regel 18)."""
    cardNotice = Signal(str)
    """Wo eine Karte jetzt liegt, oder warum sie nicht dorthin kann."""

    def __init__(self, view: QWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # Vor ``setParent``: das Umhängen löst sofort ein Resize aus, und
        # ``_place`` fragt dort nach den drei Zonen. Stünden sie erst danach,
        # stürbe das Fenster beim Bauen.
        self.left: QWidget | None = None
        self.right: QWidget | None = None
        self.bottom: QWidget | None = None
        self.veil: QWidget | None = None
        self.places: dict[str, CardPlace] = {key: CardPlace(key) for key in SIDE_CARDS}
        """Wo jede Seitenkarte liegen soll (:class:`CardPlace`) — gezeigt wird
        sie dort, solange sich die beiden nicht überdecken (:meth:`_card_targets`)."""
        self._targets: dict[str, QRect] = {}
        """Die zuletzt gesetzten Ziele der sichtbaren Seitenkarten. Gemeldet wird
        aus ihnen, nicht aus der Geometrie mitten in einer Gleitbewegung."""
        self._docked: dict[str, str] = {}
        """Welchen Rand jede Zone gerade trägt — nur bei einem Wechsel wird neu
        poliert (:func:`_dock`)."""
        self._drag: _CardDrag | None = None
        self._outline: tuple[QWidget, ...] = ()
        """Die vier Linien um die Stelle, an der die gezogene Karte landete."""
        self._other_outline: tuple[QWidget, ...] = ()
        """Die vier Linien um die Stelle, an die die andere Karte dabei wanderte."""
        self._moves: dict[int, QPropertyAnimation] = {}
        """Die laufende Bewegung je Zone — festgehalten, weil eine Animation,
        die niemand hält, mitten im Weg eingesammelt wird."""
        self._placing = False
        """Ob gerade gesetzt wird — siehe ``_place``."""
        self._pending: bool | None = None
        """Ob ein Setzen für den nächsten Ereignisdurchlauf vorgemerkt ist —
        und ob es bewegt (:meth:`_place_later`)."""

        self.view = view
        view.setParent(self)

    def childEvent(self, event: QChildEvent) -> None:  # noqa: N802 — Qt-Name
        """Karten und Schleier liegen über der Grafikfläche (:func:`hold_above_the_view`)."""
        hold_above_the_view(event)
        super().childEvent(event)

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
        for zone, side in ((left, "left"), (right, "right")):
            _dock(zone, side)
            self._docked[side] = side
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

        **Wer stirbt, wird nicht weiter beobachtet** — ``_watch`` bestellte
        nie ab, und seit die Fenster sterben können, lief der Filter in ihren
        Abbau hinein. Der Griff dagegen und seine Messung stehen bei
        :func:`~app.ui.leash.stop_watching_the_dying`; er wird hier zuerst
        gefragt, weil ein sterbendes Objekt keine Geometrie mehr hat, nach der
        sich rechnen ließe.
        """
        if stop_watching_the_dying(self, watched, event):
            return False
        if event.type() in (
            QEvent.Type.Resize,
            QEvent.Type.Show,
            QEvent.Type.Hide,
            QEvent.Type.LayoutRequest,
        ):
            self._place_later(moving=True)
        return super().eventFilter(watched, event)

    def _place_later(self, *, moving: bool) -> None:
        """Einmal je Ereignisdurchlauf setzen, nicht je Ereignis.

        Jedes ``Resize``, ``Show``, ``Hide`` und ``LayoutRequest`` jedes Kindes
        rechnete die Zonen sofort neu: 433 Durchläufe beim Start (0,34 bis
        0,38 s), 217 beim Öffnen einer Platte, 671 auf Weg 1, 81 bis 115 ms je
        Undo (Review Leistung B4, 21.09.2026). Ein Durchlauf reicht, wenn die
        Ereignisse des Takts durch sind. **Während des Setzens** kommt nichts
        dazu — dieselbe Regel wie in :meth:`_place`: Was das Setzen selbst
        auslöst, meint nichts Neues. ``resizeEvent`` und :meth:`reflow` setzen
        weiter sofort; wer dort ankommt, weiß, dass sich etwas geändert hat.
        """
        if self._placing:
            return
        if self._pending is None:
            self._pending = moving
            # Ein Zeitgeber mit null und kein nachgereichtes Ereignis: Die
            # Listen legen ihre Zeilen selbst über einen Nullzeitgeber
            # (``QListView``, verzögertes ``doItemsLayout``), und gemessen wird
            # an ``visualRect`` — ein Ereignis käme vor den Zeilen dran und
            # läse die alte Höhe (gemessen am 21.09.2026, ``test_overlay``).
            QTimer.singleShot(0, self._place_pending)
        else:
            self._pending = self._pending or moving

    def _place_pending(self) -> None:
        """Der vorgemerkte Durchlauf — genau einer, mit der stärksten Bewegung."""
        pending, self._pending = self._pending, None
        if pending is None or not isValid(self):
            return
        self._place(moving=pending)

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
            # ``stop()`` sendet kein ``finished``, und allein das Entfernen
            # aus ``_moves`` löst die Elternbindung nicht: Ohne diese Zeile
            # bliebe je ersetzter Bewegung ein Qt-Kind am Host stehen.
            running.deleteLater()

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
        # **Über die Ereignisschleife, nicht über ``DeleteWhenStopped``.** Die
        # Löschregel ließ Qt die Animation beim Anhalten sofort freigeben —
        # auch beim Abbau des Hosts, dessen Kind sie ist; der Host gab sie dann
        # ein zweites Mal frei, und zwei Tests später brach ``sizeHintForRow``
        # mit einem beschädigten Heap ab (test_overlay: Gleiten, dann Messen).
        move.finished.connect(move.deleteLater)
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

        # Die Seitenkarten wachsen nur so weit nach unten, wie ihr Inhalt
        # reicht — höchstens bis kurz vors untere Ende, damit die Werkzeugzeile
        # frei bleibt. Wo sie stehen, sagen ihre Plätze (:class:`CardPlace`).
        self._targets = self._card_targets(width, self.card_room())
        for key, target in self._targets.items():
            zone = self.side_zone(key)
            if zone is not None:
                self._move(zone, target, moving)

        # Die Werkzeugzeile sitzt mittig unten und ist so breit, wie sie sein
        # muss — nicht so breit wie das Fenster.
        if self.bottom.isVisibleTo(self):
            wanted, tall = self._bottom_size(width)
            self._move(
                self.bottom,
                QRect((width - wanted) // 2, height - tall - MARGIN, wanted, tall),
                moving,
            )

        self._tell_the_view_about_the_zones()

    def card_room(self) -> int:
        """Die Unterkante, über die keine Seitenkarte reicht — darunter die Werkzeugzeile."""
        return max(self.height() - EDGE - MARGIN - self._bottom_room(), 0)

    def side_zone(self, key: str) -> QWidget | None:
        """Die Zone einer Seitenkarte (:data:`SIDE_CARDS`)."""
        return self.left if key == "left" else self.right if key == "right" else None

    def _card_width(self, key: str, width: int) -> int:
        """Wie breit eine Seitenkarte ist — gleich, wo sie steht."""
        if key == "left":
            return card_width(LEFT_WIDTH, LEFT_MAX, width)
        return self._right_width(width)

    def _card_sizes(
        self, width: int, room: int, places: Mapping[str, CardPlace]
    ) -> dict[str, QSize]:
        """Breite und Höhe jeder sichtbaren Seitenkarte an diesen Plätzen.

        **Eine schwebende Karte teilt zu, was sie bekommt:** den Raum unter
        ihrer Oberkante (:func:`floating_top`), wie :func:`card_rect` sie
        zeichnet. Mit ``room`` fehlten ihren Listen unten Punkte, und eine
        wachsende Liste schob die Karte nach oben, statt zu rollen. Nie kürzer
        als die Mindesthöhe, die die Zone selbst nennt — eine Zone ohne gültigen
        Wunsch hieße sonst null Punkte hoch, und ein leeres Rechteck überdeckt
        nichts.
        """
        sizes: dict[str, QSize] = {}
        for key in SIDE_CARDS:
            zone = self.side_zone(key)
            if zone is None or not zone.isVisibleTo(self):
                continue
            place = places.get(key, CardPlace(key))
            share = room if place.edge else max(room - floating_top(place, room), 0)
            self._share_room(zone, share)
            card = self._card_width(key, width)
            wanted = natural_height(zone, width=card) if key == "right" else natural_height(zone)
            sizes[key] = QSize(card, min(max(wanted, zone.minimumHeight()), share))
        return sizes

    def _card_targets(self, width: int, room: int) -> dict[str, QRect]:
        """Wohin die sichtbaren Seitenkarten gehören, nach ihren Plätzen.

        **Überdecken sie sich** — nach einer Größenänderung des Fensters, an
        einem kleineren Bildschirm —, stehen beide vorübergehend an ihrem
        Stammplatz; die eigene Anordnung bleibt gespeichert und gilt wieder,
        sobald das Fenster reicht. Am Stammplatz passen beide immer
        (:data:`NARROW_CARD_SHARE`). Der Rand, an dem eine Karte liegt, geht an
        Stilblatt und Maske (:func:`_dock`); eine schwebende ist rundum rund.
        """
        places = dict(self.places)
        sizes = self._card_sizes(width, room, places)
        targets = {key: card_rect(places[key], width, room, size) for key, size in sizes.items()}
        if len(targets) == len(SIDE_CARDS) and targets["left"].intersects(targets["right"]):
            places = {key: CardPlace(key) for key in SIDE_CARDS}
            # Am Rand gilt der ganze Raum, nicht der einer schwebenden Karte.
            sizes = self._card_sizes(width, room, places)
            targets = {
                key: card_rect(places[key], width, room, size) for key, size in sizes.items()
            }
        for key in targets:
            zone = self.side_zone(key)
            if zone is not None and self._docked.get(key) != places[key].edge:
                self._docked[key] = places[key].edge
                _dock(zone, places[key].edge)
        return targets

    def set_places(self, places: Mapping[str, CardPlace]) -> None:
        """Die Plätze aus den Einstellungen übernehmen — zwei Karten an einem Rand nie."""
        wanted = {key: places.get(key, CardPlace(key)) for key in SIDE_CARDS}
        if wanted["left"].edge and wanted["left"].edge == wanted["right"].edge:
            wanted = {key: CardPlace(key) for key in SIDE_CARDS}
        self.places = wanted
        self._place(moving=False)
        self._describe_grips()

    def put_card(self, key: str, place: CardPlace) -> bool:
        """Eine Seitenkarte an diesen Platz — mit Tausch und Ausweichen.

        Die Regeln stehen bei :func:`settled_places`. Geht es nicht, bleibt
        alles, wie es war, und :attr:`cardNotice` sagt warum (Regel 17: mit dem
        Weg zurück). Ein Strg+Z nimmt das nicht zurück: Die Lage einer Karte
        ist Darstellung wie die Kamera, kein Dokumentzustand (§2.1).
        """
        width, room = self.width(), self.card_room()
        settled = settled_places(
            key, place, self.places, self._card_sizes(width, room, self.places), width, room
        )
        if settled is None:
            self.cardNotice.emit(
                tr(
                    "Neben der anderen Karte ist hier kein Platz. Doppelklick auf den "
                    "Griff legt die Karte zurück."
                )
            )
            return False
        changed = settled != self.places
        self.places = settled
        self._place(moving=True)
        self._describe_grips()
        if changed:
            self.placesChanged.emit({name: value.text() for name, value in settled.items()})
        self.cardNotice.emit(_placed_sentence(key, settled[key]))
        return True

    def reset_cards(self) -> None:
        """Beide Seitenkarten an ihren Stammplatz (*Ansicht → Karten an ihren Platz*)."""
        home = {key: CardPlace(key) for key in SIDE_CARDS}
        changed = home != self.places
        self.places = home
        self._place(moving=True)
        self._describe_grips()
        if changed:
            self.placesChanged.emit({name: value.text() for name, value in home.items()})
        self.cardNotice.emit(tr("Beide Karten liegen an ihrem Platz."))

    def nudge(self, key: str, across: int, down: int) -> None:
        """Eine Seitenkarte mit der Tastatur schieben — vom Rand los, wo sie anlag.

        **Senkrecht löst sich eine Karte am Rand** und bleibt an ihrer Seite:
        Wer an der angedockten Karte ↓ drückt, will sie tiefer haben. Ändert
        der Druck nichts — ↑ oben am Fenster, ← am linken Rand —, sagt der
        Griff nichts; eine Ansage „liegt wieder an ihrem Platz“ für einen
        Druck ohne Wirkung wäre eine Bestätigung für nichts.
        """
        zone = self.side_zone(key)
        if zone is None or not zone.isVisibleTo(self):
            return
        width, room = self.width(), self.card_room()
        start = self._targets.get(key, zone.geometry())
        moved = start.translated(across, down)
        left = min(max(moved.left(), 0), max(width - moved.width(), 0))
        top = min(max(moved.top(), 0), max(room - moved.height(), 0))
        place = dropped_place(QRect(QPoint(left, top), moved.size()), width, room, 0)
        current = self.places[key]
        if down and not across and current.edge and place.edge == current.edge:
            if top == start.top():
                return
            place = CardPlace(
                "",
                0.0 if current.edge == "left" else 1.0,
                _share(top - MARGIN, room - 2 * MARGIN),
            )
        if place == current:
            return
        self.put_card(key, place)

    def begin_drag(self, key: str, at: QPoint) -> None:
        """Der Zug am Griff beginnt — ``at`` in Bildschirmkoordinaten.

        **Die Größen der Karten werden hier einmal gemessen**, nicht je
        Mausbewegung: :meth:`_card_sizes` teilt den Listen ihren Raum neu zu.
        Ebenso werden die Umrisslinien hier gezeigt und nach oben geholt; je
        Bewegung ändert sich nur ihre Geometrie (:meth:`drag_to`).
        """
        zone = self.side_zone(key)
        if zone is None or not zone.isVisibleTo(self):
            return
        start = zone.geometry()
        width, room = self.width(), self.card_room()
        places = dict(self.places)
        self._drag = _CardDrag(
            key,
            self.mapFromGlobal(at) - start.topLeft(),
            start.size(),
            places[key],
            sizes=self._card_sizes(width, room, places),
            before=places,
            settled=places,
        )
        if not self._outline:
            self._outline = tuple(self._outline_line() for _ in range(4))
            self._other_outline = tuple(self._outline_line() for _ in range(4))
        self._show_outline(self._outline, start)
        for line in self._outline:
            line.show()
            line.raise_()
        for line in self._other_outline:
            line.raise_()
        self.dragHint.emit(_drag_sentence(key, places, places, places[key]))

    def drag_to(self, at: QPoint) -> None:
        """Der Umriss folgt dem Zeiger — und zeigt, wo die Karte beim Loslassen landet.

        Gerechnet wird mit :func:`settled_places`, derselben Regel wie beim
        Loslassen: Der Umriss steht am Ergebnis, ein zweiter an der Stelle, an
        die die andere Karte wanderte, und der Satz nennt den Fall (Regel 18:
        Er ist die zweite Kodierung neben dem Umriss und muss stimmen).
        """
        drag = self._drag
        if drag is None:
            return
        width, room = self.width(), self.card_room()
        corner = self.mapFromGlobal(at) - drag.grab
        left = min(max(corner.x(), 0), max(width - drag.size.width(), 0))
        top = min(max(corner.y(), 0), max(room - drag.size.height(), 0))
        drag.place = dropped_place(QRect(QPoint(left, top), drag.size), width, room)
        drag.settled = settled_places(drag.key, drag.place, drag.before, drag.sizes, width, room)
        size = drag.sizes.get(drag.key, drag.size)
        other = next(name for name in SIDE_CARDS if name != drag.key)
        wandering = False
        if drag.settled is None:
            self._show_outline(self._outline, card_rect(drag.place, width, room, size))
        else:
            self._show_outline(self._outline, card_rect(drag.settled[drag.key], width, room, size))
            wandering = other in drag.sizes and drag.settled[other] != drag.before[other]
            if wandering:
                self._show_outline(
                    self._other_outline,
                    card_rect(drag.settled[other], width, room, drag.sizes[other]),
                )
        # Nur bei einem Wechsel: Gezeigt und verborgen wird ein natives Fenster.
        for line in self._other_outline:
            if line.isVisible() != wandering:
                line.setVisible(wandering)
        self.dragHint.emit(_drag_sentence(drag.key, drag.before, drag.settled, drag.place))

    def end_drag(self, commit: bool) -> None:
        """Loslassen legt die Karte hin; Escape und ein verlorener Fokus nicht."""
        drag, self._drag = self._drag, None
        self._hide_outline()
        self.dragHint.emit("")
        if drag is not None and commit:
            self.put_card(drag.key, drag.place)

    def dragging(self) -> str:
        """Welche Karte gerade gezogen wird — leer, wenn keine."""
        return self._drag.key if self._drag is not None else ""

    def _show_outline(self, lines: tuple[QWidget, ...], rect: QRect) -> None:
        """Vier Linien um die Stelle, an die eine Karte käme — nur ihre Geometrie.

        **Linien, keine Karte und keine Maske:** Jede Karte ist ein natives
        Fenster über der Grafikfläche und malt bei jeder Bewegung sofort; ein
        Umriss mit Maske riss über Vulkan das Gerät (``ansicht.md``,
        „Maßtinte“). Vier schmale Widgets ohne Durchsicht malen nur sich.
        Gezeigt und nach oben geholt werden sie einmal (:meth:`begin_drag`).
        """
        top, bottom, left, right = lines
        thick = CARD_OUTLINE_WIDTH
        top.setGeometry(rect.left(), rect.top(), rect.width(), thick)
        bottom.setGeometry(rect.left(), rect.top() + rect.height() - thick, rect.width(), thick)
        left.setGeometry(rect.left(), rect.top(), thick, rect.height())
        right.setGeometry(rect.left() + rect.width() - thick, rect.top(), thick, rect.height())

    def _outline_line(self) -> QWidget:
        line = QWidget(self)
        line.setObjectName(OUTLINE)
        line.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        line.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        line.hide()
        return line

    def _hide_outline(self) -> None:
        for line in (*self._outline, *self._other_outline):
            line.hide()

    def _describe_grips(self) -> None:
        """Jeder Griff sagt, wo seine Karte jetzt liegt (Bildschirmleser)."""
        for grip in living(self, CardGrip):
            grip.describe()

    def _right_width(self, width: int) -> int:
        """Wie breit die rechte Karte wird — nie schmaler als ihre vordere Seite.

        **Die Spalte wird breiter, statt abzuschneiden** (RM-488): Ein Knopftext
        oder ein Haken lässt sich nicht kürzen, und ein Rollbereich, der nur
        senkrecht rollt, schnitt ihn rechts ab, ohne Balken (offscreen an einer
        gewählten Fläche: „Loch oder Aussparung zeichnen …“ 30 Punkte zu breit).
        Bis 0.5.2 gab das Dock des Hauptfensters diese Breite von selbst her;
        seit der Reiter *Auswahl* in dieser Karte steht (RM-511), rechnet sie
        die Zone selbst — höchstens bis an den Fensterrand. Ansicht und Zonen
        lesen dieselbe Zahl (:meth:`_tell_the_view_about_the_zones`).
        """
        card = card_width(RIGHT_WIDTH, RIGHT_MAX, width, RIGHT_SHARE)
        if self.right is None:
            return card
        least = self.right.minimumSizeHint().width()
        return max(card, min(least, width - 2 * EDGE))

    def _tell_the_view_about_the_zones(self) -> None:
        """Die Ansicht darf sagen, dass sie den Zonen ausweichen will.

        Für den Viewport ist das Übereinanderliegen links und rechts richtig:
        man sieht das Modell hinter den Karten, und das ist der Sinn der
        Anordnung. Im Skizzenmodus ist die untere Karte die Ausnahme: Umriss,
        Ziehgriff und Zahl müssen **oberhalb** davon liegen. Der Viewport liest
        deshalb neben den beiden Breiten auch ihre echte Höhe und verschiebt
        nur seine Skizzenkamera in die freie Fläche.

        Wer ausweichen will, bringt ``set_zone_margins`` mit; wer nichts
        mitbringt, bekommt weiterhin die ganze Fläche.

        Seit dem Schnitt in §30.1 (P4) ersetzt der Skizzenmodus die Ansicht
        nicht mehr — er sitzt als Leiste über ihr. ``Viewport.set_zone_margins``
        lässt die Szene weiterhin unter linken und rechten Karten stehen, hält
        die aktive Zeichnung aber aus der unteren heraus. Gleichzeitig weichen
        die seitlichen Karten dieser Leiste über ``_bottom_room`` aus.

        Die Stelle bleibt, weil sie eine Frage beantwortet, die wieder
        auftreten kann: Eine Ansicht mit eigener Werkzeugleiste gehört nicht
        unter die Karten. ``tests/test_overlay.py`` hält sie mit einer eigenen
        Attrappe fest — ohne die wäre sie eine Zusage, die niemand mehr
        prüft.

        **Gemeldet werden die Größen, die die Karten wirklich bekommen**, also
        dieselbe Rechnung wie in ``_lay_out``. Vorher standen hier die
        Grundwerte, und die gelten nur bis etwa 2000 Pixel Fensterbreite:
        Im Vollbild war die linke Karte 332 statt 260 Pixel breit, der Rand
        also 72 Pixel zu schmal — und genau dort, bei x = 284, lag die
        Ebenenwahl des Skizzeneditors unter der Karte. Ausweichen, das die
        eigene Größe nicht kennt, weicht am Ende nicht aus. Unten zählt aus
        demselben Grund ``_bottom_room()`` statt einer festen Werkzeughöhe.
        """
        inner = getattr(self.view, "currentWidget", None)
        target = inner() if callable(inner) else self.view
        setter = getattr(target, "set_zone_margins", None)
        if not callable(setter):
            return
        # **Die Lücke zwischen den Karten, wo sie auch stehen** (Konzept
        # verschiebbare Karten): Jede sichtbare Seitenkarte sperrt ihren
        # Streifen, gemeldet wird der breiteste freie (:func:`free_span`). In
        # der Stammlage sind das die Zahlen von vorher.
        left, right = free_span(self.width(), self._targets.values())
        setter(left, right, self._bottom_room())
        # Die Ansichtsleiste weicht jeder Karte aus, die über ihr läge, nicht
        # nur der unteren (``ViewBar.place``).
        cards = getattr(target, "set_card_rects", None)
        if callable(cards):
            cards(tuple(self._targets.values()))

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
            if is_room_taker(child) and child.isVisibleTo(zone)
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
        return self._bottom_size(self.width())[1] + MARGIN

    def _bottom_size(self, width: int) -> tuple[int, int]:
        """Breite und Höhe der unteren Karte bei dieser Fensterbreite.

        **Die Höhe gilt für die Breite, die die Karte bekommt.** Ein
        umbrechender Satz — die Statuszeile des Skizzenmodus — meldet in
        ``sizeHint()`` die Höhe seiner Wunschbreite; zugeteilt bekommt die
        Karte aber höchstens die Fensterbreite, und darin bricht der Satz auf
        zwei Zeilen, von denen die zweite hinter der Zeile darunter verschwand
        (gemessen am gebauten Fenster, 13.09.2026: „Geschlossen · Noch 4 Maße
        fehlen …" endete mitten im Wort). ``heightForWidth`` fragt die Höhe
        für die Breite, die es wirklich gibt; eine Karte ohne umbrechenden
        Inhalt antwortet darauf mit minus eins und behält ihren Wunsch.
        """
        assert self.bottom is not None
        size = self.bottom.sizeHint()
        wanted = min(size.width(), width - 2 * MARGIN)
        tall = size.height()
        if self.bottom.hasHeightForWidth():
            tall = max(tall, self.bottom.heightForWidth(wanted))
        return wanted, tall


@dataclass(slots=True)
class _CardDrag:
    """Ein laufender Zug am Griff: welche Karte, wo gegriffen, und wohin sie käme.

    ``sizes`` und ``before`` gelten ab dem Griff (:meth:`OverlayHost.begin_drag`);
    ``settled`` ist das Ergebnis, das das Loslassen gerade hätte, oder ``None``,
    wenn neben der anderen Karte kein Platz ist.
    """

    key: str
    grab: QPoint
    size: QSize
    place: CardPlace
    sizes: dict[str, QSize]
    before: dict[str, CardPlace]
    settled: dict[str, CardPlace] | None


#: Die Tasten, die der Griff mit Fokus selbst bedient (:meth:`CardGrip.event`).
_GRIP_KEYS: Final = frozenset(
    {
        Qt.Key.Key_Left,
        Qt.Key.Key_Right,
        Qt.Key.Key_Up,
        Qt.Key.Key_Down,
        Qt.Key.Key_Return,
        Qt.Key.Key_Enter,
        Qt.Key.Key_Space,
        Qt.Key.Key_Menu,
    }
)


def _drag_sentence(
    key: str,
    before: Mapping[str, CardPlace],
    settled: Mapping[str, CardPlace] | None,
    wanted: CardPlace,
) -> str:
    """Was das Loslassen gerade täte, je Fall ein Satz — für die Statuszeile.

    Der Satz beschreibt das Ergebnis von :func:`settled_places`, nicht die
    Stelle unter dem Zeiger: Tausch, Ausweichen und „kein Platz“ sieht man so
    vor dem Loslassen und nicht erst danach.
    """
    if settled is None:
        return tr("Hier ist neben der anderen Karte kein Platz.")
    other = next(name for name in settled if name != key)
    mine, theirs = settled[key], settled[other]
    if theirs == before[other]:
        if mine.edge == "left":
            return tr("Loslassen legt die Karte an den linken Rand.")
        if mine.edge == "right":
            return tr("Loslassen legt die Karte an den rechten Rand.")
        if mine != wanted:
            return tr("Loslassen legt die Karte neben die andere.")
        return tr("Loslassen lässt die Karte hier schweben.")
    if mine.edge and theirs.edge:
        if before[key].edge:
            return tr("Loslassen tauscht die beiden Karten.")
        if mine.edge == "left":
            return tr("Loslassen legt die Karte an den linken Rand, die andere an den rechten.")
        return tr("Loslassen legt die Karte an den rechten Rand, die andere an den linken.")
    if mine.edge == "left":
        return tr("Loslassen legt die Karte an den linken Rand, die andere rückt beiseite.")
    if mine.edge == "right":
        return tr("Loslassen legt die Karte an den rechten Rand, die andere rückt beiseite.")
    return tr("Loslassen lässt die Karte hier schweben, die andere rückt beiseite.")


def _placed_sentence(key: str, place: CardPlace) -> str:
    """Wo eine Karte jetzt liegt, mit dem Rückweg."""
    if place == CardPlace(key):
        return tr("Die Karte liegt wieder an ihrem Platz.")
    if place.edge == "left":
        return tr("Die Karte liegt jetzt links. Doppelklick auf den Griff legt sie zurück.")
    if place.edge == "right":
        return tr("Die Karte liegt jetzt rechts. Doppelklick auf den Griff legt sie zurück.")
    return tr(
        "Die Karte schwebt jetzt über der Ansicht. Doppelklick auf den Griff legt sie zurück."
    )


def _no_host() -> OverlayHost | None:
    """Der Wirt eines Griffs, der noch keinen hat."""
    return None


class CardGrip(QToolButton):
    """Der Griff, an dem eine Seitenkarte verschoben wird.

    Entscheidung Robert, 06.10.2026, nach dem Fragebogen zu 0.5.3 („Bewegliche
    Menüs?“): Die Karten links und rechts lassen sich innerhalb des Fensters
    verschieben und rasten an den Rändern ein; ein eigenes Fenster werden sie
    nicht — dort fehlten Strg+Z, Entf und die Palette, und ein Kind über der
    Grafikfläche, das umzieht, macht seine Vorfahren nativ (Soll-Ablauf in
    ``konzepte/konzept-verschiebbare-karten-2026-10.md``).

    **Ziehen zeigt einen Umriss am Zeiger**, erst das Loslassen legt die Karte
    hin (:meth:`OverlayHost._show_outline`); Escape oder ein verlorener Fokus
    brechen ab. **Doppelklick legt sie an ihren Stammplatz zurück.** Ein
    einfacher Klick tut nichts. **Die Tastatur kann dasselbe:** Pfeile
    schieben (mit Umschalt weiter), Eingabe-, Leer- und Menütaste nennen die
    drei Plätze. Der Satz in der Statuszeile ist die zweite Kodierung neben
    dem Umriss (Regel 18).

    ``corner`` legt den Griff selbst in die obere rechte Ecke seines
    Elternteils (die linke Karte, :meth:`sit_in_corner`); in einer Reiterkarte
    steht er als Eckwidget, dort setzt Qt ihn (``QTabWidget.setCornerWidget``).

    **Er entsteht vor dem Inhalt seiner Karte**, damit er in der Tabfolge
    vorn steht: Die Fokuskette folgt der Entstehung, und ein Umhängen im
    selben Fenster lässt seinen Platz darin stehen. Den Wirt bekommt er
    deshalb erst danach (:meth:`attach`). Nachträglich umgeordnet wird nicht —
    ein Lauf in Python über ``nextInFocusChain`` hängt jedes zurückgegebene
    Widget an seinen Vorgänger, und der Speicherbereiniger nahm mit einer
    kurzlebigen Hülle Merkmalfenster und Karte der Handlungen mit
    (``oberflaeche.md``, „Die Tabulatortaste geht denselben Weg wie das Auge“).
    """

    def __init__(
        self,
        host: OverlayHost | None,
        key: str,
        name: str,
        parent: QWidget,
        *,
        corner: bool = False,
    ) -> None:
        super().__init__(parent)
        self._host: Callable[[], OverlayHost | None] = (
            weakref.ref(host) if host is not None else _no_host
        )
        self.key = key
        self._pressed: QPoint | None = None
        self._dragging = False
        self._corner = False
        self.setObjectName("cardGrip")
        self.setIcon(icon("grip", self))
        self.setAutoRaise(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(cursor("move", self))
        self.setAccessibleName(name)
        self.setToolTip(tr("Karte verschieben. Doppelklick legt sie zurück."))
        self.describe()
        if corner:
            self.sit_in_corner(parent)

    def attach(self, host: OverlayHost) -> None:
        """Den Wirt nachreichen, wenn der Griff vor ihm entstanden ist."""
        self._host = weakref.ref(host)
        self.describe()

    def sit_in_corner(self, card: QWidget) -> None:
        """In die obere rechte Ecke dieser Karte, über ihre Kopfzeile."""
        if self.parentWidget() is not card:
            self.setParent(card)
        card.installEventFilter(self)
        self._corner = True
        self._seat()
        self.show()

    def describe(self) -> None:
        """Wo die Karte liegt, als Satz für den Bildschirmleser."""
        host = self._host()
        place = host.places.get(self.key, CardPlace(self.key)) if host is not None else None
        if place is None or place.edge == "left":
            text = tr(
                "Liegt links an. Pfeiltasten schieben die Karte, die Eingabetaste nennt die Plätze."
            )
        elif place.edge == "right":
            text = tr(
                "Liegt rechts an. Pfeiltasten schieben die Karte, die Eingabetaste "
                "nennt die Plätze."
            )
        else:
            text = tr(
                "Schwebt über der Ansicht. Pfeiltasten schieben die Karte, die Eingabetaste "
                "nennt die Plätze."
            )
        self.setAccessibleDescription(text)

    def place_menu(self) -> QMenu:
        """Die drei Plätze als Menü — gebaut hier, gezeigt in :meth:`_show_menu`."""
        menu = QMenu(self)
        for label, place in (
            (tr("An den linken Rand"), CardPlace("left")),
            (tr("An den rechten Rand"), CardPlace("right")),
            (tr("An ihren Platz"), CardPlace(self.key)),
        ):
            action = menu.addAction(label)
            action.triggered.connect(lambda _checked=False, place=place: self._put(place))
        return menu

    def _put(self, place: CardPlace) -> None:
        host = self._host()
        if host is not None:
            host.put_card(self.key, place)

    def _show_menu(self, at: QPoint | None = None) -> None:
        menu = self.place_menu()
        menu.exec(at if at is not None else self.mapToGlobal(QPoint(0, self.height())))
        menu.deleteLater()

    def _seat(self) -> None:
        """In die obere rechte Ecke des Elternteils, über die Kopfzeile."""
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        self.move(max(parent.width() - self.width() - CARD_PADDING, 0), CARD_PADDING)
        self.raise_()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802 — Qt-Name
        if stop_watching_the_dying(self, watched, event):
            return False
        if self._corner and event.type() in (QEvent.Type.Resize, QEvent.Type.LayoutRequest):
            self._seat()
        return super().eventFilter(watched, event)

    def _cancel(self) -> None:
        host = self._host()
        dragging, self._dragging, self._pressed = self._dragging, False, None
        if dragging and host is not None:
            host.end_drag(commit=False)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        self._pressed = event.globalPosition().toPoint()
        self._dragging = False
        event.accept()

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        host = self._host()
        if self._pressed is None or host is None:
            return
        at = event.globalPosition().toPoint()
        if not self._dragging:
            if (at - self._pressed).manhattanLength() < QApplication.startDragDistance():
                return
            self._dragging = True
            host.begin_drag(self.key, self._pressed)
        host.drag_to(at)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        host = self._host()
        dragging, self._dragging, self._pressed = self._dragging, False, None
        if dragging and host is not None:
            host.end_drag(commit=True)
        event.accept()

    @override
    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        self._put(CardPlace(self.key))
        event.accept()

    @override
    def event(self, event: QEvent) -> bool:
        """**Der Griff nimmt seine Tasten vor den Kürzeln des Fensters.**

        Escape ist im Fenster gebunden (eine Auswahlstufe zurück), und Qt
        stellt ein Kürzel vor den Tastendruck: Ohne das hier brach Escape einen
        Zug nicht ab, er landete beim Loslassen trotzdem (gemessen 06.10.2026).
        Beansprucht wird Escape nur während eines Zugs, die Pfeile, Eingabe,
        Leer- und Menütaste, solange der Griff den Fokus hat.
        """
        if event.type() == QEvent.Type.ShortcutOverride and isinstance(event, QKeyEvent):
            key = Qt.Key(event.key())
            if (key == Qt.Key.Key_Escape and self._dragging) or key in _GRIP_KEYS:
                event.accept()
                return True
        return super().event(event)

    @override
    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = Qt.Key(event.key())
        if key == Qt.Key.Key_Escape and self._dragging:
            self._cancel()
            event.accept()
            return
        step = NUDGE_FAR if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else NUDGE
        moves = {
            Qt.Key.Key_Left: (-step, 0),
            Qt.Key.Key_Right: (step, 0),
            Qt.Key.Key_Up: (0, -step),
            Qt.Key.Key_Down: (0, step),
        }
        host = self._host()
        if key in moves and host is not None:
            host.nudge(self.key, *moves[key])
            event.accept()
            return
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space, Qt.Key.Key_Menu):
            self._show_menu()
            event.accept()
            return
        super().keyPressEvent(event)

    @override
    def focusOutEvent(self, event: QFocusEvent) -> None:
        self._cancel()
        super().focusOutEvent(event)

    @override
    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        self._show_menu(event.globalPos())
        event.accept()
