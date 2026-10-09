"""Die Grundformen (Bauplan §30.1, Ausgabestufe eins).

Rechteck, Langloch, Kreis und Vieleck als fertige Skizzen: exakt konstruierte
Punkte plus die Bedingungen, die die Maße tragen. Dialog, CLI und Agent
erzeugen Skizzen ausschließlich hierüber — nie über rohe Punktlisten
(Leitprinzip 5). Der Solver bestätigt die Konstruktion, statt sie zu suchen:
der Startzustand ist bereits die Lösung, ein Lauf kostet Mikrosekunden.

Alle Formen liegen mittig um den Ursprung; wo eine Form hingehört, entscheidet
die Operation, die sie verbraucht.
"""

from __future__ import annotations

import math

from app.core.errors import ValidationError, require_positive
from app.core.types import Point2, Sketch, SketchConstraint, SketchElement
from app.core.units import EPS_GEOM
from app.i18n import _

#: Die Grundformen, die jede Skizzen-Op anbietet — eine Quelle für alle Dialoge.
SHAPE_CHOICES: tuple[str, ...] = ("rectangle", "slot", "circle", "polygon")

#: Die zwei Muster — sie geben **mehrere** Umrisse zurück und nicht einen.
#:
#: Deshalb stehen sie nicht in :data:`SHAPE_CHOICES`: Drehen, Ziehen und
#: Übergang rechnen mit genau einem Querschnitt, und ein Lochkreis um eine
#: Achse gedreht ist kein Bauteil. Angeboten werden sie nur dort, wo mehrere
#: Umrisse ohnehin vorkommen — beim Hochziehen und bei der Tasche.
PATTERN_CHOICES: tuple[str, ...] = ("bolt_circle", "hole_grid")

#: Was Hochziehen und Tasche zur Wahl stellen: beides zusammen.
SHAPE_AND_PATTERN_CHOICES: tuple[str, ...] = SHAPE_CHOICES + PATTERN_CHOICES


def rectangle(length: float, width: float) -> Sketch:
    """Ein Rechteck, Länge in X, Breite in Y.

    Flache Punktindizes: unten (0, 1), rechts (2, 3), oben (4, 5), links (6, 7).
    """
    require_positive("length", length)
    require_positive("width", width)
    half_l, half_w = length / 2.0, width / 2.0
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((-half_l, -half_w), (half_l, -half_w))),
            SketchElement("line", ((half_l, -half_w), (half_l, half_w))),
            SketchElement("line", ((half_l, half_w), (-half_l, half_w))),
            SketchElement("line", ((-half_l, half_w), (-half_l, -half_w))),
        ),
        constraints=(
            SketchConstraint("coincident", (1, 2)),
            SketchConstraint("coincident", (3, 4)),
            SketchConstraint("coincident", (5, 6)),
            SketchConstraint("coincident", (7, 0)),
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("vertical", (2, 3)),
            SketchConstraint("horizontal", (4, 5)),
            SketchConstraint("vertical", (6, 7)),
            SketchConstraint("distance", (0, 1), _number(length)),
            SketchConstraint("distance", (2, 3), _number(width)),
            SketchConstraint("fixed", (0,)),
        ),
    )


def rectangle_between(first: Point2, second: Point2, plane: str = "plane:xy") -> Sketch:
    """Ein achsparalleles Rechteck zwischen zwei Gegenecken, so wie es aufgezogen wurde (RM-559).

    **Bemaßt, nicht frei**, anders als ein Rechteck im Skizzeneditor: Beim
    Aufziehen in der Ansicht gibt es keine Bedingungsknöpfe, und ein Quader
    ist für den Kunden ein Ding mit drei Maßen, die er danach im Schrittdialog
    ändert. Beide Seiten stehen deshalb als Maß, und die **erste Ecke steht
    fest** — dort hat er angesetzt, und ein geändertes Maß wächst von ihr weg.

    Dieselbe Punktfolge wie :func:`rectangle`: unten (0, 1), rechts (2, 3),
    oben (4, 5), links (6, 7), in den Koordinaten der Ebene ``plane``.
    """
    low_x, high_x = sorted((float(first[0]), float(second[0])))
    low_y, high_y = sorted((float(first[1]), float(second[1])))
    width, depth = high_x - low_x, high_y - low_y
    require_positive("length", width)
    require_positive("width", depth)
    # Welcher der vier Eckpunkte die erste Ecke ist: unten links ist Punkt 0,
    # unten rechts 1, oben rechts 3, oben links 5 — je der Anfang einer Seite
    # oder ihr Ende, beide liegen nach den Deckungen an derselben Stelle.
    left = float(first[0]) <= float(second[0])
    bottom = float(first[1]) <= float(second[1])
    anchor = {(True, True): 0, (False, True): 1, (False, False): 3, (True, False): 5}[
        (left, bottom)
    ]
    return Sketch(
        plane=plane,
        elements=(
            SketchElement("line", ((low_x, low_y), (high_x, low_y))),
            SketchElement("line", ((high_x, low_y), (high_x, high_y))),
            SketchElement("line", ((high_x, high_y), (low_x, high_y))),
            SketchElement("line", ((low_x, high_y), (low_x, low_y))),
        ),
        constraints=(
            SketchConstraint("coincident", (1, 2)),
            SketchConstraint("coincident", (3, 4)),
            SketchConstraint("coincident", (5, 6)),
            SketchConstraint("coincident", (7, 0)),
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("vertical", (2, 3)),
            SketchConstraint("horizontal", (4, 5)),
            SketchConstraint("vertical", (6, 7)),
            SketchConstraint("distance", (0, 1), _number(width)),
            SketchConstraint("distance", (2, 3), _number(depth)),
            SketchConstraint("fixed", (anchor,)),
        ),
    )


