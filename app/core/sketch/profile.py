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
from collections.abc import Callable
from dataclasses import dataclass, replace
from itertools import pairwise
from typing import Any, Final, Literal

from app.core.errors import CORRECT_INPUT, Action, GeometryError
from app.core.sketch.planes import to_world
from app.core.types import PlaneFrame, Point2, SketchElement, SolvedSketch, Vec3
from app.core.units import (
    EPS_GEOM,
    circle_point,
    exact_atan2,
    exact_sin,
    is_zero,
    ring_area,
)
from app.i18n import TranslatableText, _

#: Wie nah zwei Endpunkte beieinander liegen müssen, um als verbunden zu
#: gelten. Gelöste Koinzidenzen liegen bei 1e-9; das hier ist bewusst gröber,
#: bleibt aber weit unter jedem druckbaren Maß.
_JOIN_TOL = 1e-4

#: Der Stand der Profilbildung, wie er in die Cache-Kennung jeder Operation
#: eingeht, die eine Zeichnung zu Umrissen macht (``cache_version``).
#:
#: **Eine Zahl für alle Verbraucher**, weil eine Änderung hier alle trifft:
#: Hochziehen, Tasche, Drehen, Führen, Überblenden und Lochfeld lesen dieselben
#: Umrisse. ``holes-in-place-1`` (Durchsicht P6.6): Ein Loch in einer Platte,
#: die nicht um den Ursprung lag, ging bis dahin verloren — ein Ergebnis ohne
#: Loch darf danach nicht mehr aus dem Speicher- oder Dateicache kommen.
#: ``snapped-ends-2`` (RM-391): Kettenenden rasten aufeinander ein
#: (:func:`_starting_at`); ein undichter Körper aus einer Lücke unter der
#: Fangtoleranz darf nicht aus dem Cache zurückkommen.
PROFILE_REVISION: Final = "snapped-ends-2"

#: Die Elementarten, die sich zu einer Kette verbinden — alles mit zwei Enden.
#: Kreis und volle Ellipse sind je ein Umriss für sich, ein Punkt ist keiner.
_CHAINED: Final = frozenset({"line", "arc", "spline", "elliptical_arc"})


@dataclass(frozen=True, slots=True)
class ProfileSegment:
    """Eine Strecke oder ein Bogen des Umrisses.

    ``via`` ist bei Bögen ein Punkt **auf** der Kurve zwischen Anfang und
    Ende — damit bleibt die Geometrie beim Umdrehen der Laufrichtung
    dieselbe, und der Kern baut den Bogen aus drei Punkten exakt nach."""

    kind: Literal["line", "arc", "spline", "ellipse"]
    start: Point2
    end: Point2
    via: Point2 | None = None
    through: tuple[Point2, ...] = ()
    """Bei einem Spline **alle** Punkte, durch die er läuft, einschließlich
    Anfang und Ende. Der Kern legt daraus eine B-Spline-Kurve, die jeden davon
    trifft — segmentiert wird nichts, und beim Umdrehen der Laufrichtung dreht
    sich diese Liste mit."""
    ellipse: tuple[Point2, Point2, Point2] | None = None
    """Bei einem Stück Ellipse die Ellipse selbst: Mitte, Ende der ersten und
    Ende der zweiten Achse, wie im Element gespeichert (RM-188 P6.6a).

    Aus drei Punkten auf der Kurve ließe sich eine Ellipse nicht
    zurückrechnen, anders als ein Kreis — sie reist deshalb mit. ``via``
    liegt wie beim Bogen auf der Kurve zwischen Anfang und Ende und
    entscheidet, welchen der beiden Wege das Stück nimmt. Eine volle Ellipse
    ist ein Stück, dessen Ende auf seinem Anfang liegt; sie läuft gegen den
    Uhrzeigersinn."""


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

    Verschachtelung folgt den echten Kurven. Sich schneidende oder berührende
    Ringe werden mit einem Handlungsvorschlag abgelehnt; ihre Fläche wäre
    ohne eine zusätzliche Entscheidung nicht eindeutig.
    """
    # Hilfsgeometrie trägt Bedingungen, aber keinen Umriss (§30.1). Eine
    # Mittellinie, an der zwei Bohrungen symmetrisch hängen, soll nicht als
    # Kante im extrudierten Körper landen.
    shaping = [element for element in solved.elements if not element.construction]
    circles = [element for element in shaping if element.kind == "circle"]
    # **Eine volle Ellipse ist ein Umriss für sich**, wie ein Kreis — und nicht
    # ein Glied, das in eine Kette gerät: Ihr Anfang liegt auf dem Ende ihrer
    # ersten Achse, und eine Linie, die dort zufällig endet, hätte sich sonst
    # in ihren Ring gehängt.
    ellipses = [element for element in shaping if element.kind == "ellipse"]
    drawable = [element for element in shaping if element.kind in _CHAINED]
    if not circles and not ellipses and not drawable:
        raise _broken(_("Die Skizze enthält nichts, was einen Umriss ergeben könnte."))

    loops: list[Profile] = [
        Profile(circle=(element.points[0], math.dist(element.points[0], element.points[1])))
        for element in circles
    ]
    loops.extend(
        Profile(segments=(_segment(element.kind, element.points),)) for element in ellipses
    )
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
    bearing = [loop for loop in loops if ring_area(_outline(loop)) > EPS_GEOM * EPS_GEOM]
    if not bearing:
        raise _broken(_("Die Skizze umschließt keine Fläche."))
    # **Eine Kette, die sich selbst kreuzt, wird hier abgewiesen** und nicht
    # erst am Ergebnis: extrudiert kam ein Körper heraus, dessen Netz nicht
    # wasserdicht war — ``is_closed`` sagte am exakten Körper sogar True, und
    # er ging ohne Befund in STL-Export und Schichtanalyse (Gesamtreview D-8).
    for loop in bearing:
        if crosses_itself(loop):
            raise _broken(_("Der Umriss kreuzt sich selbst — die Fläche ist dort nicht eindeutig."))
    return _nested(bearing)


def path_of(solved: SolvedSketch) -> Profile:
    """Die gelöste Skizze als **offene** Kette — eine Bahn, kein Umriss (E3).

    :func:`regions_of` sucht Ringe und meldet ein freies Ende als Fehler; eine
    Bahn ist genau das Gegenteil: Sie hat zwei freie Enden und schließt nicht.
    Zurück kommt trotzdem ein :class:`Profile` — der B-Rep-Kern baut aus seinen
    Segmenten denselben Draht wie aus einem Umriss (``_wire``), und ein
    zweiter Typ für dieselbe Kette wäre eine zweite Stelle, an der Bögen und
    Splines richtig übersetzt werden müssten.

    Drei Bedingungen, und jede ist ein Satz statt eines Programmfehlers:

    * **Etwas zu führen muss da sein.** Eine leere Zeichnung oder eine aus
      lauter Hilfslinien ergibt keine Bahn.
    * **Genau zwei freie Enden.** Ein Ring hat keines — er wäre eine
      geschlossene Bahn, und was daran Anfang ist, entschiede niemand. Drei
      Enden heißt Verzweigung, und dann ist die Bahn nicht eine, sondern
      mehrere.
    * **Ein Kreis ist keine Bahn.** Er hat kein Ende, an dem der Querschnitt
      säße; wer im Kreis führen will, dreht (``sketch_revolve``).

    Gelaufen wird vom ersten freien Ende, das in der Reihenfolge der Elemente
    auftaucht — bei zwei Enden ist die Richtung die einzige Wahl, die bleibt,
    und der Docstring der Operation nennt sie.
    """
    shaping = [element for element in solved.elements if not element.construction]
    if any(element.kind == "circle" for element in shaping):
        raise _broken(
            _("Ein Kreis ist keine Bahn — er hat kein Ende, an dem der Querschnitt beginnt.")
        )
    if any(element.kind == "ellipse" for element in shaping):
        raise _broken(
            _("Eine Ellipse ist keine Bahn — sie hat kein Ende, an dem der Querschnitt beginnt.")
        )
    drawable = [element for element in shaping if element.kind in _CHAINED]
    if not drawable:
        raise _broken(_("Die Skizze enthält nichts, was eine Bahn ergeben könnte."))
    segments = [_segment(element.kind, element.points) for element in drawable]

    # Wie oft jeder Punkt vorkommt: einmal heißt freies Ende. Verglichen wird
    # über ``_joins`` und nicht über Gleichheit — zwei gezeichnete Enden treffen
    # sich auf die Toleranz genau, nicht auf das Bit (Regel 6).
    ends: list[Point2] = []
    for segment in segments:
        ends.append(segment.start)
        ends.append(segment.end)
    free = [
        point
        for index, point in enumerate(ends)
        if not any(_joins(point, other) for other in ends[:index] + ends[index + 1 :])
    ]
    if len(free) != 2:
        raise _broken(
            _("Eine Bahn hat genau zwei Enden — diese Zeichnung ist ein Ring oder verzweigt sich.")
        )

    start = free[0]
    first = next(
        index
        for index, segment in enumerate(segments)
        if _joins(segment.start, start) or _joins(segment.end, start)
    )
    head = segments.pop(first)
    chain = [head if _joins(head.start, start) else _flipped(head)]
    while segments:
        tail = chain[-1].end
        matches = [
            (index, candidate)
            for index, candidate in enumerate(segments)
            if _joins(tail, candidate.start) or _joins(tail, candidate.end)
        ]
        if not matches:
            raise _broken(_("Die Bahn zerfällt in mehrere Stücke — sie muss zusammenhängen."))
        index, candidate = matches[0]
        segments.pop(index)
        chain.append(_starting_at(candidate, tail))
    return Profile(segments=tuple(chain))


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
            raise _broken(
                _("Der Umriss verzweigt sich — an einem Punkt treffen sich mehr als zwei Kanten.")
            )
        index, candidate = matches[0]
        segments.pop(index)
        chain.append(_starting_at(candidate, tail))
    # Der Ring schließt auf den Anfang, nicht bloß in seine Nähe — siehe
    # :func:`_starting_at`.
    chain[0] = _starting_at(chain[0], chain[-1].end)
    return tuple(chain)


def _outline(profile: Profile) -> list[Point2]:
    """Eine Polylinie, die dem Umriss folgt — nur zum Einordnen.

    Die Punktfolge dient der groben Flächenauswahl und dem Rückfall ohne
    exakten Kern. Kreisgrenzen werden beim Verschachteln analytisch geprüft.

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
                centre[0] + radius * circle_point(steps, index)[0],
                centre[1] + radius * circle_point(steps, index)[1],
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
        if segment.kind == "spline":
            points.extend(_along_spline(segment.through)[:-1])
        elif segment.kind == "ellipse":
            points.extend(ellipse_segment_points(segment, CHORD_ERROR)[:-1])
        else:
            points.append(segment.start)
    return points


