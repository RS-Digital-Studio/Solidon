"""Skizzen ändern: Trimmen, Verlängern, Versetzen, Spiegeln (Bauplan §30.1).

Die vier Werkzeuge, ohne die jede Kontur Handarbeit ist, die nicht aus einer
Grundform kommt. Fusion hat sie in einer eigenen Gruppe; Solidon hatte sie
gar nicht — man konnte zeichnen und bemaßen, aber nichts kürzen.

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
from dataclasses import replace

from app.core.errors import ValidationError
from app.core.types import Point2, Sketch, SketchConstraint, SketchElement
from app.i18n import _

#: Wie nah zwei Punkte sein müssen, um als derselbe zu gelten. Keine Toleranz
#: im Sinne von Regel 7: das ist die Auflösung einer Zeichnung, keine Passung.
EPS_SKETCH = 1e-9

#: Wie weit ein Schnittpunkt außerhalb der Strecke liegen darf und trotzdem als
#: „auf ihr" gilt. In Anteilen der Streckenlänge.
_ON_SEGMENT = 1e-9


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

    Sortiert nach ihrer Lage auf der Linie. Nur für Linien — ein Bogen, den
    man trimmt, ist eine eigene Rechnung, und ihn hier stillschweigend zu
    übergehen wäre schlimmer, als ihn abzulehnen.
    """
    element = sketch.elements[index]
    if element.kind != "line":
        raise ValidationError(
            "element",
            _("Trimmen und Verlängern arbeiten an Linien — dieses Element ist eine andere Art."),
        )
    line = (element.points[0], element.points[1])

    found: list[Point2] = []
    for other_index, other in enumerate(sketch.elements):
        if other_index == index:
            continue
        if other.kind == "line":
            point = line_intersection(line, (other.points[0], other.points[1]))
            if (
                point is not None
                and 0.0 <= _parameter_on((other.points[0], other.points[1]), point) <= 1.0
            ):
                found.append(point)
        elif other.kind == "circle":
            centre = other.points[0]
            edge = other.points[1]
            radius = math.hypot(edge[0] - centre[0], edge[1] - centre[1])
            found.extend(circle_intersections(line, centre, radius))

    return sorted(found, key=lambda point: _parameter_on(line, point))


# --- Die vier Werkzeuge ----------------------------------------------------------


def trim(sketch: Sketch, index: int, at: Point2) -> Sketch:
    """Kürzt eine Linie an der Kreuzung, die dem Klick am nächsten liegt.

    Weg ist das Stück, auf das geklickt wurde — genau wie in jedem CAD. Liegt
    der Klick jenseits aller Kreuzungen, fällt die ganze Linie weg; auch das
    ist die übliche Antwort, und sie ist rücknehmbar.
    """
    element = sketch.elements[index]
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

    if before and after:
        # Zwischen zwei Kreuzungen geklickt: das Stück dazwischen fällt weg,
        # und aus einer Linie werden zwei.
        return _replace_element(
            sketch,
            index,
            (
                SketchElement(kind="line", points=(line[0], before[-1])),
                SketchElement(kind="line", points=(after[0], line[1])),
            ),
        )
    if after:
        return _replace_element(
            sketch, index, (SketchElement(kind="line", points=(after[0], line[1])),)
        )
    if before:
        return _replace_element(
            sketch, index, (SketchElement(kind="line", points=(line[0], before[-1])),)
        )
    return _replace_element(sketch, index, ())