def circle_around(centre: Point2, diameter: float, plane: str = "plane:xy") -> Sketch:
    """Ein Kreis um eine angeklickte Mitte, mit seinem Durchmesser als Maß (RM-559).

    Die Mitte steht fest, der Durchmesser ist eine ``diameter``-Bedingung —
    dieselbe, die der Skizzeneditor für einen getippten Kreis schreibt; der
    Randpunkt liegt rechts der Mitte. Punkte: Mitte (0), Randpunkt (1).
    """
    require_positive("diameter", diameter)
    x, y = float(centre[0]), float(centre[1])
    return Sketch(
        plane=plane,
        elements=(SketchElement("circle", ((x, y), (x + diameter / 2.0, y))),),
        constraints=(
            SketchConstraint("diameter", (0, 1), _number(diameter)),
            SketchConstraint("fixed", (0,)),
        ),
    )


def simple_shape(sketch: Sketch) -> str | None:
    """``"rectangle"`` oder ``"circle"``, wenn die Zeichnung genau eine dieser Formen ist.

    Gefragt vom Schrittdialog (RM-559, E11): Ein aufgezogener Quader ist für
    den Kunden drei Zahlen, und die bekommt er vorn — *Breite*, *Tiefe* und
    *Höhe* statt eines Umrisses, den er erst im Editor öffnen müsste. Erkannt
    wird an der Geometrie, nicht an der Herkunft: Ein im Editor gezeichnetes
    achsparalleles Rechteck ist dieselbe Sache. Hilfsgeometrie zählt nicht.
    """
    elements = [element for element in sketch.elements if not element.construction]
    if len(elements) == 1 and elements[0].kind == "circle":
        return "circle"
    if len(elements) != 4 or any(element.kind != "line" for element in elements):
        return None
    tolerance = EPS_GEOM
    for element in elements:
        (ax, ay), (bx, by) = element.points
        if not (math.isclose(ax, bx, abs_tol=tolerance) or math.isclose(ay, by, abs_tol=tolerance)):
            return None
        if math.isclose(ax, bx, abs_tol=tolerance) and math.isclose(ay, by, abs_tol=tolerance):
            return None
    # Geschlossen und nicht verzweigt: jeder Endpunkt trifft genau einen anderen.
    ends = [point for element in elements for point in element.points]
    for index, point in enumerate(ends):
        partners = sum(
            1
            for other, candidate in enumerate(ends)
            if other != index
            and math.isclose(point[0], candidate[0], abs_tol=tolerance)
            and math.isclose(point[1], candidate[1], abs_tol=tolerance)
        )
        if partners != 1:
            return None
    return "rectangle"


def held_point(sketch: Sketch) -> Point2 | None:
    """Der eine feste Punkt der Zeichnung — oder nichts, wenn es keinen oder mehrere gibt.

    Um ihn wächst eine aufgezogene Form, wenn ihr Maß im Schrittdialog
    wechselt: die erste Ecke des Rechtecks, die Mitte des Kreises
    (:func:`rectangle_between`, :func:`circle_around`, Bauplan §30.1).
    """
    held = [constraint for constraint in sketch.constraints if constraint.kind == "fixed"]
    if len(held) != 1 or len(held[0].targets) != 1:
        return None
    points = [point for element in sketch.elements for point in element.points]
    index = held[0].targets[0]
    if not 0 <= index < len(points):
        return None
    return points[index]


