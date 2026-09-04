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
from app.core.sketch.planes import to_world
from app.core.types import PlaneFrame, Point2, SketchElement, SolvedSketch, Vec3
from app.core.units import EPS_GEOM, is_zero
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

    # **Ein Umriss ohne Fläche ist eine Eingabe und kein Programmfehler.**
    # Der Fall ist lösbar und trotzdem unbrauchbar: Wer *horizontal* und
    # *vertikal* auf dieselbe Linie setzt, hat keinen Widerspruch gebaut — die
    # Linie schrumpft auf einen Punkt und ist dann beides. Der Solver meldet
    # dafür richtig zwei Freiheitsgrade und ein Restfehler von null.
    #
    # Weiter unten kann daraus niemand etwas machen: OpenCASCADE antwortete mit
    # ``StdFail_NotDone: BRep_API: command not done``, die C++-Ausnahme wurde
    # nach der Regel in ``errors.py`` zum ``InternalError``, und der Nutzer las
    # „Im Programm ist ein unerwarteter Fehler aufgetreten" samt Knopf für den
    # Fehlerbericht — für zwei Bedingungen, die er selbst gesetzt hat.
    #
    # Geprüft wird hier und nicht in den vier Operationen: alle vier gehen
    # durch diese Stelle. Die Grenze ist ``EPS_GEOM`` im Quadrat, weil sie auf
    # einer Fläche steht und nicht auf einer Länge (Regel 7).
    #
    # **Verworfen, nicht bloß gezählt.** Hier stand ``all(...)`` und warf nur,
    # wenn *keine* Kette trug — ein Rechteck mit 1200 mm² neben einer
    # geschrumpften Linie ging damit durch, und die leere Kette wanderte weiter
    # in den exakten Kern. Was keine Fläche hat, ist keine Region: Es fliegt
    # heraus, und erst wenn nichts übrig bleibt, ist die Skizze der Fehler.
    bearing = [loop for loop in loops if _area(_outline(loop)) > EPS_GEOM * EPS_GEOM]
    if not bearing:
        raise _broken(_("Die Skizze umschließt keine Fläche."))
    # **Eine Kette, die sich selbst kreuzt, wird hier abgewiesen** und nicht
    # erst am Ergebnis: extrudiert kam ein Körper heraus, dessen Netz nicht
    # wasserdicht war — ``is_closed`` sagte am exakten Körper sogar True, und
    # er ging ohne Befund in STL-Export und Schichtanalyse (Gesamtreview D-8).
    for loop in bearing:
        if _crosses_itself(loop):
            raise _broken(_("Der Umriss kreuzt sich selbst — die Fläche ist dort nicht eindeutig."))
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
    darin liegt, und nichts davon geht in den Kern.

    **Ein Bogen wird abgetastet wie in der Ansicht** (:func:`_along_arc`), und
    zwar aus zwei Gründen. Der eine ist die Einordnung: Anfang und Stützpunkt
    allein machten aus einem 270°-Bogen ein Dreieck, und ein Loch, das im
    Bogen lag, aber nicht im Dreieck, galt als eigener Umriss statt als Loch.
    Der andere ist der Flächenfilter in :func:`regions_of`: Eine Kette aus
    einem einzigen Bogen, dessen Ende auf seinem Anfang liegt, ergab zwei
    Punkte, daraus die Fläche null — die Ansicht zeichnete einen Kreis, und
    die Operation antwortete „Die Skizze umschließt keine Fläche."
    """
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
        arc = (
            arc_through(segment.start, segment.via, segment.end)
            if segment.kind == "arc" and segment.via is not None
            else None
        )
        if arc is not None:
            centre, radius, sweep = arc
            # Ohne den letzten Punkt: Er ist der Anfang des nächsten Segments,
            # und bei einem vollen Umlauf der eigene Anfang.
            points.extend(_along_arc(centre, segment.start, sweep, radius)[:-1])
            continue
        points.append(segment.start)
        points.extend(segment.through[1:-1])
    return points


def _crosses_itself(loop: Profile) -> bool:
    """Ob zwei Linien der Kette sich im Inneren schneiden.

    Nur Linienpaare, keine Bögen oder Splines: Deren Näherungspolylinie
    könnte eine Kreuzung melden, wo die exakte Kurve keine hat — eine falsche
    Ablehnung wäre schlimmer als die alte Lücke. Ein geteilter Endpunkt zählt
    nicht (benachbarte Segmente teilen ihn immer), und ein Punkt, der eine
    fremde Linie nur berührt, auch nicht — gemeldet wird der echte Schnitt.
    """
    lines = [segment for segment in loop.segments if segment.kind == "line"]
    for index, one in enumerate(lines):
        for other in lines[index + 1 :]:
            if any(_joins(a, b) for a in (one.start, one.end) for b in (other.start, other.end)):
                continue
            if _strictly_crossing(one.start, one.end, other.start, other.end):
                return True
    return False


def _strictly_crossing(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    """Ob die Strecken AB und CD sich echt schneiden — Berührung zählt nicht."""

    def side(tail: Point2, head: Point2, point: Point2) -> float:
        return (head[0] - tail[0]) * (point[1] - tail[1]) - (head[1] - tail[1]) * (
            point[0] - tail[0]
        )

    # Das Kreuzprodukt ist eine Fläche — dieselbe Grenze wie beim Flächenfilter
    # in ``regions_of``.
    limit = EPS_GEOM * EPS_GEOM
    first = (side(a, b, c), side(a, b, d))
    second = (side(c, d, a), side(c, d, b))
    return min(first) < -limit < limit < max(first) and min(second) < -limit < limit < max(second)


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


def signed_area(profile: Profile) -> float:
    """Die vorzeichenbehaftete Fläche eines Umrisses — Bögen exakt.

    Positiv heißt linksherum (gegen den Uhrzeigersinn), negativ rechtsherum.
    Löcher zählen nicht mit: Ein Loch ist ein eigener Umriss mit eigenem
    Drehsinn, und genau danach fragt der Aufrufer (``brep.profiles._face``).

    Gerechnet wird die Schuhbandformel über die **Sehnen**, plus je Bogen die
    Kreissegmentfläche ``r²/2 · (Δ - sin Δ)`` zwischen Sehne und Kurve. Das
    ist nicht nur genauer als ein Sehnenvieleck, es ist der Unterschied
    zwischen richtig und falsch: Ein Bogen über 180° wölbt sich weiter, als
    seine Sehne trägt, und das Sehnenvieleck bekommt dort den **umgekehrten**
    Drehsinn. Ein Pac-Man aus einem 270°-Bogen maß so -50 mm² statt +235,6 —
    sein Loch galt dem Kern damit als zweite Außenkontur, und der Körper
    wurde vom Bohren größer statt kleiner (1213,4 statt 1142,8 mm³).
    """
    if profile.circle is not None:
        return math.pi * profile.circle[1] ** 2
    points: list[Point2] = []
    curved = 0.0
    for segment in profile.segments:
        points.append(segment.start)
        # Beim Spline die Stützpunkte dazwischen; Anfang und Ende stehen schon
        # da, das Ende als Anfang des nächsten Segments.
        points.extend(segment.through[1:-1])
        if segment.kind != "arc" or segment.via is None:
            continue
        arc = arc_through(segment.start, segment.via, segment.end)
        if arc is not None:
            _, radius, sweep = arc
            curved += radius * radius * (sweep - math.sin(sweep)) / 2.0
    total = 0.0
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1], strict=True):
        total += x0 * y1 - x1 * y0
    return total / 2.0 + curved


def _nested(loops: list[Profile]) -> tuple[Profile, ...]:
    """Ordnet jeden Ring dem kleinsten zu, der ihn umschließt.

    Dem **kleinsten**, nicht dem ersten: bei einem Kasten in einem Kasten in
    einem Kasten gehört der innerste an den mittleren, und wer den erstbesten
    Treffer nimmt, hängt ihn nach außen. Und über alle Ebenen: gerade Tiefe
    ist Material, ungerade Tiefe ist Loch. Die Insel in einem Loch steht als
    eigener Umriss wieder da — vorher fiel die dritte Ebene stillschweigend
    weg: Die Zeichnung zeigte sie, der Körper hatte sie nicht, und keine
    Zeile sagte es (Gesamtreview D-7).
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

    def depth_of(index: int) -> int:
        steps = 0
        current = parents[index]
        while current is not None:
            steps += 1
            current = parents[current]
        return steps

    # Jeder Ring gerader Tiefe wird ein Umriss; seine direkten Kinder liegen
    # eine Ebene tiefer und sind damit seine Löcher.
    return tuple(
        replace(loop, holes=tuple(loops[i] for i, parent in enumerate(parents) if parent == index))
        for index, loop in enumerate(loops)
        if depth_of(index) % 2 == 0
    )