def crosses_itself(loop: Profile) -> bool:
    """Ob zwei Teilstücke der Kette sich in ihrem Inneren schneiden.

    Für einen Umriss wie für eine offene Bahn (``sketch_sweep``, P6.5b): Die
    Prüfung fragt Paare von Teilstücken und kennt keinen Ringschluss.

    Wenn der B-Rep-Kern installiert ist, prüft OpenCASCADE genau die Bögen und
    interpolierenden B-Splines, die später den Körper bilden. Damit kann weder
    eine grobe Sehne eine Kreuzung erfinden noch eine Abtastung eine schmale
    Schleife übersehen. Ohne B-Rep bleibt die Punktfolge als Rückfall; dann
    kann aus diesen Profilen ohnehin kein exakter Körper entstehen.

    Geteilte Endpunkte und bloße Berührungen zählen weiterhin nicht.
    """
    exact = _crosses_exactly(loop)
    if exact is not None:
        return exact
    return _crosses_approximately(loop)


def _crosses_exactly(loop: Profile) -> bool | None:
    """Prüft den Umriss mit den exakten zweidimensionalen Kernkurven.

    ``None`` heißt ausschließlich, dass der optionale B-Rep-Kern nicht
    installiert ist. Fehler beim Kurvenbau werden nicht verschluckt.
    """
    from app.core.brep.kernel import available

    if not available():
        return None

    from OCP.GC import GC_MakeArcOfCircle2d, GC_MakeSegment2d
    from OCP.Geom2d import Geom2d_Circle
    from OCP.Geom2dAPI import Geom2dAPI_InterCurveCurve
    from OCP.gp import gp_Ax2d, gp_Dir2d, gp_Pnt2d

    def point(value: Point2) -> Any:
        return gp_Pnt2d(value[0], value[1])

    def line(start: Point2, end: Point2) -> Any | None:
        if _joins(start, end):
            return None
        return GC_MakeSegment2d(point(start), point(end)).Value()

    curves: list[tuple[Any, ProfileSegment]] = []
    for segment in loop.segments:
        curve: Any | None
        if segment.kind == "ellipse":
            from app.core.brep.profiles import ellipse_curve_2d

            curve = ellipse_curve_2d(segment)
        elif segment.kind == "spline":
            through = segment.through or (segment.start, segment.end)
            if len(through) < 2 or all(_joins(through[0], other) for other in through[1:]):
                curve = None
            else:
                from app.core.brep.profiles import spline_curve_2d

                curve = spline_curve_2d(through)
        elif segment.kind == "arc" and segment.via is not None:
            turn = arc_through(segment.start, segment.via, segment.end)
            if turn is None:
                curve = line(segment.start, segment.end)
            elif abs(turn[2]) >= 2.0 * math.pi:
                curve = Geom2d_Circle(gp_Ax2d(point(turn[0]), gp_Dir2d(1.0, 0.0)), turn[1])
            else:
                curve = GC_MakeArcOfCircle2d(
                    point(segment.start), point(segment.via), point(segment.end)
                ).Value()
        else:
            curve = line(segment.start, segment.end)
        if curve is not None:
            curves.append((curve, segment))

    def lies_at_an_end(intersection: Any, segment: ProfileSegment) -> bool:
        value = (float(intersection.X()), float(intersection.Y()))
        return _joins(value, segment.start) or _joins(value, segment.end)

    for curve, segment in curves:
        if segment.kind != "spline":
            continue
        found = Geom2dAPI_InterCurveCurve(curve, EPS_GEOM)
        if found.NbSegments() > 0:
            return True
        for index in range(1, found.NbPoints() + 1):
            if not lies_at_an_end(found.Point(index), segment):
                return True

    for index, (first, first_segment) in enumerate(curves):
        for second, second_segment in curves[index + 1 :]:
            found = Geom2dAPI_InterCurveCurve(first, second, EPS_GEOM)
            # **Zwei Stücke, die aufeinander liegen, kreuzen sich auch** —
            # nur meldet OpenCASCADE das nicht als Punkt, sondern als
            # gemeinsames Stück. Eine Linie, die auf sich selbst zurückläuft
            # (0→10, dann 10→5), ergab so einen Umriss mit einer Spitze ohne
            # Breite; der Kern baute daraus einen Körper, den seine eigene
            # Prüfung für ungültig hielt (Durchsicht 22.09.2026). **Aber nur,
            # wenn das Stück eine Länge hat** (:func:`_share_a_stretch`).
            if found.NbSegments() > 0 and _share_a_stretch(first_segment, second_segment):
                return True
            for point_index in range(1, found.NbPoints() + 1):
                intersection = found.Point(point_index)
                if not lies_at_an_end(intersection, first_segment) and not lies_at_an_end(
                    intersection, second_segment
                ):
                    return True
    return False


