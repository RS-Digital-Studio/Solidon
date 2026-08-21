"""Vom gelösten Skizzenelement zum geschlossenen Umriss (Bauplan §30.1).

Die Skizzen-Operationen brauchen keinen Punktehaufen, sondern einen Umriss:
eine geschlossene Kette aus Strecken und Bögen — oder einen einzelnen Kreis.
Bögen bleiben Bögen: der B-Rep-Kern bekommt die exakte Kurve, nicht eine
Segmentfolge (§30).

Ein Umriss, der nicht schließt oder sich verzweigt, ist keine Rechengrundlage
und wird mit einem Vorschlag zurückgewiesen — nicht stillschweigend geflickt
(Regel 21).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final, Literal

from app.core.errors import CORRECT_INPUT, Action, GeometryError
from app.core.types import Point2, SolvedSketch
from app.core.units import EPS_GEOM
from app.i18n import TranslatableText, _

#: Wie nah zwei Endpunkte beieinander liegen müssen, um als verbunden zu
#: gelten. Gelöste Koinzidenzen liegen bei 1e-9; das hier ist bewusst gröber,
#: bleibt aber weit unter jedem druckbaren Maß.
_JOIN_TOL = 1e-4


@dataclass(frozen=True, slots=True)
class ProfileSegment:
    """Eine Strecke oder ein Bogen des Umrisses.

    ``via`` ist bei Bögen ein Punkt **auf** der Kurve zwischen Anfang und
    Ende — damit bleibt die Geometrie beim Umdrehen der Laufrichtung
    dieselbe, und der Kern baut den Bogen aus drei Punkten exakt nach."""

    kind: Literal["line", "arc", "spline"]
    start: Point2
    end: Point2
    via: Point2 | None = None
    through: tuple[Point2, ...] = ()
    """Bei einem Spline **alle** Punkte, durch die er läuft, einschließlich
    Anfang und Ende. Der Kern legt daraus eine B-Spline-Kurve, die jeden davon
    trifft — segmentiert wird nichts, und beim Umdrehen der Laufrichtung dreht
    sich diese Liste mit."""


@dataclass(frozen=True, slots=True)
class Profile:
    """Ein geschlossener Umriss: entweder eine Segmentkette oder ein Kreis.

    ``holes`` sind Umrisse **innerhalb** dieses einen — eine Platte mit einem
    Loch ist ein Umriss mit einem Loch, nicht zwei Umrisse. Der Kern setzt sie
    als innere Ringe derselben Fläche ein; wer sie stattdessen als zweiten
    Körper abzöge, bekäme dasselbe Ergebnis über eine Boolesche Operation, die
    hier niemand braucht."""

    segments: tuple[ProfileSegment, ...] = ()
    circle: tuple[Point2, float] | None = None
    holes: tuple[Profile, ...] = ()


def profile_of(solved: SolvedSketch) -> Profile:
    """Verkettet die Elemente einer gelösten Skizze zu **einem** Umriss.

    Der Weg jeder bestehenden Operation, und er bleibt streng: mehr als ein
    getrennter Umriss ist hier ein Fehler, keine Auswahl. Wer Regionen will,
    nimmt ``regions_of`` und entscheidet selbst, welche."""
    found = regions_of(solved)
    if len(found) > 1:
        raise _broken(
            _("Diese Skizze enthält mehrere getrennte Umrisse — diese Operation nimmt einen.")
        )
    return found[0]


def regions_of(solved: SolvedSketch) -> tuple[Profile, ...]:
    """Alle geschlossenen Umrisse einer Skizze, verschachtelte als Löcher.

    Bis hierher gab es genau einen. Eine Platte mit einem Loch — der häufigste
    Fall im ganzen Katalog — war damit nicht zeichenbar: die zweite Kette blieb
    beim Verketten einfach übrig, und die Meldung sprach von einem offenen
    Ende, obwohl beide Ketten geschlossen waren.

    Verschachtelung wird über einen Punkt der inneren Kette gegen die äußere
    entschieden, an einer Näherungspolylinie. Die Näherung betrifft nur die
    **Einordnung**; die Geometrie, die in den Kern geht, bleibt exakt — ein
    Bogen bleibt ein Bogen. Eine Kette, die eine andere schneidet statt sie zu
    umschließen, wird nicht in Teilflächen zerlegt: das wäre eine planare
    Arrangement-Rechnung, und sie müsste jede Kurve polygonisieren, um sie
    danach als Kurve auszugeben.
    """
    # Hilfsgeometrie trägt Bedingungen, aber keinen Umriss (§30.1). Eine
    # Mittellinie, an der zwei Bohrungen symmetrisch hängen, soll nicht als
    # Kante im extrudierten Körper landen.
    shaping = [element for element in solved.elements if not element.construction]
    circles = [element for element in shaping if element.kind == "circle"]
    drawable = [element for element in shaping if element.kind in ("line", "arc", "spline")]
    if not circles and not drawable:
        raise _broken(_("Die Skizze enthält nichts, was einen Umriss ergeben könnte."))

    loops: list[Profile] = [
        Profile(circle=(element.points[0], math.dist(element.points[0], element.points[1])))
        for element in circles
    ]
    segments = [_segment(element.kind, element.points) for element in drawable]
    while segments:
        loops.append(Profile(segments=_one_loop(segments)))

    # **Ein Umriss ohne Flaeche ist eine Eingabe und kein Programmfehler.**
    # Der Fall ist loesbar und trotzdem unbrauchbar: Wer *horizontal* und
    # *vertikal* auf dieselbe Linie setzt, hat keinen Widerspruch gebaut — die
    # Linie schrumpft auf einen Punkt und ist dann beides. Der Solver meldet
    # dafuer richtig zwei Freiheitsgrade und ein Restfehler von null.
    #
    # Weiter unten kann daraus niemand etwas machen: OpenCASCADE antwortete mit
    # ``StdFail_NotDone: BRep_API: command not done``, die C++-Ausnahme wurde
    # nach der Regel in ``errors.py`` zum ``InternalError``, und der Nutzer las
    # „Im Programm ist ein unerwarteter Fehler aufgetreten" samt Knopf fuer den
    # Fehlerbericht — fuer zwei Bedingungen, die er selbst gesetzt hat.
    #
    # Geprueft wird hier und nicht in den vier Operationen: alle vier gehen
    # durch diese Stelle. Die Grenze ist ``EPS_GEOM`` im Quadrat, weil sie auf
    # einer Flaeche steht und nicht auf einer Laenge (Regel 7).
    #
    # **Verworfen, nicht bloss gezaehlt.** Hier stand ``all(...)`` und warf nur,
    # wenn *keine* Kette trug — ein Rechteck mit 1200 mm² neben einer
    # geschrumpften Linie ging damit durch, und die leere Kette wanderte weiter
    # in den exakten Kern. Was keine Flaeche hat, ist keine Region: Es fliegt
    # heraus, und erst wenn nichts uebrig bleibt, ist die Skizze der Fehler.
    bearing = [loop for loop in loops if _area(_outline(loop)) > EPS_GEOM * EPS_GEOM]
    if not bearing:
        raise _broken(_("Die Skizze umschließt keine Fläche."))
    return _nested(bearing)


def _one_loop(segments: list[ProfileSegment]) -> tuple[ProfileSegment, ...]:
    """Verkettet vom ersten Segment aus, bis der Ring schließt.

    Verbraucht dabei aus ``segments``, was er nimmt — was übrig bleibt, ist der
    nächste Ring. Die Kette endet, sobald sie zum Anfang zurückfindet, und
    nicht erst, wenn nichts mehr da ist: sonst zöge ein Ring den nächsten über
    einen zufällig benachbarten Punkt mit hinein."""
    chain = [segments.pop(0)]
    while not _joins(chain[-1].end, chain[0].start):
        tail = chain[-1].end
        matches = [
            (index, candidate)
            for index, candidate in enumerate(segments)
            if _joins(tail, candidate.start) or _joins(tail, candidate.end)
        ]
        if not matches:
            raise _broken(_("Der Umriss ist nicht geschlossen — ein Ende bleibt frei."))
        if len(matches) > 1:
            raise _broken(_("Der Umriss verzweigt sich — an einem Punkt treffen sich drei Kanten."))
        index, candidate = matches[0]
        segments.pop(index)
        chain.append(candidate if _joins(tail, candidate.start) else _flipped(candidate))
    return tuple(chain)


def _outline(profile: Profile) -> list[Point2]:
    """Eine Polylinie, die dem Umriss folgt — nur zum Einordnen.

    Ein Kreis wird zu einem Zwölfeck: genau genug, um zu entscheiden, ob etwas
    darin liegt, und nichts davon geht in den Kern."""
    if profile.circle is not None:
        centre, radius = profile.circle
        steps = 12
        return [
            (
                centre[0] + radius * math.cos(2.0 * math.pi * index / steps),
                centre[1] + radius * math.sin(2.0 * math.pi * index / steps),
            )
            for index in range(steps)
        ]
    points: list[Point2] = []
    for segment in profile.segments:
        points.append(segment.start)
        if segment.via is not None:
            points.append(segment.via)
        points.extend(segment.through[1:-1])
    return points


def _inside(point: Point2, outline: list[Point2]) -> bool:
    """Strahlverfahren: ungerade Zahl von Schnitten heißt innen."""
    x, y = point
    within = False
    count = len(outline)
    for index in range(count):
        ax, ay = outline[index]
        bx, by = outline[(index + 1) % count]
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            within = not within
    return within


def _area(outline: list[Point2]) -> float:
    """Der Betrag der Schuhbandformel — als Maß dafür, wer wen umschließt."""
    total = 0.0
    for index in range(len(outline)):
        ax, ay = outline[index]
        bx, by = outline[(index + 1) % len(outline)]
        total += ax * by - bx * ay
    return abs(total) / 2.0


def _nested(loops: list[Profile]) -> tuple[Profile, ...]:
    """Ordnet jeden Ring dem kleinsten zu, der ihn umschließt.

    Dem **kleinsten**, nicht dem ersten: bei einem Kasten in einem Kasten in
    einem Kasten gehört der innerste an den mittleren, und wer den erstbesten
    Treffer nimmt, hängt ihn nach außen. Tiefer als eine Ebene wird nicht
    gebohrt — ein Loch in einem Loch ist wieder Material und braucht eine
    zweite Operation, die es auch gibt.
    """
    if len(loops) == 1:
        return (loops[0],)
    outlines = [_outline(loop) for loop in loops]
    areas = [_area(outline) for outline in outlines]
    parents: list[int | None] = []
    for index, outline in enumerate(outlines):
        probe = outline[0]
        candidates = [
            other
            for other in range(len(loops))
            if other != index and areas[other] > areas[index] and _inside(probe, outlines[other])
        ]
        parents.append(min(candidates, key=lambda other: areas[other]) if candidates else None)
    return tuple(
        replace(loop, holes=tuple(loops[i] for i, parent in enumerate(parents) if parent == index))
        for index, loop in enumerate(loops)
        if parents[index] is None
    )


def shifted(profile: Profile, dx: float, dy: float) -> Profile:
    """Derselbe Umriss, in der Ebene verschoben — wo er hingehört, entscheidet
    die Operation, nicht die Skizze."""
    if profile.circle is not None:
        centre, radius = profile.circle
        return Profile(circle=((centre[0] + dx, centre[1] + dy), radius))
    return Profile(
        segments=tuple(
            ProfileSegment(
                segment.kind,
                (segment.start[0] + dx, segment.start[1] + dy),
                (segment.end[0] + dx, segment.end[1] + dy),
                via=None if segment.via is None else (segment.via[0] + dx, segment.via[1] + dy),
                # Die Stützpunkte ziehen mit: ohne sie käme der Spline
                # verschoben an seinen Enden und unverschoben dazwischen an.
                through=tuple((x + dx, y + dy) for x, y in segment.through),
            )
            for segment in profile.segments
        )
    )


def _segment(kind: str, points: tuple[Point2, ...]) -> ProfileSegment:
    if kind == "line":
        return ProfileSegment("line", points[0], points[1])
    if kind == "spline":
        return ProfileSegment("spline", points[0], points[-1], through=points)
    centre, start, end = points
    return ProfileSegment("arc", start, end, via=_arc_midpoint(centre, start, end))


#: Unterhalb dieses Winkels gelten Anfang und Ende eines Bogens als derselbe
#: Punkt — der Löser liefert Koordinaten mit Restfehler um 1e-12, bit-genaue
#: Gleichheit gibt es dort nie (Regel 6).
_FULL_CIRCLE_EPS: Final = 1e-9


def _arc_midpoint(centre: Point2, start: Point2, end: Point2) -> Point2:
    """Der Punkt auf halbem Weg des Bogens, gegen den Uhrzeigersinn gerechnet."""
    radius = math.dist(centre, start)
    begin = math.atan2(start[1] - centre[1], start[0] - centre[0])
    finish = math.atan2(end[1] - centre[1], end[0] - centre[0])
    sweep = (finish - begin) % (2.0 * math.pi)
    if sweep <= _FULL_CIRCLE_EPS:
        # Zusammenfallende Enden sind ein Vollkreis, kein Nullbogen. Mit
        # `== 0.0` fing das den Löser-Fall nie: der Stützpunkt landete auf
        # dem Startpunkt, und der B-Rep-Kern baute einen Bogen ohne
        # Ausdehnung statt eines Kreises.
        sweep = 2.0 * math.pi
    middle = begin + sweep / 2.0
    return (centre[0] + radius * math.cos(middle), centre[1] + radius * math.sin(middle))


def _flipped(segment: ProfileSegment) -> ProfileSegment:
    return ProfileSegment(
        segment.kind,
        segment.end,
        segment.start,
        via=segment.via,
        through=tuple(reversed(segment.through)),
    )


def _joins(a: Point2, b: Point2) -> bool:
    return math.dist(a, b) <= _JOIN_TOL


def _broken(detail: TranslatableText | str) -> GeometryError:
    return GeometryError(
        _("Aus dieser Skizze wird kein Umriss."),
        detail,
        suggestions=(
            Action("open_sketch", _("Skizze ansehen"), primary=True),
            CORRECT_INPUT,
        ),
    )