def shifted(profile: Profile, dx: float, dy: float) -> Profile:
    """Derselbe Umriss, in der Ebene verschoben — wo er hingehört, entscheidet
    die Operation, nicht die Skizze.

    Die Löcher ziehen mit, wie bei :func:`scaled`. Sie fehlten hier, und
    ``sketch_pocket`` legt **jede** Region durch diese Funktion, auch bei
    0/0: Dieselbe Skizze extrudierte mit Loch und schnitt als Tasche ohne —
    die Insel war weggefräst, still.
    """
    if profile.circle is not None:
        centre, radius = profile.circle
        return Profile(
            circle=((centre[0] + dx, centre[1] + dy), radius),
            holes=tuple(shifted(one, dx, dy) for one in profile.holes),
        )
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
        ),
        holes=tuple(shifted(one, dx, dy) for one in profile.holes),
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


def arc_through(start: Point2, via: Point2, end: Point2) -> tuple[Point2, float, float] | None:
    """Mitte, Radius und vorzeichenbehaftete Weite eines Bogens durch drei Punkte.

    Die Gegenrichtung zu :func:`_arc_midpoint`: Dort wird aus Mittelpunkt,
    Anfang und Ende der Stützpunkt; hier aus Anfang, Stützpunkt und Ende
    wieder der Kreis. ``via`` liegt **auf** der Kurve und entscheidet damit,
    welchen der beiden Wege um den Kreis der Bogen nimmt — die Weite ist
    positiv gegen den Uhrzeigersinn und negativ mit ihm.

    Fallen Anfang und Ende zusammen, ist es ein **voller Umlauf**: Dann liegt
    der Mittelpunkt zwischen Anfang und Stützpunkt, denn ``_arc_midpoint``
    setzt den Stützpunkt in diesem Fall dem Anfang gegenüber.

    ``None`` heißt: Diese drei Punkte tragen keinen Kreis — sie liegen auf
    einer Geraden oder fallen zusammen. Der Aufrufer nimmt dann die Sehne,
    und das ist dort die richtige Antwort und nicht ein Kreis mit riesigem
    Radius, der numerisch auseinanderfliegt.
    """
    if math.dist(start, end) <= _JOIN_TOL:
        radius = math.dist(start, via) / 2.0
        if radius <= EPS_GEOM:
            return None
        centre = ((start[0] + via[0]) / 2.0, (start[1] + via[1]) / 2.0)
        return centre, radius, 2.0 * math.pi
    (ax, ay), (bx, by), (cx, cy) = start, via, end
    # Umkreismittelpunkt über die Determinante; sie ist zugleich das Maß dafür,
    # wie weit die drei Punkte von einer Geraden entfernt sind.
    below = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if is_zero(below):
        return None
    first, second, third = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (first * (by - cy) + second * (cy - ay) + third * (ay - by)) / below
    uy = (first * (cx - bx) + second * (ax - cx) + third * (bx - ax)) / below
    radius = math.dist((ux, uy), start)
    if radius <= EPS_GEOM:
        return None
    begin = math.atan2(ay - uy, ax - ux)
    middle = math.atan2(by - uy, bx - ux)
    finish = math.atan2(cy - uy, cx - ux)
    sweep = (finish - begin) % (2.0 * math.pi)
    # Liegt der Stützpunkt jenseits des Endes, führt der Bogen andersherum.
    if (middle - begin) % (2.0 * math.pi) > sweep:
        sweep -= 2.0 * math.pi
    return (ux, uy), radius, sweep


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