def _crosses_approximately(loop: Profile) -> bool:
    """Rückfallprüfung über die gezeichnete Punktfolge ohne B-Rep-Kern."""
    pieces: list[tuple[Point2, Point2]] = []
    for segment in loop.segments:
        points: tuple[Point2, ...]
        if segment.kind == "arc" and segment.via is not None:
            arc = arc_through(segment.start, segment.via, segment.end)
            points = (
                (segment.start, segment.end)
                if arc is None
                else _along_arc(arc[0], segment.start, arc[2], arc[1])
            )
        elif segment.kind == "spline":
            points = _along_spline(segment.through or (segment.start, segment.end))
        elif segment.kind == "ellipse":
            points = ellipse_segment_points(segment, CHORD_ERROR)
        else:
            points = (segment.start, segment.end)
        pieces.extend(pairwise(points))

    for index, one in enumerate(pieces):
        for other in pieces[index + 1 :]:
            if strictly_crossing(one[0], one[1], other[0], other[1]):
                return True
            if _overlapping(one[0], one[1], other[0], other[1]):
                return True
    return False


def _share_a_stretch(first: ProfileSegment, second: ProfileSegment) -> bool:
    """Ob zwei Stücke, die OpenCASCADE als deckungsgleich meldet, eine Länge teilen.

    **Zwei Bögen desselben Kreises, die nur an einem Ende aneinanderstoßen,
    meldet** ``Geom2dAPI_InterCurveCurve`` **als gemeinsames Stück** — sobald
    die Enden im letzten Bit auseinanderliegen. Die Naht eines exakten
    Zylinders teilt den Rand einer Bohrung genau so in zwei Bögen, und die
    Flächenkontur einer Platte mit Langloch galt damit als „kreuzt sich
    selbst" (gemessen 23.09.2026: y = -1,6·10⁻¹⁵ gegen -8,4·10⁻¹⁶ am selben Ende).
    Geteilt ist erst, was eine Länge über ``EPS_GEOM`` hat: auf einer Geraden
    über :func:`_overlapping`, auf einem Kreis über die gemeinsamen Winkel.
    Alles andere — ein Spline dabei — bleibt beim Wort des Kerns.
    """
    if first.kind == "line" and second.kind == "line":
        return _overlapping(first.start, first.end, second.start, second.end)
    if first.kind == "ellipse" and second.kind == "ellipse":
        return _ellipses_share_a_stretch(first, second)
    if first.kind != "arc" or second.kind != "arc" or first.via is None or second.via is None:
        return True
    one = arc_through(first.start, first.via, first.end)
    other = arc_through(second.start, second.via, second.end)
    if one is None or other is None:
        return True
    if math.dist(one[0], other[0]) > _JOIN_TOL or abs(one[1] - other[1]) > _JOIN_TOL:
        return True

    def interval(segment: ProfileSegment, turn: tuple[Point2, float, float]) -> tuple[float, float]:
        centre, _radius, sweep = turn
        begin = segment.start if sweep > 0.0 else segment.end
        return exact_atan2(begin[1] - centre[1], begin[0] - centre[0]), abs(sweep)

    low, span = interval(first, one)
    other_low, other_span = interval(second, other)
    shift = (other_low - low) % (2.0 * math.pi)
    shared = 0.0
    for start in (low + shift, low + shift - 2.0 * math.pi):
        shared += max(0.0, min(low + span, start + other_span) - max(low, start))
    return shared * one[1] > EPS_GEOM