def slot(length: float, width: float) -> Sketch:
    """Ein Langloch: Gesamtlänge in X, Breite in Y, halbrunde Enden.

    Punkte: untere Linie (0, 1), rechter Bogen (2 Mitte, 3 Anfang, 4 Ende),
    obere Linie (5, 6), linker Bogen (7 Mitte, 8 Anfang, 9 Ende). Beide Bögen
    laufen gegen den Uhrzeigersinn.
    """
    require_positive("length", length)
    require_positive("width", width)
    if length <= width:
        raise ValidationError(
            "length",
            _("Ein Langloch muss länger als breit sein — sonst ist es ein Kreis."),
            value=length,
            constraint="slot_proportion",
        )
    radius = width / 2.0
    half_s = (length - width) / 2.0
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((-half_s, -radius), (half_s, -radius))),
            SketchElement("arc", ((half_s, 0.0), (half_s, -radius), (half_s, radius))),
            SketchElement("line", ((half_s, radius), (-half_s, radius))),
            SketchElement("arc", ((-half_s, 0.0), (-half_s, radius), (-half_s, -radius))),
        ),
        constraints=(
            # Bewusst ohne Horizontal-Bedingungen auf den Flanken: zusammen mit
            # Koinzidenzen, Radien und Mittenabstand wären sie in der
            # symmetrischen Lage linear abhängig, und der Solver lehnt einen
            # überbestimmten Satz ab — zu Recht, auch bei den eigenen Formen.
            SketchConstraint("coincident", (1, 3)),
            SketchConstraint("coincident", (4, 5)),
            SketchConstraint("coincident", (6, 8)),
            SketchConstraint("coincident", (9, 0)),
            SketchConstraint("horizontal", (7, 2)),
            SketchConstraint("distance", (7, 2), _number(length - width)),
            SketchConstraint("distance", (2, 3), _number(width / 2.0)),
            SketchConstraint("distance", (7, 8), _number(width / 2.0)),
            SketchConstraint("fixed", (2,)),
        ),
    )


def circle(diameter: float) -> Sketch:
    """Ein Kreis um den Ursprung. Punkte: Mitte (0), Randpunkt (1)."""
    require_positive("diameter", diameter)
    return Sketch(
        plane="plane:xy",
        elements=(SketchElement("circle", ((0.0, 0.0), (diameter / 2.0, 0.0))),),
        constraints=(
            SketchConstraint("distance", (0, 1), _number(diameter / 2.0)),
            SketchConstraint("fixed", (0,)),
        ),
    )


def polygon(diameter: float, corners: int) -> Sketch:
    """Ein regelmäßiges Vieleck, Durchmesser über die Ecken, eine Kante unten.

    ``corners`` Linien; Punktindizes je Linie ``(2·k, 2·k + 1)``.
    """
    require_positive("diameter", diameter)
    if not 3 <= corners <= 64:
        raise ValidationError(
            "corners",
            _("Ein Vieleck braucht zwischen drei und vierundsechzig Ecken."),
            value=corners,
            constraint="corner_count",
        )
    radius = diameter / 2.0
    side = 2.0 * radius * math.sin(math.pi / corners)
    # Die erste Ecke so gelegt, dass die erste Kante unten waagerecht liegt.
    start_angle = -math.pi / 2.0 - math.pi / corners
    vertices = [
        (
            radius * math.cos(start_angle + 2.0 * math.pi * k / corners),
            radius * math.sin(start_angle + 2.0 * math.pi * k / corners),
        )
        for k in range(corners)
    ]
    elements = tuple(
        SketchElement("line", (vertices[k], vertices[(k + 1) % corners])) for k in range(corners)
    )
    constraints: list[SketchConstraint] = []
    for k in range(corners):
        constraints.append(SketchConstraint("coincident", (2 * k + 1, (2 * k + 2) % (2 * corners))))
        constraints.append(SketchConstraint("distance", (2 * k, 2 * k + 1), _number(side)))
    constraints.append(SketchConstraint("horizontal", (0, 1)))
    constraints.append(SketchConstraint("fixed", (0,)))
    return Sketch(plane="plane:xy", elements=elements, constraints=tuple(constraints))