def extend(sketch: Sketch, index: int, at: Point2) -> Sketch:
    """Verlängert eine Linie bis zur nächsten Kante in Klickrichtung.

    Geklickt wird auf die Hälfte, die wachsen soll — dieselbe Geste wie beim
    Trimmen, nur andersherum.
    """
    element = sketch.elements[index]
    line = (element.points[0], element.points[1])
    reach = _reachable(sketch, index, line)
    if not reach:
        raise ValidationError(
            "element",
            _("In dieser Richtung liegt keine Kante, bis zu der verlängert werden könnte."),
        )

    towards_end = _parameter_on(line, at) >= 0.5
    candidates = [point for point in reach if (_parameter_on(line, point) > 1.0) == towards_end]
    if not candidates:
        raise ValidationError(
            "element",
            _("In dieser Richtung liegt keine Kante — auf der anderen Hälfte gibt es eine."),
        )

    target = min(
        candidates, key=lambda point: abs(_parameter_on(line, point) - (1.0, 0.0)[not towards_end])
    )
    points = (line[0], target) if towards_end else (target, line[1])
    return _replace_element(sketch, index, (SketchElement(kind="line", points=points),))


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
                SketchElement(kind="circle", points=(centre, (centre[0] + radius, centre[1])))
            )

    if not copies:
        raise ValidationError(
            "element",
            _("Versetzen arbeitet an Linien und Kreisen — ein Bogen wird dabei eine neue Kurve."),
        )
    return replace(sketch, elements=(*sketch.elements, *copies))


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
        copies.append(SketchElement(kind=element.kind, points=points))

    if not copies:
        raise ValidationError(
            "elements",
            _("Nichts ausgewählt — erst die Elemente wählen, dann spiegeln."),
        )
    return replace(sketch, elements=(*sketch.elements, *copies))


# --- Bedingungen umnummerieren ---------------------------------------------------


def _reachable(sketch: Sketch, index: int, line: tuple[Point2, Point2]) -> list[Point2]:
    """Kreuzungen auf der **Geraden**, auch außerhalb der Strecke."""
    found: list[Point2] = []
    for other_index, other in enumerate(sketch.elements):
        if other_index == index or other.kind != "line":
            continue
        point = line_intersection(line, (other.points[0], other.points[1]))
        if point is None:
            continue
        # Der Treffer muss auf der anderen Strecke liegen — eine Kante, die
        # dort aufhört, verlängert nichts.
        if -_ON_SEGMENT <= _parameter_on((other.points[0], other.points[1]), point) <= 1.0:
            found.append(point)
    return found


def _replace_element(sketch: Sketch, index: int, fresh: tuple[SketchElement, ...]) -> Sketch:
    """Tauscht ein Element gegen keines, eines oder zwei — mit umnummerierten
    Bedingungen.

    Die Bedingungen des ersetzten Elements fallen weg: seine Punkte sind
    andere geworden, und eine Bemaßung auf einer gekürzten Linie behauptet
    eine Länge, die nicht mehr stimmt. Alle übrigen rücken auf.
    """
    starts = offsets_of(sketch)
    begin = starts[index]
    count = len(sketch.elements[index].points)
    added = sum(len(element.points) for element in fresh)

    mapping: dict[int, int] = {}
    for old in range(len(flat_points(sketch))):
        if begin <= old < begin + count:
            continue
        mapping[old] = old if old < begin else old - count + added

    elements = (*sketch.elements[:index], *fresh, *sketch.elements[index + 1 :])
    constraints = tuple(
        SketchConstraint(
            entry.kind, tuple(mapping[target] for target in entry.targets), entry.value
        )
        for entry in sketch.constraints
        if all(target in mapping for target in entry.targets)
    )
    return replace(sketch, elements=elements, constraints=constraints)


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

    ``frame`` ist der Rahmen einer Flächenebene oder ``None`` für eine der
    drei Grundebenen. ``mesh`` ist ein ``MeshData`` — nicht typisiert, weil
    dieses Modul sonst die Geometrie-Schicht importieren müsste, nur um einen
    Namen zu nennen.
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

    body = mesh.raw  # type: ignore[attr-defined]
    section = body.section(plane_origin=np.asarray(origin), plane_normal=np.asarray(normal))
    if section is None:
        raise ValidationError(
            "plane",
            _("Diese Ebene schneidet den Körper nicht — dort gibt es keine Kante."),
        )

    added: list[SketchElement] = []
    for entity in section.entities:
        points = section.vertices[entity.points]
        flat = [
            (
                float(np.dot(point - np.asarray(origin), np.asarray(x_axis))),
                float(np.dot(point - np.asarray(origin), np.asarray(y_axis))),
            )
            for point in points
        ]
        for first, second in itertools.pairwise(flat):
            if math.dist(first, second) > EPS_SKETCH:
                added.append(SketchElement(kind="line", points=(first, second), construction=True))

    if not added:
        raise ValidationError(
            "plane",
            _("Der Schnitt ergibt keine Kante, an der sich zeichnen ließe."),
        )
    return replace(sketch, elements=(*sketch.elements, *added))


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
