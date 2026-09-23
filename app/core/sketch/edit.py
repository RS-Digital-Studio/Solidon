"""Skizzen ändern: Trimmen, Verlängern, Versetzen, Spiegeln, Verrunden, Fase
(Bauplan §30.1).

Die Werkzeuge, ohne die jede Kontur Handarbeit ist, die nicht aus einer
Grundform kommt. Fusion hat sie in einer eigenen Gruppe; Solidon hatte sie
gar nicht — man konnte zeichnen und bemaßen, aber nichts kürzen. Verrunden
und Fase kamen am 13.09.2026 dazu (Robert: „schräge kanten kann man auch
nicht machen"): Beide brechen eine Ecke aus zwei Linien, das eine mit einem
tangentialen Bogen, das andere mit einer Schräge.

**Hier und nicht in der Oberfläche.** Jede dieser Handlungen rechnet
Schnittpunkte und Abstände; das ist Geometrie, und Geometrie rechnet der Kern
(Regel 2 dem Geist nach — der Editor erzeugt am Ende einen Skizzentext, den
eine Op verbraucht, und dieser Text muss überall derselbe sein).

Die Bedingungen reisen mit, soweit sie können. Ein getrimmtes Element behält
seine Bedingungen; ein weggefallenes nimmt sie mit — dieselbe Regel wie beim
Löschen, denn eine Bedingung auf einem Punkt, den es nicht mehr gibt, ist
keine Bedingung mehr, sondern ein Absturz beim nächsten Lauf.
"""

from __future__ import annotations

import itertools
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

from app.core.errors import CANCEL, Action, ValidationError, require_positive
from app.core.sketch.planes import feature_plane_parts, standing_on_feature, to_plane
from app.core.sketch.profile import (
    _JOIN_TOL,
    _flat_curve,
    arc_sweep,
    ellipse_element_extremes,
    ellipse_frame,
    parameter_sweep,
)
from app.core.sketch.solver import CURVE_SLOTS, closest_on_spline
from app.core.types import (
    PlaneFrame,
    Point2,
    SceneObject,
    Sketch,
    SketchConstraint,
    SketchElement,
    Vec3,
)
from app.core.units import EPS_GEOM, MAX_FACET_SAG, PLANE_PARALLEL
from app.i18n import _

#: Wie nah zwei Punkte sein müssen, um als derselbe zu gelten. Keine Toleranz
#: im Sinne von Regel 7: das ist die Auflösung einer Zeichnung, keine Passung.
EPS_SKETCH = 1e-9

#: Wie weit ein Schnittpunkt außerhalb der Strecke liegen darf und trotzdem als
#: „auf ihr" gilt. In Anteilen der Streckenlänge.
_ON_SEGMENT = 1e-9

#: Unterhalb dieses Abstands sind zwei Treffer dieselbe Stelle — das Maß für
#: das Rechenrauschen zweier Teilstrecken, die sich einen Knoten teilen.
_SAME_SPOT = 1e-9


def flat_points(sketch: Sketch) -> list[Point2]:
    """Alle Punkte der Skizze in der Reihenfolge, die die Bedingungen zählen."""
    return [point for element in sketch.elements for point in element.points]


def offsets_of(sketch: Sketch) -> list[int]:
    """Der flache Index, an dem jedes Element beginnt."""
    result: list[int] = []
    total = 0
    for element in sketch.elements:
        result.append(total)
        total += len(element.points)
    return result


# --- Schnittpunkte ---------------------------------------------------------------


def line_intersection(first: tuple[Point2, Point2], second: tuple[Point2, Point2]) -> Point2 | None:
    """Wo zwei Geraden sich treffen, oder nichts, wenn sie parallel sind.

    Gerechnet wird auf den **Geraden**, nicht auf den Strecken: Verlängern
    braucht genau den Punkt außerhalb, und Trimmen prüft danach selbst, ob er
    auf der Strecke liegt.
    """
    (ax, ay), (bx, by) = first
    (cx, cy), (dx, dy) = second
    denominator = (bx - ax) * (dy - cy) - (by - ay) * (dx - cx)
    if abs(denominator) < EPS_SKETCH:
        return None
    t = ((cx - ax) * (dy - cy) - (cy - ay) * (dx - cx)) / denominator
    return (ax + t * (bx - ax), ay + t * (by - ay))


def circle_intersections(
    line: tuple[Point2, Point2], centre: Point2, radius: float
) -> list[Point2]:
    """Wo eine Gerade einen Kreis schneidet — keiner, einer oder zwei Punkte."""
    (ax, ay), (bx, by) = line
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared < EPS_SKETCH:
        return []
    fx, fy = ax - centre[0], ay - centre[1]
    b = 2.0 * (fx * dx + fy * dy)
    c = fx * fx + fy * fy - radius * radius
    discriminant = b * b - 4.0 * length_squared * c
    if discriminant < 0.0:
        return []
    root = math.sqrt(discriminant)
    return [
        (ax + t * dx, ay + t * dy)
        for t in ((-b - root) / (2.0 * length_squared), (-b + root) / (2.0 * length_squared))
    ]


def ellipse_intersections(line: tuple[Point2, Point2], element: SketchElement) -> list[Point2]:
    """Wo eine Gerade eine Ellipse oder einen Ellipsenbogen trifft — exakt.

    Im Kreis der Ellipse ist sie ein Einheitskreis: Die Gerade wird in dessen
    Rahmen gebracht (dieselbe affine Abbildung, mit der die Profilbildung
    rechnet, :class:`~app.core.sketch.profile.EllipseFrame`), dort mit
    :func:`circle_intersections` geschnitten und zurückgebracht — keine
    Sehnenkette, keine Winkelfunktion. Ein Ellipsenbogen behält nur, was
    gegen den Uhrzeigersinn zwischen seinem Anfang und seinem Ende liegt.
    """
    frame = ellipse_frame(*element.points[:3])
    if frame.first <= EPS_SKETCH or frame.second <= EPS_SKETCH:
        return []
    ux, uy = frame.axis

    def inside(point: Point2) -> Point2:
        dx, dy = point[0] - frame.centre[0], point[1] - frame.centre[1]
        return ((dx * ux + dy * uy) / frame.first, (-dx * uy + dy * ux) / frame.second)

    hits = circle_intersections((inside(line[0]), inside(line[1])), (0.0, 0.0), 1.0)
    parameters = [(x / size, y / size) for x, y in hits if (size := math.hypot(x, y)) > EPS_SKETCH]
    if element.kind == "elliptical_arc":
        start = frame.parameter(element.points[3])
        reach = parameter_sweep(start, frame.parameter(element.points[4]))
        parameters = [
            parameter
            for parameter in parameters
            if math.hypot(parameter[0] - start[0], parameter[1] - start[1]) <= EPS_SKETCH
            or parameter_sweep(start, parameter) <= reach + EPS_SKETCH
        ]
    return [frame.at(*parameter) for parameter in parameters]


def _parameter_on(line: tuple[Point2, Point2], point: Point2) -> float:
    """Wo auf der Strecke ein Punkt liegt: 0 am Anfang, 1 am Ende."""
    (ax, ay), (bx, by) = line
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared < EPS_SKETCH:
        return 0.0
    return ((point[0] - ax) * dx + (point[1] - ay) * dy) / length_squared


def crossings_on(sketch: Sketch, index: int) -> list[Point2]:
    """Alle Stellen, an denen andere Elemente diese Linie kreuzen.

    Sortiert nach ihrer Lage auf der Linie, und **nur auf der Strecke
    selbst**: Eine Kante jenseits des Linienendes machte aus dem Trimmen ein
    Verlängern — aus 0→10 mit einer Kante bei 30 wurde 30→10, ein Stück, das
    vollständig außerhalb des Originals liegt (Gesamtreview D-4). Nur für
    Linien — ein Bogen, den man trimmt, ist eine eigene Rechnung, und ihn
    hier stillschweigend zu übergehen wäre schlimmer, als ihn abzulehnen.

    Als **Schnittkante** zählt dagegen jede Art: Bogen und Spline schneiden
    über dieselbe Punktfolge, die auch das Profil rechnet — unsichtbar als
    Kante trimmten sie an der falschen Stelle, sobald zusätzlich eine Linie
    kreuzte (Gesamtreview D-10).
    """
    element = sketch.elements[index]
    if element.kind != "line":
        raise ValidationError(
            "element",
            _("Trimmen und Verlängern arbeiten an Linien — dieses Element ist eine andere Art."),
        )
    line = (element.points[0], element.points[1])

    return sorted(
        (
            point
            for point in _meetings(sketch, index, line)
            if -_ON_SEGMENT <= _parameter_on(line, point) <= 1.0 + _ON_SEGMENT
        ),
        key=lambda point: _parameter_on(line, point),
    )


def _meetings(sketch: Sketch, index: int, line: tuple[Point2, Point2]) -> list[Point2]:
    """Wo die **Gerade** dieser Linie andere Elemente trifft — jede Art.

    Die eine Schnittsuche für beide Werkzeuge: Auf dem anderen Element muss
    der Treffer liegen, auf der eigenen Strecke nicht — Trimmen filtert das
    hinterher, Verlängern braucht gerade die Treffer jenseits der Enden.
    Vorher hatte das Verlängern eine eigene Suche, und die sah nur Linien:
    ein Kreis oder Bogen als Ziel existierte nicht, während dasselbe Element
    beim Trimmen längst als Kante zählte.

    **Gleiche Stellen werden zusammengelegt.** Der Knoten einer Punktfolge
    gehört zwei Teilstrecken, und beide meldeten ihn — zwei Treffer im
    Abstand des Rechenrauschens, und ein Klick dazwischen machte beim
    Trimmen aus dem Nachbarpaar ein Nullstück.
    """
    found: list[Point2] = []
    for other_index, other in enumerate(sketch.elements):
        if other_index == index:
            continue
        if other.kind == "line":
            point = line_intersection(line, (other.points[0], other.points[1]))
            if (
                point is not None
                and -_ON_SEGMENT
                <= _parameter_on((other.points[0], other.points[1]), point)
                <= 1.0 + _ON_SEGMENT
            ):
                found.append(point)
        elif other.kind == "circle":
            centre = other.points[0]
            edge = other.points[1]
            radius = math.hypot(edge[0] - centre[0], edge[1] - centre[1])
            found.extend(circle_intersections(line, centre, radius))
        elif other.kind in ("ellipse", "elliptical_arc"):
            found.extend(ellipse_intersections(line, other))
        else:
            flat = _flat_curve(other)
            for begin, end in itertools.pairwise(flat):
                point = line_intersection(line, (begin, end))
                if (
                    point is not None
                    and -_ON_SEGMENT <= _parameter_on((begin, end), point) <= 1.0 + _ON_SEGMENT
                ):
                    found.append(point)

    unique: list[Point2] = []
    for point in found:
        if all(math.hypot(point[0] - kept[0], point[1] - kept[1]) > _SAME_SPOT for kept in unique):
            unique.append(point)
    return unique


# --- Die vier Werkzeuge ----------------------------------------------------------


def trim(sketch: Sketch, index: int, at: Point2) -> Sketch:
    """Kürzt eine Linie an der Kreuzung, die dem Klick am nächsten liegt.

    Weg ist das Stück, auf das geklickt wurde — genau wie in jedem CAD. Liegt
    der Klick jenseits aller Kreuzungen, fällt die ganze Linie weg; auch das
    ist die übliche Antwort, und sie ist rücknehmbar.

    Eine Ellipse und ein Ellipsenbogen werden ebenso getrimmt
    (:func:`_trimmed_ellipse`) — so entsteht ein Ellipsenbogen, wie in Fusion,
    das dafür kein eigenes Werkzeug hat.
    """
    element = sketch.elements[index]
    if element.kind in ELLIPSE_KINDS:
        return _trimmed_ellipse(sketch, index, at)
    line = (element.points[0], element.points[1])
    crossings = crossings_on(sketch, index)
    if not crossings:
        raise ValidationError(
            "element",
            _("Diese Linie kreuzt nichts — zum Trimmen braucht es eine Kante zum Kürzen."),
        )

    click = _parameter_on(line, at)
    before = [point for point in crossings if _parameter_on(line, point) < click]
    after = [point for point in crossings if _parameter_on(line, point) > click]

    # Zwischen zwei Kreuzungen geklickt, fällt das Stück dazwischen weg, und
    # aus einer Linie werden zwei. **Ein Stück ohne Länge ist keines:** Die
    # Enden einer Rechteckseite sind selbst Kreuzungen — der Nachbar setzt
    # dort an —, und ein Klick auf die Seite ließ zwei Linien der Länge null
    # stehen, deckungsgleich mit den Ecken, statt die Seite zu entfernen
    # (Durchsicht 22.09.2026). Jedes CAD nimmt dort die ganze Seite.
    pieces: list[tuple[Point2, Point2]] = []
    if before and math.dist(line[0], before[-1]) > _JOIN_TOL:
        pieces.append((line[0], before[-1]))
    if after and math.dist(after[0], line[1]) > _JOIN_TOL:
        pieces.append((after[0], line[1]))
    return _rebuilt_line(sketch, index, tuple(pieces))


def extend(sketch: Sketch, index: int, at: Point2) -> Sketch:
    """Verlängert eine Linie bis zur nächsten Kante in Klickrichtung.

    Geklickt wird auf die Hälfte, die wachsen soll — dieselbe Geste wie beim
    Trimmen, nur andersherum.
    """
    element = sketch.elements[index]
    if element.kind != "line":
        raise ValidationError(
            "element",
            _("Trimmen und Verlängern arbeiten an Linien — dieses Element ist eine andere Art."),
        )
    line = (element.points[0], element.points[1])
    reach = _meetings(sketch, index, line)
    if not reach:
        raise ValidationError(
            "element",
            _("In dieser Richtung liegt keine Kante, bis zu der verlängert werden könnte."),
        )

    towards_end = _parameter_on(line, at) >= 0.5
    candidates = [
        point
        for point in reach
        if (_parameter_on(line, point) > 1.0 if towards_end else _parameter_on(line, point) < 0.0)
    ]
    if not candidates:
        raise ValidationError(
            "element",
            _("In dieser Richtung liegt keine Kante — auf der anderen Hälfte gibt es eine."),
        )

    target = min(
        candidates, key=lambda point: abs(_parameter_on(line, point) - (1.0, 0.0)[not towards_end])
    )
    points = (line[0], target) if towards_end else (target, line[1])
    return _rebuilt_line(sketch, index, (points,))


def _ellipse_crossings(sketch: Sketch, index: int) -> list[Point2]:
    """Wo andere Elemente diese Ellipse schneiden — exakt gegen die Ellipse
    (:func:`ellipse_intersections`), die anderen als die Punktfolge, die auch
    das Profil rechnet; eine Linie ist darin genau sie selbst. Beim
    Ellipsenbogen zählt nur, was auf seiner Spanne liegt."""
    element = sketch.elements[index]
    found: list[Point2] = []
    for other_index, other in enumerate(sketch.elements):
        if other_index == index:
            continue
        for begin, end in itertools.pairwise(_flat_curve(other)):
            found.extend(
                point
                for point in ellipse_intersections((begin, end), element)
                if -_ON_SEGMENT <= _parameter_on((begin, end), point) <= 1.0 + _ON_SEGMENT
            )
    unique: list[Point2] = []
    for point in found:
        if all(math.dist(point, kept) > _SAME_SPOT for kept in unique):
            unique.append(point)
    return unique