def _holes(centres: list[Point2], diameter: float) -> Sketch:
    """Kreise gleicher Größe an gegebenen Mittelpunkten, jeder für sich fest.

    Jedes Loch bekommt seinen eigenen Radius als Maß und seinen eigenen
    Festpunkt — damit ist die Skizze bestimmt, ohne dass ein Loch am anderen
    hängt. Das ist die Entscheidung gegen ein assoziatives Muster: die
    Parametrik liegt in Solidon eine Ebene höher (§13, Maße sind Ausdrücke),
    und ein zweiter Mechanismus daneben wäre einer, der mit dem ersten
    auseinanderlaufen kann.
    """
    radius = diameter / 2.0
    elements = tuple(
        SketchElement("circle", (centre, (centre[0] + radius, centre[1]))) for centre in centres
    )
    constraints: list[SketchConstraint] = []
    for index in range(len(centres)):
        centre_point = 2 * index
        constraints.append(
            SketchConstraint("distance", (centre_point, centre_point + 1), _number(radius))
        )
        constraints.append(SketchConstraint("fixed", (centre_point,)))
    return Sketch(plane="plane:xy", elements=elements, constraints=tuple(constraints))


def _at_least_two(field: str, value: int) -> None:
    if value < 2:
        raise ValidationError(
            field,
            _("Ein Muster braucht mindestens zwei Elemente."),
            value=value,
            constraint="pattern_count",
        )


def bolt_circle(pitch_diameter: float, count: int, hole_diameter: float) -> Sketch:
    """Löcher gleichmäßig auf einem Teilkreis — Flansch, Deckel, Nabe.

    Das erste Loch liegt auf der positiven X-Achse; von dort geht es gegen den
    Uhrzeigersinn. Von Hand hieß dieselbe Skizze, jeden Mittelpunkt einzeln
    auszurechnen, mit einem Rechenfehler je Gelegenheit.
    """
    require_positive("pitch_diameter", pitch_diameter)
    require_positive("hole_diameter", hole_diameter)
    _at_least_two("count", count)
    if hole_diameter >= pitch_diameter:
        raise ValidationError(
            "hole_diameter",
            _("Die Löcher sind größer als der Teilkreis, auf dem sie sitzen."),
            value=hole_diameter,
            constraint="hole_fits",
        )
    radius = pitch_diameter / 2.0
    centres = [
        (
            radius * math.cos(2.0 * math.pi * index / count),
            radius * math.sin(2.0 * math.pi * index / count),
        )
        for index in range(count)
    ]
    return _holes(centres, hole_diameter)


def hole_grid(columns: int, rows: int, spacing: float, hole_diameter: float) -> Sketch:
    """Ein Lochraster um den Ursprung — Lüftungsgitter, Steckplatte, Lochblech.

    ``spacing`` ist der Abstand von Mitte zu Mitte, in beiden Richtungen
    derselbe: ein Raster mit zwei Abständen ist zwei Entscheidungen, und die
    zweite braucht selten jemand.
    """
    require_positive("spacing", spacing)
    require_positive("hole_diameter", hole_diameter)
    if columns * rows < 2:
        _at_least_two("columns", columns * rows)
    if columns < 1 or rows < 1:
        _at_least_two("columns", min(columns, rows))
    if hole_diameter >= spacing:
        raise ValidationError(
            "hole_diameter",
            _("Die Löcher sind mindestens so groß wie ihr Abstand — sie überschneiden sich."),
            value=hole_diameter,
            constraint="hole_fits",
        )
    return _holes(grid_centres(columns, rows, spacing), hole_diameter)


def grid_centres(
    columns: int, rows: int, spacing: float, *, origin: Point2 = (0, 0)
) -> list[Point2]:
    """Gemeinsames mittiges Raster für Skizzenmuster und begrenzte Feldschnitte."""
    require_positive("spacing", spacing)
    if any(type(count) is not int or count < 1 for count in (columns, rows)):
        raise ValidationError(
            "columns",
            _("Wählen Sie mindestens eine ganze Reihe und Spalte."),
            constraint="pattern_count",
        )
    if not all(math.isfinite(number) for number in (spacing, *origin)):
        raise ValidationError(
            "origin",
            _("Rasterabstand und Ursprung müssen endliche Zahlen sein."),
            constraint="finite",
        )
    left = origin[0] - (columns - 1) * spacing / 2.0
    bottom = origin[1] - (rows - 1) * spacing / 2.0
    return [
        (left + column * spacing, bottom + row * spacing)
        for row in range(rows)
        for column in range(columns)
    ]


def _number(value: float) -> str:
    """Ein Maß als Ausdruck der Grammatik (§13) — immer dezimal, nie ``1e-05``."""
    return format(float(value), ".9f")