# --- Die gezeichnete Kurve (§30.1, Konzept „Die Skizze in den Raum") --------


#: Wie weit eine Sehne höchstens von ihrem Bogen abweichen darf, in Millimetern.
#:
#: Keine Materialtoleranz im Sinne von Regel 7 — hier geht es nicht um eine
#: Passung, sondern darum, ab wann ein Kreis wie ein Vieleck aussieht. Feiner
#: als die Vernetzung des B-Rep-Kerns (``DEFLECTION`` = 0,05): In die Skizze
#: wird hineingezoomt, in ein fertiges Netz seltener.
CHORD_ERROR = 0.02

#: Untergrenze der Segmentzahl je Bogen. Ein Viertelkreis mit zwei Sehnen sähe
#: auch dann falsch aus, wenn die Sehnentoleranz es zuließe.
_LEAST_STEPS = 8

#: Obergrenze. Bei einem Kreis von einem Meter verlangte die Toleranz über
#: dreitausend Punkte für eine Linie, die niemand von einer feineren
#: unterscheidet.
_MOST_STEPS = 360


@dataclass(frozen=True, slots=True)
class SketchCurve:
    """Ein Skizzenelement als Punktfolge im Raum.

    Was die Ansicht braucht, um eine Skizze dorthin zu zeichnen, wo sie liegt:
    keine exakten Kurven wie im :class:`ProfileSegment` — die gehen an den
    B-Rep-Kern —, sondern abgetastete Punkte in Weltkoordinaten.

    Ein **Kreis trägt seinen ersten Punkt am Ende noch einmal**. Damit ist
    „geschlossen" an der Punktfolge abzulesen und braucht kein eigenes Feld,
    das man vergessen kann zu setzen.

    Ein **Punkt** kommt als Folge der Länge eins. Wer ihn zeichnet, sieht das
    an der Länge; eine zweite Liste daneben wäre eine zweite Stelle, an der
    die Reihenfolge stimmen muss.
    """

    points: tuple[Vec3, ...]
    construction: bool = False
    """Hilfsgeometrie — sie wird anders gezeichnet und bildet kein Profil."""


