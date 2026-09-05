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
from app.core.sketch.profile import _flat_curve
from app.core.types import Point2, Sketch, SketchConstraint, SketchElement
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
                SketchElement(
                    kind="line", points=(line[0], before[-1]), construction=element.construction
                ),
                SketchElement(
                    kind="line", points=(after[0], line[1]), construction=element.construction
                ),
            ),
        )
    if after:
        return _replace_element(
            sketch,
            index,
            (
                SketchElement(
                    kind="line", points=(after[0], line[1]), construction=element.construction
                ),
            ),
        )
    if before:
        return _replace_element(
            sketch,
            index,
            (
                SketchElement(
                    kind="line", points=(line[0], before[-1]), construction=element.construction
                ),
            ),
        )
    return _replace_element(sketch, index, ())


def extend(sketch: Sketch, index: int, at: Point2) -> Sketch:
    """Verlängert eine Linie bis zur nächsten Kante in Klickrichtung.

    Geklickt wird auf die Hälfte, die wachsen soll — dieselbe Geste wie beim
    Trimmen, nur andersherum.
    """
    element = sketch.elements[index]
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
    return _replace_element(
        sketch,
        index,
        (SketchElement(kind="line", points=points, construction=element.construction),),
    )


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
        copies.append(replace(element, points=points))

    if not copies:
        raise ValidationError(
            "elements",
            _("Nichts ausgewählt — erst die Elemente wählen, dann spiegeln."),
        )
    return replace(sketch, elements=(*sketch.elements, *copies))


# --- Bedingungen umnummerieren ---------------------------------------------------


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


#: Die Bedingungsarten, die ein Maß tragen und deshalb mitskaliert werden
#: müssen. Alles andere — Deckung, Parallelität, Tangente — ist eine Aussage
#: über Lage und Richtung und bleibt unter einer Ähnlichkeitsabbildung wahr.
MEASURED_KINDS: frozenset[str] = frozenset({"distance", "radius", "diameter"})


def scaled(sketch: Sketch, factor: float) -> tuple[Sketch, tuple[str, ...]]:
    """Die Skizze um *factor* vergrößern — Punkte **und** Maße.

    Der Grund, aus dem das hier steht und nicht in der Oberfläche: Die Punkte
    allein zu strecken genügt nicht. Ein ``distance``-Maß von 50 zieht der
    Löser beim nächsten Lauf wieder auf 50 zusammen, und die Zeichnung springt
    in ihre alte Größe zurück — sichtbar erst nach dem Schließen des Dialogs.
    Skaliert wird deshalb um den **Schwerpunkt der Punkte**, damit die
    Zeichnung an Ort und Stelle bleibt, und jedes Maß wandert mit.

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

    points = [point for element in sketch.elements for point in element.points]
    if not points:
        return sketch, ()
    centre_x = sum(x for x, _y in points) / len(points)
    centre_y = sum(y for _x, y in points) / len(points)

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
        constraints.append(replace(constraint, value=_written(measure * factor)))

    return replace(sketch, elements=elements, constraints=tuple(constraints)), tuple(kept)


def _written(value: float) -> str:
    """Ein Maß so schreiben, wie es in der Projektdatei steht.

    Punkt als Trennzeichen (der Kern rechnet und schreibt so, Regel 6), und
    ohne die Nachkommastellen, die aus der Fließkommarechnung übrig bleiben:
    ``50 * 1.2`` ergibt ``60.00000000000001``, und das stünde danach im Feld.
    Sechs Stellen sind feiner, als jeder Drucker auflöst, und lassen ``0.05``
    unversehrt.
    """
    rounded = round(value, 6)
    return f"{rounded:g}"