def _trimmed_ellipse(sketch: Sketch, index: int, at: Point2) -> Sketch:
    """Trimmen an einer Ellipse oder einem Ellipsenbogen (RM-188 P6.6a).

    Die Kreuzungen teilen die Kurve; weg ist das Stück, auf das geklickt
    wurde. Eine volle Ellipse braucht dafür zwei Kreuzungen und wird ein
    Ellipsenbogen, der gegen den Uhrzeigersinn von der Kreuzung hinter dem
    Klick zu der davor läuft. Ein Bogen verliert das Stück zwischen den
    Kreuzungen um den Klick — oder bis zu seinem Ende, wie eine Linie — und
    wird dabei zu höchstens zwei Bögen auf **derselben** Ellipse
    (:func:`_rebuilt_ellipse`).
    """
    element = sketch.elements[index]
    frame = ellipse_frame(element.points[0], element.points[1], element.points[2])
    crossings = _ellipse_crossings(sketch, index)
    click = frame.parameter(at)
    pieces: list[tuple[Point2, Point2]] = []
    if element.kind == "ellipse":
        if len(crossings) < 2:
            raise ValidationError(
                "element",
                _(
                    "Diese Ellipse wird nicht zweimal gekreuzt — zum Trimmen braucht es "
                    "zwei Kanten, zwischen denen ein Stück wegfällt."
                ),
                constraint="too_few_crossings",
            )
        ranked = sorted(crossings, key=lambda point: parameter_sweep(click, frame.parameter(point)))
        pieces.append((ranked[0], ranked[-1]))
    else:
        start, end = element.points[3], element.points[4]
        origin = frame.parameter(start)
        reach = parameter_sweep(origin, frame.parameter(end))

        def along(point: Point2) -> float:
            return parameter_sweep(origin, frame.parameter(point))

        inner = [
            point
            for point in crossings
            if math.dist(point, start) > _JOIN_TOL
            and math.dist(point, end) > _JOIN_TOL
            and along(point) < reach
        ]
        if not inner:
            raise ValidationError(
                "element",
                _("Dieser Bogen kreuzt nichts — zum Trimmen braucht es eine Kante zum Kürzen."),
            )
        where = along(at)
        before = [point for point in inner if along(point) < where]
        after = [point for point in inner if along(point) > where]
        if before:
            pieces.append((start, max(before, key=along)))
        if after:
            pieces.append((min(after, key=along), end))
    kept = [piece for piece in pieces if math.dist(*piece) > _JOIN_TOL]
    return _rebuilt_ellipse(sketch, index, tuple(kept))


def _rebuilt_ellipse(
    sketch: Sketch, index: int, pieces: tuple[tuple[Point2, Point2], ...]
) -> Sketch:
    """Tauscht eine Ellipse oder einen Ellipsenbogen gegen die Bögen, die von
    ihr bleiben — mit den Bedingungen, die dabei weiter gelten.

    Dieselben Regeln wie bei der Linie (:func:`_rebuilt_line`): Was an Mitte
    und Achsen hing, bleibt am ersten Bogen — ein Maß der Achse misst
    weiterhin dieselbe Ellipse. Ein Bogenende, das seinen Ort behält, behält
    seine Bedingungen. **Ein zweiter Bogen hängt an der Ellipse des ersten**:
    Mitte und erstes Achsende gedeckt, die zweite Achse gleich lang. Nicht
    auch ihr Ende gedeckt — die zweite Achse steht schon durch die eigene
    Gleichung des Bogens senkrecht, und eine dritte Deckung sagte das ein
    zweites Mal: „legt fest, was schon festliegt" (gemessen). Auf welcher
    Seite ihr Ende liegt, ändert an der Ellipse nichts.
    """
    element = sketch.elements[index]
    begin = offsets_of(sketch)[index]
    count = len(element.points)
    axes = element.points[:3]
    fresh = tuple(
        SketchElement("elliptical_arc", (*axes, first, last), construction=element.construction)
        for first, last in pieces
    )
    added = 5 * len(fresh)
    mapping: dict[int, int] = {}
    for old in range(len(flat_points(sketch))):
        if begin <= old < begin + count:
            continue
        mapping[old] = old if old < begin else old - count + added
    if fresh:
        mapping.update({begin + axis: begin + axis for axis in range(3)})
    if element.kind == "elliptical_arc":
        start, end = element.points[3], element.points[4]
        for number, (first, last) in enumerate(pieces):
            if first is start:
                mapping[begin + 3] = begin + 5 * number + 3
            if last is end:
                mapping[begin + 4] = begin + 5 * number + 4

    constraints: list[SketchConstraint] = []
    for entry in sketch.constraints:
        if entry.kind in CURVE_SLOTS:
            moved = _curve_targets(entry, begin, mapping, len(fresh), size=5)
        else:
            targets = tuple(mapping.get(target, -1) for target in entry.targets)
            moved = None if min(targets, default=0) < 0 else targets
        if moved is not None:
            constraints.append(SketchConstraint(entry.kind, moved, entry.value))
    for number in range(1, len(fresh)):
        other = begin + 5 * number
        constraints.extend(
            (
                SketchConstraint("coincident", (begin, other)),
                SketchConstraint("coincident", (begin + 1, other + 1)),
                SketchConstraint("equal", (begin, begin + 2, other, other + 2)),
            )
        )
    elements = (*sketch.elements[:index], *fresh, *sketch.elements[index + 1 :])
    return replace(sketch, elements=elements, constraints=tuple(constraints))


def offset(sketch: Sketch, indices: tuple[int, ...], distance: float) -> Sketch:
    """Legt eine versetzte Kopie der gewählten Elemente daneben.

    Eine Linie wandert senkrecht zu sich selbst, ein Kreis ändert seinen
    Radius. Bögen und Splines bleiben außen vor: ihr Versatz ist keine
    Verschiebung, sondern eine neue Kurve, und eine falsche wäre schlimmer als
    keine.
    """
    if abs(distance) < EPS_SKETCH:
        raise ValidationError(
            "distance",
            _("Der Abstand ist null — ein Versatz um nichts legt eine Linie auf die andere."),
            value=distance,
        )

    copies: list[SketchElement] = []
    for index in indices:
        element = sketch.elements[index]
        if element.kind == "line":
            (ax, ay), (bx, by) = element.points[0], element.points[1]
            length = math.hypot(bx - ax, by - ay)
            if length < EPS_SKETCH:
                continue
            nx, ny = -(by - ay) / length, (bx - ax) / length
            copies.append(
                SketchElement(
                    kind="line",
                    points=(
                        (ax + nx * distance, ay + ny * distance),
                        (bx + nx * distance, by + ny * distance),
                    ),
                    construction=element.construction,
                )
            )
        elif element.kind == "circle":
            centre, edge = element.points[0], element.points[1]
            radius = math.hypot(edge[0] - centre[0], edge[1] - centre[1]) + distance
            if radius <= EPS_SKETCH:
                raise ValidationError(
                    "distance",
                    _("Der Kreis würde dabei kleiner als nichts — weniger nach innen versetzen."),
                    value=distance,
                )
            copies.append(
                SketchElement(
                    kind="circle",
                    points=(centre, (centre[0] + radius, centre[1])),
                    construction=element.construction,
                )
            )

    if not copies:
        raise ValidationError(
            "element",
            _("Versetzen arbeitet an Linien und Kreisen — ein Bogen wird dabei eine neue Kurve."),
        )
    return replace(sketch, elements=(*sketch.elements, *copies))


def move(sketch: Sketch, indices: tuple[int, ...], dx: float, dy: float) -> Sketch:
    """Schiebt die gewählten Elemente um einen Betrag — an Ort und Stelle.

    Der Griff fehlte ganz: Wer eine gezeichnete Form woandershin wollte,
    musste jeden ihrer Punkte einzeln fassen, und der Solver zog zwischen den
    Griffen alles mit. Bei einem Rechteck sind das vier Züge, von denen die
    ersten drei die Form verziehen.

    Verschoben und **nicht** kopiert — darin unterscheidet es sich von
    ``offset`` und ``mirror`` daneben. Die Elemente behalten damit ihren
    Platz in der Liste, und jede Bedingung, die auf sie zeigt, zeigt weiter
    auf dieselbe Stelle: Es gibt nichts umzunummerieren.

    Was der Solver danach mit dem Ergebnis macht, ist seine Sache. Ein Maß,
    das die Form festhält, zieht sie zurück — genauso wie beim Ziehen eines
    einzelnen Punktes, und aus demselben guten Grund.
    """
    if not indices:
        raise ValidationError(
            "elements",
            _("Nichts ausgewählt — erst die Elemente wählen, dann verschieben."),
        )
    chosen = set(indices)
    elements = tuple(
        SketchElement(
            kind=element.kind,
            points=tuple((x + dx, y + dy) for x, y in element.points),
            construction=element.construction,
        )
        if at in chosen
        else element
        for at, element in enumerate(sketch.elements)
    )
    return replace(sketch, elements=elements)


def mirror(sketch: Sketch, indices: tuple[int, ...], axis: str) -> Sketch:
    """Spiegelt die gewählten Elemente an einer der beiden Achsen.

    An der Achse, nicht an einer beliebigen Linie: das ist der Fall, den man
    beim Zeichnen fast immer meint, und er braucht keine zweite Auswahl. Die
    Bedingungen der Vorlage reisen nicht mit — die Kopie ist eine eigene
    Geometrie, und dieselbe Bemaßung zweimal wäre überbestimmt.
    """
    if axis not in ("x", "y"):
        raise ValidationError(
            "axis",
            _("Gespiegelt wird an der X- oder der Y-Achse."),
            value=axis,
        )

    def flip(point: Point2) -> Point2:
        return (point[0], -point[1]) if axis == "x" else (-point[0], point[1])

    copies = []
    for index in indices:
        element = sketch.elements[index]
        points = tuple(flip(point) for point in element.points)
        if element.kind == "arc":
            # Ein Bogen läuft gegen den Uhrzeigersinn; gespiegelt liefe er
            # andersherum. Anfang und Ende zu tauschen dreht ihn zurück.
            points = (points[0], points[2], points[1])
        elif element.kind == "elliptical_arc":
            # Derselbe Grund beim Ellipsenbogen. Die Achsenpunkte bleiben: Die
            # zweite Achse trägt nur ihre Länge, ihre Seite zählt nicht.
            points = (*points[:3], points[4], points[3])
        copies.append(replace(element, points=points))

    if not copies:
        raise ValidationError(
            "elements",
            _("Nichts ausgewählt — erst die Elemente wählen, dann spiegeln."),
        )
    return replace(sketch, elements=(*sketch.elements, *copies))


# --- Bedingungen umnummerieren ---------------------------------------------------

#: Bedingungen über **beide** Enden einer Linie, die ihre Richtung meinen und
#: nicht ihre Länge — sie gelten für jedes Stück, das von der Linie bleibt.
#: ``tangent`` und ``symmetric`` lesen die Linie als Gerade; ein Maß, ein
#: Gleich-lang oder ein Mittelpunkt meinen die Strecke und fallen mit ihr.
_ALONG_THE_LINE: Final = frozenset(
    {"horizontal", "vertical", "parallel", "perpendicular", "angle", "tangent", "symmetric"}
)


def _rebuilt_line(sketch: Sketch, index: int, pieces: tuple[tuple[Point2, Point2], ...]) -> Sketch:
    """Tauscht eine Linie gegen die Stücke, die von ihr bleiben — mit den
    Bedingungen, die dabei weiter gelten.

    **Was an einem stehen gebliebenen Ende hing, bleibt dran.** Hier fiel
    jede Bedingung der Linie weg, auch die Deckung an ihrem unberührten Ende:
    Wer ein Stück aus der Mitte trimmte oder eine Linie verlängerte, hatte
    danach eine Ecke, die beim nächsten Zug aufriss, und eine Waagerechte,
    die keine mehr war (Durchsicht 22.09.2026). Drei Regeln:

    * Ein Ende, das seinen Ort behält, behält seine Bedingungen — am Stück,
      das es trägt.
    * Ein Ende, das wegfällt oder wandert (die geklickte Hälfte beim Trimmen,
      das verlängerte Ende), verliert sie: Eine Deckung dort hielte es an
      einem Ort fest, an dem es nicht mehr ist.
    * Was die ganze Linie meint, gilt weiter, wenn es ihre **Richtung** meint
      (:data:`_ALONG_THE_LINE`) — am ersten Stück. Ein Maß, ein Gleich-lang
      oder ein Mittelpunkt meinen ihre **Länge**, und die ist eine andere
      geworden.

    Alle übrigen Bedingungen rücken mit ihren Punkten auf.
    """
    element = sketch.elements[index]
    begin = offsets_of(sketch)[index]
    count = len(element.points)
    fresh = tuple(
        SketchElement(kind="line", points=piece, construction=element.construction)
        for piece in pieces
    )
    added = 2 * len(fresh)

    mapping: dict[int, int] = {}
    for old in range(len(flat_points(sketch))):
        if begin <= old < begin + count:
            continue
        mapping[old] = old if old < begin else old - count + added
    # Die Enden, die ihren Ort behalten: der Anfang am ersten Stück, das mit
    # ihm beginnt, das Ende am letzten, das mit ihm endet.
    #
    # Verglichen wird die **Herkunft** und nicht die Zahl (Regel 6): Ein Stück,
    # das ein Ende behält, trägt genau dieses Tupel aus der alten Linie.
    start, end = element.points[0], element.points[1]
    for number, piece in enumerate(pieces):
        if piece[0] is start and begin not in mapping:
            mapping[begin] = begin + 2 * number
        if piece[1] is end:
            mapping[begin + 1] = begin + 2 * number + 1

    constraints: list[SketchConstraint] = []
    for entry in sketch.constraints:
        if entry.kind in CURVE_SLOTS:
            # **Eine Kurvenbedingung nennt die Linie über ihren Anfang**
            # (RM-188 P6.6b) — gemeint ist die Gerade, und die ist für jedes
            # Stück dieselbe. Sie wandert deshalb zu dem Stück, das ihre
            # Stelle trägt (bei *glatt* und *krümmungsstetig* der Punkt davor),
            # sonst zum ersten. Was an einem weggefallenen Ende hing, fällt mit
            # ihm, wie jede Punktbedingung.
            moved = _curve_targets(entry, begin, mapping, len(fresh))
            if moved is not None:
                constraints.append(SketchConstraint(entry.kind, moved, entry.value))
            continue
        whole = begin in entry.targets and begin + 1 in entry.targets
        if whole:
            if entry.kind not in _ALONG_THE_LINE or not fresh:
                continue
            # Die Richtung am ersten Stück: dessen Anfang für den Anfang der
            # Linie, dessen Ende für ihr Ende — beide liegen auf derselben
            # Geraden und zeigen in dieselbe Richtung.
            along = {begin: begin, begin + 1: begin + 1}
            targets = tuple(
                along[target] if target in along else mapping.get(target, -1)
                for target in entry.targets
            )
        else:
            targets = tuple(mapping.get(target, -1) for target in entry.targets)
        if min(targets, default=0) < 0:
            continue
        constraints.append(SketchConstraint(entry.kind, targets, entry.value))

    elements = (*sketch.elements[:index], *fresh, *sketch.elements[index + 1 :])
    return replace(sketch, elements=elements, constraints=tuple(constraints))