def _steps_for(radius: float, sweep: float) -> int:
    """Wie viele Sehnen ein Bogen dieses Radius und dieser Weite braucht.

    Aus der Sehnentoleranz: Bei einem Winkelschritt θ liegt die Sehnenmitte um
    ``r * (1 - cos(θ/2))`` neben dem Bogen. Nach θ aufgelöst ergibt das den
    größten Schritt, der :data:`CHORD_ERROR` noch einhält.

    Ein Radius unter der Toleranz braucht keine Rechnung — dort ist jede
    Unterteilung feiner als der Fehler, den sie vermeiden soll.
    """
    if radius <= CHORD_ERROR:
        return _LEAST_STEPS
    step = 2.0 * math.acos(max(-1.0, 1.0 - CHORD_ERROR / radius))
    if step <= EPS_GEOM:
        return _MOST_STEPS
    return max(_LEAST_STEPS, min(_MOST_STEPS, math.ceil(abs(sweep) / step)))


def _along_arc(centre: Point2, start: Point2, sweep: float, radius: float) -> tuple[Point2, ...]:
    """Die Punkte eines Bogens, von ``start`` aus um ``sweep`` gedreht."""
    begin = math.atan2(start[1] - centre[1], start[0] - centre[0])
    steps = _steps_for(radius, sweep)
    return tuple(
        (
            centre[0] + radius * math.cos(begin + sweep * index / steps),
            centre[1] + radius * math.sin(begin + sweep * index / steps),
        )
        for index in range(steps + 1)
    )