def _overlapping(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    """Ob zwei Strecken auf derselben Geraden ein Stück gemeinsam haben.

    :func:`strictly_crossing` sieht das nicht — kollinear ist für das
    Kreuzprodukt „berührt", und Berührung zählt dort nicht. Zwei Stücke, die
    aufeinander liegen, sind aber eine Spitze ohne Breite im Umriss, keine
    Berührung. Ein gemeinsamer Endpunkt allein ist kein Stück.
    """
    along = (b[0] - a[0], b[1] - a[1])
    span = along[0] * along[0] + along[1] * along[1]
    if span <= EPS_GEOM * EPS_GEOM:
        return False

    def side(point: Point2) -> float:
        return along[0] * (point[1] - a[1]) - along[1] * (point[0] - a[0])

    # Das Kreuzprodukt durch die Länge ist der Abstand zur Geraden.
    reach = EPS_GEOM * math.sqrt(span)
    if abs(side(c)) > reach or abs(side(d)) > reach:
        return False

    def at(point: Point2) -> float:
        return (along[0] * (point[0] - a[0]) + along[1] * (point[1] - a[1])) / span

    low, high = sorted((at(c), at(d)))
    shared = min(high, 1.0) - max(low, 0.0)
    return shared * math.sqrt(span) > EPS_GEOM


def strictly_crossing(a: Point2, b: Point2, c: Point2, d: Point2) -> bool:
    """Ob die Strecken AB und CD sich echt schneiden — Berührung zählt nicht.

    Öffentlich, weil die Oberfläche dieselbe Frage stellt — die Zuordnungslinien
    der Maßfelder (`placement_flow._untangle`) —, und zwei Herleitungen
    derselben Auskunft waren am 21.09.2026 schon auseinander (Toleranz hier,
    exakter Vergleich dort; `zwillinge.md`).
    """

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
        return math.pi * profile.circle[1] * profile.circle[1]
    total = 0.0
    for segment in profile.segments:
        if segment.kind == "spline":
            for piece in spline_controls(segment.through):
                total += _bezier_signed_area(piece)
            continue
        total += (segment.start[0] * segment.end[1] - segment.end[0] * segment.start[1]) / 2.0
        if segment.kind == "ellipse":
            # Das Stück zwischen Sehne und Kurve: das Kreissegment
            # ``(Δ - sin Δ) / 2`` des Einheitskreises, gestreckt um die Fläche
            # ``a · b`` der Achsen — eine affine Abbildung ändert Flächen um
            # genau diesen Faktor. Die volle Ellipse hat keine Sehne und
            # ergibt so π·a·b.
            frame, sweep = ellipse_turn(segment)
            total += frame.first * frame.second * (sweep - exact_sin(sweep)) / 2.0
            continue
        if segment.kind != "arc" or segment.via is None:
            continue
        arc = arc_through(segment.start, segment.via, segment.end)
        if arc is not None:
            _, radius, sweep = arc
            total += radius * radius * (sweep - exact_sin(sweep)) / 2.0
    return total


def _bezier_signed_area(piece: tuple[Point2, ...]) -> float:
    """Exaktes Polynom-Integral von (x·dy - y·dx)/2 eines kubischen Stücks."""
    first, one, two, last = piece
    coefficients = [
        (
            first[axis],
            3.0 * (one[axis] - first[axis]),
            3.0 * (first[axis] - 2.0 * one[axis] + two[axis]),
            -first[axis] + 3.0 * one[axis] - 3.0 * two[axis] + last[axis],
        )
        for axis in range(2)
    ]
    x, y = coefficients
    return (
        sum(j * (x[i] * y[j] - y[i] * x[j]) / (i + j) for i in range(4) for j in range(1, 4)) / 2.0
    )


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
    areas = [abs(signed_area(loop)) for loop in loops]
    contains = _containment(loops, outlines)
    parents: list[int | None] = []
    for index, outline in enumerate(outlines):
        probe = outline[0]
        candidates = [
            other
            for other in range(len(loops))
            if other != index and areas[other] > areas[index] and contains(other, probe)
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


def _containment(
    loops: list[Profile], outlines: list[list[Point2]]
) -> Callable[[int, Point2], bool]:
    """Prüft die Randringe und liefert ihren gemeinsamen Punktklassifizierer.

    Ohne B-Rep bleiben Kreise analytisch. Die übrigen Kurven folgen dann
    derselben Polylinie wie der Netzkern; mit B-Rep werden echte Drähte und
    Flächen geprüft, einschließlich sehr schmaler Schnitte und Berührungen.
    """
    from app.core.brep.kernel import available

    exact = available()
    if exact:
        from OCP.BRepClass import BRepClass_FaceClassifier
        from OCP.BRepExtrema import BRepExtrema_DistShapeShape
        from OCP.TopAbs import TopAbs_IN

        from app.core.brep.profiles import _face, _lift_xy, _wire

        wires = [_wire(loop, _lift_xy) for loop in loops]
        faces = [_face(loop, _lift_xy) for loop in loops]
    else:
        from shapely.geometry import LinearRing

        rings = [LinearRing(outline) for outline in outlines]

    for index, first in enumerate(loops):
        for other in range(index + 1, len(loops)):
            second = loops[other]
            if first.circle is not None and second.circle is not None:
                centre, radius = first.circle
                middle, reach = second.circle
                distance = math.dist(centre, middle)
                touching = abs(radius - reach) - EPS_GEOM <= distance <= radius + reach + EPS_GEOM
            elif exact:
                measure = BRepExtrema_DistShapeShape(wires[index], wires[other])
                if not measure.IsDone():
                    raise _broken(_("Die Umrisse lassen sich nicht sicher voneinander trennen."))
                touching = measure.Value() <= EPS_GEOM
            else:
                touching = rings[index].distance(rings[other]) <= EPS_GEOM
            if touching:
                raise _broken(
                    _(
                        "Zwei Umrisse schneiden oder berühren sich — verschieben Sie sie "
                        "auseinander oder zeichnen Sie einen gemeinsamen Umriss."
                    )
                )

    def inside(index: int, point: Point2) -> bool:
        circle = loops[index].circle
        if circle is not None:
            return math.dist(circle[0], point) < circle[1]
        if exact:
            # **Der Punkt im Raum, nicht in den Parametern der Fläche.** Ein
            # ``gp_Pnt2d`` liest der Klassifizierer als (u, v) der Fläche, und
            # die Ebene einer Fläche aus einem Draht hat ihren Ursprung in der
            # Mitte des Drahts: An einer Platte von (0 | 0) bis (40 | 20) wurde
            # ein Kreis bei (10 | 10) bei (30 | 20) gesucht, auf dem Rand — und
            # das Loch war weg (seit v0.3.5, Durchsicht P6.6). Die Fläche liegt
            # auf ``_lift_xy``, also derselbe Punkt auf Höhe null.
            return bool(
                BRepClass_FaceClassifier(faces[index], _lift_xy(point), EPS_GEOM).State()
                == TopAbs_IN
            )
        return _inside(point, outlines[index])

    return inside


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

    def moved(point: Point2) -> Point2:
        return (point[0] + dx, point[1] + dy)

    return Profile(
        segments=tuple(
            ProfileSegment(
                segment.kind,
                moved(segment.start),
                moved(segment.end),
                via=None if segment.via is None else moved(segment.via),
                # Die Stützpunkte ziehen mit: ohne sie käme der Spline
                # verschoben an seinen Enden und unverschoben dazwischen an.
                through=tuple(moved(point) for point in segment.through),
                # Und die Ellipse mit ihren drei Punkten — sonst liefen Anfang
                # und Ende verschoben um eine Kurve, die stehen geblieben ist.
                ellipse=None
                if segment.ellipse is None
                else (
                    moved(segment.ellipse[0]),
                    moved(segment.ellipse[1]),
                    moved(segment.ellipse[2]),
                ),
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
    if kind == "ellipse":
        centre, first, second = points
        frame = ellipse_frame(centre, first, second)
        # Die volle Ellipse beginnt und endet am Ende ihrer ersten Achse; der
        # Stützpunkt liegt gegenüber, wie beim vollen Bogen.
        start = frame.at(1.0, 0.0)
        return ProfileSegment(
            "ellipse", start, start, via=frame.at(-1.0, 0.0), ellipse=(centre, first, second)
        )
    if kind == "elliptical_arc":
        centre, first, second, start, end = points
        frame = ellipse_frame(centre, first, second)
        middle = ccw_middle(frame.parameter(start), frame.parameter(end))
        return ProfileSegment(
            "ellipse", start, end, via=frame.at(*middle), ellipse=(centre, first, second)
        )
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
    # Die Winkel über ``exact_atan2`` (RM-187): Die Weite wird zu den Ecken
    # jedes abgetasteten Bogens, ``math.atan2`` rundet je Maschine anders.
    begin = exact_atan2(ay - uy, ax - ux)
    middle = exact_atan2(by - uy, bx - ux)
    finish = exact_atan2(cy - uy, cx - ux)
    sweep = (finish - begin) % (2.0 * math.pi)
    # Liegt der Stützpunkt jenseits des Endes, führt der Bogen andersherum.
    if (middle - begin) % (2.0 * math.pi) > sweep:
        sweep -= 2.0 * math.pi
    return (ux, uy), radius, sweep


def arc_sweep(centre: Point2, start: Point2, end: Point2) -> float:
    """Wie weit ein Bogen vom Anfang zum Ende läuft — gegen den Uhrzeigersinn, im Bogenmaß.

    **Zusammenfallende Enden sind ein Vollkreis, kein Nullbogen.** Mit
    ``== 0.0`` fing das den Löser-Fall nie: Der Stützpunkt landete auf dem
    Startpunkt, und der B-Rep-Kern baute einen Bogen ohne Ausdehnung statt
    eines Kreises.

    **Eine Antwort für alle Leser** — Profil, Ansicht, Zeichenfläche,
    Zeichnungshülle. Die Zeichenfläche rechnete bis zum 23.09.2026 selbst, in
    Grad und ohne diese Regel: Ein Bogen, dessen Enden der Löser
    zusammengeführt hatte, war im Profil ein Kreis und auf dem Blatt
    unsichtbar und nicht anklickbar.
    """
    begin = exact_atan2(start[1] - centre[1], start[0] - centre[0])
    finish = exact_atan2(end[1] - centre[1], end[0] - centre[0])
    sweep = (finish - begin) % (2.0 * math.pi)
    return 2.0 * math.pi if sweep <= _FULL_CIRCLE_EPS else sweep


def _arc_midpoint(centre: Point2, start: Point2, end: Point2) -> Point2:
    """Der Punkt auf halbem Weg des Bogens, gegen den Uhrzeigersinn gerechnet."""
    radius = math.dist(centre, start)
    begin = exact_atan2(start[1] - centre[1], start[0] - centre[0])
    sweep = arc_sweep(centre, start, end)
    return points_on_circle(centre, radius, [begin + sweep / 2.0])[0]


def _flipped(segment: ProfileSegment) -> ProfileSegment:
    return ProfileSegment(
        segment.kind,
        segment.end,
        segment.start,
        via=segment.via,
        through=tuple(reversed(segment.through)),
        ellipse=segment.ellipse,
    )


def _joins(a: Point2, b: Point2) -> bool:
    return math.dist(a, b) <= _JOIN_TOL


def _starting_at(segment: ProfileSegment, point: Point2) -> ProfileSegment:
    """Das Stück, das an *point* anschließt — in dieser Richtung und mit genau
    diesem Anfang.

    **Eingerastet, nicht bloß nah.** Verkettet wird über :func:`_joins` auf
    ``_JOIN_TOL``; der exakte Kern verbindet zwei Kanten aber nur, wenn ihre
    Ecken auf seine eigene Toleranz (10⁻⁷) zusammenfallen. Ein Linienzug, dessen
    letztes Ende nur über die Fangtoleranz am Anfang liegt, ergab dazwischen
    einen Draht mit zwei Ecken an einer Stelle und einen undichten Körper
    (RM-391: nach dem Strecken schloss er auf 4,5·10⁻⁷). Die Abweichung liegt
    unter ``_JOIN_TOL`` und damit unter jedem druckbaren Maß; ein Bogen behält
    seinen Stützpunkt, ein Spline seine inneren Punkte.
    """
    oriented = segment if _joins(point, segment.start) else _flipped(segment)
    if oriented.start == point:
        return oriented
    through = (point, *oriented.through[1:]) if oriented.through else ()
    return replace(oriented, start=point, through=through)


def _broken(detail: TranslatableText | str) -> GeometryError:
    return GeometryError(
        _("Aus dieser Skizze wird kein Umriss."),
        detail,
        suggestions=(
            Action("open_sketch", _("Skizze ansehen"), primary=True),
            CORRECT_INPUT,
        ),
    )


# --- Ellipsen (RM-188 P6.6a) ---------------------------------------------------------

#: Unterhalb dieser Länge hat ein Parametervektor keine Richtung — nur ein
#: Schutz gegen die Teilung durch null, keine Toleranz (Regel 7).
_TINY_PARAMETER: Final = 1e-15

#: Wie weit ein abgetastetes Stück im Parameter höchstens reicht, als Kosinus:
#: ein Sechzehntel des Umlaufs. Die Sehnengrenze allein reichte bei sehr
#: kleinen Ellipsen mit einem Viereck — dieselbe Überlegung wie ``_LEAST_STEPS``
#: beim Bogen. ``cos(π/8)`` als Wurzelausdruck: Wurzeln rundet jede Maschine
#: gleich, ``math.cos`` nicht (RM-187).
_WIDEST_STEP: Final = math.sqrt(2.0 + math.sqrt(2.0)) / 2.0

#: Wie oft ein Stück höchstens geteilt wird. Zweiundfünfzig Teilungen sind
#: die Stellenzahl eines ``float`` — feiner lässt sich kein Parameter teilen.
_DEEPEST_SPLIT: Final = 52


@dataclass(frozen=True, slots=True)
class EllipseFrame:
    """Eine Ellipse, wie Profil, Netzweg und Ansicht sie rechnen.

    ``axis`` ist die Einheitsrichtung der ersten Achse, ``first`` und
    ``second`` sind die beiden Halbachsen. Der Parameter ``(cos t, sin t)``
    läuft im rechtshändigen Rahmen aus der ersten Achse und derselben um
    90 Grad gedreht — also **gegen den Uhrzeigersinn**, gleich auf welcher
    Seite der gespeicherte zweite Achsenpunkt liegt: Er trägt die Länge der
    zweiten Achse, ihre Richtung folgt aus der ersten.

    Gerechnet wird ohne Winkelfunktion. Ein Parameter ist ein Einheitsvektor
    im Kreis der Ellipse, und was zwischen zwei davon liegt, findet die
    Halbierung ihrer Summe — Grundrechenarten und Wurzeln, auf jeder Maschine
    dieselbe Zahl (RM-187). Nur wo eine Entscheidung mit großem Abstand fällt
    (Drehsinn, Flächenvorzeichen), steht ``atan2``.
    """

    centre: Point2
    axis: Point2
    first: float
    second: float

    def at(self, cos: float, sin: float) -> Point2:
        """Der Punkt der Ellipse zum Parameter ``(cos, sin)``."""
        ux, uy = self.axis
        return (
            self.centre[0] + self.first * cos * ux - self.second * sin * uy,
            self.centre[1] + self.first * cos * uy + self.second * sin * ux,
        )

    def parameter(self, point: Point2) -> Point2:
        """Der Parameter, an dem der Strahl von der Mitte durch ``point`` die
        Ellipse trifft — für einen Punkt auf ihr genau seiner."""
        ux, uy = self.axis
        dx, dy = point[0] - self.centre[0], point[1] - self.centre[1]
        x = (dx * ux + dy * uy) / self.first
        y = (-dx * uy + dy * ux) / self.second
        size = math.hypot(x, y)
        if size <= _TINY_PARAMETER:
            return (1.0, 0.0)
        return (x / size, y / size)


def ellipse_frame(centre: Point2, first_end: Point2, second_end: Point2) -> EllipseFrame:
    """Der Rahmen einer Ellipse aus Mitte und den Enden ihrer beiden Achsen."""
    first = math.dist(centre, first_end)
    second = math.dist(centre, second_end)
    if first <= _TINY_PARAMETER:
        return EllipseFrame(centre, (1.0, 0.0), first, second)
    axis = ((first_end[0] - centre[0]) / first, (first_end[1] - centre[1]) / first)
    return EllipseFrame(centre, axis, first, second)


def ccw_middle(start: Point2, end: Point2) -> Point2:
    """Der Parameter auf halbem Weg **gegen den Uhrzeigersinn** von ``start``
    nach ``end`` — beide Einheitsvektoren im Kreis der Ellipse.

    Zusammenfallende Enden sind ein voller Umlauf, und die Mitte liegt
    gegenüber — dieselbe Lesart wie beim Bogen (:func:`arc_sweep`).
    """
    if math.hypot(end[0] - start[0], end[1] - start[1]) <= _FULL_CIRCLE_EPS:
        return (-start[0], -start[1])
    sx, sy = start[0] + end[0], start[1] + end[1]
    size = math.hypot(sx, sy)
    if size <= _FULL_CIRCLE_EPS:
        # Genau gegenüber: eine halbe Drehung weiter liegt die Mitte bei 90°.
        return (-start[1], start[0])
    cross = start[0] * end[1] - start[1] * end[0]
    if cross > 0.0:
        return (sx / size, sy / size)
    return (-sx / size, -sy / size)


def parameter_sweep(start: Point2, end: Point2) -> float:
    """Wie weit der Parameter gegen den Uhrzeigersinn von ``start`` bis
    ``end`` läuft, im Bogenmaß in (0, 2π] — zusammenfallend ist ein Umlauf.

    Nur für Entscheidungen und Flächen, nicht für Punkte (siehe
    :class:`EllipseFrame`)."""
    cross = start[0] * end[1] - start[1] * end[0]
    dot = start[0] * end[0] + start[1] * end[1]
    sweep = exact_atan2(cross, dot) % (2.0 * math.pi)
    return 2.0 * math.pi if sweep <= _FULL_CIRCLE_EPS else sweep


def ellipse_turn(segment: ProfileSegment) -> tuple[EllipseFrame, float]:
    """Der Rahmen eines Ellipsenstücks und wie weit es läuft — mit Vorzeichen.

    Positiv heißt gegen den Uhrzeigersinn vom Anfang zum Ende, negativ mit
    ihm; welcher der beiden Wege gemeint ist, sagt ``via``. Liegt das Ende
    auf dem Anfang, ist es die volle Ellipse, gegen den Uhrzeigersinn.
    """
    assert segment.ellipse is not None, "ein Ellipsenstück trägt seine Ellipse"
    frame = ellipse_frame(*segment.ellipse)
    if math.dist(segment.start, segment.end) <= _JOIN_TOL:
        return frame, 2.0 * math.pi
    start = frame.parameter(segment.start)
    sweep = parameter_sweep(start, frame.parameter(segment.end))
    if segment.via is None:
        return frame, sweep
    if parameter_sweep(start, frame.parameter(segment.via)) < sweep:
        return frame, sweep
    return frame, sweep - 2.0 * math.pi


def ellipse_segment_points(segment: ProfileSegment, sag: float) -> tuple[Point2, ...]:
    """Ein Ellipsenstück als Punktfolge vom Anfang zum Ende.

    Keine Sehne liegt weiter als ``sag`` neben der Kurve, und das ist keine
    Schätzung: Im Kreis der Ellipse liegt der Punkt eines Bogens, der am
    weitesten von seiner Sehne entfernt ist, auf halbem Parameterweg — und
    eine affine Abbildung erhält, wo eine Tangente parallel zur Sehne steht.
    Also wird dort gemessen und geteilt, bis die Grenze hält.

    Anfang und Ende sind **die** Punkte des Stücks, nicht ihre Projektion auf
    die Kurve: Der Nachbar in der Kette endet genau dort, und ein Rest von
    10⁻¹⁰ zwischen beiden wäre im Netz eine Kante ohne Länge.
    """
    frame, sweep = ellipse_turn(segment)
    start = frame.parameter(segment.start)
    end = frame.parameter(segment.end)
    full = abs(sweep) >= 2.0 * math.pi - _FULL_CIRCLE_EPS
    if full:
        parameters = _ccw_parameters(frame, start, start, sag, full=True)
    elif sweep > 0.0:
        parameters = _ccw_parameters(frame, start, end, sag, full=False)
    else:
        parameters = list(reversed(_ccw_parameters(frame, end, start, sag, full=False)))
    points = [frame.at(*parameter) for parameter in parameters]
    points[0] = segment.start
    points[-1] = segment.end if not full else segment.start
    return tuple(points)


def _ccw_parameters(
    frame: EllipseFrame, start: Point2, end: Point2, sag: float, *, full: bool
) -> list[Point2]:
    """Die Parameter gegen den Uhrzeigersinn von ``start`` bis ``end``,
    einschließlich beider, so fein, dass keine Sehne mehr als ``sag`` abweicht."""
    if full:
        stops = [start, (-start[1], start[0]), (-start[0], -start[1]), (start[1], -start[0]), start]
    else:
        middle = ccw_middle(start, end)
        stops = [start, ccw_middle(start, middle), middle, ccw_middle(middle, end), end]
    found = [stops[0]]
    for first, second in pairwise(stops):
        found.extend(_refined(frame, first, second, sag))
    return found


def _refined(frame: EllipseFrame, first: Point2, second: Point2, sag: float) -> list[Point2]:
    """Die Teilpunkte zwischen zwei Parametern unter einem Viertelumlauf, ohne
    den ersten und mit dem letzten."""
    found: list[Point2] = []
    pending = [(first, second, 0)]
    while pending:
        begin, end, depth = pending.pop()
        sx, sy = begin[0] + end[0], begin[1] + end[1]
        size = math.hypot(sx, sy)
        middle = (sx / size, sy / size) if size > _TINY_PARAMETER else (-begin[1], begin[0])
        wide = begin[0] * end[0] + begin[1] * end[1] < _WIDEST_STEP
        if depth < _DEEPEST_SPLIT and (wide or _chord_gap(frame, begin, middle, end) > sag):
            pending.append((middle, end, depth + 1))
            pending.append((begin, middle, depth + 1))
            continue
        found.append(end)
    return found


def _chord_gap(frame: EllipseFrame, begin: Point2, middle: Point2, end: Point2) -> float:
    """Wie weit die Kurve zwischen zwei Parametern von ihrer Sehne abweicht —
    gemessen am Punkt auf halbem Parameterweg, dem weitesten (siehe
    :func:`ellipse_segment_points`)."""
    ax, ay = frame.at(*begin)
    bx, by = frame.at(*end)
    mx, my = frame.at(*middle)
    span = math.hypot(bx - ax, by - ay)
    if span <= _TINY_PARAMETER:
        return math.hypot(mx - ax, my - ay)
    return abs((bx - ax) * (my - ay) - (by - ay) * (mx - ax)) / span


def ellipse_segment_extremes(segment: ProfileSegment) -> list[Point2]:
    """Die Scheitel in x- und y-Richtung, die das Ellipsenstück überstreicht.

    An einer gedrehten Ellipse liegen sie weder auf ihren Achsenenden noch auf
    Anfang oder Ende. ``x(t)`` hat seine Extrema, wo ``(cos t, sin t)`` in
    Richtung ``(a·uₓ, -b·u_y)`` zeigt, ``y(t)`` bei ``(a·u_y, b·uₓ)`` — je in
    beide Richtungen, und genommen werden die, die im Bereich des Stücks
    liegen.
    """
    frame, sweep = ellipse_turn(segment)
    ux, uy = frame.axis
    first, second = frame.first, frame.second
    candidates: list[Point2] = []
    for x, y in ((first * ux, -second * uy), (first * uy, second * ux)):
        size = math.hypot(x, y)
        if size <= _TINY_PARAMETER:
            continue
        candidates.extend(((x / size, y / size), (-x / size, -y / size)))
    if abs(sweep) >= 2.0 * math.pi - _FULL_CIRCLE_EPS:
        return [frame.at(*candidate) for candidate in candidates]
    low = frame.parameter(segment.start if sweep > 0.0 else segment.end)
    reach = abs(sweep)
    return [
        frame.at(*candidate)
        for candidate in candidates
        if parameter_sweep(low, candidate) <= reach or _same_parameter(low, candidate)
    ]


def ellipse_element_extremes(element: SketchElement) -> list[Point2]:
    """Die Scheitel in x und y einer Ellipse oder eines Ellipsenbogens der
    Zeichnung, beim Bogen samt seinen Enden — für Hüllen, die die ganze Kurve
    meinen (Strecken um die Mitte, Einpassen, Bauraumprüfung)."""
    segment = _segment(element.kind, element.points)
    ends = [segment.start, segment.end] if element.kind == "elliptical_arc" else []
    return [*ends, *ellipse_segment_extremes(segment)]


def arc_segment_extremes(segment: ProfileSegment) -> list[Point2]:
    """Die Scheitel in x- und y-Richtung, die ein Kreisbogenstück überstreicht.

    Ein Bogenstück führt Anfang, Ende und Stützpunkt, aber nicht seine Mitte —
    sie ist der Umkreismittelpunkt der drei. Ein Bogen über mehr als einen
    Viertelkreis reicht mit einem Scheitel weiter als seine drei Punkte; die
    Achsprüfung beim Drehen sah deshalb einen 340°-Bogen nicht, dessen linker
    Scheitel über der Achse lag (RM-188 P6.6, dieselbe Lücke wie beim Spline,
    Gesamtreview D-3). Welche Richtung das Stück läuft, sagt der Stützpunkt;
    ``atan2`` entscheidet hier nur, gerechnet wird kein Punkt damit.
    """
    if segment.via is None:
        return []
    (ax, ay), (bx, by), (cx, cy) = segment.start, segment.via, segment.end
    twice = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(twice) <= _TINY_PARAMETER:
        return []
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / twice
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / twice
    radius = math.hypot(ax - ux, ay - uy)
    turn = 2.0 * math.pi

    def angle(point: Point2) -> float:
        return exact_atan2(point[1] - uy, point[0] - ux)

    begin = angle(segment.start)
    reach = (angle(segment.end) - begin) % turn
    whole = math.dist(segment.start, segment.end) <= _JOIN_TOL
    counter_clockwise = whole or (angle(segment.via) - begin) % turn <= reach
    found: list[Point2] = []
    for quarter, (dx, dy) in enumerate(((1.0, 0.0), (0.0, 1.0), (-1.0, 0.0), (0.0, -1.0))):
        swept = (quarter * math.pi / 2.0 - begin) % turn
        inside = whole or (swept <= reach if counter_clockwise else swept >= reach)
        if inside:
            found.append((ux + radius * dx, uy + radius * dy))
    return found


def _same_parameter(one: Point2, other: Point2) -> bool:
    return math.hypot(one[0] - other[0], one[1] - other[1]) <= _FULL_CIRCLE_EPS


def _ellipses_share_a_stretch(first: ProfileSegment, second: ProfileSegment) -> bool:
    """Ob zwei Ellipsenstücke, die OpenCASCADE als deckungsgleich meldet, eine
    Länge teilen — die Frage aus :func:`_share_a_stretch` für Ellipsen.

    Zwei Stücke **einer** Ellipse, die nur an einem Ende aneinanderstoßen,
    teilen nichts: dieselbe Naht wie beim geteilten Kreis (B37 der
    Skizzendurchsicht). Geteilt ist erst, was über ``EPS_GEOM`` lang ist,
    gemessen an der kleineren Halbachse — das unterschätzt die Länge und
    meldet im Zweifel eine Kreuzung.
    """
    one, one_sweep = ellipse_turn(first)
    other, other_sweep = ellipse_turn(second)
    probes = [other.at(1.0, 0.0), other.at(0.0, 1.0), other.at(-1.0, 0.0), other.at(0.0, -1.0)]
    if math.dist(one.centre, other.centre) > _JOIN_TOL or any(
        math.dist(point, one.at(*one.parameter(point))) > _JOIN_TOL for point in probes
    ):
        return True

    def interval(segment: ProfileSegment, sweep: float) -> tuple[float, float]:
        begin = segment.start if sweep > 0.0 else segment.end
        cos, sin = one.parameter(begin)
        return exact_atan2(sin, cos), abs(sweep)

    low, span = interval(first, one_sweep)
    other_low, other_span = interval(second, other_sweep)
    shift = (other_low - low) % (2.0 * math.pi)
    shared = 0.0
    for start in (low + shift, low + shift - 2.0 * math.pi):
        shared += max(0.0, min(low + span, start + other_span) - max(low, start))
    return shared * min(one.first, one.second) > EPS_GEOM


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
    # ``acos`` als ``atan2(√((1 - y)(1 + y)), y)`` über ``exact_atan2``: Die
    # Schrittzahl entscheidet über die Ecken, ``math.acos`` rundet je Maschine
    # anders (RM-187).
    cosine = max(-1.0, 1.0 - CHORD_ERROR / radius)
    step = 2.0 * exact_atan2(math.sqrt((1.0 - cosine) * (1.0 + cosine)), cosine)
    if step <= EPS_GEOM:
        return _MOST_STEPS
    return max(_LEAST_STEPS, min(_MOST_STEPS, math.ceil(abs(sweep) / step)))


def _along_arc(centre: Point2, start: Point2, sweep: float, radius: float) -> tuple[Point2, ...]:
    """Die Punkte eines Bogens, von ``start`` aus um ``sweep`` gedreht."""
    begin = exact_atan2(start[1] - centre[1], start[0] - centre[0])
    steps = _steps_for(radius, sweep)
    return points_on_circle(
        centre, radius, [begin + sweep * index / steps for index in range(steps + 1)]
    )


def points_on_circle(centre: Point2, radius: float, angles: list[float]) -> tuple[Point2, ...]:
    """Die Punkte eines Kreises zu diesen Winkeln — plattformgleich, als ein Feld gerechnet.

    :func:`~app.core.geom.mesh.periodic_sin_cos` statt ``exact_cos`` und
    ``exact_sin`` je Punkt (RM-187): Die rechnen in ``decimal``, und die
    Skizzenvorschau baut einen wachsenden Kreis bei jeder Mausbewegung neu —
    mit bis zu :data:`_MOST_STEPS` Punkten fiel sie dabei unter die Bildrate.
    Eine Quelle für Skizze und extrudierten Körper
    (``geom.sketch_solid``): Beide Bögen tragen dieselben Ecken.
    """
    from app.core.geom.mesh import periodic_sin_cos

    sines, cosines = periodic_sin_cos(angles)
    return tuple(
        (centre[0] + radius * cosine, centre[1] + radius * sine)
        for cosine, sine in zip(cosines.tolist(), sines.tolist(), strict=True)
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
        # Dieselbe Antwort wie in ``_arc_midpoint`` — zwei Zahlen für die
        # Frage „ist das ein Vollkreis?" hießen: Der Viewport zeichnete einen
        # Kreis, in den Kern ging ein Bogen ohne Ausdehnung.
        return _along_arc(centre, start, arc_sweep(centre, start, end), radius)
    if element.kind == "spline":
        return _along_spline(points)
    if element.kind in ("ellipse", "elliptical_arc"):
        # Dieselbe Abtastung wie im Netzweg, nur mit der Sehnengrenze der
        # Ansicht — und wie beim Kreis trägt die volle Ellipse ihren ersten
        # Punkt am Ende noch einmal.
        return ellipse_segment_points(_segment(element.kind, points), CHORD_ERROR)
    return (points[0],)


def spline_controls(points: tuple[Point2, ...]) -> tuple[tuple[Point2, ...], ...]:
    """Kubische Bézier-Kontrollpunkte der gemeinsamen Catmull-Rom-Kurve."""
    pieces = []
    for index in range(len(points) - 1):
        before = points[max(index - 1, 0)]
        first, second = points[index], points[index + 1]
        after = points[min(index + 2, len(points) - 1)]
        one = (first[0] + (second[0] - before[0]) / 6.0, first[1] + (second[1] - before[1]) / 6.0)
        two = (second[0] - (after[0] - first[0]) / 6.0, second[1] - (after[1] - first[1]) / 6.0)
        pieces.append((first, one, two, second))
    return tuple(pieces)


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
    for first, one, two, second in spline_controls(points):
        for step in range(1, per_piece + 1):
            share = step / per_piece
            rest = 1.0 - share
            curve.append(
                (
                    rest * rest * rest * first[0]
                    + 3.0 * rest * rest * share * one[0]
                    + 3.0 * rest * share * share * two[0]
                    + share * share * share * second[0],
                    rest * rest * rest * first[1]
                    + 3.0 * rest * rest * share * one[1]
                    + 3.0 * rest * share * share * two[1]
                    + share * share * share * second[1],
                )
            )
    return tuple(curve)


def flat_curve(element: SketchElement) -> tuple[Point2, ...]:
    """Ein Element als Punktfolge in der Zeichenebene — dieselbe, die
    :func:`curves_of` in die Ansicht legt. Für die Zeichenfläche des Editors,
    die daran trifft und zeichnet: eine Kurve, eine Punktfolge."""
    return _flat_curve(element)


def curves_of(solved: SolvedSketch, frame: PlaneFrame) -> tuple[SketchCurve, ...]:
    """Die gelöste Skizze als Punktfolgen im Raum, in Reihenfolge der Elemente.

    Der Weg von der Zeichnung in die Ansicht (§30.1, Stufe zwei): Jedes
    Element wird in der Ebene abgetastet und über
    :func:`app.core.sketch.planes.to_world` an seinen Ort gelegt.

    **Ohne Qt und ohne Renderer**, und das ist der Zweck. Offscreen gibt es
    keinen, und was hinter dieser Wache gerechnet wird, prüft in der Suite
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
        if segment.kind == "ellipse":
            # Anders als beim Bogen **genau**: Eine Ellipse ist neu, es gibt
            # keine gespeicherte Form, deren Lage sich dadurch verschöbe, und
            # die Scheitel einer gedrehten Ellipse liegen weit neben ihren
            # drei Punkten.
            corners.extend(ellipse_segment_extremes(segment))
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
                ellipse=None
                if segment.ellipse is None
                else (
                    moved(segment.ellipse[0]),
                    moved(segment.ellipse[1]),
                    moved(segment.ellipse[2]),
                ),
            )
            for segment in profile.segments
        ),
        holes=tuple(scaled(one, factor, centre) for one in profile.holes),
    )
