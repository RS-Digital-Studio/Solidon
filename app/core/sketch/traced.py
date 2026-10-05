"""Ein Sehnenzug wird Strecken, Bögen und Kreise (Nachbau, Bauplan §42).

Ein Schnitt durch ein Dreiecksnetz ist ein Vieleck: Eine Bohrung kommt als
Folge kurzer Strecken heraus, eine gerade Kante als viele Stücke auf einer
Geraden. Der Nachbau braucht daraus eine Skizze, die ein Mensch bearbeiten
kann — eine Strecke je Kante, einen Bogen je Rundung, einen Kreis je Bohrung.

Zuerst fallen Punkte weg, die auf der Geraden ihrer Nachbarn liegen: Eine
Ebene quer durch einen facettierten Zylinder trifft auch die Diagonalen der
Vierecke, und diese Punkte liegen auf der Sehne, nicht auf dem Kreis. Dann
wird der Zug von seiner schärfsten Ecke aus gierig geteilt: so weit wie
möglich als Strecke oder als Bogen, das längere Stück gewinnt, bei Gleichstand
die Strecke. **Ein Bogen braucht mindestens drei Sehnen, jede mit höchstens
``MAX_ARC_STEP`` Grad Drehung in derselben Richtung** — ein Sechseck bleibt
sechs Strecken, obwohl seine Ecken auf einem Kreis liegen.

Plattformgleich (``.claude/rules/kern.md``): Der Kreis ist eine algebraische
Einpassung über ``math.fsum`` und die Cramersche Regel, Drehungen werden über
Skalar- und Kreuzprodukte gegen ``exact_cos_degrees`` verglichen, nie über
Winkel.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise
from typing import Any, Final

import numpy as np

from app.core.types import Point2, SketchElement
from app.core.units import EPS_GEOM, exact_cos_degrees, exact_sin_degrees

#: Wie weit eine Sehne eines Bogens höchstens dreht (Grad). Facettierte
#: Rundungen aus CAD-Programmen drehen je Sehne 3 bis 20 Grad; ein Achteck mit
#: 45 Grad bleibt Strecken.
MAX_ARC_STEP: Final = 30.0

#: Wie viele Sehnen ein Bogen mindestens hat — zwei Strecken mit einem Knick
#: sind eine Ecke, kein Bogen.
MIN_ARC_CHORDS: Final = 3

#: Bis zu welchem Winkel (Grad) ein Bogen an einer Strecke als tangential
#: gilt. Eine eingepasste Rundung liegt um Hundertstelgrad neben ihrer
#: Tangente, eine Ecke daneben um Grade.
NEAR_TANGENT: Final = 1.0


def traced_loop(
    points: Sequence[Point2],
    tolerance: float,
    *,
    sag: float | None = None,
    shortest: float = 0.0,
) -> tuple[SketchElement, ...]:
    """Ein geschlossener Zug als Strecken, Bögen oder ein Kreis.

    ``points`` läuft einmal herum, ohne den Anfang am Ende zu wiederholen.
    ``tolerance`` ist, wie weit ein Punkt des Zugs neben der Strecke oder dem
    Kreis liegen darf, der ihn ersetzt; ``sag`` (ohne Angabe ``tolerance``),
    wie weit der Bogen zwischen zwei Punkten von ihrer Sehne abstehen darf —
    die Facetten einer Rundung liegen um ihre Sehnenhöhe innerhalb des
    Kreises. Jeder Bogen hat gleich lange Schenkel (seine Mitte liegt auf der
    Mittelsenkrechten seiner Enden), und benachbarte Elemente teilen ihre
    Endpunkte genau. **Eine gerade Kante kippt nicht**: Eine Strecke nimmt
    keinen Punkt einer Rundung dazu, der sie um Hundertstel von der Kante
    dreht (:func:`_exact_part`) — am Besenhalter deckte die gekippte Wand
    sonst die Senkbohrung darin mit einer Haut zu. Eine Strecke unter
    ``shortest`` zieht sich zu einem Punkt zusammen (:func:`_without_short`):
    Am Besenhalter stand eine Strecke von 0,017 mm neben einem Bogen, und die
    Fläche daran bekam vom Kern keine dichte Vernetzung.
    """
    bulge = tolerance if sag is None else sag
    ring = _without_straight(_distinct(points))
    if len(ring) < 3:
        return ()
    straight = _straightness(ring)
    whole = _fitted_circle([*ring, ring[0]], tolerance, bulge)
    if whole is not None and _steady(_turns([ring[-1], *ring, ring[0]])):
        centre, radius = whole
        return (SketchElement("circle", (centre, (centre[0] + radius, centre[1]))),)
    start = _sharpest(ring)
    ring = ring[start:] + ring[:start]
    walk, pieces = _split(ring, tolerance, bulge, straight)
    if len(pieces) > 1:
        # Ohne scharfe Ecke beginnt der Zug mitten in einer Rundung, und ihr
        # Rest am Ende ist zu kurz für einen Bogen. Der zweite Durchgang
        # beginnt am Ende des längsten Stücks: Es ließ sich nicht weiter
        # ziehen, dort ist also ein echter Übergang.
        longest = max(pieces, key=lambda piece: (piece[1] - piece[0], -piece[0]))
        start = longest[1] % len(ring)
        ring = ring[start:] + ring[:start]
        walk, pieces = _split(ring, tolerance, bulge, straight)
    pieces = _closed_around(walk, pieces, tolerance, bulge, straight)
    count = len(walk) - 1
    spans = [
        [walk[first % count], walk[last % count], walk[((first + last) // 2) % count], circle]
        for first, last, circle in pieces
    ]
    return tuple(
        _between(start, end, middle, circle)
        for start, end, middle, circle in _tangent(_without_short(spans, shortest), tolerance)
    )


def _tangent(spans: list[list[Any]], tolerance: float) -> list[list[Any]]:
    """Ein Bogen, der fast tangential aus einer Strecke kommt, kommt genau tangential.

    Die eingepasste Mitte liegt um Rundungsrauschen neben der Normalen der
    Strecke; der Kreis taucht dann neben dem gemeinsamen Punkt um Bruchteile
    eines Mikrometers über die Strecke, und die Skizze kreuzt sich selbst. Am
    Besenhalter waren es 0,4 µm an einem Zwickel neben einer Bohrung. Die
    Mitte rückt auf der Mittelsenkrechten der Bogenenden bis auf die Normale —
    nur wenn der Übergang fast tangential ist (``NEAR_TANGENT``) und die Mitte
    dabei höchstens ``tolerance`` wandert.
    """
    limit = exact_sin_degrees(NEAR_TANGENT)
    count = len(spans)
    for index, (start, end, _middle, circle) in enumerate(spans):
        if circle is None:
            continue
        centre = on_bisector(circle[0], start, end)
        before, after = spans[index - 1], spans[(index + 1) % count]
        for line, junction in ((before, start), (after, end)):
            if line[3] is not None:
                continue
            direction = (line[1][0] - line[0][0], line[1][1] - line[0][1])
            length = math.hypot(*direction)
            leg = math.dist(centre, junction)
            if length <= EPS_GEOM or leg <= EPS_GEOM:
                continue
            unit = (direction[0] / length, direction[1] / length)
            offset = (centre[0] - junction[0]) * unit[0] + (centre[1] - junction[1]) * unit[1]
            if abs(offset) > limit * leg:
                continue
            across = (start[1] - end[1], end[0] - start[0])
            span = math.hypot(*across)
            if span <= EPS_GEOM:
                continue
            bisector = (across[0] / span, across[1] / span)
            facing = bisector[0] * unit[0] + bisector[1] * unit[1]
            if abs(facing) <= EPS_GEOM:
                continue
            shift = -offset / facing
            if abs(shift) > tolerance:
                continue
            centre = (centre[0] + bisector[0] * shift, centre[1] + bisector[1] * shift)
            break
        spans[index][3] = (centre, math.dist(centre, start))
    return spans


def _without_short(spans: list[list[Any]], shortest: float) -> list[list[Any]]:
    """Ohne Strecken unter ``shortest``: Ihre Nachbarn treffen sich an ihrer Stelle.

    Wo sie sich treffen, entscheidet, was kippen darf. Zwei Strecken treffen
    sich in ihrem Schnittpunkt, wenn er nahe liegt — so behalten beide ihre
    Richtung. Neben einem Bogen bleibt die Strecke, wo sie ist, und der Bogen
    rückt (``_between`` setzt seine Mitte neu); zwei Bögen treffen sich in der
    Mitte des Stücks.
    """
    while len(spans) > 3:
        short = next(
            (
                index
                for index, (start, end, _middle, circle) in enumerate(spans)
                if circle is None and math.dist(start, end) < shortest
            ),
            None,
        )
        if short is None:
            break
        before, after = spans[short - 1], spans[(short + 1) % len(spans)]
        start, end = spans[short][0], spans[short][1]
        middle = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        if before[3] is None and after[3] is None:
            meeting = _crossing(before[0], before[1], after[0], after[1])
            if meeting is None or math.dist(meeting, middle) > shortest:
                longer = math.dist(before[0], before[1]) >= math.dist(after[0], after[1])
                meeting = start if longer else end
        elif before[3] is None:
            meeting = start
        elif after[3] is None:
            meeting = end
        else:
            meeting = middle
        before[1] = meeting
        after[0] = meeting
        del spans[short]
    return spans


def _crossing(a: Point2, b: Point2, c: Point2, d: Point2) -> Point2 | None:
    """Der Schnittpunkt der Geraden durch ``a``, ``b`` und durch ``c``, ``d`` — oder ``None``."""
    first = (b[0] - a[0], b[1] - a[1])
    second = (d[0] - c[0], d[1] - c[1])
    cross = first[0] * second[1] - first[1] * second[0]
    if abs(cross) <= EPS_GEOM * math.hypot(*first) * math.hypot(*second):
        return None
    reach = ((c[0] - a[0]) * second[1] - (c[1] - a[1]) * second[0]) / cross
    return (a[0] + first[0] * reach, a[1] + first[1] * reach)


def _split(
    ring: list[Point2], tolerance: float, sag: float, straight: float
) -> tuple[list[Point2], list[tuple[int, int, tuple[Point2, float] | None]]]:
    """Der Zug ab seinem ersten Punkt gierig geteilt: je Stück das längere aus Strecke und Bogen."""
    count = len(ring)
    walk = [*ring, ring[0]]
    turns = _turns([*ring[-1:], *walk, *ring[1:2]])
    pieces: list[tuple[int, int, tuple[Point2, float] | None]] = []
    index = 0
    while index < count:
        line = _longest_line(walk, index, tolerance)
        first, last = _exact_part(walk[index : line + 1], straight)
        line = index + last
        arc, circle = _longest_arc(walk, turns, index, tolerance, sag)
        if circle is not None and arc > line:
            pieces.append((index, arc, circle))
            index = arc
            continue
        if first > 0:
            pieces.append((index, index + first, None))
        pieces.append((index + first, line, None))
        index = line
    return walk, pieces


def _exact_part(run: Sequence[Point2], straight: float) -> tuple[int, int]:
    """Welcher Teil eines Streckenzugs die Strecke trägt: erste und letzte Ecke.

    Eine Strecke darf um ``tolerance`` neben ihren Punkten liegen — das ist
    für die Sehnen einer Freiformkurve gedacht. Läuft sie aber über eine
    gerade Kante und nimmt am Ende noch einen Punkt der Rundung dahinter
    mit, kippt die ganze Kante um bis zu ``tolerance``. Liegt der Zug bis zu
    einer Ecke auf seiner Geraden (``straight``, die Auflösung der Datei) und
    ist dieser Teil länger als der Rest, endet die Strecke dort; dasselbe vom
    anderen Ende her. Sonst trägt sie den ganzen Zug.
    """
    last = len(run) - 1
    head = 1
    while head < last and all(
        _off_line(run[0], run[inner], run[head + 1]) <= straight for inner in range(1, head + 1)
    ):
        head += 1
    if head < last and math.dist(run[0], run[head]) > math.dist(run[head], run[last]):
        return 0, head
    tail = last - 1
    while tail > 0 and all(
        _off_line(run[tail - 1], run[inner], run[last]) <= straight for inner in range(tail, last)
    ):
        tail -= 1
    if tail > 0 and math.dist(run[tail], run[last]) > math.dist(run[0], run[tail]):
        return tail, last
    return 0, last


def on_bisector(centre: Point2, start: Point2, end: Point2) -> Point2:
    """Der Punkt der Mittelsenkrechten von ``start`` und ``end`` nächst ``centre``.

    So bleibt ein Bogen ein Bogen, wenn seine Enden rücken: Mit festen
    Punkten und ungleich langen Schenkeln weist der Löser die Skizze als
    Widerspruch ab.
    """
    middle = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
    across = (start[1] - end[1], end[0] - start[0])
    length = math.hypot(*across)
    if length <= EPS_GEOM:
        return centre
    unit = (across[0] / length, across[1] / length)
    reach = (centre[0] - middle[0]) * unit[0] + (centre[1] - middle[1]) * unit[1]
    return (middle[0] + unit[0] * reach, middle[1] + unit[1] * reach)


def _distinct(points: Sequence[Point2]) -> list[Point2]:
    """Ohne doppelte Nachbarn, auch nicht zwischen Ende und Anfang."""
    kept: list[Point2] = []
    for point in points:
        flat = (float(point[0]), float(point[1]))
        if not kept or math.dist(flat, kept[-1]) > EPS_GEOM:
            kept.append(flat)
    while len(kept) > 1 and math.dist(kept[0], kept[-1]) <= EPS_GEOM:
        kept.pop()
    return kept


def _straightness(points: Sequence[Point2]) -> float:
    """Ab wann ein Punkt neben der Geraden seiner Nachbarn liegt — die Auflösung der Datei.

    Ein Netz aus STL steht in einfacher Genauigkeit; Punkte einer schrägen
    Geraden liegen um einige Millionstel daneben. Dieselbe Schwelle wie die
    Projektion in die Skizze (``sketch.edit._straight_enough``).
    """
    reach = max((max(abs(point[0]), abs(point[1])) for point in points), default=0.0)
    return max(EPS_GEOM, 4.0 * float(np.spacing(np.float32(reach))))


def _without_straight(ring: list[Point2]) -> list[Point2]:
    """Ohne die Punkte, die auf der Geraden ihrer beiden Nachbarn liegen."""
    if len(ring) < 4:
        return ring
    straight = _straightness(ring)
    kept = list(ring)
    changed = True
    while changed and len(kept) > 3:
        changed = False
        result: list[Point2] = []
        count = len(kept)
        for index, point in enumerate(kept):
            before = result[-1] if result else kept[index - 1]
            after = kept[(index + 1) % count]
            if _off_line(before, point, after) <= straight and _between_points(
                before, point, after
            ):
                changed = True
                continue
            result.append(point)
        kept = result if len(result) >= 3 else kept
    return kept


def _between_points(start: Point2, point: Point2, end: Point2) -> bool:
    """Ob ``point`` zwischen ``start`` und ``end`` liegt — eine Spitze ist keine Gerade."""
    return (point[0] - start[0]) * (end[0] - point[0]) + (point[1] - start[1]) * (
        end[1] - point[1]
    ) >= 0.0


def _off_line(start: Point2, point: Point2, end: Point2) -> float:
    """Wie weit ``point`` neben der Strecke von ``start`` nach ``end`` liegt."""
    span = math.dist(start, end)
    if span <= EPS_GEOM:
        return math.dist(start, point)
    return (
        abs(
            (end[0] - start[0]) * (point[1] - start[1])
            - (end[1] - start[1]) * (point[0] - start[0])
        )
        / span
    )


def _turns(points: Sequence[Point2]) -> list[tuple[float, float]]:
    """Je innerem Punkt: Kreuzprodukt und Kosinus der Drehung zwischen seinen Sehnen.

    ``points`` trägt vorn und hinten je einen Nachbarn mehr; das Ergebnis
    gehört zu ``points[1:-1]``.
    """
    turns = []
    for before, point, after in zip(points, points[1:], points[2:], strict=False):
        first = (point[0] - before[0], point[1] - before[1])
        second = (after[0] - point[0], after[1] - point[1])
        lengths = math.hypot(*first) * math.hypot(*second)
        if lengths <= EPS_GEOM * EPS_GEOM:
            turns.append((0.0, 1.0))
            continue
        cross = first[0] * second[1] - first[1] * second[0]
        dot = first[0] * second[0] + first[1] * second[1]
        turns.append((cross / lengths, dot / lengths))
    return turns


def _sharpest(ring: list[Point2]) -> int:
    """Der Punkt mit der schärfsten Drehung — dort beginnt kein Bogen."""
    turns = _turns([ring[-1], *ring, ring[0]])
    return min(range(len(ring)), key=lambda index: (turns[index][1], index))


def _steady(turns: Sequence[tuple[float, float]]) -> bool:
    """Ob jede Sehne höchstens ``MAX_ARC_STEP`` dreht, alle in dieselbe Richtung."""
    if not turns:
        return False
    least = exact_cos_degrees(MAX_ARC_STEP)
    sign = 1.0 if turns[0][0] > 0.0 else -1.0
    return all(cosine >= least and cross * sign > 0.0 for cross, cosine in turns)


def _longest_line(walk: list[Point2], start: int, tolerance: float) -> int:
    """Das letzte Ende, bis zu dem eine Strecke ab ``start`` alle Punkte trägt."""
    end = start + 1
    while end + 1 < len(walk) and all(
        _off_line(walk[start], walk[inner], walk[end + 1]) <= tolerance
        for inner in range(start + 1, end + 1)
    ):
        end += 1
    return end


def _longest_arc(
    walk: list[Point2],
    turns: list[tuple[float, float]],
    start: int,
    tolerance: float,
    sag: float,
) -> tuple[int, tuple[Point2, float] | None]:
    """Das letzte Ende, bis zu dem ein Kreis ab ``start`` alle Punkte trägt.

    ``turns[k]`` gehört zu ``walk[k]``. Wächst erst in Verdopplungen, dann
    halbierend — eine Einpassung kostet einen Durchgang über das Stück.
    """
    last = len(walk) - 1

    def holds(end: int) -> tuple[Point2, float] | None:
        if end > last or not _steady(turns[start + 1 : end]):
            return None
        return _fitted_circle(walk[start : end + 1], tolerance, sag)

    shortest = start + MIN_ARC_CHORDS
    best = holds(shortest)
    if best is None:
        return start, None
    good, step = shortest, 1
    while True:
        trial = min(good + step, last)
        if trial == good:
            break
        circle = holds(trial)
        if circle is None:
            break
        good, best, step = trial, circle, step * 2
    bad = min(good + step, last + 1)
    while bad - good > 1:
        middle = (good + bad) // 2
        circle = holds(middle)
        if circle is None:
            bad = middle
        else:
            good, best = middle, circle
    return good, best


def _fitted_circle(
    points: Sequence[Point2], tolerance: float, sag: float
) -> tuple[Point2, float] | None:
    """Der Kreis, der alle Punkte innerhalb ``tolerance`` trägt — sonst ``None``.

    Algebraische Einpassung (Kåsa) um den Schwerpunkt, gelöst mit der
    Cramerschen Regel über ``math.fsum``: ohne LAPACK, auf jeder Maschine
    dieselben Bits. **Die Punkte allein beweisen keinen Bogen**: Am
    Besenhalter lag eine 67 mm lange gerade Kante zwischen zwei kleinen
    Rundungen, und ein Kreis mit 226 mm Radius ging durch alle Punkte — und
    stand 2,5 mm neben der Kante. Deshalb darf keine Sehne zwischen zwei
    Folgepunkten weiter als ``sag`` vom Kreis abstehen.
    """
    count = len(points)
    if count < 3:
        return None
    mean_x = math.fsum(point[0] for point in points) / count
    mean_y = math.fsum(point[1] for point in points) / count
    shifted = [(point[0] - mean_x, point[1] - mean_y) for point in points]
    squares = [u * u + v * v for u, v in shifted]
    uu = math.fsum(u * u for u, _v in shifted)
    vv = math.fsum(v * v for _u, v in shifted)
    uv = math.fsum(u * v for u, v in shifted)
    uz = math.fsum(u * z for (u, _v), z in zip(shifted, squares, strict=True))
    vz = math.fsum(v * z for (_u, v), z in zip(shifted, squares, strict=True))
    determinant = uu * vv - uv * uv
    if abs(determinant) <= EPS_GEOM * max(uu * vv, EPS_GEOM):
        return None
    first = (-uz * vv + vz * uv) / determinant
    second = (-vz * uu + uz * uv) / determinant
    mean_square = math.fsum(squares) / count
    radius_square = (first * first + second * second) / 4.0 + mean_square
    if radius_square <= EPS_GEOM * EPS_GEOM:
        return None
    centre = (mean_x - first / 2.0, mean_y - second / 2.0)
    radius = math.sqrt(radius_square)
    if any(abs(math.dist(point, centre) - radius) > tolerance for point in points):
        return None
    for before, after in pairwise(points):
        half = math.dist(before, after) / 2.0
        if (
            half >= radius
            or half * half / (radius + math.sqrt(radius * radius - half * half)) > sag
        ):
            return None
    return centre, radius


def _closed_around(
    walk: list[Point2],
    pieces: list[tuple[int, int, tuple[Point2, float] | None]],
    tolerance: float,
    sag: float,
    straight: float,
) -> list[tuple[int, int, tuple[Point2, float] | None]]:
    """Läuft der Zug ohne Ecke durch seinen Anfang, werden erstes und letztes Stück eins."""
    if len(pieces) < 2:
        return pieces
    first, last = pieces[0], pieces[-1]
    if (first[2] is None) != (last[2] is None):
        return pieces
    count = len(walk) - 1
    joined = [*walk[last[0] : count], *walk[: first[1] + 1]]
    if first[2] is None:
        if all(
            _off_line(joined[0], point, joined[-1]) <= tolerance for point in joined[1:-1]
        ) and _exact_part(joined, straight) == (0, len(joined) - 1):
            return [(last[0], count + first[1], None), *pieces[1:-1]]
        return pieces
    turns = _turns(joined)
    circle = _fitted_circle(joined, tolerance, sag)
    if circle is None or not _steady(turns):
        return pieces
    return [(last[0], count + first[1], circle), *pieces[1:-1]]


def _between(
    start: Point2, end: Point2, middle: Point2, circle: tuple[Point2, float] | None
) -> SketchElement:
    """Die Strecke oder der Bogen von ``start`` nach ``end`` über ``middle``."""
    if circle is None:
        return SketchElement("line", (start, end))
    centre = on_bisector(circle[0], start, end)
    # Gegen den Uhrzeigersinn um die Mitte liegt die Bogenmitte rechts der
    # Sehne. Der Löser liest einen Bogen so herum; läuft der Zug andersherum,
    # tauschen Anfang und Ende.
    counter_clockwise = (middle[0] - start[0]) * (end[1] - start[1]) - (middle[1] - start[1]) * (
        end[0] - start[0]
    ) > 0.0
    return SketchElement("arc", (centre, start, end) if counter_clockwise else (centre, end, start))