def _flat_curve(element: SketchElement) -> tuple[Point2, ...]:
    """Ein Element als Punktfolge in der Zeichenebene.

    Der Bogen läuft **gegen den Uhrzeigersinn** von Anfang nach Ende — so
    steht es im Vertrag von :class:`SketchElement`, und daran hängt, ob eine
    Kontur den kurzen oder den langen Weg nimmt. Ein Bogen, dessen Ende genau
    auf seinem Anfang liegt, ist ein voller Umlauf und keine Strecke der
    Länge null.
    """
    points = element.points
    if element.kind == "line":
        return (points[0], points[1])
    if element.kind == "circle":
        centre, rim = points[0], points[1]
        radius = math.hypot(rim[0] - centre[0], rim[1] - centre[1])
        return _along_arc(centre, rim, 2.0 * math.pi, radius)
    if element.kind == "arc":
        centre, start, end = points[0], points[1], points[2]
        radius = math.hypot(start[0] - centre[0], start[1] - centre[1])
        begin = math.atan2(start[1] - centre[1], start[0] - centre[0])
        finish = math.atan2(end[1] - centre[1], end[0] - centre[0])
        sweep = (finish - begin) % (2.0 * math.pi)
        # Dieselbe Schwelle wie in ``_arc_midpoint`` — zwei Zahlen für die
        # Frage „ist das ein Vollkreis?" hießen: Der Viewport zeichnete einen
        # Kreis, in den Kern ging ein Bogen ohne Ausdehnung.
        if sweep <= _FULL_CIRCLE_EPS:
            sweep = 2.0 * math.pi
        return _along_arc(centre, start, sweep, radius)
    if element.kind == "spline":
        return _along_spline(points)
    return (points[0],)


