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
        if sweep <= EPS_GEOM:
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