def _curve_targets(
    entry: SketchConstraint,
    begin: int,
    mapping: dict[int, int],
    pieces: int,
    *,
    size: int = 2,
) -> tuple[int, ...] | None:
    """Die Ziele einer Kurvenbedingung, nachdem die Kurve bei ``begin`` in
    ``pieces`` Stücke zu je ``size`` Punkten zerfiel — oder ``None``, wenn sie
    mit ihr fällt. Die Kurve wandert zu dem Stück, das die Stelle trägt."""
    slots = CURVE_SLOTS[entry.kind]
    targets: list[int] = []
    for slot, target in enumerate(entry.targets):
        if slot in slots and target == begin:
            if not pieces:
                return None
            spot = mapping.get(entry.targets[slot - 1]) if slot > 0 else None
            if entry.kind != "on_curve" and spot is not None and 0 <= spot - begin < size * pieces:
                targets.append(begin + size * ((spot - begin) // size))
            else:
                targets.append(begin)
            continue
        moved = mapping.get(target)
        if moved is None:
            return None
        targets.append(moved)
    return tuple(targets)


# --- Splinepunkte (RM-188 P6.6a) ---------------------------------------------------

#: Die kleinste Punktzahl eines Splines — unter zweien ist er ein Punkt
#: (dieselbe Grenze wie im Löser).
_LEAST_SPLINE_POINTS: Final = 2


def spline_point_added(sketch: Sketch, index: int, at: Point2) -> tuple[Sketch, int]:
    """Ein Punkt mehr im Spline ``index`` — dort, wo die Kurve ``at`` am
    nächsten kommt. Zurück kommen die Zeichnung und der flache Index des
    neuen Punkts.

    Der Punkt liegt **auf** der Kurve und nicht am Klick: Eine Kurve, die
    durch einen weiteren ihrer eigenen Punkte läuft, behält ihre Lage an
    allen alten Punkten und ändert ihre Form nur um den neuen herum —
    derselbe Griff wie „Stützpunkt einfügen" in Fusion. Die Bedingungen
    rücken mit ihren Punkten auf; eine Bedingung auf der ganzen Kurve nennt
    ihren Anfang, und der bleibt.
    """
    element = sketch.elements[index]
    if element.kind != "spline":
        raise ValidationError(
            "element",
            _("Punkte einfügen und entfernen lässt sich an einer Kurve durch Punkte."),
            constraint="not_a_spline",
        )
    piece, spot = closest_on_spline(element.points, at)
    if min(math.dist(spot, knot) for knot in element.points[piece : piece + 2]) <= _JOIN_TOL:
        # Zwei Punkte an einer Stelle machen ein Stück ohne Länge, und dort
        # hätte die Kurve keine Richtung.
        raise ValidationError(
            "point",
            _("Hier liegt schon ein Punkt der Kurve — zwischen zwei Punkten klicken."),
            constraint="point_there",
        )
    begin = offsets_of(sketch)[index]
    local = piece + 1
    points = (*element.points[:local], spot, *element.points[local:])
    added = begin + local
    constraints = tuple(
        SketchConstraint(
            entry.kind,
            tuple(target + 1 if target >= added else target for target in entry.targets),
            entry.value,
        )
        for entry in sketch.constraints
    )
    elements = (
        *sketch.elements[:index],
        replace(element, points=points),
        *sketch.elements[index + 1 :],
    )
    return replace(sketch, elements=elements, constraints=constraints), added


def spline_point_removed(sketch: Sketch, flat: int) -> Sketch:
    """Nimmt den Punkt ``flat`` aus seinem Spline — die Kurve läuft danach
    durch die übrigen.

    Was an dem Punkt hing, fällt mit ihm. Eine Bedingung auf der **ganzen**
    Kurve bleibt: Sie nennt deren ersten Punkt (RM-188 P6.6b), und fällt der
    erste weg, ist der nächste der neue erste — unter derselben Nummer.
    """
    offsets = offsets_of(sketch)
    owner = next(
        (
            position
            for position, element in enumerate(sketch.elements)
            if offsets[position] <= flat < offsets[position] + len(element.points)
        ),
        None,
    )
    if owner is None or sketch.elements[owner].kind != "spline":
        raise ValidationError(
            "point",
            _("Punkte einfügen und entfernen lässt sich an einer Kurve durch Punkte."),
            value=flat,
            constraint="not_a_spline",
        )
    element = sketch.elements[owner]
    if len(element.points) <= _LEAST_SPLINE_POINTS:
        raise ValidationError(
            "point",
            _(
                "Eine Kurve braucht mindestens zwei Punkte — "
                "statt des Punkts die ganze Kurve löschen."
            ),
            value=flat,
            constraint="least_points",
        )
    begin = offsets[owner]
    local = flat - begin
    points = (*element.points[:local], *element.points[local + 1 :])
    constraints: list[SketchConstraint] = []
    for entry in sketch.constraints:
        slots = CURVE_SLOTS.get(entry.kind, ())
        targets: list[int] = []
        for slot, target in enumerate(entry.targets):
            if slot in slots and target == begin:
                targets.append(begin)
            elif target == flat:
                break
            else:
                targets.append(target - 1 if target > flat else target)
        else:
            constraints.append(SketchConstraint(entry.kind, tuple(targets), entry.value))
    elements = (
        *sketch.elements[:owner],
        replace(element, points=points),
        *sketch.elements[owner + 1 :],
    )
    return replace(sketch, elements=elements, constraints=tuple(constraints))


def removed(sketch: Sketch, indices: Iterable[int]) -> Sketch:
    """Die Zeichnung ohne die Elemente ``indices`` — und ohne jede Bedingung,
    die einen ihrer Punkte liest; die übrigen Ziele rücken auf.

    Der Weg des Löschens im Editor und der Rücknahme einer Tangente, die ihren
    Berührpunkt als Hilfspunkt mitgebracht hat (:func:`taken_back`) — eine
    Rechnung für beides.
    """
    dropped = set(indices)
    offsets = offsets_of(sketch)
    gone: set[int] = set()
    for index in dropped:
        gone.update(range(offsets[index], offsets[index] + len(sketch.elements[index].points)))
    mapping: dict[int, int] = {}
    fresh = 0
    for old in range(len(flat_points(sketch))):
        if old in gone:
            continue
        mapping[old] = fresh
        fresh += 1
    elements = tuple(element for at, element in enumerate(sketch.elements) if at not in dropped)
    constraints = tuple(
        SketchConstraint(
            entry.kind, tuple(mapping[target] for target in entry.targets), entry.value
        )
        for entry in sketch.constraints
        if all(target in mapping for target in entry.targets)
    )
    return replace(sketch, elements=elements, constraints=constraints)


# --- Ellipsen zeichnen (RM-188 P6.6a) ------------------------------------------------


def ellipse_from_clicks(
    centre: Point2, first_end: Point2, across: Point2
) -> tuple[Point2, Point2, Point2] | None:
    """Die drei Punkte einer Ellipse aus drei Klicks — oder ``None``.

    Der erste Klick ist die Mitte, der zweite das Ende der ersten Achse, der
    dritte sagt, wie weit die Ellipse **quer** dazu reicht: Sein Abstand von
    der ersten Achse ist die zweite Halbachse, und der gespeicherte Punkt
    liegt senkrecht über der Mitte — vom dritten Klick zählt nur seine Höhe
    über der Achse. So steht die zweite Achse von Anfang an senkrecht, und der
    Löser muss nichts zurechtrücken, was die Hand nicht gemeint hat.

    ``None`` heißt: keine Ellipse — die erste Achse hat keine Länge, oder der
    dritte Klick liegt auf ihr. Die Grenze ist die des Lösers (``EPS_GEOM``).
    """
    ux, uy = first_end[0] - centre[0], first_end[1] - centre[1]
    first = math.hypot(ux, uy)
    if first <= EPS_GEOM:
        return None
    ux, uy = ux / first, uy / first
    height = -(across[0] - centre[0]) * uy + (across[1] - centre[1]) * ux
    if abs(height) <= EPS_GEOM:
        return None
    return centre, first_end, (centre[0] - uy * height, centre[1] + ux * height)


def onto_ellipse(axes: Sequence[Point2], point: Point2) -> Point2:
    """Wo der Strahl von der Mitte durch ``point`` die Ellipse trifft — für
    einen Punkt auf ihr er selbst (``profile.EllipseFrame.parameter``)."""
    frame = ellipse_frame(axes[0], axes[1], axes[2])
    return frame.at(*frame.parameter(point))


def carried_onto(old: Sequence[Point2], new: Sequence[Point2], point: Point2) -> Point2:
    """Derselbe Punkt auf einer gedrehten oder gestreckten Ellipse — an
    derselben Stelle ihres Parameters. So wandern die Enden eines
    Ellipsenbogens mit, wenn jemand an einer Achse zieht, und der Bogen behält
    seine Spanne."""
    before = ellipse_frame(old[0], old[1], old[2])
    after = ellipse_frame(new[0], new[1], new[2])
    return after.at(*before.parameter(point))


# --- Bedingungen zwischen Kurven planen (RM-188 P6.6b) -------------------------------

#: Die Elementarten, an denen eine Kurvenbedingung hängen kann
#: (``solver.CURVE_SLOTS``). Ein loser Punkt ist keine Kurve.
CURVE_KINDS: Final = frozenset({"line", "circle", "arc", "ellipse", "elliptical_arc", "spline"})

#: Die beiden Ellipsenarten — für *gleich groß* über beide Achsen.
ELLIPSE_KINDS: Final = frozenset({"ellipse", "elliptical_arc"})


@dataclass(frozen=True, slots=True)
class CurvePlan:
    """Was eine Bedingung zwischen Kurven an der Zeichnung ändert.

    ``constraints`` kommen dazu. ``helper`` ist ein Hilfspunkt, der vorher als
    letztes Element angehängt wird — seine Nummer steht in den Zielen schon
    drin. Ein Plan und keine fertige Zeichnung, damit Knopf, Kontextmenü und
    die Frage „steht sie schon?" dieselbe Rechnung lesen.
    """

    constraints: tuple[SketchConstraint, ...]
    helper: Point2 | None = None


def with_plan(sketch: Sketch, plan: CurvePlan) -> Sketch:
    """Die Zeichnung mit dem Plan — ein Schritt, ein Rückgängig."""
    elements = sketch.elements
    if plan.helper is not None:
        elements = (*elements, SketchElement("point", (plan.helper,), construction=True))
    return replace(sketch, elements=elements, constraints=(*sketch.constraints, *plan.constraints))


def _spots(element: SketchElement, begin: int, *, ends_only: bool) -> tuple[int, ...]:
    """Die eigenen Punkte einer Kurve, an denen ein Übergang sitzen kann.

    Ihre Enden — beim Spline auch jeder Punkt, durch den er läuft, außer für
    *krümmungsstetig*: Innen ist ein Catmull-Rom-Spline nur tangentenstetig.
    Kreis und Ellipse haben keine Enden.
    """
    kind = element.kind
    if kind == "line":
        return (begin, begin + 1)
    if kind == "arc":
        return (begin + 1, begin + 2)
    if kind == "elliptical_arc":
        return (begin + 3, begin + 4)
    if kind == "spline":
        last = begin + len(element.points) - 1
        return (begin, last) if ends_only else tuple(range(begin, last + 1))
    return ()


def curve_gap(element: SketchElement, point: Point2) -> float:
    """Wie weit ``point`` neben der Kurve liegt, die *Punkt auf Kurve* meint:
    die Gerade einer Linie, der Kreis eines Bogens, die Ellipse eines
    Ellipsenbogens, der Spline selbst. Bei der Ellipse radial gemessen — nie
    weniger als der wahre Abstand, und null genau auf ihr."""
    points = element.points
    if element.kind == "line":
        return _off_line(points[0], point, points[1])
    if element.kind in ("circle", "arc"):
        return abs(math.dist(points[0], point) - math.dist(points[0], points[1]))
    if element.kind in ELLIPSE_KINDS:
        return math.dist(point, onto_ellipse(points, point))
    if element.kind == "spline":
        _piece, spot = closest_on_spline(points, point)
        return math.dist(spot, point)
    return math.inf


def _solved(sketch: Sketch, points: Sequence[Point2], index: int) -> SketchElement:
    """Das Element ``index`` mit seinen gelösten Punkten."""
    element = sketch.elements[index]
    begin = offsets_of(sketch)[index]
    return replace(element, points=tuple(points[begin : begin + len(element.points)]))


def _linked(sketch: Sketch, first: int, second: int) -> bool:
    return first == second or any(
        entry.kind == "coincident" and set(entry.targets) == {first, second}
        for entry in sketch.constraints
    )


def _joint(
    sketch: Sketch, points: Sequence[Point2], first: int, second: int, *, ends_only: bool
) -> tuple[int, int, SketchConstraint | None] | None:
    """Wo zwei Kurven aneinanderstoßen: die Stelle an der ersten, die an der
    zweiten und die Bedingung, die den Stoß erst festhält — oder ``None``.

    Zuerst zwei eigene Punkte am selben Ort, verbunden durch eine Deckung
    oder nur übereinander gezeichnet (dann kommt die Deckung dazu). Danach ein
    Ende der einen Kurve, das auf der anderen liegt; die Stelle ist dann für
    beide dieser Punkt, und *Punkt auf Kurve* hält ihn dort. Ein Spline liest
    einen Übergang nur an einem seiner eigenen Punkte (``solver``), ein Ende
    auf seinem Inneren zählt deshalb nicht.
    """
    offsets = offsets_of(sketch)
    one, other = sketch.elements[first], sketch.elements[second]
    one_spots = _spots(one, offsets[first], ends_only=ends_only)
    other_spots = _spots(other, offsets[second], ends_only=ends_only)
    pairs = [(a, b) for a in one_spots for b in other_spots]
    for a, b in pairs:
        if _linked(sketch, a, b):
            return a, b, None
    for a, b in pairs:
        if math.dist(points[a], points[b]) <= _JOIN_TOL:
            return a, b, SketchConstraint("coincident", (a, b))
    for spots, carrier in ((one_spots, second), (other_spots, first)):
        if sketch.elements[carrier].kind == "spline":
            continue
        head = offsets[carrier]
        shape = _solved(sketch, points, carrier)
        for spot in spots:
            held = SketchConstraint("on_curve", (spot, head))
            if held in sketch.constraints:
                return spot, spot, None
            if curve_gap(shape, points[spot]) <= _JOIN_TOL:
                return spot, spot, held
    return None


def _closest_approach(one: SketchElement, other: SketchElement) -> Point2:
    """Die Mitte zwischen den nächsten Stellen zweier Kurven — der Startort
    eines Berührpunkts, den der Löser danach genau setzt.

    Beide Kurven als die Punktfolge der Ansicht (``_flat_curve``, schon auf
    ``CHORD_ERROR`` genau); eine Linie, die darin nur zwei Punkte hat, wird
    auf 64 Stellen geteilt. Dann das nächste Paar. Deterministisch und ohne
    Zufall; genau muss es nicht sein, nur auf der richtigen Seite — und
    schnell, denn die Knopfleiste fragt bei jeder Auswahl, ob es einen Plan
    gibt.
    """
    import numpy as np

    def dense(element: SketchElement) -> Any:
        flat = np.asarray(_flat_curve(element), dtype=float)
        if len(flat) != 2:
            return flat
        steps = np.linspace(0.0, 1.0, 65)
        return flat[0] + (flat[1] - flat[0]) * steps[:, None]

    first, second = dense(one), dense(other)
    gaps = np.linalg.norm(first[:, None, :] - second[None, :, :], axis=2)
    row, column = np.unravel_index(int(np.argmin(gaps)), gaps.shape)
    middle = (first[row] + second[column]) / 2.0
    return (float(middle[0]), float(middle[1]))


def tangent_plan(
    sketch: Sketch, points: Sequence[Point2], first: int, second: int
) -> CurvePlan | None:
    """Wie zwei Kurven tangential werden — oder ``None``, wenn es an dieser
    Auswahl nicht geht.

    Vier Lagen, in dieser Reihenfolge:

    * **Sie stoßen aneinander** (:func:`_joint`): *glatt* an dieser Stelle —
      der Übergang einer Kontur, Linie in Bogen, Spline in Kreis.
    * **Linie und Kreis oder Bogen ohne Stoß**: die bestehende Tangente
      (``tangent``, Abstand der Mitte zur Geraden gleich dem Radius), wie sie
      immer war — in jeder Reihenfolge der Auswahl. Hier entstand einmal eine
      Bedingung mit fünf Zielen, und mit dem Bogen zuerst gewählt bot sich der
      Knopf gar nicht an (Befund B2 der P6.6-Arbeit).
    * **Zwei andere Kurven ohne Stoß**: ein Hilfspunkt als Berührpunkt, auf
      beiden Kurven und dort glatt — drei Bedingungen, die zusammen genau eine
      Freiheit nehmen, und ein Punkt, an dem man die Berührung später findet.
    * **Ein Spline ohne Stoß**: nichts. Er liest einen Übergang nur an einem
      seiner Punkte; der Weg dahin ist, einen davon auf die andere Kurve zu
      legen.
    """
    one, other = sketch.elements[first], sketch.elements[second]
    if first == second or one.kind not in CURVE_KINDS or other.kind not in CURVE_KINDS:
        return None
    if one.kind == other.kind == "line":
        return None
    offsets = offsets_of(sketch)
    heads = (offsets[first], offsets[second])
    joint = _joint(sketch, points, first, second, ends_only=False)
    if joint is not None:
        spot, other_spot, link = joint
        smooth = SketchConstraint("smooth", (spot, heads[0], other_spot, heads[1]))
        return CurvePlan((*((link,) if link is not None else ()), smooth))
    kinds = {one.kind, other.kind}
    if "line" in kinds and len(kinds) == 2 and kinds <= {"line", "circle", "arc"}:
        line, round_ = (heads[0], heads[1]) if one.kind == "line" else (heads[1], heads[0])
        return CurvePlan((SketchConstraint("tangent", (line, line + 1, round_, round_ + 1)),))
    if "spline" in kinds:
        return None
    helper = len(points)
    touch = _closest_approach(_solved(sketch, points, first), _solved(sketch, points, second))
    return CurvePlan(
        (
            SketchConstraint("on_curve", (helper, heads[0])),
            SketchConstraint("on_curve", (helper, heads[1])),
            SketchConstraint("smooth", (helper, heads[0], helper, heads[1])),
        ),
        helper=touch,
    )


def curvature_plan(
    sketch: Sketch, points: Sequence[Point2], first: int, second: int
) -> CurvePlan | None:
    """*Krümmungsstetig* zwischen einem Spline und der Kurve an seinem Ende.

    Braucht einen Stoß an einem **Ende** des Splines (:func:`_joint` mit
    ``ends_only``) — innen hat er keine eindeutige Krümmung. Krümmungsstetig
    schließt glatt ein: Steht *glatt* dort noch nicht, kommt es mit, in
    demselben Schritt. ``None``, wenn keiner der beiden ein Spline ist oder
    sie nicht aneinanderstoßen.
    """
    one, other = sketch.elements[first], sketch.elements[second]
    if first == second or one.kind not in CURVE_KINDS or other.kind not in CURVE_KINDS:
        return None
    if "spline" not in (one.kind, other.kind):
        return None
    joint = _joint(sketch, points, first, second, ends_only=True)
    if joint is None:
        return None
    spot, other_spot, link = joint
    offsets = offsets_of(sketch)
    heads = (offsets[first], offsets[second])
    planned: list[SketchConstraint] = [] if link is None else [link]
    if not _between(sketch, "smooth", heads):
        planned.append(SketchConstraint("smooth", (spot, heads[0], other_spot, heads[1])))
    planned.append(SketchConstraint("curvature", (spot, heads[0], other_spot, heads[1])))
    return CurvePlan(tuple(planned))


def on_curve_plan(sketch: Sketch, point: int, curve: int) -> CurvePlan | None:
    """*Punkt auf Kurve* — ``None``, wenn der Punkt zur Kurve selbst gehört."""
    element = sketch.elements[curve]
    head = offsets_of(sketch)[curve]
    if element.kind not in CURVE_KINDS or head <= point < head + len(element.points):
        return None
    return CurvePlan((SketchConstraint("on_curve", (point, head)),))


def equal_axes_plan(
    sketch: Sketch, points: Sequence[Point2], first: int, second: int
) -> CurvePlan | None:
    """Zwei Ellipsen gleich groß: beide Achsen gleich, die längere zur längeren.

    Welche Achse die erste ist, legt die Zeichenreihenfolge fest und nicht die
    Größe (§9) — wer zwei Ellipsen gleich groß macht, meint aber gleiche
    Form. Gepaart wird deshalb nach der gezeichneten Länge.
    """
    one, other = sketch.elements[first], sketch.elements[second]
    if first == second or one.kind not in ELLIPSE_KINDS or other.kind not in ELLIPSE_KINDS:
        return None
    offsets = offsets_of(sketch)
    a, b = offsets[first], offsets[second]

    def major_first(begin: int) -> bool:
        return math.dist(points[begin], points[begin + 1]) >= math.dist(
            points[begin], points[begin + 2]
        )

    swapped = major_first(a) != major_first(b)
    return CurvePlan(
        (
            SketchConstraint("equal", (a, a + 1, b, b + (2 if swapped else 1))),
            SketchConstraint("equal", (a, a + 2, b, b + (1 if swapped else 2))),
        )
    )


def _curve_heads(entry: SketchConstraint) -> frozenset[int]:
    return frozenset(entry.targets[slot] for slot in CURVE_SLOTS[entry.kind])


def _between(sketch: Sketch, kind: str, heads: tuple[int, int]) -> list[int]:
    """Die Bedingungen der Art ``kind`` zwischen genau diesen zwei Kurven."""
    wanted = frozenset(heads)
    return [
        at
        for at, entry in enumerate(sketch.constraints)
        if entry.kind == kind and _curve_heads(entry) == wanted
    ]


def curve_constraints_present(
    sketch: Sketch, action: str, first: int, second: int
) -> tuple[int, ...]:
    """Welche Bedingungen ``action`` an dieser Auswahl schon angelegt hat —
    leer, wenn keine. ``first`` und ``second`` sind Elementindizes, bei
    *Punkt auf Kurve* der Punkt (flach) und die Kurve.

    Gefragt wird nach der **Aussage** und nicht nach den Zielen: *glatt*
    zwischen zwei Kurven steht, gleich an welcher Stelle und in welcher
    Reihenfolge es angelegt wurde. Für die Tangente zählt auch die alte Form
    (``tangent``) zwischen Linie und Kreis oder Bogen.
    """
    offsets = offsets_of(sketch)
    if action == "on_curve":
        wanted = SketchConstraint("on_curve", (first, offsets[second]))
        return tuple(at for at, entry in enumerate(sketch.constraints) if entry == wanted)
    heads = (offsets[first], offsets[second])
    if action == "curvature":
        return tuple(_between(sketch, "curvature", heads))
    if action == "equal":
        # Gleich groß zwischen zwei Ellipsen: je eine Achse der einen und eine
        # der anderen — welche zu welcher, sagt der Plan nach der Länge, hier
        # zählt nur, dass beide Paare stehen.
        a, b = heads
        axes_of_one = {(a, a + 1), (a, a + 2)}
        axes_of_other = {(b, b + 1), (b, b + 2)}
        matching = [
            at
            for at, entry in enumerate(sketch.constraints)
            if entry.kind == "equal"
            and {entry.targets[:2], entry.targets[2:]} & axes_of_one
            and {entry.targets[:2], entry.targets[2:]} & axes_of_other
        ]
        return tuple(matching) if len(matching) >= 2 else ()
    found = _between(sketch, "smooth", heads)
    for at, entry in enumerate(sketch.constraints):
        if entry.kind != "tangent":
            continue
        line, rest = entry.targets[:2], entry.targets[2:]
        if {line[0], rest[0]} == set(heads) and line[1] == line[0] + 1:
            found.append(at)
    return tuple(sorted(found))


def taken_back(sketch: Sketch, action: str, first: int, second: int) -> Sketch | None:
    """Die Zeichnung ohne die Bedingungen, die ``action`` an dieser Auswahl
    angelegt hat — ``None``, wenn dort keine steht (siehe
    :func:`curve_constraints_present`).

    Eine Tangente, die ihren Berührpunkt als Hilfspunkt mitgebracht hat
    (:func:`tangent_plan`), nimmt ihn wieder mit: Ein loser Punkt auf zwei
    Kurven wäre danach eine Bedingung, die niemand mehr sieht.
    """
    present = curve_constraints_present(sketch, action, first, second)
    if not present:
        return None
    helpers: set[int] = set()
    if action == "tangent":
        offsets = offsets_of(sketch)
        for at in present:
            entry = sketch.constraints[at]
            if entry.kind != "smooth" or entry.targets[0] != entry.targets[2]:
                continue
            point = entry.targets[0]
            owner = next(
                (
                    index
                    for index, element in enumerate(sketch.elements)
                    if offsets[index] == point and element.kind == "point"
                ),
                None,
            )
            heads = _curve_heads(entry)
            hanging = [other for other in sketch.constraints if point in other.targets]
            if owner is not None and all(
                other == entry
                or (
                    other.kind == "on_curve"
                    and other.targets[0] == point
                    and other.targets[1] in heads
                )
                for other in hanging
            ):
                helpers.add(owner)
    kept = tuple(entry for at, entry in enumerate(sketch.constraints) if at not in set(present))
    thinner = replace(sketch, constraints=kept)
    return removed(thinner, helpers) if helpers else thinner


# --- Projizieren -----------------------------------------------------------------

#: Die drei Grundebenen als Ursprung und Normale. Feature-Ebenen bringen ihren
#: Rahmen selbst mit — deshalb steht hier nur, was feststeht.
BASE_PLANES: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "plane:xy": ((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "plane:xz": ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
    "plane:yz": ((0.0, 0.0, 0.0), (1.0, 0.0, 0.0)),
}


def project(sketch: Sketch, mesh: object, frame: object = None) -> Sketch:
    """Holt die Schnittkurve eines Körpers als Hilfsgeometrie in die Skizze.

    Bei Weg 1 — fremdes Modell anpassen — ist das der Normalfall: eine Bohrung
    soll auf die vorhandene Kante ausgerichtet werden, und ohne die Kante in
    der Zeichnung bleibt nur Abmessen und Abtippen.

    **Als Hilfsgeometrie**, nicht als Kontur. Was aus dem Körper kommt, ist
    zum Anlehnen da; wer es extrudieren will, schaltet es um. Andersherum
    stünde beim nächsten Extrudieren ein zweiter Umriss in der Skizze, den
    niemand gezeichnet hat.

    **Und fest, wie die Flächenkontur** (RM-188 P3.4): Jeder Punkt trägt
    ``fixed``. Frei stand hier nach dem Projizieren der Lochplatte „noch 1568
    Maße fehlen", und was man an eine Kante hängte, zog die Kante mit. Punkte,
    die auf einer Geraden liegen, fallen dabei weg — der Schnitt durch die
    Platte kam als 392 Strecken, obwohl die Außenkante vier hat —, und was
    schon in der Zeichnung steht, kommt nicht doppelt.

    ``frame`` ist der Rahmen einer Flächenebene oder ``None`` für eine der
    drei Grundebenen. ``mesh`` ist ein ``MeshData`` oder ein exakter Körper —
    nicht typisiert, weil dieses Modul sonst die Geometrie-Schicht importieren
    müsste, nur um einen Namen zu nennen. **Ein exakter Körper wird exakt
    geschnitten** (P3.5, :func:`_exact_section`): Kreise, Bögen und Strecken
    statt eines Sehnenzugs aus seiner Vernetzung.
    """
    import numpy as np

    if frame is not None:
        origin = tuple(float(value) for value in frame.origin)  # type: ignore[attr-defined]
        normal = tuple(float(value) for value in frame.normal)  # type: ignore[attr-defined]
        x_axis = tuple(float(value) for value in frame.x_axis)  # type: ignore[attr-defined]
        y_axis = tuple(float(value) for value in frame.y_axis)  # type: ignore[attr-defined]
    else:
        origin, normal = BASE_PLANES.get(sketch.plane, BASE_PLANES["plane:xy"])
        x_axis, y_axis = _axes_for(sketch.plane)

    exact = _exact_section(mesh, origin, x_axis, y_axis)
    if exact is not None:
        if not exact:
            raise ValidationError(
                "plane",
                _("Diese Ebene schneidet den Körper nicht — dort gibt es keine Kante."),
            )
        return _held_projection(sketch, [exact])

    body = mesh.raw  # type: ignore[attr-defined]
    section = body.section(plane_origin=np.asarray(origin), plane_normal=np.asarray(normal))
    if section is None:
        raise ValidationError(
            "plane",
            _("Diese Ebene schneidet den Körper nicht — dort gibt es keine Kante."),
        )

    vertices = np.asarray(section.vertices, dtype=np.float64)
    straight = _straight_enough(vertices)
    chains: list[tuple[SketchElement, ...]] = []
    for entity in section.entities:
        indices = list(entity.points)
        flat = [
            (
                float(np.dot(point - np.asarray(origin), np.asarray(x_axis))),
                float(np.dot(point - np.asarray(origin), np.asarray(y_axis))),
            )
            for point in vertices[indices]
        ]
        closed = len(indices) > 3 and indices[0] == indices[-1]
        kept = _corners(flat[:-1], straight) if closed else _chain_corners(flat, straight)
        steps = zip(kept, [*kept[1:], kept[0]], strict=True) if closed else itertools.pairwise(kept)
        chains.append(
            tuple(
                SketchElement(kind="line", points=(first, second), construction=True)
                for first, second in steps
                if math.dist(first, second) > EPS_SKETCH
            )
        )

    if not any(chains):
        raise ValidationError(
            "plane",
            _("Der Schnitt ergibt keine Kante, an der sich zeichnen ließe."),
        )
    return _held_projection(sketch, chains)


def _held_projection(sketch: Sketch, chains: Sequence[tuple[SketchElement, ...]]) -> Sketch:
    """Die Schnittkurven fest an die Zeichnung — exakt wie am Netz (:func:`_held_copy`)."""
    grown, fresh = _held_copy(sketch, chains)
    if not fresh:
        raise ValidationError(
            "plane",
            _("Diese Kanten stehen schon in der Zeichnung."),
            constraint="already_there",
        )
    return grown


def _exact_section(
    body: object,
    origin: tuple[float, ...],
    x_axis: tuple[float, ...],
    y_axis: tuple[float, ...],
) -> tuple[SketchElement, ...] | None:
    """Der exakte Schnitt eines exakten Körpers als Hilfsgeometrie — sonst ``None`` (P3.5).

    Am Netz liefert ``trimesh`` einen Sehnenzug, und eine Bohrung kommt als
    Vieleck aus Dutzenden kurzer Strecken in die Zeichnung — ohne Mitte, an
    der sich eine Bemaßung festmachen ließe. Am exakten Körper schneidet
    ``brep.section`` die Ebene mit den echten Flächen: Kreise bleiben Kreise,
    Bögen Bögen, und was keines von beiden ist, wird eine Kurve. Ein Netz
    bekommt ``None`` und nimmt den bisherigen Weg; der exakte Kern wird träge
    geholt, denn ohne ihn gibt es keinen exakten Körper.
    """
    from app.core.brep.kernel import Solid

    if not isinstance(body, Solid):
        return None
    from app.core.brep.section import plane_section

    curves = plane_section(
        body,
        (float(origin[0]), float(origin[1]), float(origin[2])),
        (float(x_axis[0]), float(x_axis[1]), float(x_axis[2])),
        (float(y_axis[0]), float(y_axis[1]), float(y_axis[2])),
    )
    return tuple(
        SketchElement(kind=curve.kind, points=curve.points, construction=True) for curve in curves
    )


def _axes_for(plane: str) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Die zwei Zeichenrichtungen einer Grundebene.

    Dieselbe Wahl wie in ``planes.frame_of``: die waagerechte Fläche wird zur
    globalen XY-Ebene, damit dieselbe Skizze auf dem Tisch und auf dem Deckel
    gleich herum liegt.
    """
    if plane == "plane:xz":
        return ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    if plane == "plane:yz":
        return ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    return ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))


# --- Flächenkontur ------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class FaceOutline:
    """Was :func:`face_outline` übernommen hat — die Zeichnung und was die Zeile sagt."""

    sketch: Sketch
    loops: int
    """Wie viele Ränder neu in der Zeichnung stehen, der äußere mitgezählt."""
    exact: bool
    """Aus den Kurven des exakten Körpers — sonst aus den Kanten des Netzes."""
    circles: int = 0
    """Wie viele Ränder am Netz als Kreis aus einem erkannten Merkmal kamen."""
    deviation: float = 0.0
    """Wie weit diese Kreise höchstens neben dem Netzrand liegen, in Millimetern."""


#: Der Weg zu einer Fläche, wenn die Zeichnung auf keiner steht.
PICK_A_FACE = Action(id="sketch.pick_face", label=_("Eine Fläche wählen"), primary=True)


def face_outline(sketch: Sketch, objects: Iterable[SceneObject], frame: PlaneFrame) -> FaceOutline:
    """Die Ränder der Fläche, auf der die Zeichnung steht — als feste Hilfsgeometrie.

    **Eine eigene Handlung neben** :func:`project` (RM-188 P3.4;
    Konzept vollwertiges CAD §6 und §13.3). *Projizieren* schneidet die Körper mit der
    Zeichenebene, und auf der Fläche selbst, auf der man zeichnet, schneidet
    sie nichts: sechs von sechs Flächen von ``plate_holes.stl`` endeten mit
    „Diese Ebene schneidet den Körper nicht". Die Kontur einer Fläche ist ihr
    Rand, und den gibt es auch dort — außen einer, innen je Loch einer.

    **Woher der Rand kommt:** Am exakten Körper aus seinen Kurven
    (``brep.edit.face_loops``) — eine Bohrung kommt als Kreis, ein Bogen
    als Bogen und eine Ellipse als Ellipse. Am Netz aus den Randringen
    (``perceive.relations``); ein Ring,
    den ein erkanntes Merkmal als Kreis belegt (Bohrung oder Zapfen, Achse
    durch die Ebene), wird ein Kreis — aber nur, wenn er an keiner Stelle
    weiter als ``MAX_FACET_SAG`` neben dem Ring liegt, an den Ecken und in
    der Mitte jeder Sehne. Ein Merkmal, das schlecht passt, erzeugt so keine
    falsche Kontur; der Ring bleibt dann, was das Netz sagt.

    **Fest, als Hilfsgeometrie, und eine Kopie.** Jeder Punkt trägt ein
    ``fixed``: Was sich an ihr ausrichtet, zieht sie nicht mit, und sie zählt
    nicht zu den Maßen, die der Zeichnung fehlen. Ändert sich der Körper
    später, folgt sie nicht — das sagt die Oberfläche beim Übernehmen. Was
    schon in der Zeichnung steht (derselbe Rand zum zweiten Mal übernommen),
    kommt nicht doppelt.

    ``frame`` ist der Rahmen der Zeichenebene. Sie darf über der Fläche
    liegen, parallel verschoben; gegen die Fläche gekippt käme der Rand
    verzerrt an — dann gibt es eine Absage statt einer Ellipse, die niemand
    bestellt hat.
    """
    root = standing_on_feature(sketch.plane)
    if root is None:
        raise ValidationError(
            "plane",
            _(
                "Diese Zeichnung liegt auf keiner Fläche eines Körpers. "
                "Eine Fläche anklicken und dort zeichnen — Kanten in einer "
                "freien Ebene holt „Projizieren“."
            ),
            constraint="not_on_a_face",
            suggestions=[PICK_A_FACE, CANCEL],
        )
    object_id, feature_id = feature_plane_parts(root)
    found = _face_of(objects, object_id, feature_id)
    if found is None:
        raise ValidationError(
            "plane",
            _("Diese Fläche gibt es in der Szene nicht mehr."),
            value=feature_id,
            constraint="unknown_feature",
            suggestions=[PICK_A_FACE, CANCEL],
        )
    entry, feature = found
    normal = tuple(float(value) for value in feature.params.get("normal", (0.0, 0.0, 1.0)))
    if _length(_cross(normal, frame.normal)) > PLANE_PARALLEL:
        raise ValidationError(
            "plane",
            _(
                "Die Zeichenebene ist gegen ihre Fläche geneigt — die Kontur käme "
                "verzerrt an. Auf der Fläche selbst oder parallel dazu zeichnen."
            ),
            constraint="tilted_to_face",
            suggestions=[PICK_A_FACE, CANCEL],
        )

    from app.core.brep.kernel import Solid

    if isinstance(entry.mesh, Solid):
        loops = _exact_outline(entry.mesh, feature.face_indices, frame)
        return _with_outline(sketch, loops, exact=True)
    loops, circles, deviation = _mesh_outline(entry, feature, frame)
    return _with_outline(sketch, loops, exact=False, circles=circles, deviation=deviation)


def _face_of(
    objects: Iterable[SceneObject], object_id: str, feature_id: str
) -> tuple[SceneObject, Any] | None:
    """Körper und ebene Fläche zu einer Flächenebene — gesucht wie in ``planes.frame_for``."""
    for entry in objects:
        if object_id and entry.id != object_id:
            continue
        feature = entry.features.get(feature_id)
        if feature is not None and feature.kind == "face":
            return entry, feature
    return None


def _exact_outline(
    solid: Any, face_indices: Sequence[int], frame: PlaneFrame
) -> list[tuple[SketchElement, ...]]:
    """Die Ränder einer exakten Fläche, je Rand die Elemente in der Zeichenebene."""
    from app.core.brep.edit import face_loops

    # Die Drehrichtung der Zeichnung: gegen den Uhrzeigersinn heißt um das
    # Kreuzprodukt ihrer beiden Achsen — auf ``plane:xz`` ist das nicht die
    # Normale (siehe ``planes.BASE_FRAMES``), und ein Bogen, der um die
    # falsche Achse gelesen wird, ist sein Gegenstück.
    turning = _cross(frame.x_axis, frame.y_axis)
    loops: list[tuple[SketchElement, ...]] = []
    for index in solid.faces_of_triangles(tuple(face_indices)):
        for loop in face_loops(solid, index):
            elements: list[SketchElement] = []
            for piece in loop.pieces:
                flat = [to_plane(frame, point) for point in piece.points]
                if piece.kind == "line":
                    elements.append(SketchElement("line", (flat[0], flat[1]), construction=True))
                elif piece.kind == "circle" and piece.centre is not None:
                    centre = to_plane(frame, piece.centre)
                    elements.append(SketchElement("circle", (centre, flat[0]), construction=True))
                elif piece.kind == "arc" and piece.centre is not None:
                    centre = to_plane(frame, piece.centre)
                    ends = (flat[0], flat[1])
                    if _dot(piece.axis or turning, turning) < 0.0:
                        ends = (flat[1], flat[0])
                    elements.append(SketchElement("arc", (centre, *ends), construction=True))
                elif (
                    piece.kind in ("ellipse", "elliptical_arc")
                    and piece.centre is not None
                    and piece.major_end is not None
                    and piece.minor_end is not None
                ):
                    # Die Ellipse selbst, nicht ihre Sehnen (RM-188 P6.6a): Mitte
                    # und die Enden beider Halbachsen, wie die Skizze sie trägt.
                    # Der Bogen dreht wie der Kreisbogen um die Zeichenrichtung.
                    axes = (
                        to_plane(frame, piece.centre),
                        to_plane(frame, piece.major_end),
                        to_plane(frame, piece.minor_end),
                    )
                    if piece.kind == "ellipse":
                        elements.append(SketchElement("ellipse", axes, construction=True))
                    else:
                        ends = (flat[0], flat[1])
                        if _dot(piece.axis or turning, turning) < 0.0:
                            ends = (flat[1], flat[0])
                        # Die Enden genau auf ihre Ellipse: Aus einer Kante,
                        # die OpenCASCADE als B-Spline führt, liegen sie nur
                        # innerhalb der Kantentoleranz darauf — und über lauter
                        # festen Punkten hielte der Löser jeden Rest über
                        # ``EPS_GEOM`` für einen Widerspruch.
                        shape = ellipse_frame(*axes)
                        ends = (
                            shape.at(*shape.parameter(ends[0])),
                            shape.at(*shape.parameter(ends[1])),
                        )
                        elements.append(
                            SketchElement("elliptical_arc", (*axes, *ends), construction=True)
                        )
                else:
                    elements.extend(
                        SketchElement("line", (first, second), construction=True)
                        for first, second in itertools.pairwise(flat)
                        if math.dist(first, second) > EPS_GEOM
                    )
            if not elements:
                continue
            # Der Außenrand zuerst — in der Zeichnung und in der Zählung.
            if loop.outer:
                loops.insert(0, tuple(elements))
            else:
                loops.append(tuple(elements))
    return loops


def _mesh_outline(
    entry: SceneObject, feature: Any, frame: PlaneFrame
) -> tuple[list[tuple[SketchElement, ...]], int, float]:
    """Die Randringe einer Netzfläche — Kreise, wo ein Merkmal sie belegt.

    Zurück kommen die Ränder (der äußere zuerst), wie viele davon Kreise
    wurden und wie weit diese höchstens neben dem Netz liegen.
    """
    import numpy as np

    from app.core.perceive.features import ROUND_WALL_KINDS
    from app.core.perceive.relations import boundary_rings, ring_in_order

    body = entry.mesh.raw  # type: ignore[attr-defined]
    rings = boundary_rings(body, feature)
    if not rings:
        raise ValidationError(
            "plane",
            _(
                "Der Rand dieser Fläche ist am Netz nicht eindeutig. "
                "„Projizieren“ holt die Kanten über einen Schnitt."
            ),
            constraint="unreadable_rim",
        )
    vertices = np.asarray(body.vertices, dtype=np.float64)
    round_walls = [
        candidate
        for candidate in entry.features.values()
        if candidate.kind in ROUND_WALL_KINDS
        and {"diameter", "axis", "centre"} <= set(candidate.params)
    ]
    flat_rings: list[list[Point2]] = []
    used: list[int] = []
    for ring in rings:
        order = ring_in_order(ring)
        used.extend(order)
        flat_rings.append(
            [to_plane(frame, (float(x), float(y), float(z))) for x, y, z in vertices[order]]
        )
    straight = _straight_enough(vertices[used])
    outer = max(range(len(flat_rings)), key=lambda index: abs(_ring_area(flat_rings[index])))
    loops: list[tuple[SketchElement, ...]] = []
    circles = 0
    deviation = 0.0
    for index in [outer, *(other for other in range(len(flat_rings)) if other != outer)]:
        ring_points = flat_rings[index]
        circle = _circle_on(ring_points, round_walls, frame)
        if circle is not None:
            centre, radius, off = circle
            circles += 1
            deviation = max(deviation, off)
            rim = (centre[0] + radius, centre[1])
            loops.append((SketchElement("circle", (centre, rim), construction=True),))
            continue
        kept = _corners(ring_points, straight)
        loops.append(
            tuple(
                SketchElement("line", (first, second), construction=True)
                for first, second in zip(kept, [*kept[1:], kept[0]], strict=True)
                if math.dist(first, second) > EPS_GEOM
            )
        )
    return loops, circles, deviation


def _circle_on(
    ring: Sequence[Point2], round_walls: Sequence[Any], frame: PlaneFrame
) -> tuple[Point2, float, float] | None:
    """Der Kreis eines Merkmals, auf dem dieser Ring liegt — oder nichts.

    Gemessen wird an den Ecken **und** in der Mitte jeder Sehne: Ein Sechseck
    hat alle Ecken auf einem Kreis, aber seine Seiten nicht. Unter mehreren
    passenden Merkmalen gilt das, das am wenigsten abweicht.
    """
    best: tuple[Point2, float, float] | None = None
    for candidate in round_walls:
        axis = tuple(float(value) for value in candidate.params["axis"])
        origin = tuple(float(value) for value in candidate.params["centre"])
        radius = float(candidate.params["diameter"]) / 2.0
        facing = _dot(axis, frame.normal)
        if radius <= EPS_GEOM or abs(facing) <= PLANE_PARALLEL:
            continue
        # Wo die Achse die Zeichenebene durchstößt — in beide Richtungen.
        gap = [frame.origin[place] - origin[place] for place in range(3)]
        along = _dot(gap, frame.normal) / facing
        centre = to_plane(
            frame,
            (
                origin[0] + along * axis[0],
                origin[1] + along * axis[1],
                origin[2] + along * axis[2],
            ),
        )
        samples = [
            *ring,
            *(
                ((first[0] + second[0]) / 2.0, (first[1] + second[1]) / 2.0)
                for first, second in zip(ring, [*ring[1:], ring[0]], strict=True)
            ),
        ]
        off = max(abs(math.dist(point, centre) - radius) for point in samples)
        if off <= MAX_FACET_SAG and (best is None or off < best[2]):
            best = (centre, radius, off)
    return best


def _corners(ring: Sequence[Point2], straight: float) -> list[Point2]:
    """Die Ecken eines geschlossenen Rings — Punkte auf einer Geraden fallen weg.

    Begonnen wird am Punkt, der am weitesten vom Schwerpunkt liegt: Er ist
    sicher eine Ecke, und von ihm aus reicht ein Umlauf.
    """
    count = len(ring)
    if count < 4:
        return list(ring)
    middle = (
        math.fsum(point[0] for point in ring) / count,
        math.fsum(point[1] for point in ring) / count,
    )
    start = max(range(count), key=lambda index: math.dist(ring[index], middle))
    walk = [ring[(start + step) % count] for step in range(count)]
    kept = [walk[0]]
    for index in range(1, count):
        following = walk[(index + 1) % count]
        if _off_line(kept[-1], walk[index], following) > straight:
            kept.append(walk[index])
    return kept if len(kept) >= 3 else list(ring)


def _chain_corners(chain: Sequence[Point2], straight: float) -> list[Point2]:
    """Die Ecken eines offenen Zugs — die Enden bleiben, Punkte auf Geraden fallen."""
    if len(chain) < 3:
        return list(chain)
    kept = [chain[0]]
    for index in range(1, len(chain) - 1):
        if _off_line(kept[-1], chain[index], chain[index + 1]) > straight:
            kept.append(chain[index])
    kept.append(chain[-1])
    return kept


def _straight_enough(points: Any) -> float:
    """Ab wann ein Punkt neben einer Geraden liegt — die Auflösung der Datei.

    Ein Netz aus STL steht in einfacher Genauigkeit, und dort liegen drei
    Punkte einer schrägen Kante um einige Millionstel neben ihrer Geraden:
    viermal der Abstand benachbarter Zahlen bei dieser Größe, mindestens
    ``EPS_GEOM``.
    """
    import numpy as np

    reach = float(np.abs(np.asarray(points, dtype=np.float64)).max()) if len(points) else 0.0
    return max(EPS_GEOM, 4.0 * float(np.spacing(np.float32(reach))))


def _off_line(start: Point2, point: Point2, end: Point2) -> float:
    """Wie weit ``point`` neben der Geraden durch ``start`` und ``end`` liegt."""
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


def _ring_area(ring: Sequence[Point2]) -> float:
    """Die vorzeichenbehaftete Fläche eines geschlossenen Zugs."""
    return 0.5 * math.fsum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(ring, [*ring[1:], ring[0]], strict=True)
    )


def _with_outline(
    sketch: Sketch,
    loops: Sequence[tuple[SketchElement, ...]],
    *,
    exact: bool,
    circles: int = 0,
    deviation: float = 0.0,
) -> FaceOutline:
    """Die Ränder an die Zeichnung hängen, jeden Punkt fest — ohne Doppeltes."""
    grown, fresh = _held_copy(sketch, loops)
    return FaceOutline(sketch=grown, loops=fresh, exact=exact, circles=circles, deviation=deviation)


def _held_copy(sketch: Sketch, loops: Sequence[tuple[SketchElement, ...]]) -> tuple[Sketch, int]:
    """Was aus dem Körper kommt, an die Zeichnung hängen — fest und ohne Doppeltes.

    Der gemeinsame Weg von :func:`face_outline` und :func:`project`: Jeder
    neue Punkt trägt ``fixed``, und ein Element, das schon in der Zeichnung
    steht (:func:`_element_key`), kommt nicht noch einmal. Zurück kommt die
    Zeichnung — **dieselbe**, wenn nichts neu war — und wie viele der Züge
    etwas beigetragen haben.
    """
    present = {_element_key(element) for element in sketch.elements}
    added: list[SketchElement] = []
    fresh = 0
    for loop in loops:
        new = [element for element in loop if _element_key(element) not in present]
        if new:
            fresh += 1
        added.extend(new)
        present.update(_element_key(element) for element in new)
    if not added:
        return sketch, 0
    start = len(flat_points(sketch))
    count = sum(len(element.points) for element in added)
    held = tuple(SketchConstraint("fixed", (start + offset,)) for offset in range(count))
    grown = replace(
        sketch,
        elements=(*sketch.elements, *added),
        constraints=(*sketch.constraints, *held),
    )
    return grown, fresh


def _element_key(element: SketchElement) -> tuple[str, tuple[tuple[float, float], ...]]:
    """Woran ein schon übernommener Rand wiedererkannt wird — Art und Punkte.

    Auf ``_JOIN_TOL`` gerundet, dieselbe Nähe, in der die Profilbildung zwei
    Enden für einen Punkt hält. Die Reihenfolge der Punkte zählt dabei nicht:
    Eine Strecke ist in beide Richtungen dieselbe.
    """
    digits = round(-math.log10(_JOIN_TOL))
    points = tuple(
        sorted((round(x, digits) + 0.0, round(y, digits) + 0.0) for x, y in element.points)
    )
    return element.kind, points


def _cross(first: Sequence[float], second: Sequence[float]) -> Vec3:
    return (
        first[1] * second[2] - first[2] * second[1],
        first[2] * second[0] - first[0] * second[2],
        first[0] * second[1] - first[1] * second[0],
    )


def _dot(first: Sequence[float], second: Sequence[float]) -> float:
    return first[0] * second[0] + first[1] * second[1] + first[2] * second[2]


def _length(vector: Sequence[float]) -> float:
    return math.sqrt(_dot(vector, vector))


def arc_through(start: Point2, end: Point2, via: Point2) -> tuple[Point2, Point2, Point2] | None:
    """Drei Punkte auf einem Bogen → wie ihn die Skizze speichert.

    Zurück kommt ``(Mitte, Anfang, Ende)`` — das Format, in dem ein
    ``SketchElement("arc", …)`` seine Punkte trägt, in der Projektdatei steht
    und vom Löser gelesen wird. Es bleibt unangetastet; was sich am 24.08.2026
    geändert hat, ist allein die **Reihenfolge, in der geklickt wird**: erst
    Anfang und Ende, dann die Wölbung, wie in Fusion und Onshape. Vorher war
    der erste Klick die Mitte — ein Punkt, der auf keiner Kante liegt und den
    man beim Zeichnen eines Umrisses nicht im Kopf hat.

    **Anfang und Ende können dabei tauschen**, und das ist der Teil, den man
    leicht verliert: Der Kern läuft den Bogen immer gegen den Uhrzeigersinn
    vom Anfang zum Ende (``sweep = (finish - begin) % 2π``). Liegt die
    geklickte Wölbung auf der anderen Hälfte des Kreises, wäre das die falsche
    von zwei möglichen Bögen — dann werden die Enden getauscht.

    ``None`` heißt: kein Bogen. Die drei Punkte liegen auf einer Geraden oder
    zwei von ihnen fallen zusammen; ein Kreis durch sie gibt es dann nicht.
    Der Aufrufer entscheidet, was er dem Nutzer sagt — hier unten ist von
    Bedienung nichts bekannt.
    """
    ax, ay = start
    bx, by = end
    cx, cy = via
    # Zweifache Fläche des Dreiecks: null heißt kollinear, und dann gibt es
    # keinen Umkreis. Der Vergleich läuft gegen die Kantenlängen, nicht gegen
    # eine feste Zahl — drei Punkte im Abstand von Metern sind bei derselben
    # absoluten Abweichung noch krumm, drei im Zehntelmillimeter nicht mehr.
    twice_area = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
    span = max(math.dist(start, end), math.dist(start, via), math.dist(end, via))
    if span <= EPS_SKETCH or abs(twice_area) <= EPS_SKETCH * span * span:
        return None

    a2 = ax * ax + ay * ay
    b2 = bx * bx + by * by
    c2 = cx * cx + cy * cy
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    centre = (
        (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d,
        (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d,
    )

    # Läuft der Bogen gegen den Uhrzeigersinn von Anfang nach Ende an der
    # Wölbung vorbei? Sonst sind es die Enden andersherum.
    def angle(point: Point2) -> float:
        return math.atan2(point[1] - centre[1], point[0] - centre[0])

    begin = angle(start)
    sweep_end = (angle(end) - begin) % (2.0 * math.pi)
    sweep_via = (angle(via) - begin) % (2.0 * math.pi)
    if sweep_via > sweep_end:
        return (centre, end, start)
    return (centre, start, end)


# --- Ecken: Verrunden und Fase ---------------------------------------------------


@dataclass(frozen=True, slots=True)
class Corner:
    """Zwei Linien, die sich an einem Punkt treffen — und wo genau.

    ``first`` und ``second`` sind je ``(Elementindex, lokaler Punkt)``: der
    lokale Punkt ist das Ende, das in der Ecke liegt (0 oder 1). ``spot`` ist
    die Ecke selbst in gelösten Koordinaten.
    """

    first: tuple[int, int]
    second: tuple[int, int]
    spot: Point2


#: Wie nah zwei Endpunkte beieinanderliegen dürfen, um als eine Ecke zu
#: gelten — die Deckungstoleranz der Profilbildung, nicht die Zeichenauflösung:
#: Ein Umriss schließt sich in ``profile`` auf dieselbe Weite, und die Zahl
#: steht deshalb dort und nicht ein zweites Mal hier.
_CORNER_TOL = _JOIN_TOL


def corner_at(sketch: Sketch, points: Sequence[Point2], flat: int) -> Corner | None:
    """Die Ecke aus zwei Linien an diesem Punkt — oder keine.

    Gesucht wird über die **gelösten** Punkte (``points``), nicht die
    gespeicherten: Zwei Linienenden bilden eine Ecke, wenn sie am selben Ort
    liegen, gleich ob eine Deckung sie dorthin gezogen hat oder ein Klick.
    Genau zwei Linien müssen es sein — drei Linien an einem Punkt haben keine
    eindeutige Ecke, ein Bogen an einer Linie ist schon rund. **Und eine
    Hilfslinie zählt nicht:** Sie ist ``kind == "line"`` mit
    ``construction``, und aus ihr würde sonst ein Bogen oder eine Schräge
    ohne das Kennzeichen — eine Profilkante, die ``regions_of`` mitnimmt
    (Fund des Reviews vom 14.09.2026).
    """
    if not 0 <= flat < len(points):
        return None
    spot = points[flat]
    offsets = offsets_of(sketch)
    ends: list[tuple[int, int]] = []
    for index, element in enumerate(sketch.elements):
        if element.kind != "line" or element.construction:
            continue
        begin = offsets[index]
        for local in (0, 1):
            if math.dist(points[begin + local], spot) <= _CORNER_TOL:
                ends.append((index, local))
    if len(ends) != 2 or ends[0][0] == ends[1][0]:
        return None
    return Corner(ends[0], ends[1], spot)


def _corner_directions(
    sketch: Sketch, points: Sequence[Point2], corner: Corner
) -> tuple[tuple[float, float], tuple[float, float], float, float]:
    """Einheitsrichtungen von der Ecke weg entlang beider Linien, und wie
    lang die Linien sind."""
    offsets = offsets_of(sketch)
    away: list[tuple[float, float]] = []
    lengths: list[float] = []
    for index, local in (corner.first, corner.second):
        begin = offsets[index]
        far = points[begin + (1 - local)]
        dx, dy = far[0] - corner.spot[0], far[1] - corner.spot[1]
        length = math.hypot(dx, dy)
        if length <= EPS_SKETCH:
            raise ValidationError(
                "element",
                _("Eine der beiden Linien hat keine Länge — an ihr gibt es keine Ecke."),
            )
        away.append((dx / length, dy / length))
        lengths.append(length)
    return away[0], away[1], lengths[0], lengths[1]


def _corner_angle(u: tuple[float, float], v: tuple[float, float]) -> float:
    """Der Winkel zwischen den beiden Schenkeln, im offenen Bereich (0, π)."""
    dot = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
    theta = math.acos(dot)
    if theta <= 1e-6 or theta >= math.pi - 1e-6:
        raise ValidationError(
            "element",
            _("Die beiden Linien liegen auf einer Geraden — dort gibt es keine Ecke zu brechen."),
        )
    return theta


def _shortened(
    sketch: Sketch, corner: Corner, first_to: Point2, second_to: Point2
) -> tuple[SketchElement, ...]:
    """Beide Linien mit dem Eckende auf die neuen Punkte gesetzt."""
    elements = list(sketch.elements)
    for (index, local), spot in ((corner.first, first_to), (corner.second, second_to)):
        element = elements[index]
        moved = list(element.points)
        moved[local] = spot
        elements[index] = replace(element, points=tuple(moved))
    return tuple(elements)


def _without_corner_joint(
    sketch: Sketch, first_flat: int, second_flat: int
) -> tuple[SketchConstraint, ...]:
    """Die Bedingungen ohne die Deckung, die beide Eckenden verband."""
    joint = {first_flat, second_flat}
    return tuple(
        entry
        for entry in sketch.constraints
        if not (entry.kind == "coincident" and set(entry.targets) == joint)
    )


def fillet(sketch: Sketch, points: Sequence[Point2], flat: int, radius: float) -> Sketch:
    """Bricht die Ecke an ``flat`` mit einem Bogen vom Radius ``radius``.

    Beide Linien werden bis zum Berührpunkt gekürzt, dazwischen liegt ein
    Bogen, der beide tangential berührt — und das bleibt so: Deckung an
    beiden Enden, der Radius als Maß, und die Tangente an jeder Linie als
    **Senkrecht** zwischen der Linie und dem Radiusstrahl zu ihrem
    Berührpunkt. Ein verrundetes Rechteck lässt sich danach an jeder Ecke
    ziehen, und die Rundung läuft mit statt zu zerreißen.

    **Warum nicht die Tangentenbedingung selbst:** Sie misst den Abstand der
    Mitte zur Geraden gegen den Radius, und an einem Bogenende, das per
    Deckung *auf* der Linie liegt, ist das ein doppelter Nullpunkt — die
    Ableitung nach dem Ende ist dort null, die Jacobimatrix singulär, und der
    Löser meldete „legt fest, was schon festliegt" über eine Skizze, die
    genau bestimmt war (gemessen 13.09.2026). Die Senkrechte sagt dasselbe
    mit einer Ableitung, die trägt.

    Der Radius muss zur Ecke passen: Der Berührpunkt liegt ``r / tan(θ/2)``
    von der Ecke entfernt, und wenn das weiter ist als eine der Linien lang,
    gibt es die Rundung dort nicht — die Meldung nennt den größten Radius,
    der noch passt.
    """
    require_positive("radius", radius)
    corner = corner_at(sketch, points, flat)
    if corner is None:
        raise ValidationError(
            "element",
            _("Hier treffen sich keine zwei Linien — Verrunden braucht eine Ecke aus zwei Linien."),
        )
    u, v, length_u, length_v = _corner_directions(sketch, points, corner)
    theta = _corner_angle(u, v)
    reach = radius / math.tan(theta / 2.0)
    room = min(length_u, length_v)
    if reach >= room - EPS_SKETCH:
        raise ValidationError(
            "radius",
            _(
                "Der Radius ist zu groß für diese Ecke — er muss kleiner sein als {most}.",
                most=written_measure(room * math.tan(theta / 2.0)),
            ),
            value=radius,
            constraint="maximum",
            values={"most": written_measure(room * math.tan(theta / 2.0))},
        )
    cx, cy = corner.spot
    touch_u: Point2 = (cx + u[0] * reach, cy + u[1] * reach)
    touch_v: Point2 = (cx + v[0] * reach, cy + v[1] * reach)
    bisector = (u[0] + v[0], u[1] + v[1])
    bisector_length = math.hypot(*bisector)
    bisector = (bisector[0] / bisector_length, bisector[1] / bisector_length)
    centre: Point2 = (
        cx + bisector[0] * radius / math.sin(theta / 2.0),
        cy + bisector[1] * radius / math.sin(theta / 2.0),
    )
    # Die Wölbung zeigt zur Ecke hin: der Punkt des Kreises, der ihr am
    # nächsten liegt. Damit läuft der Bogen auf der kurzen Seite.
    via: Point2 = (centre[0] - bisector[0] * radius, centre[1] - bisector[1] * radius)
    stored = arc_through(touch_u, touch_v, via)
    if stored is None:
        raise ValidationError(
            "radius",
            _("Aus diesem Radius wird an dieser Ecke kein Bogen."),
            value=radius,
        )

    offsets = offsets_of(sketch)
    first_flat = offsets[corner.first[0]] + corner.first[1]
    second_flat = offsets[corner.second[0]] + corner.second[1]
    first_line = (offsets[corner.first[0]], offsets[corner.first[0]] + 1)
    second_line = (offsets[corner.second[0]], offsets[corner.second[0]] + 1)
    arc_begin = len(points)
    arc_centre, arc_start, arc_end = arc_begin, arc_begin + 1, arc_begin + 2
    # ``arc_through`` darf Anfang und Ende tauschen — welches Ende an welcher
    # Linie sitzt, sagt der Ort.
    start_at_u = math.dist(stored[1], touch_u) <= math.dist(stored[2], touch_u)
    end_of_u = arc_start if start_at_u else arc_end
    end_of_v = arc_end if start_at_u else arc_start

    elements = _shortened(sketch, corner, touch_u, touch_v)
    arc = SketchElement("arc", stored)
    constraints = (
        *_without_corner_joint(sketch, first_flat, second_flat),
        SketchConstraint("coincident", (first_flat, end_of_u)),
        SketchConstraint("coincident", (second_flat, end_of_v)),
        SketchConstraint("perpendicular", (*first_line, arc_centre, end_of_u)),
        SketchConstraint("perpendicular", (*second_line, arc_centre, end_of_v)),
        SketchConstraint("radius", (arc_centre, arc_start), written_measure(radius)),
    )
    return replace(sketch, elements=(*elements, arc), constraints=constraints)


def chamfer(sketch: Sketch, points: Sequence[Point2], flat: int, distance: float) -> Sketch:
    """Bricht die Ecke an ``flat`` mit einer Schräge, ``distance`` von der
    Ecke entfernt auf beiden Linien.

    Beide Linien werden um das Maß gekürzt, dazwischen liegt eine gerade
    Kante — die Fase. Sie bleibt an beiden Enden verbunden und trägt ihre
    Länge als Maß; ihr Winkel bleibt frei, denn ein Maß für „gleich weit von
    einer Ecke, die es nicht mehr gibt" kennt die Bedingungsliste nicht.
    Gezogen wird ein gefastes Rechteck damit weiter als Ganzes, und wer die
    Fase schräger will, zieht an ihrem Ende.
    """
    require_positive("distance", distance)
    corner = corner_at(sketch, points, flat)
    if corner is None:
        raise ValidationError(
            "element",
            _("Hier treffen sich keine zwei Linien — eine Fase braucht eine Ecke aus zwei Linien."),
        )
    u, v, length_u, length_v = _corner_directions(sketch, points, corner)
    _corner_angle(u, v)
    room = min(length_u, length_v)
    if distance >= room - EPS_SKETCH:
        raise ValidationError(
            "distance",
            _(
                "Die Fase ist zu groß für diese Ecke — sie muss kleiner sein als {most}.",
                most=written_measure(room),
            ),
            value=distance,
            constraint="maximum",
            values={"most": written_measure(room)},
        )
    cx, cy = corner.spot
    cut_u: Point2 = (cx + u[0] * distance, cy + u[1] * distance)
    cut_v: Point2 = (cx + v[0] * distance, cy + v[1] * distance)

    offsets = offsets_of(sketch)
    first_flat = offsets[corner.first[0]] + corner.first[1]
    second_flat = offsets[corner.second[0]] + corner.second[1]
    edge_begin = len(points)
    elements = _shortened(sketch, corner, cut_u, cut_v)
    edge = SketchElement("line", (cut_u, cut_v))
    constraints = (
        *_without_corner_joint(sketch, first_flat, second_flat),
        SketchConstraint("coincident", (first_flat, edge_begin)),
        SketchConstraint("coincident", (second_flat, edge_begin + 1)),
        SketchConstraint(
            "distance", (edge_begin, edge_begin + 1), written_measure(math.dist(cut_u, cut_v))
        ),
    )
    return replace(sketch, elements=(*elements, edge), constraints=constraints)


#: Die Bedingungsarten, die ein Maß tragen und deshalb mitskaliert werden
#: müssen. Alles andere — Deckung, Parallelität, Tangente — ist eine Aussage
#: über Lage und Richtung und bleibt unter einer Ähnlichkeitsabbildung wahr.
MEASURED_KINDS: frozenset[str] = frozenset({"distance", "radius", "diameter"})


def _drawing_box(sketch: Sketch) -> tuple[Point2, Point2] | None:
    """Das Hüllrechteck dessen, was gezeichnet ist — Kreise, Bögen und
    Ellipsen ganz.

    Die Punkte allein sagen es nicht: Ein Kreis führt Mitte und einen
    Randpunkt, ein Bogen Mitte, Anfang und Ende. Gemessen wird deshalb am
    Rand selbst — Kreis bis zu seinem Radius in jeder Achsenrichtung, Bogen
    über seine Enden und die Achsenpunkte, die in seiner Spanne liegen,
    Ellipse und Ellipsenbogen über ihre Scheitel in x und y.
    Hilfsgeometrie zählt mit, wenn sonst nichts da ist: Auch eine Zeichnung
    aus lauter Hilfslinien hat eine Mitte. ``None`` für eine leere Skizze.
    """
    shaping = [element for element in sketch.elements if not element.construction]
    found: list[Point2] = []
    for element in shaping or list(sketch.elements):
        if element.kind == "circle":
            (cx, cy), rim = element.points
            radius = math.dist((cx, cy), rim)
            found.extend(((cx - radius, cy - radius), (cx + radius, cy + radius)))
        elif element.kind == "arc":
            centre, start, end = element.points
            radius = math.dist(centre, start)
            found.extend((start, end))
            begin = math.atan2(start[1] - centre[1], start[0] - centre[0])
            sweep = arc_sweep(centre, start, end)
            for quarter in range(4):
                angle = quarter * math.pi / 2.0
                if (angle - begin) % (2.0 * math.pi) <= sweep:
                    found.append(
                        (
                            centre[0] + radius * (1.0, 0.0, -1.0, 0.0)[quarter],
                            centre[1] + radius * (0.0, 1.0, 0.0, -1.0)[quarter],
                        )
                    )
        elif element.kind in ELLIPSE_KINDS:
            # Die Scheitel, die das Stück überstreicht — an einer gedrehten
            # Ellipse liegen sie auf keinem ihrer gespeicherten Punkte.
            found.extend(ellipse_element_extremes(element))
        else:
            found.extend(element.points)
    if not found:
        return None
    return (
        (min(x for x, _y in found), min(y for _x, y in found)),
        (max(x for x, _y in found), max(y for _x, y in found)),
    )


def scaled(sketch: Sketch, factor: float) -> tuple[Sketch, tuple[str, ...]]:
    """Die Skizze um *factor* vergrößern — Punkte **und** Maße.

    Der Grund, aus dem das hier steht und nicht in der Oberfläche: Die Punkte
    allein zu strecken genügt nicht. Ein ``distance``-Maß von 50 zieht der
    Löser beim nächsten Lauf wieder auf 50 zusammen, und die Zeichnung springt
    in ihre alte Größe zurück — sichtbar erst nach dem Schließen des Dialogs.
    Skaliert wird deshalb um die **Mitte der Zeichnung**, damit sie an Ort und
    Stelle bleibt, und jedes Maß wandert mit.

    **Die Mitte der Geometrie, nicht der Schwerpunkt ihrer Punkte**
    (:func:`_drawing_box`). Hier stand der Schwerpunkt, und ein Kreis trägt
    Mitte **und** einen Randpunkt: Sein Punktschwerpunkt liegt auf halbem
    Radius neben der Mitte, und ein Kreis um den Ursprung wanderte beim
    Strecken um ein Viertel des Zuwachses zur Seite — gemessen am 22.09.2026
    im Dialog *Zwischen zwei Umrissen aufspannen*, Kreis Ø 30 um (0 | 0) auf
    Ø 40 um (-2,5 | 0).

    **Ein Maß an einem Projektparameter bleibt stehen.** Ein Wert wie
    ``=@breite`` ist die ausgesprochene Absicht des Nutzers (Regel 8); ihn
    still durch eine Zahl zu ersetzen, nähme ihm den Parameter, ohne es zu
    sagen. Solche Maße kommen als zweiter Rückgabewert zurück — wer skaliert,
    weiß damit, dass die Zeichnung nicht vollständig gefolgt ist, und kann es
    sagen, statt eine Größe zu versprechen, die nicht eintritt.

    ``factor`` muss endlich und größer als null sein: Null faltet die
    Zeichnung auf einen Punkt, negativ spiegelt sie, und beides ist keine
    Größenänderung.
    """
    if not math.isfinite(factor) or factor <= 0.0:
        raise ValidationError(
            title=_("Die Zeichnung lässt sich nicht auf dieses Maß bringen."),
            field="factor",
            detail=_("Der Faktor muss endlich und größer als null sein."),
            constraint="positive",
            values={"factor": str(factor)},
        )

    box = _drawing_box(sketch)
    if box is None:
        return sketch, ()
    (low_x, low_y), (high_x, high_y) = box
    centre_x = (low_x + high_x) / 2.0
    centre_y = (low_y + high_y) / 2.0

    def pulled(point: Point2) -> Point2:
        return (
            centre_x + (point[0] - centre_x) * factor,
            centre_y + (point[1] - centre_y) * factor,
        )

    elements = tuple(
        replace(element, points=tuple(pulled(point) for point in element.points))
        for element in sketch.elements
    )

    kept: list[str] = []
    constraints: list[SketchConstraint] = []
    for constraint in sketch.constraints:
        if constraint.kind not in MEASURED_KINDS or not constraint.value.strip():
            constraints.append(constraint)
            continue
        try:
            measure = float(constraint.value)
        except ValueError:
            # Ein Ausdruck, kein blanker Wert — er hängt an einem Parameter
            # oder rechnet selbst. Beides bleibt, wie es ist.
            kept.append(constraint.value)
            constraints.append(constraint)
            continue
        constraints.append(replace(constraint, value=written_measure(measure * factor)))

    return replace(sketch, elements=elements, constraints=tuple(constraints)), tuple(kept)


def polygon_at(centre: Point2, corner: Point2, corners: int) -> Sketch:
    """Ein regelmäßiges Vieleck aus Mitte und einer Ecke — **frei**, nicht
    bemaßt (§30.1).

    Die Form entsteht mit zwei Klicks, und deshalb hält sie nur, was diese
    zwei Klicks aussagen: Sie ist regelmäßig, sie liegt um diese Mitte, und
    sie geht durch diese Ecke. Mitte und Größe bleiben Freiheitsgrade, bis
    jemand sie bemaßt — dieselbe Entscheidung wie beim gezeichneten Rechteck
    („gezeichnet heißt frei, getippt heißt bemaßt").

    **Regelmäßig gehalten wird über einen Hilfskreis**, nicht über Winkel an
    den Ecken. Beides wäre möglich; der Hilfskreis hat zwei Vorteile, und
    beide sind gemessen:

    * **Er ist unabhängig.** „Alle Ecken auf einem Kreis" sind ``corners - 1``
      Gleichungen, „alle Seiten gleich lang" weitere ``corners - 1`` — zusammen
      genau so viele, wie ein geschlossenes Vieleck an Formfreiheiten hat.
      Über Winkel geht die Rechnung nicht auf: Ein geschlossener Zug bringt
      seine letzten beiden Winkel selbst mit, und wer sie trotzdem hinschreibt,
      bekommt „Eine Bedingung legt fest, was schon festliegt".
    * **Er ist der Griff, den man sucht.** Der Kreis ist der Umkreis; sein
      Radius ist das Maß, das an einem Sechseck jeder meint, und er hat einen
      Mittelpunkt, an dem die Form hängt. Ohne ihn gäbe es in der Zeichnung
      keinen Punkt, der „die Mitte" wäre.

    Gemessen an der fertigen Form: ``free_dof`` ist **3** — Mitte und Radius.
    Die Drehung ist die Eichfreiheit des Randpunkts auf seinem Kreis, und die
    zählt ``solver._rank_with_circle_gauges`` seit je nicht mit.

    Flache Punktindizes: Linie ``k`` hat ``(2k, 2k + 1)``, der Hilfskreis
    ``(2·corners, 2·corners + 1)`` — Mitte und Randpunkt.
    """
    if not 3 <= corners <= 64:
        raise ValidationError(
            "corners",
            _("Ein Vieleck braucht zwischen drei und vierundsechzig Ecken."),
            value=corners,
            constraint="corner_count",
        )
    radius = math.dist(centre, corner)
    require_positive("radius", radius)
    start = math.atan2(corner[1] - centre[1], corner[0] - centre[0])
    vertices = [
        (
            centre[0] + radius * math.cos(start + 2.0 * math.pi * k / corners),
            centre[1] + radius * math.sin(start + 2.0 * math.pi * k / corners),
        )
        for k in range(corners)
    ]
    elements = [
        SketchElement("line", (vertices[k], vertices[(k + 1) % corners])) for k in range(corners)
    ]
    elements.append(SketchElement("circle", (centre, vertices[0]), construction=True))
    hub = 2 * corners
    rim = hub + 1
    constraints: list[SketchConstraint] = [
        SketchConstraint("coincident", (2 * k + 1, (2 * k + 2) % (2 * corners)))
        for k in range(corners)
    ]
    # Der Randpunkt des Hilfskreises **ist** die erste Ecke. Ein eigener Punkt
    # daneben wäre ein zweiter Ort für dieselbe Aussage.
    constraints.append(SketchConstraint("coincident", (rim, 0)))
    constraints.extend(SketchConstraint("equal", (hub, rim, hub, 2 * k)) for k in range(1, corners))
    constraints.extend(
        SketchConstraint("equal", (0, 1, 2 * k, 2 * k + 1)) for k in range(1, corners)
    )
    return Sketch(plane="plane:xy", elements=tuple(elements), constraints=tuple(constraints))


def slot_between(first: Point2, second: Point2, width: float) -> Sketch:
    """Ein Langloch zwischen zwei Mittelpunkten — **frei**, nicht bemaßt.

    Zwei Flanken und zwei Halbkreisbögen, gegen den Uhrzeigersinn: untere
    Flanke, Bogen um ``second``, obere Flanke, Bogen um ``first``. „Unten" und
    „oben" gelten dabei quer zur Verbindung der beiden Mittelpunkte, in jeder
    Richtung gleich — das Langloch der Grundformen liegt in X, dieses liegt so,
    wie geklickt wurde.

    **Die Flanken hängen als Senkrechte am Radiusstrahl** und nicht als
    Tangenten. Der Grund steht bei :func:`fillet`, und er gilt hier
    unverändert: Das Bogenende liegt per Deckung *auf* der Flanke, dort ist die
    Tangentenbedingung ein doppelter Nullpunkt, ihre Ableitung null und die
    Jacobimatrix singulär. ``perpendicular`` sagt dasselbe mit einer Ableitung,
    die trägt.

    Beide Enden gleich rund hält **eine** ``equal``-Bedingung zwischen den
    Radien. Ohne sie wäre das Langloch an einem Ende dicker als am anderen und
    hieße trotzdem so.

    Gemessen: ``free_dof`` ist **5** — beide Mittelpunkte und die Breite. Mit
    Festpunkt, Mittenabstand und Breite bleibt die Drehung um den festen
    Mittelpunkt, wie bei jeder gezeichneten Form.

    Flache Punktindizes: untere Flanke ``(0, 1)``, rechter Bogen
    ``(2 Mitte, 3 Anfang, 4 Ende)``, obere Flanke ``(5, 6)``, linker Bogen
    ``(7 Mitte, 8 Anfang, 9 Ende)`` — dieselbe Reihenfolge wie
    ``shapes.slot``.
    """
    require_positive("width", width)
    reach = math.dist(first, second)
    require_positive("length", reach)
    radius = width / 2.0
    along = ((second[0] - first[0]) / reach, (second[1] - first[1]) / reach)
    across = (-along[1], along[0])

    def beside(point: Point2, sideways: float) -> Point2:
        return (point[0] + across[0] * sideways, point[1] + across[1] * sideways)

    low_first = beside(first, -radius)
    low_second = beside(second, -radius)
    high_second = beside(second, radius)
    high_first = beside(first, radius)
    elements = (
        SketchElement("line", (low_first, low_second)),
        SketchElement("arc", (second, low_second, high_second)),
        SketchElement("line", (high_second, high_first)),
        SketchElement("arc", (first, high_first, low_first)),
    )
    constraints = (
        SketchConstraint("coincident", (1, 3)),
        SketchConstraint("coincident", (4, 5)),
        SketchConstraint("coincident", (6, 8)),
        SketchConstraint("coincident", (9, 0)),
        SketchConstraint("equal", (2, 3, 7, 8)),
        SketchConstraint("perpendicular", (0, 1, 2, 3)),
        SketchConstraint("perpendicular", (5, 6, 2, 4)),
        SketchConstraint("perpendicular", (5, 6, 7, 8)),
        SketchConstraint("perpendicular", (0, 1, 7, 9)),
    )
    return Sketch(plane="plane:xy", elements=elements, constraints=constraints)


#: Wie viele Löcher ein gezeichnetes Lochbild mindestens hat — eines ist
#: ein Kreis und kein Muster — und wie viele der Lochkreis höchstens trägt.
LEAST_PATTERN_HOLES: Final = 2
MOST_BOLT_CIRCLE_HOLES: Final = 64


def hole_grid_between(
    first: Point2, opposite: Point2, columns: int, rows: int, hole_diameter: float
) -> Sketch:
    """Ein Lochraster aus zwei Klicks — **frei**, nicht bemaßt (§30.1).

    Der erste Klick setzt die Mitte des ersten Lochs, der zweite die Mitte
    des gegenüberliegenden; Spalten und Zeilen kommen aus der Leiste, die
    Abstände folgen aus dem Zug — in x und y getrennt, so wie gezogen wurde.
    Bis zum 16.09.2026 war das Lochraster ein Menüeintrag mit festen Maßen
    („4 mal 3, Abstand 10"), ohne Vorschau und ohne Feld; Robert wollte es
    „genauso bauen" wie Vieleck und Langloch.

    **Was das Raster zusammenhält, sind Bedingungen zwischen Mitten, keine
    Festpunkte.** Die Löcher des Menüs trugen je einen ``fixed`` und je ein
    Radiusmaß — bestimmt, aber unverschiebbar. Hier hält jede Zeile
    ``horizontal``, jede Spalte ``vertical``, die Abstände der ersten Zeile
    und der ersten Spalte ``equal``, und alle Radien ``equal`` zum ersten.
    Damit ist das Raster starr bis auf seine Lage und seine zwei Abstände:
    Gemessen ist ``free_dof`` **5** bei 4 mal 3 — Lage, zwei Abstände, ein
    Radius; eine Spalte allein hat einen Abstand weniger. Den Durchmesser
    bemaßt die Leiste, wie die Breite des Langlochs; eine getippte Zahl
    bemaßt beide Abstände.

    Flache Punktindizes: Loch ``k`` (Zeile ``j``, Spalte ``i``,
    ``k = j · columns + i``) hat Mitte ``2k`` und Randpunkt ``2k + 1``.
    """
    if type(columns) is not int or type(rows) is not int or columns < 1 or rows < 1:
        raise ValidationError(
            "columns",
            _("Wählen Sie mindestens eine ganze Reihe und Spalte."),
            constraint="pattern_count",
        )
    if columns * rows < LEAST_PATTERN_HOLES:
        raise ValidationError(
            "columns",
            _("Ein Muster braucht mindestens zwei Elemente."),
            value=columns * rows,
            constraint="pattern_count",
        )
    require_positive("hole_diameter", hole_diameter)
    step_x = (opposite[0] - first[0]) / (columns - 1) if columns > 1 else 0.0
    step_y = (opposite[1] - first[1]) / (rows - 1) if rows > 1 else 0.0
    # **Zwei Klicks am selben Fleck und zwei Klicks in einer Flucht sind zwei
    # Lagen**, und nur die erste heißt „die Klicks liegen aufeinander". Wer
    # für ein Raster aus vier Spalten und drei Zeilen senkrecht unter den
    # ersten Klick klickte, las genau diesen Satz — die Klicks lagen zwanzig
    # Millimeter auseinander, nur eben ohne Abstand quer (Durchsicht
    # 22.09.2026).
    lacks_x = columns > 1 and abs(step_x) <= EPS_SKETCH
    lacks_y = rows > 1 and abs(step_y) <= EPS_SKETCH
    if lacks_x and lacks_y:
        require_positive("spacing", 0.0)
    if lacks_x or lacks_y:
        raise ValidationError(
            "spacing",
            _(
                "Das Raster braucht Abstand in beiden Richtungen — der zweite Klick liegt "
                "in einer Flucht mit dem ersten. Schräg gegenüber klicken oder Spalten "
                "beziehungsweise Zeilen in der Leiste auf eins stellen."
            ),
            value=0.0,
            constraint="grid_in_line",
        )
    tightest = min(step for step in (abs(step_x), abs(step_y)) if step > 0.0)
    if hole_diameter >= tightest:
        raise ValidationError(
            "hole_diameter",
            _("Die Löcher sind mindestens so groß wie ihr Abstand — sie überschneiden sich."),
            value=hole_diameter,
            constraint="hole_fits",
        )
    radius = hole_diameter / 2.0
    centres = [
        (first[0] + i * step_x, first[1] + j * step_y) for j in range(rows) for i in range(columns)
    ]
    elements = tuple(
        SketchElement("circle", (centre, (centre[0] + radius, centre[1]))) for centre in centres
    )

    def at(i: int, j: int) -> int:
        return 2 * (j * columns + i)

    constraints: list[SketchConstraint] = [
        SketchConstraint("equal", (0, 1, at(i, j), at(i, j) + 1))
        for j in range(rows)
        for i in range(columns)
        if (i, j) != (0, 0)
    ]
    constraints.extend(
        SketchConstraint("horizontal", (at(i, j), at(i + 1, j)))
        for j in range(rows)
        for i in range(columns - 1)
    )
    constraints.extend(
        SketchConstraint("vertical", (at(i, j), at(i, j + 1)))
        for i in range(columns)
        for j in range(rows - 1)
    )
    constraints.extend(
        SketchConstraint("equal", (at(0, 0), at(1, 0), at(i, 0), at(i + 1, 0)))
        for i in range(1, columns - 1)
    )
    constraints.extend(
        SketchConstraint("equal", (at(0, 0), at(0, 1), at(0, j), at(0, j + 1)))
        for j in range(1, rows - 1)
    )
    return Sketch(plane="plane:xy", elements=elements, constraints=tuple(constraints))


def bolt_circle_at(centre: Point2, first_hole: Point2, count: int, hole_diameter: float) -> Sketch:
    """Ein Lochkreis aus zwei Klicks — **frei**, nicht bemaßt (§30.1).

    Der erste Klick setzt die Mitte, der zweite die Mitte des ersten Lochs;
    die Anzahl kommt aus der Leiste. Wie beim Vieleck hält ein **Hilfskreis**
    die Form: Er ist der Teilkreis, sein Randpunkt *ist* die Mitte des ersten
    Lochs, alle weiteren Mitten liegen per ``equal`` auf ihm, und gleiche
    Sehnen zwischen Nachbarn verteilen sie gleichmäßig — bei zwei Löchern ist
    die Mitte ihr ``midpoint``, denn zwei Punkte haben nur eine Sehne. Alle
    Radien hängen ``equal`` am ersten.

    Gemessen ist ``free_dof`` **4** — Mitte, Teilkreis und Lochradius; die
    Drehung ist die Eichfreiheit des Randpunkts auf seinem Kreis, die
    ``solver._rank_with_circle_gauges`` nicht mitzählt. Den Durchmesser
    bemaßt die Leiste, eine getippte Zahl den Teilkreis.

    Flache Punktindizes: Loch ``k`` hat Mitte ``2k`` und Randpunkt ``2k + 1``,
    der Teilkreis ``(2 · count, 2 · count + 1)`` — Mitte und Randpunkt.
    """
    if type(count) is not int or count < LEAST_PATTERN_HOLES:
        raise ValidationError(
            "count",
            _("Ein Muster braucht mindestens zwei Elemente."),
            value=count,
            constraint="pattern_count",
        )
    if count > MOST_BOLT_CIRCLE_HOLES:
        raise ValidationError(
            "count",
            _("Ein Lochkreis trägt höchstens vierundsechzig Löcher."),
            value=count,
            constraint="pattern_count",
        )
    require_positive("hole_diameter", hole_diameter)
    pitch_radius = math.dist(centre, first_hole)
    require_positive("radius", pitch_radius)
    chord = 2.0 * pitch_radius * math.sin(math.pi / count)
    if hole_diameter >= chord:
        raise ValidationError(
            "hole_diameter",
            _("Die Löcher sind mindestens so groß wie ihr Abstand — sie überschneiden sich."),
            value=hole_diameter,
            constraint="hole_fits",
        )
    radius = hole_diameter / 2.0
    start = math.atan2(first_hole[1] - centre[1], first_hole[0] - centre[0])
    centres = [
        (
            centre[0] + pitch_radius * math.cos(start + 2.0 * math.pi * k / count),
            centre[1] + pitch_radius * math.sin(start + 2.0 * math.pi * k / count),
        )
        for k in range(count)
    ]
    elements = [SketchElement("circle", (hole, (hole[0] + radius, hole[1]))) for hole in centres]
    elements.append(SketchElement("circle", (centre, first_hole), construction=True))
    hub = 2 * count
    rim = hub + 1
    # Der Randpunkt des Teilkreises **ist** die Mitte des ersten Lochs — ein
    # eigener Punkt daneben wäre ein zweiter Ort für dieselbe Aussage.
    constraints: list[SketchConstraint] = [SketchConstraint("coincident", (rim, 0))]
    if count == 2:
        # Zwei Löcher haben nur eine Sehne, und die geht durch die Mitte:
        # ``midpoint`` sagt beides — gegenüber und auf dem Teilkreis — in
        # zwei Gleichungen. Ein ``equal`` zum Teilkreis dazu legte fest, was
        # damit schon festliegt, und der Löser meldete genau das.
        constraints.append(SketchConstraint("midpoint", (hub, 0, 2)))
    else:
        constraints.extend(
            SketchConstraint("equal", (hub, rim, hub, 2 * k)) for k in range(1, count)
        )
        constraints.extend(
            SketchConstraint("equal", (0, 2, 2 * k, 2 * ((k + 1) % count))) for k in range(1, count)
        )
    constraints.extend(SketchConstraint("equal", (0, 1, 2 * k, 2 * k + 1)) for k in range(1, count))
    return Sketch(plane="plane:xy", elements=tuple(elements), constraints=tuple(constraints))


def written_measure(value: float) -> str:
    """Ein Maß so schreiben, wie es in der Projektdatei steht.

    Punkt als Trennzeichen (der Kern rechnet und schreibt so, Regel 6), und
    ohne die Nachkommastellen, die aus der Fließkommarechnung übrig bleiben:
    ``50 * 1.2`` ergibt ``60.00000000000001``, und das stünde danach im Feld.
    Sechs **Nachkommastellen** sind feiner, als jeder Drucker auflöst, und
    lassen ``0.05`` unversehrt.

    **Fest geschrieben und nicht mit ``:g``.** Hier stand ``f"{wert:g}"``, und
    das sind sechs *gültige Ziffern*, nicht sechs Nachkommastellen: Aus einem
    auf 1234,5678 mm gestreckten Maß wurde ``1234.57``, aus 123,4567 wurde
    ``123.457``. Und unter 10⁻⁴ oder ab einer Million schrieb ``:g`` eine
    Exponentenzahl (``5e-05``, ``2e+06``), die die Grammatik aus §13 nicht
    liest — die Zeichnung ließ sich danach nicht mehr lösen (Durchsicht
    22.09.2026). Dieselbe Regel wie ``shapes._number``, nur ohne die Nullen am
    Ende.
    """
    text = f"{round(value, 6):.6f}".rstrip("0").rstrip(".")
    # ``-0.000000`` wird oben zu ``-0``, und das ist dieselbe Null.
    return "0" if text in ("", "-0") else text