def _along_spline(points: tuple[Point2, ...]) -> tuple[Point2, ...]:
    """Ein Spline als Punktfolge — Catmull-Rom, wie ihn die Zeichenfläche malt.

    Dieselbe Kurve wie in ``SketchCanvas._paint_element``: kubische Stücke,
    deren Kontrollpunkte aus den Nachbarn gemittelt sind. Eine Vorschau, die
    Ecken zeigt, wo das Ergebnis keine hat, wäre eine Aussage über die
    Geometrie, die nicht stimmt.
    """
    count = len(points)
    if count < 2:
        return points
    steps = max(_LEAST_STEPS, min(_MOST_STEPS, 12 * (count - 1)))
    per_piece = max(1, steps // (count - 1))
    curve: list[Point2] = [points[0]]
    for index in range(count - 1):
        before = points[max(index - 1, 0)]
        first, second = points[index], points[index + 1]
        after = points[min(index + 2, count - 1)]
        one = (first[0] + (second[0] - before[0]) / 6.0, first[1] + (second[1] - before[1]) / 6.0)
        two = (second[0] - (after[0] - first[0]) / 6.0, second[1] - (after[1] - first[1]) / 6.0)
        for step in range(1, per_piece + 1):
            share = step / per_piece
            rest = 1.0 - share
            curve.append(
                (
                    rest**3 * first[0]
                    + 3.0 * rest**2 * share * one[0]
                    + 3.0 * rest * share**2 * two[0]
                    + share**3 * second[0],
                    rest**3 * first[1]
                    + 3.0 * rest**2 * share * one[1]
                    + 3.0 * rest * share**2 * two[1]
                    + share**3 * second[1],
                )
            )
    return tuple(curve)


def curves_of(solved: SolvedSketch, frame: PlaneFrame) -> tuple[SketchCurve, ...]:
    """Die gelöste Skizze als Punktfolgen im Raum, in Reihenfolge der Elemente.

    Der Weg von der Zeichnung in die Ansicht (§30.1, Stufe zwei): Jedes
    Element wird in der Ebene abgetastet und über
    :func:`app.core.sketch.planes.to_world` an seinen Ort gelegt.

    **Ohne Qt und ohne VTK**, und das ist der Zweck. Offscreen gibt es keinen
    Plotter, und was hinter dieser Wache gerechnet wird, prüft in der Suite
    niemand mehr. Hier steht die ganze Aussage darüber, *was* zu zeichnen ist;
    die Ansicht reicht sie weiter, ohne sie zu verändern.

    Konstruktionsgeometrie kommt mit — sie wird anders gezeichnet, aber sie
    steht im Bild. Nur die Profilbildung übergeht sie (:func:`regions_of`).
    """
    return tuple(
        SketchCurve(
            points=tuple(to_world(frame, point) for point in _flat_curve(element)),
            construction=element.construction,
        )
        for element in solved.elements
    )


def bounds_of(profile: Profile) -> tuple[Point2, Point2]:
    """Der Hüllrechteck-Bereich eines Umrisses, Löcher zählen nicht mit.

    Löcher liegen definitionsgemäß **innerhalb** ihrer Außenkontur, tragen
    also nichts zum Bereich bei. Bei einem Kreis kommt der Bereich aus Mitte
    und Radius; bei Bögen aus Anfang, Ende und Stützpunkt — eine Näherung nach
    außen, denn der Scheitel eines Bogens kann weiter liegen als seine drei
    Punkte. Für das, wofür der Bereich hier gebraucht wird — einen Mittelpunkt
    zum Skalieren —, reicht das: Der Mittelpunkt einer symmetrischen Form
    stimmt, und bei einer unsymmetrischen ist jede Wahl eine Setzung.
    """
    if profile.circle is not None:
        (cx, cy), radius = profile.circle
        return (cx - radius, cy - radius), (cx + radius, cy + radius)
    corners: list[Point2] = []
    for segment in profile.segments:
        corners.append(segment.start)
        corners.append(segment.end)
        if segment.via is not None:
            corners.append(segment.via)
        corners.extend(segment.through)
    if not corners:
        return (0.0, 0.0), (0.0, 0.0)
    xs = [p[0] for p in corners]
    ys = [p[1] for p in corners]
    return (min(xs), min(ys)), (max(xs), max(ys))


def scaled(profile: Profile, factor: float, centre: Point2) -> Profile:
    """Denselben Umriss um ``centre`` skaliert — Löcher wandern mit.

    **Um einen Mittelpunkt und nicht um den Ursprung**, und das ist der ganze
    Sinn: Die Grundformen des Katalogs liegen um den Ursprung zentriert, eine
    gezeichnete Skizze liegt irgendwo. Wer sie um den Ursprung verkleinerte,
    bekäme keinen Pyramidenstumpf, sondern einen schiefen Keil — die Form
    wanderte beim Schrumpfen zum Nullpunkt.

    Die Löcher werden mit demselben Mittelpunkt skaliert, nicht mit ihrem
    eigenen: Sie sollen ihre Lage **relativ zur Außenkontur** behalten.
    """

    def moved(p: Point2) -> Point2:
        return (
            centre[0] + (p[0] - centre[0]) * factor,
            centre[1] + (p[1] - centre[1]) * factor,
        )

    if profile.circle is not None:
        centre_of, radius = profile.circle
        return Profile(
            circle=(moved(centre_of), radius * factor),
            holes=tuple(scaled(one, factor, centre) for one in profile.holes),
        )
    return Profile(
        segments=tuple(
            ProfileSegment(
                kind=segment.kind,
                start=moved(segment.start),
                end=moved(segment.end),
                via=None if segment.via is None else moved(segment.via),
                through=tuple(moved(p) for p in segment.through),
            )
            for segment in profile.segments
        ),
        holes=tuple(scaled(one, factor, centre) for one in profile.holes),
    )
