"""Ellipse, Ellipsenbogen und die neuen Skizzenbedingungen (RM-188 P6.6a/b).

Jede Zahl hier kommt aus einer Formel, die der Prüfling nicht kennt: Die
Fläche einer Ellipse ist π·a·b, ihr Umfang eine Reihe nach Gauß–Kummer, ein
angeschnittener Bogen ein Segment ``a·b/2·(Δ - sin Δ)`` mit eigener
Bogenlänge aus einem Integral, das dieser Test selbst rechnet. Ein Löser, der
die Achsen verdreht, eine Profilbildung, die den Bogen um die falsche Seite
führt, ein Kern, der eine Sehnenkette statt der Kurve baut — jedes davon
fällt an einer dieser Zahlen auf und nicht an einem Wert, den der Code selbst
geliefert hat.

**Die Punkte einer Ellipse** (§9): Mitte, Ende der ersten Achse, Ende der
zweiten Achse. Die zweite steht senkrecht auf der ersten — das ist die eigene
Gleichung des Elements, wie beim Bogen die gleich langen Schenkel. Ein
Ellipsenbogen trägt dazu Anfang und Ende und läuft gegen den Uhrzeigersinn
vom einen zum anderen, wie ein Kreisbogen.
"""

from __future__ import annotations

import math
from itertools import pairwise

import numpy as np
import pytest

from app.core.errors import SketchConflictError, ValidationError
from app.core.sketch import solver
from app.core.sketch.solver import solve_sketch
from app.core.types import Sketch, SketchConstraint, SketchElement
from tests.helpers import assert_sketch_gradients, exact_kernel


def _axes(points: tuple[tuple[float, float], ...]) -> tuple[float, float, float]:
    """Erste Halbachse, zweite Halbachse und die Drehung der ersten in Grad —
    unabhängig vom Prüfling aus den drei Punkten gerechnet."""
    (cx, cy), (mx, my), (nx, ny) = points[:3]
    first = math.hypot(mx - cx, my - cy)
    second = math.hypot(nx - cx, ny - cy)
    return first, second, math.degrees(math.atan2(my - cy, mx - cx))


def _on_ellipse(points: tuple[tuple[float, float], ...], spot: tuple[float, float]) -> float:
    """``x²/a² + y²/b² - 1`` im Achsenrahmen der Ellipse — null heißt: darauf."""
    (cx, cy), (mx, my) = points[:2]
    a, b, _turn = _axes(points)
    ux, uy = (mx - cx) / a, (my - cy) / a
    dx, dy = spot[0] - cx, spot[1] - cy
    along = dx * ux + dy * uy
    across = -dx * uy + dy * ux
    return (along / a) ** 2 + (across / b) ** 2 - 1.0


# --- Das Element im Löser --------------------------------------------------------------


def test_a_free_ellipse_keeps_five_degrees_of_freedom() -> None:
    """Mitte, zwei Halbachsen, eine Drehung: fünf — nicht sechs Koordinaten.

    Die zweite Achse steht senkrecht auf der ersten; ohne diese eigene
    Gleichung zählte die Zeile einen Freiheitsgrad, den die Form nicht hat.
    """
    sketch = Sketch("plane:xy", (SketchElement("ellipse", ((0.0, 0.0), (20.0, 0.0), (0.0, 10.0))),))

    solved = solve_sketch(sketch)

    assert solved.free_dof == 5


def test_a_skewed_second_axis_comes_back_perpendicular() -> None:
    """Gezeichnet schief, gelöst senkrecht.

    Wohin der Löser die Punkte dabei schiebt, ist keine Zusage: Wie beim Bogen
    mit ungleichen Schenkeln findet er eine nahe Lösung, nicht die mit der
    kleinsten Bewegung. Die Zeichenfläche legt die zweite Achse deshalb schon
    beim Klick senkrecht (``SketchCanvas``), und der Fall hier ist der einer
    fremden Datei."""
    sketch = Sketch("plane:xy", (SketchElement("ellipse", ((5.0, 2.0), (25.0, 2.0), (8.0, 12.0))),))

    points = solve_sketch(sketch).elements[0].points
    (cx, cy), (mx, my), (nx, ny) = points
    cosine = ((mx - cx) * (nx - cx) + (my - cy) * (ny - cy)) / (
        math.hypot(mx - cx, my - cy) * math.hypot(nx - cx, ny - cy)
    )

    assert cosine == pytest.approx(0.0, abs=1e-9)


def test_a_measured_turned_ellipse_is_determined() -> None:
    """Fest, zwei Achsmaße und ein Winkel — nichts wackelt mehr.

    Die Achsmaße tragen die **ganzen** Achsen (``diameter``), wie der Kunde
    eine elliptische Öffnung beschreibt: 40 × 20. Die Drehung von 30 Grad
    hängt über ``angle`` an einer festen Hilfslinie.
    """
    turn = math.radians(30.0)
    sketch = Sketch(
        "plane:xy",
        (
            SketchElement(
                "ellipse",
                (
                    (1.0, -1.0),
                    (18.0 * math.cos(turn), 17.0 * math.sin(turn)),
                    (-9.0 * math.sin(turn), 11.0 * math.cos(turn)),
                ),
            ),
            SketchElement("line", ((-30.0, -20.0), (-10.0, -20.0)), construction=True),
        ),
        (
            SketchConstraint("fixed", (0,)),
            SketchConstraint("diameter", (0, 1), "40"),
            SketchConstraint("diameter", (0, 2), "20"),
            SketchConstraint("fixed", (3,)),
            SketchConstraint("fixed", (4,)),
            SketchConstraint("angle", (3, 4, 0, 1), "30"),
        ),
    )

    solved = solve_sketch(sketch)
    a, b, degrees = _axes(solved.elements[0].points)

    assert solved.free_dof == 0
    assert (a, b) == pytest.approx((20.0, 10.0), abs=1e-9)
    assert degrees == pytest.approx(30.0, abs=1e-7)


def test_a_free_elliptical_arc_keeps_seven_degrees_of_freedom() -> None:
    """Die Ellipse mit ihren fünf und zwei Enden, die auf ihr wandern."""
    sketch = Sketch(
        "plane:xy",
        (
            SketchElement(
                "elliptical_arc",
                ((0.0, 0.0), (20.0, 0.0), (0.0, 10.0), (20.0, 0.0), (0.0, 10.0)),
            ),
        ),
    )

    assert solve_sketch(sketch).free_dof == 7


def test_the_ends_of_an_elliptical_arc_land_on_their_ellipse() -> None:
    """Anfang und Ende, gezeichnet neben der Kurve, liegen gelöst auf ihr —
    nachgeprüft an der Ellipsengleichung, nicht an der Gleichung des Lösers."""
    sketch = Sketch(
        "plane:xy",
        (
            SketchElement(
                "elliptical_arc",
                ((0.0, 0.0), (20.0, 0.0), (0.0, 10.0), (15.0, 8.0), (-12.0, 9.5)),
            ),
        ),
    )

    points = solve_sketch(sketch).elements[0].points

    assert _on_ellipse(points, points[3]) == pytest.approx(0.0, abs=1e-8)
    assert _on_ellipse(points, points[4]) == pytest.approx(0.0, abs=1e-8)


@pytest.mark.parametrize("kind", ["ellipse", "elliptical_arc"])
def test_an_ellipse_needs_two_axes_longer_than_zero(kind: str) -> None:
    """Eine Achse der Länge null ist eine Eingabe und kein Programmfehler."""
    points = [(0.0, 0.0), (0.0, 0.0), (0.0, 10.0)]
    if kind == "elliptical_arc":
        points += [(0.0, 10.0), (0.0, -10.0)]
    sketch = Sketch("plane:xy", (SketchElement(kind, tuple(points)),))  # type: ignore[arg-type]

    with pytest.raises(ValidationError) as refused:
        solve_sketch(sketch)

    assert refused.value.constraint == "positive"
    assert refused.value.suggestions


def test_the_wrong_number_of_points_is_refused_for_both_new_kinds() -> None:
    for kind, count in (("ellipse", 2), ("elliptical_arc", 3)):
        points = tuple((float(index), float(index * index)) for index in range(count))
        with pytest.raises(ValidationError) as refused:
            solve_sketch(Sketch("plane:xy", (SketchElement(kind, points),)))  # type: ignore[arg-type]
        assert refused.value.constraint == "point_count"


@pytest.mark.parametrize("kind", ["ellipse", "elliptical_arc"])
def test_a_fully_fixed_ellipse_is_determined_not_redundant(kind: str) -> None:
    """Die Regel des festen Bogens (B28) gilt für jede eigene Gleichung.

    Eine übernommene Kontur nagelt jeden Punkt fest, und wer die Punkte einer
    Ellipse einzeln festlegt, tut dasselbe. Die eigene Gleichung wäre dann die
    siebte Zeile über sechs Koordinaten — „Eine Bedingung legt fest, was schon
    festliegt" über einer Zeichnung, an der nichts zu viel ist. Sie entfällt,
    wenn sie an den gespeicherten Punkten gilt.
    """
    points = [(0.0, 0.0), (20.0, 0.0), (0.0, 10.0)]
    if kind == "elliptical_arc":
        points += [(20.0, 0.0), (0.0, 10.0)]
    sketch = Sketch(
        "plane:xy",
        (SketchElement(kind, tuple(points)),),  # type: ignore[arg-type]
        tuple(SketchConstraint("fixed", (index,)) for index in range(len(points))),
    )

    solved = solve_sketch(sketch)

    assert solved.free_dof == 0


def test_a_fixed_ellipse_with_a_skewed_axis_stays_a_contradiction() -> None:
    """Gilt die eigene Gleichung an den festen Punkten nicht, bleibt sie — und
    der Widerspruch wird gemeldet wie beim festen Bogen."""
    sketch = Sketch(
        "plane:xy",
        (SketchElement("ellipse", ((0.0, 0.0), (20.0, 0.0), (3.0, 10.0))),),
        tuple(SketchConstraint("fixed", (index,)) for index in range(3)),
    )

    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(sketch)

    assert caught.value.suggestions


def test_every_implicit_gradient_of_the_new_curves_matches_central_differences() -> None:
    """Die eigenen Gleichungen von Ellipse und Ellipsenbogen, gegen zentrale
    Differenzen — in allgemeiner, schiefer Lage, damit kein Term null ist."""
    sketch = Sketch(
        "plane:xy",
        (
            SketchElement("ellipse", ((1.3, -0.7), (18.2, 6.1), (-2.9, 9.4))),
            SketchElement(
                "elliptical_arc",
                ((30.1, 4.2), (41.7, 9.9), (27.4, 12.6), (39.8, 13.3), (22.6, 9.1)),
            ),
        ),
    )
    assert_sketch_gradients(sketch, step=1e-6, atol=1e-6)


def test_both_lists_of_element_kinds_stay_the_same() -> None:
    """Der Löser zählt die Punkte je Art, das Einlesen prüft die Art einer
    fremden Datei — eine neue Art gehört an beide Stellen, sonst rechnet der
    Löser, was das Einlesen abweist (dieselbe Falle wie bei den Bedingungen)."""
    from app.core.sketch.serialize import _ELEMENT_KINDS

    assert set(solver._ELEMENT_POINTS) | set(solver._ELEMENT_MINIMUM) == set(_ELEMENT_KINDS)


def test_an_ellipse_and_its_arc_survive_the_text() -> None:
    """Die Rundreise durch den Parametertext — Art, Punkte, Hilfskennzeichen."""
    from app.core.sketch.serialize import sketch_from_text, sketch_to_text

    sketch = Sketch(
        "plane:xz",
        (
            SketchElement("ellipse", ((1.5, -2.0), (21.5, -2.0), (1.5, 8.0))),
            SketchElement(
                "elliptical_arc",
                ((0.0, 0.0), (0.0, 12.0), (-5.0, 0.0), (0.0, 12.0), (0.0, -12.0)),
                construction=True,
            ),
        ),
        (SketchConstraint("diameter", (0, 1), "40"),),
    )

    assert sketch_from_text(sketch_to_text(sketch)) == sketch


# --- Unabhängige Sollwerte ---------------------------------------------------------------


def _perimeter(a: float, b: float) -> float:
    """Der Umfang einer Ellipse über die Gauß–Kummer-Reihe.

    ``π(a + b) · Σ (½ über n)² hⁿ`` mit ``h = ((a - b)/(a + b))²`` — eine Reihe,
    die der Prüfling nicht kennt und die bei ``a/b = 2,6`` nach sechzig
    Gliedern weit unter 10⁻¹² steht.
    """
    h = ((a - b) / (a + b)) ** 2
    total, term = 1.0, 1.0
    for n in range(1, 60):
        # (½ über n) = (½)(½ - 1)…(½ - n + 1) / n!
        term *= (0.5 - (n - 1)) / n
        total += term * term * h**n
    return math.pi * (a + b) * total


def _arc_length(a: float, b: float, begin: float, end: float) -> float:
    """``∫ √(a² sin² t + b² cos² t) dt`` über [begin, end], Gauß–Legendre mit
    zwanzig Knoten je Teilstück und vierundsechzig Teilstücken."""
    nodes, weights = np.polynomial.legendre.leggauss(20)
    total = 0.0
    pieces = 64
    for index in range(pieces):
        low = begin + (end - begin) * index / pieces
        high = begin + (end - begin) * (index + 1) / pieces
        t = (high - low) / 2.0 * nodes + (high + low) / 2.0
        values = np.sqrt((a * np.sin(t)) ** 2 + (b * np.cos(t)) ** 2)
        total += float(np.sum(weights * values)) * (high - low) / 2.0
    return total


def _turned(
    a: float, b: float, degrees: float, centre: tuple[float, float], t: float
) -> tuple[float, float]:
    """Ein Punkt der Ellipse zum Parameter ``t``, unabhängig gerechnet."""
    turn = math.radians(degrees)
    x, y = a * math.cos(t), b * math.sin(t)
    return (
        centre[0] + x * math.cos(turn) - y * math.sin(turn),
        centre[1] + x * math.sin(turn) + y * math.cos(turn),
    )


def _ellipse_element(
    a: float, b: float, degrees: float, centre: tuple[float, float], *, flip: bool = False
) -> SketchElement:
    """Die drei Punkte einer gedrehten Ellipse — mit dem zweiten Achsenpunkt
    auf Wunsch auf der anderen Seite, was an der Form nichts ändert."""
    second = _turned(a, b, degrees, centre, -math.pi / 2.0 if flip else math.pi / 2.0)
    return SketchElement("ellipse", (centre, _turned(a, b, degrees, centre, 0.0), second))


def _d_shape(
    a: float, b: float, degrees: float, centre: tuple[float, float], begin: float, end: float
) -> Sketch:
    """Ein angeschnittener Ellipsenbogen, geschlossen von seiner Sehne."""
    start = _turned(a, b, degrees, centre, begin)
    finish = _turned(a, b, degrees, centre, end)
    arc = SketchElement(
        "elliptical_arc",
        (
            centre,
            _turned(a, b, degrees, centre, 0.0),
            _turned(a, b, degrees, centre, math.pi / 2.0),
            start,
            finish,
        ),
    )
    chord = SketchElement("line", (finish, start))
    return Sketch(
        "plane:xy",
        (arc, chord),
        (SketchConstraint("coincident", (4, 5)), SketchConstraint("coincident", (6, 3))),
    )


def _assert_chords_within(
    points: tuple[tuple[float, float], ...], flat: list[tuple[float, float]], limit: float
) -> None:
    """Keine Sehne weiter als ``limit`` von der Kurve — dicht nachgemessen:
    Zwischen je zwei Ecken wird die echte Kurve an 32 Stellen abgetastet."""
    (cx, cy), (mx, my), (nx, ny) = points[:3]
    a = math.hypot(mx - cx, my - cy)
    b = math.hypot(nx - cx, ny - cy)
    ux, uy = (mx - cx) / a, (my - cy) / a

    def angle(spot: tuple[float, float]) -> float:
        dx, dy = spot[0] - cx, spot[1] - cy
        return math.atan2((-dx * uy + dy * ux) / b, (dx * ux + dy * uy) / a)

    worst = 0.0
    for first, second in pairwise(flat):
        low, high = angle(first), angle(second)
        if high < low:
            high += 2.0 * math.pi
        span = math.dist(first, second)
        for step in range(1, 32):
            t = low + (high - low) * step / 32
            x, y = a * math.cos(t), b * math.sin(t)
            spot = (cx + x * ux - y * uy, cy + x * uy + y * ux)
            gap = (
                abs(
                    (second[0] - first[0]) * (spot[1] - first[1])
                    - (second[1] - first[1]) * (spot[0] - first[0])
                )
                / span
            )
            worst = max(worst, gap)
    assert worst <= limit * (1.0 + 1e-9), f"größte Sehnenabweichung {worst:.4g} über {limit}"


# --- Umriss, Fläche und Kern ----------------------------------------------------------


def test_a_full_ellipse_is_an_outline_of_its_own() -> None:
    from app.core.sketch.profile import regions_of

    sketch = Sketch("plane:xy", (_ellipse_element(20.0, 10.0, 0.0, (0.0, 0.0)),))
    regions = regions_of(solve_sketch(sketch))

    assert len(regions) == 1
    (segment,) = regions[0].segments
    assert segment.kind == "ellipse"
    assert segment.start == segment.end, "die volle Ellipse endet auf ihrem Anfang"


@pytest.mark.parametrize("flip", [False, True])
@pytest.mark.parametrize("degrees", [0.0, 30.0, 117.0])
def test_the_area_of_a_turned_ellipse_is_pi_a_b(degrees: float, flip: bool) -> None:
    """π·a·b, gleich wie gedreht und auf welcher Seite der zweite Achsenpunkt liegt."""
    from app.core.sketch.profile import regions_of, signed_area

    sketch = Sketch("plane:xy", (_ellipse_element(20.0, 7.5, degrees, (13.0, -4.0), flip=flip),))
    area = signed_area(regions_of(solve_sketch(sketch))[0])

    assert area == pytest.approx(math.pi * 20.0 * 7.5, rel=1e-12)


@pytest.mark.parametrize(
    ("begin", "end"),
    [(0.3, 2.1), (-1.0, 3.9), (2.5, 2.5 + 1.5 * math.pi)],
)
def test_a_cut_elliptical_arc_encloses_its_segment(begin: float, end: float) -> None:
    """``a·b/2 · (Δ - sin Δ)`` — das Kreissegment des Einheitskreises, gestreckt.

    Auch über 180 Grad: Dort wölbt sich der Bogen weiter, als seine Sehne
    trägt, und ein Sehnenvieleck bekäme den falschen Drehsinn.
    """
    from app.core.sketch.profile import regions_of, signed_area

    region = regions_of(solve_sketch(_d_shape(18.0, 6.0, 40.0, (2.0, 3.0), begin, end)))[0]
    sweep = end - begin

    assert abs(signed_area(region)) == pytest.approx(
        18.0 * 6.0 / 2.0 * (sweep - math.sin(sweep)), rel=1e-9
    )


def test_an_elliptical_hole_stays_a_hole_whichever_way_it_was_drawn() -> None:
    """Die elliptische Öffnung aus dem Kundenweg (§13.9), in einer Platte, die
    nicht um den Ursprung liegt."""
    from app.core.sketch.profile import regions_of

    plate = (
        SketchElement("line", ((0.0, 0.0), (60.0, 0.0))),
        SketchElement("line", ((60.0, 0.0), (60.0, 40.0))),
        SketchElement("line", ((60.0, 40.0), (0.0, 40.0))),
        SketchElement("line", ((0.0, 40.0), (0.0, 0.0))),
    )
    for flip in (False, True):
        hole = _ellipse_element(20.0, 10.0, 25.0, (30.0, 20.0), flip=flip)
        regions = regions_of(solve_sketch(Sketch("plane:xy", (*plate, hole))))
        assert len(regions) == 1 and len(regions[0].holes) == 1


def test_a_full_ellipse_is_no_path() -> None:
    from app.core.errors import GeometryError
    from app.core.sketch.profile import path_of

    sketch = Sketch("plane:xz", (_ellipse_element(10.0, 5.0, 0.0, (0.0, 0.0)),))
    with pytest.raises(GeometryError) as refused:
        path_of(solve_sketch(sketch))
    assert refused.value.suggestions


def test_an_elliptical_arc_is_a_path() -> None:
    from app.core.sketch.profile import path_of

    arc = SketchElement(
        "elliptical_arc",
        ((10.0, 0.0), (20.0, 0.0), (10.0, 30.0), (0.0, 0.0), (20.0, 0.0)),
    )
    path = path_of(solve_sketch(Sketch("plane:xz", (arc,))))

    assert [segment.kind for segment in path.segments] == ["ellipse"]


def test_the_view_curve_of_an_ellipse_closes_and_stays_on_the_curve() -> None:
    """Die Ansicht zeichnet die Ellipse als geschlossenen Zug auf der Kurve,
    mit Sehnen innerhalb der Grenze der Ansicht (``CHORD_ERROR``)."""
    from app.core.sketch.planes import frame_for_plane
    from app.core.sketch.profile import CHORD_ERROR, curves_of

    element = _ellipse_element(30.0, 12.0, 35.0, (5.0, 5.0))
    solved = solve_sketch(Sketch("plane:xy", (element,)))
    frame = frame_for_plane("plane:xy")
    assert frame is not None
    (curve,) = curves_of(solved, frame)
    flat = [(x, y) for x, y, _z in curve.points]

    assert flat[0] == pytest.approx(flat[-1])
    points = solved.elements[0].points
    assert max(abs(_on_ellipse(points, spot)) for spot in flat) < 1e-12
    _assert_chords_within(points, flat, CHORD_ERROR)


def test_the_mesh_outline_keeps_its_chords_within_the_facet_sag() -> None:
    """Der Netzweg (Tasche im STL, Feldschnitt): Sehnenfehler ≤ ``MAX_FACET_SAG``,
    jede Ecke auf der Kurve — an einer großen, flachen, gedrehten Ellipse."""
    from app.core.geom.sketch_solid import outline_points
    from app.core.sketch.profile import regions_of
    from app.core.units import MAX_FACET_SAG

    element = _ellipse_element(80.0, 9.0, 63.0, (-12.0, 40.0))
    solved = solve_sketch(Sketch("plane:xy", (element,)))
    ring = outline_points(regions_of(solved)[0])
    points = solved.elements[0].points

    assert max(abs(_on_ellipse(points, spot)) for spot in ring) < 1e-12
    _assert_chords_within(points, [*ring, ring[0]], MAX_FACET_SAG)


@pytest.mark.parametrize("degrees", [0.0, 30.0, 104.0])
def test_an_extruded_turned_ellipse_measures_its_area_and_its_perimeter(degrees: float) -> None:
    """Der exakte Kern baut eine **echte** Ellipse: Volumen π·a·b·h, und die
    Kanten oben und unten sind Ellipsen mit dem Umfang aus der Reihe.

    Gemessen wird die Länge mit ``GCPnts_AbscissaPoint`` und ausdrücklicher
    Genauigkeit. ``BRepGProp`` integriert ohne Vorgabe grob (3·10⁻⁴ daneben),
    und die Mantelfläche kam selbst mit Vorgabe um 1,3 % neben Reihe und
    Integral heraus, die sich auf 10⁻¹⁴ einig sind — gemessen im Paket P6.6 der
    Durchsicht 0.5.0 (`11c429cc2`; die Sonde ist nicht versioniert).
    """
    exact_kernel()

    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAbs import GeomAbs_Ellipse

    from app.core.brep import profiles as brep_profiles
    from app.core.sketch.profile import regions_of

    a, b, height = 25.0, 9.5, 4.0
    sketch = Sketch("plane:xy", (_ellipse_element(a, b, degrees, (7.0, -3.0)),))
    body = brep_profiles.extrude(regions_of(solve_sketch(sketch))[0], height)

    assert body.volume == pytest.approx(math.pi * a * b * height, rel=1e-9)
    rims = [
        GCPnts_AbscissaPoint.Length_s(curve, 1e-12)
        for curve in (BRepAdaptor_Curve(edge) for edge in body.edges())
        if curve.GetType() == GeomAbs_Ellipse
    ]
    assert rims == pytest.approx([_perimeter(a, b)] * 2, rel=1e-10)


def test_an_extruded_cut_arc_measures_its_segment_and_its_arc_length() -> None:
    """Der angeschnittene Bogen am Körper: Volumen aus der Segmentformel, die
    Länge der gekrümmten Kante aus einem eigenen Integral."""
    exact_kernel()

    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GCPnts import GCPnts_AbscissaPoint
    from OCP.GeomAbs import GeomAbs_Ellipse, GeomAbs_Line

    from app.core.brep import profiles as brep_profiles
    from app.core.sketch.profile import regions_of

    a, b, begin, end, height = 18.0, 6.0, -1.0, 3.9, 3.0
    body = brep_profiles.extrude(
        regions_of(solve_sketch(_d_shape(a, b, 40.0, (2.0, 3.0), begin, end)))[0], height
    )
    sweep = end - begin

    assert body.volume == pytest.approx(a * b / 2.0 * (sweep - math.sin(sweep)) * height, rel=1e-9)
    lengths = []
    for edge in body.edges():
        curve = BRepAdaptor_Curve(edge)
        if curve.GetType() == GeomAbs_Line:
            continue
        assert curve.GetType() == GeomAbs_Ellipse, "eine echte Ellipse, keine Näherung"
        # ``GCPnts_AbscissaPoint`` mit Genauigkeit; ``BRepGProp`` rechnet ohne
        # Vorgabe grob und lag um 3,4·10⁻⁴ daneben (siehe oben).
        lengths.append(GCPnts_AbscissaPoint.Length_s(curve, 1e-12))
    expected = _arc_length(a, b, begin, end)
    assert len(lengths) == 2, "unten und oben je eine gekrümmte Kante"
    assert lengths == pytest.approx([expected, expected], rel=1e-8)


# --- Jede Skizzen-Operation mit einer Ellipse ----------------------------------------


def _run(op: str, entry: object = None, **params: object) -> object:
    """Eine Operation über das Register, wie ``test_sketch_ops.run``."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}),  # type: ignore[attr-defined]
            inputs=[entry] if entry else [],  # type: ignore[list-item]
            params=spec.params(**params),
            profile=None,  # type: ignore[arg-type]
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def _text(*elements: SketchElement, plane: str = "plane:xy") -> str:
    from app.core.sketch.serialize import sketch_to_text

    return sketch_to_text(Sketch(plane, elements))


def _volume(result: object) -> float:
    return float(result.outputs[0].mesh.volume)  # type: ignore[attr-defined]


@pytest.mark.parametrize("plane", ["plane:xy", "plane:xz", "plane:yz"])
def test_extruding_a_drawn_ellipse_gives_pi_a_b_h_on_every_plane(plane: str) -> None:
    exact_kernel()

    ellipse = _ellipse_element(16.0, 6.0, 22.0, (4.0, 9.0))

    result = _run("sketch_extrude", sketch=_text(ellipse, plane=plane), height=7.0)

    assert _volume(result) == pytest.approx(math.pi * 16.0 * 6.0 * 7.0, rel=1e-9)


def test_an_elliptical_pocket_takes_pi_a_b_times_its_depth_from_an_exact_block() -> None:
    exact_kernel()

    block = _run("create_brep_box", width=60.0, depth=40.0, height=20.0).outputs[0]  # type: ignore[attr-defined]
    block.id = "obj_1"
    ellipse = _ellipse_element(14.0, 8.0, 35.0, (0.0, 0.0))

    result = _run("sketch_pocket", block, sketch=_text(ellipse), depth=5.0)

    assert _volume(result) == pytest.approx(60.0 * 40.0 * 20.0 - math.pi * 14.0 * 8.0 * 5.0)
    assert result.outputs[0].kind == "brep"  # type: ignore[attr-defined]


def test_an_elliptical_pocket_in_a_mesh_stays_within_its_chord_bound() -> None:
    """Der Netzweg: Die Ecken liegen auf der Kurve, die Sehnen innen — das
    Loch ist höchstens um Umfang mal Sehnengrenze zu klein, nie zu groß."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject
    from app.core.units import MAX_FACET_SAG

    block = SceneObject(
        id="obj_1", name="Block", mesh=MeshData.of(trimesh.creation.box((60.0, 40.0, 20.0)))
    )
    a, b = 14.0, 8.0
    ellipse = _ellipse_element(a, b, 35.0, (0.0, 0.0))

    result = _run("sketch_pocket", block, sketch=_text(ellipse), through=True)

    removed = 60.0 * 40.0 * 20.0 - _volume(result)
    exact = math.pi * a * b * 20.0
    assert exact - _perimeter(a, b) * MAX_FACET_SAG * 20.0 <= removed <= exact * (1.0 + 1e-9)


def test_turning_an_elliptical_section_follows_pappus() -> None:
    """Ein Ring mit elliptischem Querschnitt: 2π · Abstand der Mitte · π·a·b."""
    exact_kernel()

    section = _ellipse_element(4.0, 7.0, 0.0, (30.0, 10.0))

    result = _run("sketch_revolve", sketch=_text(section, plane="plane:xz"))

    assert _volume(result) == pytest.approx(2.0 * math.pi * 30.0 * math.pi * 4.0 * 7.0, rel=1e-9)


def test_an_elliptical_section_swept_along_the_bend_follows_pappus() -> None:
    """Querschnitt mit der Mitte im Ursprung, entlang des Bogens: π·a·b · R · θ."""
    exact_kernel()

    section = _ellipse_element(3.0, 2.0, 15.0, (0.0, 0.0))

    result = _run(
        "sketch_sweep", sketch=_text(section), along="arc", bend_radius=25.0, bend_angle=90.0
    )

    assert _volume(result) == pytest.approx(math.pi * 3.0 * 2.0 * 25.0 * math.pi / 2.0, rel=1e-6)


def test_a_tube_follows_a_drawn_elliptical_path() -> None:
    """Ein Rohr Ø 4 entlang eines Viertels einer Ellipse — senkrecht beginnend
    an ihrem linken Scheitel und gegen den Uhrzeigersinn nach unten: π·r² mal
    Viertelumfang, der aus der Reihe. (Am oberen Scheitel begonnen, liefe die
    Bahn waagerecht los, und die Operation sagte zu Recht ab.)"""
    exact_kernel()

    a, b = 30.0, 20.0
    path = SketchElement(
        "elliptical_arc",
        ((a, 0.0), (2.0 * a, 0.0), (a, b), (0.0, 0.0), (a, -b)),
    )

    result = _run(
        "sketch_sweep",
        shape="circle",
        length=4.0,
        along="drawn",
        path_sketch=_text(path, plane="plane:xz"),
    )

    assert _volume(result) == pytest.approx(math.pi * 4.0 * _perimeter(a, b) / 4.0, rel=1e-6)


def test_a_loft_between_an_ellipse_and_its_half_is_an_elliptical_frustum() -> None:
    """Ähnliche Querschnitte: h/3 · (A₁ + A₂ + √(A₁A₂)) = h · π·a·b · 7/12."""
    exact_kernel()

    ellipse = _ellipse_element(12.0, 5.0, 10.0, (3.0, -2.0))

    result = _run("sketch_loft", sketch=_text(ellipse), top="scaled", top_scale=0.5, height=9.0)

    assert _volume(result) == pytest.approx(9.0 * math.pi * 12.0 * 5.0 * 7.0 / 12.0, rel=1e-6)


def test_a_loft_from_an_ellipse_to_a_drawn_circle_is_a_valid_body() -> None:
    """Rund auf elliptisch: kein geschlossener Wert, aber ein gültiger Körper
    zwischen den beiden Querschnittsflächen."""
    exact_kernel()

    from app.core.brep.kernel import Solid

    bottom = _ellipse_element(12.0, 5.0, 0.0, (0.0, 0.0))
    top = SketchElement("circle", ((0.0, 0.0), (4.0, 0.0)))

    result = _run(
        "sketch_loft", sketch=_text(bottom), top="drawn", top_sketch=_text(top), height=10.0
    )
    body = result.outputs[0].mesh  # type: ignore[attr-defined]

    assert isinstance(body, Solid) and body.is_closed
    low, high = math.pi * 4.0 * 4.0 * 10.0, math.pi * 12.0 * 5.0 * 10.0
    assert low < body.volume < high


def test_a_drawn_ellipse_as_profile_clamp_seat_keeps_its_area() -> None:
    """Die Profilklemme liest den Sitz über denselben Umriss (P2.7) — auch einen
    elliptischen, auf die Sehnengrenze ihrer Kontur genau."""
    from app.core.knowledge.parts.profile_clamps import drawn_section
    from app.core.knowledge.parts.section import CONTOUR_SAG

    a, b = 11.0, 6.0
    section = drawn_section(_text(_ellipse_element(a, b, 20.0, (0.0, 0.0))))
    area = float(section.cross.area())

    assert math.pi * a * b - _perimeter(a, b) * CONTOUR_SAG <= area <= math.pi * a * b


def _dense_ellipse(a: float, b: float, degrees: float, centre: tuple[float, float]) -> np.ndarray:
    """Die Kurve dicht abgetastet — der Maßstab für Abstände im Test."""
    t = np.linspace(0.0, 2.0 * math.pi, 40_000, endpoint=False)
    turn = math.radians(degrees)
    x, y = a * np.cos(t), b * np.sin(t)
    return np.column_stack(
        (
            centre[0] + x * math.cos(turn) - y * math.sin(turn),
            centre[1] + x * math.sin(turn) + y * math.cos(turn),
        )
    )


def test_a_hole_field_in_an_elliptical_region_keeps_every_hole_whole_and_off_the_rim() -> None:
    """Lochfeld in einer elliptischen Fläche (Feldschnitt): Jedes Loch liegt
    ganz darin und mindestens den Rand weit von der Kurve — nachgemessen an der
    dicht abgetasteten Ellipse, nicht am Vieleck des Prüflings."""
    from app.core.geom.field_ops import field_tools
    from app.core.sketch.profile import regions_of

    a, b, degrees, centre, margin, radius = 30.0, 18.0, 20.0, (5.0, -3.0), 1.5, 2.0
    region = regions_of(
        solve_sketch(Sketch("plane:xy", (_ellipse_element(a, b, degrees, centre),)))
    )
    field = field_tools(region, (), diameter=2.0 * radius, spacing=8.0, margin=margin, web=1.0)
    curve = _dense_ellipse(a, b, degrees, centre)

    assert len(field.centres) > 10
    element = _ellipse_element(a, b, degrees, centre)
    for x, y in field.centres:
        assert _on_ellipse(element.points, (x, y)) < 0.0, "die Mitte liegt innen"
        gap = float(np.min(np.hypot(curve[:, 0] - x, curve[:, 1] - y)))
        assert gap >= radius + margin - 1e-6, f"Loch bei ({x:.2f} | {y:.2f}) zu nah am Rand"


def test_an_elliptical_exclusion_keeps_every_hole_off_it() -> None:
    from app.core.geom.field_ops import field_tools
    from app.core.sketch import shapes
    from app.core.sketch.profile import profile_of, regions_of

    a, b, degrees, centre, margin, radius = 14.0, 7.0, -30.0, (0.0, 0.0), 1.0, 1.5
    plate = profile_of(solve_sketch(shapes.rectangle(70.0, 50.0)))
    keep_out = regions_of(
        solve_sketch(Sketch("plane:xy", (_ellipse_element(a, b, degrees, centre),)))
    )
    field = field_tools(
        (plate,), keep_out, diameter=2.0 * radius, spacing=6.0, margin=margin, web=1.0
    )
    curve = _dense_ellipse(a, b, degrees, centre)
    element = _ellipse_element(a, b, degrees, centre)

    assert field.centres
    for x, y in field.centres:
        assert _on_ellipse(element.points, (x, y)) > 0.0, "keine Mitte im Ausschluss"
        gap = float(np.min(np.hypot(curve[:, 0] - x, curve[:, 1] - y)))
        assert gap >= radius + margin - 1e-6


# --- P6.6b: Punkt auf Kurve, glatter Übergang, Krümmung -------------------------------
#
# Die Kurve eines Splines ist die Catmull-Rom-Kurve durch seine Punkte
# (``profile.spline_controls``): Die Tests bauen ihre Bézierstücke aus dieser
# Definition selbst nach und messen Abstand, Tangente und Krümmung **an der
# Kurve** — Abstand über eine eigene Minimierung, Richtung und Krümmung über
# Differenzen dicht an der Stelle —, nie über die Gleichungen des Lösers.


def _pieces(points: tuple[tuple[float, float], ...]) -> list[np.ndarray]:
    """Die Bézierstücke der Catmull-Rom-Kurve, nach ihrer Definition."""
    q = np.asarray(points, dtype=float)
    count = len(q)
    found = []
    for index in range(count - 1):
        before = q[max(index - 1, 0)]
        after = q[min(index + 2, count - 1)]
        first, second = q[index], q[index + 1]
        found.append(
            np.array(
                [first, first + (second - before) / 6.0, second - (after - first) / 6.0, second]
            )
        )
    return found


def _bezier(piece: np.ndarray, t: float) -> np.ndarray:
    r = 1.0 - t
    return r**3 * piece[0] + 3 * r**2 * t * piece[1] + 3 * r * t**2 * piece[2] + t**3 * piece[3]


def _spline_distance(points: tuple[tuple[float, float], ...], spot: tuple[float, float]) -> float:
    """Der kürzeste Abstand eines Punkts zur Kurve — ein anderer Weg als der
    des Lösers: Je Stück ist ``|B(t) - p|²`` ein Polynom sechsten Grades, seine
    Extremstellen sind die reellen Nullstellen der Ableitung (fünften Grades).
    Gewertet werden sie und die beiden Enden.

    Nicht ``minimize_scalar``: Dessen beschränkte Suche hat eine relative
    Schranke von ``√ε`` im Parameter, also rund 1e-8 — gemessen standen 2e-8
    Abstand da, wo der Löser 2e-14 Rest hatte, und der Test las die Messung."""
    target = np.asarray(spot, dtype=float)
    best = math.inf
    for piece in _pieces(points):
        p0, p1, p2, p3 = piece
        # B(t) - p in Potenzform, steigend: c0 + c1·t + c2·t² + c3·t³.
        coefficients = [
            p0 - target,
            3.0 * (p1 - p0),
            3.0 * (p2 - 2.0 * p1 + p0),
            p3 - 3.0 * p2 + 3.0 * p1 - p0,
        ]
        x = np.polynomial.Polynomial([c[0] for c in coefficients])
        y = np.polynomial.Polynomial([c[1] for c in coefficients])
        square = x * x + y * y
        candidates = [0.0, 1.0]
        for root in square.deriv().roots():
            if abs(root.imag) < 1e-9 and -1e-12 <= root.real <= 1.0 + 1e-12:
                candidates.append(min(1.0, max(0.0, float(root.real))))
        for t in candidates:
            best = min(best, float(np.linalg.norm(_bezier(piece, t) - target)))
    return best


def _spline_end_shape(
    points: tuple[tuple[float, float], ...], at_start: bool
) -> tuple[np.ndarray, float]:
    """Einheitstangente (in Laufrichtung) und vorzeichenbehaftete Krümmung an
    einem Ende — aus Differenzen an der Kurve selbst, nicht aus ihren
    Kontrollpunkten wie der Löser.

    Einseitige Vierpunktformeln, deren Fehlerglied die vierte Ableitung trägt:
    Für ein kubisches Stück ist sie null, die Formeln sind dort also exakt bis
    auf die Rundung. Die übliche Dreipunktformel für die zweite Ableitung ist
    nur erster Ordnung und lag bei h = 1e-4 um drei Zehntausendstel daneben —
    mehr, als der Test prüfen soll."""
    pieces = _pieces(points)
    piece = pieces[0] if at_start else pieces[-1]
    h = 1e-2
    if at_start:
        p0, p1, p2, p3 = (_bezier(piece, k * h) for k in range(4))
        d1 = (-11 * p0 + 18 * p1 - 9 * p2 + 2 * p3) / (6 * h)
    else:
        p0, p1, p2, p3 = (_bezier(piece, 1.0 - k * h) for k in range(4))
        d1 = (11 * p0 - 18 * p1 + 9 * p2 - 2 * p3) / (6 * h)
    d2 = (2 * p0 - 5 * p1 + 4 * p2 - p3) / h**2
    speed = float(np.linalg.norm(d1))
    return d1 / speed, float(d1[0] * d2[1] - d1[1] * d2[0]) / speed**3


def _point_on_circle(centre: tuple[float, float], rim: tuple[float, float], spot) -> float:
    return math.dist(centre, spot) - math.dist(centre, rim)


def test_a_point_lands_on_every_kind_of_curve() -> None:
    """*Punkt auf Kurve* an allen sechs Arten — gelöst, nachgemessen je Art an
    ihrer eigenen Gleichung: Gerade (unbegrenzt), Kreis, Bogen (sein Kreis),
    Ellipse, Ellipsenbogen (seine Ellipse) und Spline (die Kurve selbst)."""
    curves = (
        SketchElement("line", ((0.0, 0.0), (30.0, 10.0))),
        SketchElement("circle", ((50.0, 0.0), (58.0, 0.0))),
        SketchElement("arc", ((80.0, 0.0), (88.0, 0.0), (80.0, 8.0))),
        _ellipse_element(12.0, 5.0, 25.0, (0.0, 40.0)),
        SketchElement(
            "elliptical_arc",
            ((40.0, 40.0), (52.0, 40.0), (40.0, 46.0), (52.0, 40.0), (40.0, 46.0)),
        ),
        SketchElement("spline", ((70.0, 30.0), (78.0, 44.0), (90.0, 36.0), (100.0, 48.0))),
    )
    heads = [0, 2, 4, 7, 10, 15]
    spots = [(12.0, 9.0), (51.0, 11.0), (86.0, 9.0), (3.0, 49.0), (47.0, 50.0), (82.0, 45.0)]
    points = tuple(SketchElement("point", (spot,)) for spot in spots)
    first_point = 19
    constraints = tuple(
        SketchConstraint("on_curve", (first_point + number, head))
        for number, head in enumerate(heads)
    )

    solved = solve_sketch(Sketch("plane:xy", (*curves, *points), constraints))
    at = [element.points for element in solved.elements]
    landed = [element.points[0] for element in solved.elements[6:]]

    (a, b) = at[0]
    assert (
        abs((b[0] - a[0]) * (landed[0][1] - a[1]) - (b[1] - a[1]) * (landed[0][0] - a[0]))
        / math.dist(a, b)
        < 1e-9
    )
    assert _point_on_circle(at[1][0], at[1][1], landed[1]) == pytest.approx(0.0, abs=1e-9)
    assert _point_on_circle(at[2][0], at[2][1], landed[2]) == pytest.approx(0.0, abs=1e-9)
    assert _on_ellipse(at[3], landed[3]) == pytest.approx(0.0, abs=1e-9)
    assert _on_ellipse(at[4], landed[4]) == pytest.approx(0.0, abs=1e-9)
    assert _spline_distance(at[5], landed[5]) < 1e-9


def test_a_point_on_a_curve_takes_one_freedom() -> None:
    """Ein freier Punkt hat zwei, auf dem Kreis einen: 2 + 3 − 1."""
    sketch = Sketch(
        "plane:xy",
        (SketchElement("circle", ((0.0, 0.0), (10.0, 0.0))), SketchElement("point", ((7.0, 8.0),))),
        (SketchConstraint("on_curve", (2, 0)),),
    )

    assert solve_sketch(sketch).free_dof == 4


@pytest.mark.parametrize(
    ("targets", "constraint"),
    [((2, 3), "not_a_curve"), ((2, 1), "not_a_curve"), ((1, 0), "own_point")],
)
def test_a_point_on_a_curve_names_a_wrong_target(targets: tuple[int, int], constraint: str) -> None:
    """Das Ziel muss der erste Punkt einer Kurve sein, und der Punkt darf nicht
    zur Kurve selbst gehören — dort gälte die Bedingung schon."""
    sketch = Sketch(
        "plane:xy",
        (
            SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("point", ((3.0, 4.0),)),
            SketchElement("point", ((6.0, 1.0),)),
        ),
        (SketchConstraint("on_curve", targets),),
    )

    with pytest.raises(ValidationError) as refused:
        solve_sketch(sketch)

    assert refused.value.constraint == constraint
    assert refused.value.suggestions


def test_a_point_held_off_its_circle_names_the_pair() -> None:
    """Widersprüchlich bestimmt: fester Kreis, fester Punkt daneben, und der
    Punkt soll auf den Kreis — das Paar wird benannt."""
    sketch = Sketch(
        "plane:xy",
        (
            SketchElement("circle", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("point", ((20.0, 0.0),)),
        ),
        (
            SketchConstraint("fixed", (0,)),
            SketchConstraint("fixed", (1,)),
            SketchConstraint("fixed", (2,)),
            SketchConstraint("on_curve", (2, 0)),
        ),
    )

    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(sketch)

    assert 3 in (caught.value.first, caught.value.second)
    assert caught.value.suggestions


def _line_arc_joint(extra: tuple[SketchConstraint, ...] = ()) -> Sketch:
    """Linie bis (20 | 0), dort ein Bogen um (20 | 9) weiter — etwas schief
    gezeichnet, damit die Tangente etwas zu tun hat."""
    return Sketch(
        "plane:xy",
        (
            SketchElement("line", ((0.0, 0.0), (20.0, 0.0))),
            SketchElement("arc", ((20.5, 9.0), (20.0, 0.0), (29.0, 9.3))),
        ),
        (SketchConstraint("coincident", (1, 3)), *extra),
    )


def test_a_line_runs_into_an_arc_without_a_kink() -> None:
    """*Glatt* an einem gemeinsamen Punkt: Linienrichtung senkrecht zum Radius
    am Übergang — nachgemessen, nicht der Rest des Lösers."""
    solved = solve_sketch(_line_arc_joint((SketchConstraint("smooth", (1, 0, 3, 2)),)))
    (a, b), (centre, start, _end) = (element.points for element in solved.elements)

    direction = (b[0] - a[0], b[1] - a[1])
    radius = (start[0] - centre[0], start[1] - centre[1])
    cosine = (direction[0] * radius[0] + direction[1] * radius[1]) / (
        math.hypot(*direction) * math.hypot(*radius)
    )
    assert cosine == pytest.approx(0.0, abs=1e-9)
    assert solved.free_dof == 4 + 5 - 2 - 1


def test_two_arcs_meet_smoothly_and_their_centres_line_up_with_the_joint() -> None:
    sketch = Sketch(
        "plane:xy",
        (
            SketchElement("arc", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0))),
            SketchElement("arc", ((0.0, 16.0), (0.0, 22.0), (0.5, 10.5))),
        ),
        (
            SketchConstraint("coincident", (2, 5)),
            SketchConstraint("smooth", (2, 0, 5, 3)),
        ),
    )

    solved = solve_sketch(sketch)
    (c1, _s1, joint), (c2, _s2, _e2) = (element.points for element in solved.elements)

    cross = (joint[0] - c1[0]) * (joint[1] - c2[1]) - (joint[1] - c1[1]) * (joint[0] - c2[0])
    assert cross / (math.dist(joint, c1) * math.dist(joint, c2)) == pytest.approx(0.0, abs=1e-9)


def _spline_joint(*extra: SketchConstraint, bend: float = 0.0) -> Sketch:
    """Linie bis (20 | 0), ein Spline beginnt dort (Punkt 2 bis 5) und ein
    Bogen um (50 | 12) an seinem Ende (Punkte 6 bis 8)."""
    return Sketch(
        "plane:xy",
        (
            SketchElement("line", ((0.0, 0.0), (20.0, 0.0))),
            SketchElement("spline", ((20.0, 0.0), (28.0, 2.5 + bend), (36.0, 8.0), (44.0, 7.0))),
            SketchElement("arc", ((50.0, 12.5), (44.0, 7.0), (58.0, 11.0))),
        ),
        (
            SketchConstraint("coincident", (1, 2)),
            SketchConstraint("coincident", (5, 7)),
            *extra,
        ),
    )


def test_a_spline_starts_along_its_line_and_ends_along_its_arc() -> None:
    """Glatter Splineanschluss an beiden Enden (G1): Die Tangente der Kurve,
    an der Kurve selbst gemessen, liegt auf der Linie und senkrecht zum Radius."""
    solved = solve_sketch(
        _spline_joint(
            SketchConstraint("smooth", (2, 2, 1, 0)),
            SketchConstraint("smooth", (5, 2, 7, 6)),
        )
    )
    line, spline, arc = (element.points for element in solved.elements)

    start_tangent, _curvature = _spline_end_shape(spline, at_start=True)
    along = np.subtract(line[1], line[0]) / math.dist(*line)
    assert abs(float(start_tangent[0] * along[1] - start_tangent[1] * along[0])) < 1e-6
    end_tangent, _curvature = _spline_end_shape(spline, at_start=False)
    radius = np.subtract(arc[1], arc[0])
    assert abs(float(end_tangent @ radius)) / float(np.linalg.norm(radius)) < 1e-6


def test_a_spline_continues_its_arc_with_the_same_curvature() -> None:
    """Krümmungsstetig (G2): Am Übergang hat die Kurve die Krümmung des Bogens,
    1/r — gemessen über Differenzen an der Kurve selbst."""
    solved = solve_sketch(
        _spline_joint(
            SketchConstraint("smooth", (5, 2, 7, 6)),
            SketchConstraint("curvature", (5, 2, 7, 6)),
        )
    )
    _line, spline, arc = (element.points for element in solved.elements)
    _tangent, curvature = _spline_end_shape(spline, at_start=False)
    radius = math.dist(arc[0], arc[1])

    assert abs(curvature) == pytest.approx(1.0 / radius, rel=1e-5)


def test_a_spline_leaves_its_line_with_curvature_zero() -> None:
    """Krümmungsstetig an eine Gerade heißt Krümmung null am Übergang — bei
    diesem Spline liegen seine ersten drei Punkte dann auf einer Geraden."""
    solved = solve_sketch(
        _spline_joint(
            SketchConstraint("smooth", (2, 2, 1, 0)),
            SketchConstraint("curvature", (2, 2, 1, 0)),
            bend=1.0,
        )
    )
    _line, spline, _arc = (element.points for element in solved.elements)
    _tangent, curvature = _spline_end_shape(spline, at_start=True)

    assert abs(curvature) < 1e-6


def test_two_splines_join_with_matching_curvature() -> None:
    first = SketchElement("spline", ((0.0, 0.0), (10.0, 6.0), (20.0, 4.0)))
    second = SketchElement("spline", ((20.0, 4.0), (30.0, 1.0), (40.0, 5.0), (50.0, -2.0)))
    sketch = Sketch(
        "plane:xy",
        (first, second),
        (
            SketchConstraint("coincident", (2, 3)),
            SketchConstraint("smooth", (2, 0, 3, 3)),
            SketchConstraint("curvature", (2, 0, 3, 3)),
        ),
    )

    solved = solve_sketch(sketch)
    one, other = (element.points for element in solved.elements)
    end_tangent, end_curvature = _spline_end_shape(one, at_start=False)
    start_tangent, start_curvature = _spline_end_shape(other, at_start=True)

    assert float(end_tangent @ start_tangent) == pytest.approx(1.0, abs=1e-6)
    assert end_curvature == pytest.approx(start_curvature, abs=1e-5)


def test_a_line_and_an_arc_cannot_share_their_curvature_and_it_says_which() -> None:
    """Widersprüchlich: Eine Gerade hat keine Krümmung, ein Bogen immer eine.

    Gelöst wäre es nur im Unendlichen, und dorthin lief der Löser: nach
    sechshundert Auswertungen ein Bogen mit 240 km Radius unter dem
    Restfehler. Ob das als Widerspruch galt, entschied die letzte Stelle des
    Rangs, und genannt wurde die Deckung statt des Übergangs. Seit RM-541
    bleibt ein Teil, der weiter als ``FARTHEST_MOVE`` liefe, stehen, und die
    Meldung nennt die beiden Bedingungen, die einander widersprechen.
    """
    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(
            _line_arc_joint(
                (
                    SketchConstraint("smooth", (1, 0, 3, 2)),
                    SketchConstraint("curvature", (1, 0, 3, 2)),
                )
            )
        )

    assert {caught.value.first, caught.value.second} == {1, 2}


@pytest.mark.parametrize("held", [(), (3,)])
def test_a_part_gets_the_same_jacobian_dense_as_sparse(held: tuple[int, ...]) -> None:
    """Kleine Teile bauen ihre Jacobimatrix gleich dicht (RM-541): Eintrag für
    Eintrag dieselbe wie die dünne mit Spaltenwahl — an Linie, Bogen, Ellipse
    und Spline samt Kurvenbedingungen, auch ohne die Spalten eines gehaltenen
    Punkts."""
    sketch = _spline_joint(
        SketchConstraint("smooth", (5, 2, 7, 6)),
        SketchConstraint("curvature", (5, 2, 7, 6)),
        SketchConstraint("smooth", (2, 2, 1, 0)),
    )
    sketch = Sketch(
        plane=sketch.plane,
        elements=(
            *sketch.elements,
            SketchElement("ellipse", ((1.3, -0.7), (18.2, 6.1), (-2.9, 9.4))),
            SketchElement("arc", ((30.0, 0.0), (40.0, 0.5), (29.0, 10.0))),
        ),
        constraints=sketch.constraints,
    )
    equations, anchors = solver._build_equations(sketch, {})
    flat = anchors.reshape(-1) + 0.01 * np.sin(np.arange(anchors.size))
    columns = np.asarray(
        [
            2 * point + axis
            for point in range(anchors.shape[0])
            if point not in held
            for axis in (0, 1)
        ]
    )
    where = {int(column): index for index, column in enumerate(columns)}

    sparse = solver._jacobian(equations, flat)[:, columns].toarray()
    dense = solver._dense_jacobian(equations, flat, where)

    assert dense.shape == sparse.shape
    assert np.array_equal(dense, sparse), "bitgleich"


def test_a_curvature_that_cannot_hold_stops_early_in_a_long_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Derselbe Widerspruch am Ende einer Kette aus zwanzig bemaßten Linien:
    Der Löser hört auf, wenn der Rest nicht mehr fällt (RM-541).

    Die Kette rechnet über ``lsmr``, und der Lauf kroch bis zur Vorgabe von
    scipy, hundert Auswertungen je Unbekannte — an vierzig Linien 16 600
    Auswertungen und 143 Sekunden im Qt-Hauptthread, von 0,0256 auf 0,0246
    Rest. Gezählt wird die Arbeit; genannt wird die Krümmung.
    """
    count = 20
    elements = [
        SketchElement("line", ((i * 5.0, 0.2 * (i % 2)), (i * 5.0 + 5.0, 0.2 * ((i + 1) % 2))))
        for i in range(count)
    ]
    end = (count * 5.0, 0.0)
    elements.append(SketchElement("arc", ((end[0], 10.0), end, (end[0] + 10.0, 10.0))))
    arc = 2 * count
    line = 2 * (count - 1)
    constraints = [
        *(SketchConstraint("coincident", (2 * i + 1, 2 * i + 2)) for i in range(count - 1)),
        *(SketchConstraint("distance", (2 * i, 2 * i + 1), "5") for i in range(count)),
        SketchConstraint("coincident", (2 * count - 1, arc + 1)),
        SketchConstraint("smooth", (2 * count - 1, line, arc + 1, arc)),
        SketchConstraint("curvature", (2 * count - 1, line, arc + 1, arc)),
        SketchConstraint("fixed", (0,)),
    ]
    sketch = Sketch(plane="plane:xy", elements=tuple(elements), constraints=tuple(constraints))
    points = sum(len(element.points) for element in elements)
    assert 2 * points > solver.EXACT_UP_TO, "die Kette rechnet über lsmr"
    evaluations: list[int] = []
    real = solver.least_squares

    def counted(*args: object, **kwargs: object) -> object:
        result = real(*args, **kwargs)  # type: ignore[arg-type]
        evaluations.append(int(result.nfev))
        return result

    monkeypatch.setattr(solver, "least_squares", counted)
    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(sketch)

    assert sum(evaluations) <= 3 * solver.STALL_WINDOW, evaluations
    assert len(constraints) - 2 in {caught.value.first, caught.value.second}, "die Krümmung"


def test_curvature_belongs_to_the_end_of_a_spline() -> None:
    """Innen ist ein Catmull-Rom-Spline nur tangentenstetig — links und rechts
    eines Stützpunkts haben verschiedene Krümmung, also gibt es dort keine."""
    with pytest.raises(ValidationError) as refused:
        solve_sketch(_spline_joint(SketchConstraint("curvature", (3, 2, 1, 0))))

    assert refused.value.constraint == "spline_end"
    assert refused.value.suggestions


def test_a_smooth_joint_set_twice_names_the_pair() -> None:
    """Überbestimmt: dieselbe Tangente zweimal — „legt fest, was schon festliegt"."""
    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(
            _line_arc_joint(
                (
                    SketchConstraint("smooth", (1, 0, 3, 2)),
                    SketchConstraint("smooth", (3, 2, 1, 0)),
                )
            )
        )

    assert {caught.value.first, caught.value.second} == {1, 2}


def _touching(curve: SketchElement, other: SketchElement, spot: tuple[float, float]) -> Sketch:
    """Zwei Kurven und ein Berührpunkt dazwischen: auf beiden, dort glatt —
    so legt die Oberfläche die Tangente zwischen Kurven ohne gemeinsamen Punkt."""
    count = len(curve.points) + len(other.points)
    return Sketch(
        "plane:xy",
        (curve, other, SketchElement("point", (spot,), construction=True)),
        (
            SketchConstraint("on_curve", (count, 0)),
            SketchConstraint("on_curve", (count, len(curve.points))),
            SketchConstraint("smooth", (count, 0, count, len(curve.points))),
        ),
    )


def test_a_line_touches_a_turned_ellipse() -> None:
    """Die Linie berührt die Ellipse: Ihr Abstand zur Mitte ist die
    Stützfunktion ``√(a²(n·u)² + b²(n·v)²)`` — die Formel der Berührung,
    unabhängig vom Berührpunkt."""
    ellipse = _ellipse_element(15.0, 6.0, 30.0, (0.0, 0.0))
    line = SketchElement("line", ((-20.0, 14.0), (20.0, 12.0)))
    solved = solve_sketch(_touching(ellipse, line, (0.0, 9.0)))
    points, (a, b), _spot = (element.points for element in solved.elements)

    (cx, cy), (mx, my), _n = points
    first, second, _turn = _axes(points)
    ux, uy = (mx - cx) / first, (my - cy) / first
    length = math.dist(a, b)
    nx, ny = -(b[1] - a[1]) / length, (b[0] - a[0]) / length
    reach = math.sqrt((first * (nx * ux + ny * uy)) ** 2 + (second * (-nx * uy + ny * ux)) ** 2)
    assert abs(nx * (cx - a[0]) + ny * (cy - a[1])) == pytest.approx(reach, abs=1e-8)


def test_two_circles_touch_through_their_contact_point() -> None:
    """Außen berührend: Mittenabstand gleich Summe der Radien."""
    solved = solve_sketch(
        _touching(
            SketchElement("circle", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("circle", ((17.0, 3.0), (23.0, 3.0))),
            (10.0, 1.0),
        )
    )
    (c1, r1), (c2, r2), _spot = (element.points for element in solved.elements)

    assert math.dist(c1, c2) == pytest.approx(math.dist(c1, r1) + math.dist(c2, r2), abs=1e-8)


def test_a_circle_touches_an_ellipse_and_they_share_the_normal_there() -> None:
    """Kein geschlossener Ausdruck mehr — nachgeprüft am Berührpunkt: auf beiden
    Kurven, und die Normalen (Kreis: radial, Ellipse: Gradient ihrer Gleichung)
    sind parallel. Freiheitsgrade: 3 + 5 + 2 − 3."""
    ellipse = _ellipse_element(14.0, 7.0, -20.0, (0.0, 0.0))
    circle = SketchElement("circle", ((20.0, 3.0), (25.0, 3.0)))
    solved = solve_sketch(_touching(ellipse, circle, (14.0, -2.0)))
    points, (centre, rim), (spot,) = (element.points for element in solved.elements)

    assert _on_ellipse(points, spot) == pytest.approx(0.0, abs=1e-9)
    assert _point_on_circle(centre, rim, spot) == pytest.approx(0.0, abs=1e-9)
    (cx, cy), (mx, my), _n = points
    first, second, _turn = _axes(points)
    ux, uy = (mx - cx) / first, (my - cy) / first
    dx, dy = spot[0] - cx, spot[1] - cy
    along, across = dx * ux + dy * uy, -dx * uy + dy * ux
    gx, gy = along / first**2, across / second**2
    normal = (gx * ux - gy * uy, gx * uy + gy * ux)
    radial = (spot[0] - centre[0], spot[1] - centre[1])
    cross = normal[0] * radial[1] - normal[1] * radial[0]
    assert cross / (math.hypot(*normal) * math.hypot(*radial)) == pytest.approx(0.0, abs=1e-9)
    assert solve_sketch(_touching(ellipse, circle, (14.0, -2.0))).free_dof == 3 + 5 + 2 - 3


def test_two_ellipses_touch() -> None:
    one = _ellipse_element(12.0, 5.0, 10.0, (0.0, 0.0))
    other = _ellipse_element(8.0, 4.0, 70.0, (18.0, 6.0))
    solved = solve_sketch(_touching(one, other, (11.0, 4.0)))
    first, second, (spot,) = (element.points for element in solved.elements)

    assert _on_ellipse(first, spot) == pytest.approx(0.0, abs=1e-9)
    assert _on_ellipse(second, spot) == pytest.approx(0.0, abs=1e-9)


def test_every_gradient_of_the_new_constraints_matches_central_differences() -> None:
    """*Punkt auf Kurve* an jeder Art, *glatt* und *krümmungsstetig* über alle
    Kurvenarten — gegen zentrale Differenzen, in schiefer Lage."""
    elements = (
        SketchElement("line", ((0.3, -0.4), (21.1, 3.3))),
        SketchElement("circle", ((40.2, 1.3), (47.7, 3.9))),
        SketchElement("arc", ((70.4, 0.6), (78.1, 2.2), (69.2, 8.9))),
        SketchElement("ellipse", ((1.3, 30.7), (15.8, 36.1), (-1.4, 37.9))),
        SketchElement(
            "elliptical_arc",
            ((40.1, 30.2), (52.6, 33.9), (38.9, 37.4), (50.8, 37.3), (32.6, 34.1)),
        ),
        SketchElement("spline", ((70.2, 30.1), (78.3, 41.2), (90.1, 35.3), (99.4, 47.2))),
        SketchElement("point", ((12.2, 8.9),)),
    )
    # Flache Indizes: Linie 0-1, Kreis 2-3, Bogen 4-6, Ellipse 7-9,
    # Ellipsenbogen 10-14, Spline 15-18, der lose Punkt 19.
    constraints = (
        SketchConstraint("on_curve", (19, 0)),
        SketchConstraint("on_curve", (19, 2)),
        SketchConstraint("on_curve", (19, 4)),
        SketchConstraint("on_curve", (19, 7)),
        SketchConstraint("on_curve", (19, 10)),
        SketchConstraint("on_curve", (19, 15)),
        SketchConstraint("smooth", (1, 0, 19, 2)),
        SketchConstraint("smooth", (5, 4, 13, 10)),
        SketchConstraint("smooth", (19, 7, 16, 15)),
        SketchConstraint("smooth", (18, 15, 13, 10)),
        SketchConstraint("curvature", (15, 15, 19, 7)),
        SketchConstraint("curvature", (18, 15, 13, 10)),
        SketchConstraint("curvature", (1, 0, 5, 4)),
    )
    assert_sketch_gradients(Sketch("plane:xy", elements, constraints), step=1e-6, atol=1e-6)


def test_the_elliptical_opening_stays_solvable_while_its_axes_vary() -> None:
    """Der Kundenweg aus §13.9: eine elliptische Öffnung, deren Achsen an
    Projektparametern hängen, daneben ein Spline, der glatt und
    krümmungsstetig aus einem Bogen kommt. Über den ganzen Bereich der
    Parameter bleibt alles lösbar, und Achsen, Tangente und Krümmung halten."""
    base = _spline_joint(
        SketchConstraint("smooth", (5, 2, 7, 6)),
        SketchConstraint("curvature", (5, 2, 7, 6)),
    )
    opening = _ellipse_element(10.0, 4.0, 15.0, (30.0, -20.0))
    sketch = Sketch(
        "plane:xy",
        (*base.elements, opening),
        (
            *base.constraints,
            SketchConstraint("fixed", (9,)),
            SketchConstraint("diameter", (9, 10), "=@long"),
            SketchConstraint("diameter", (9, 11), "=@short"),
        ),
    )
    for long in (12.0, 20.0, 31.0, 44.0):
        solved = solve_sketch(sketch, {"long": long, "short": long / 2.5})
        a, b, _turn = _axes(solved.elements[3].points)
        assert (a, b) == pytest.approx((long / 2.0, long / 5.0), abs=1e-9)
        _line, spline, arc = (element.points for element in solved.elements[:3])
        _tangent, curvature = _spline_end_shape(spline, at_start=False)
        assert abs(curvature) == pytest.approx(1.0 / math.dist(arc[0], arc[1]), rel=1e-5)


def test_both_lists_of_constraint_kinds_know_the_three_new_ones() -> None:
    from app.core.sketch.serialize import _CONSTRAINT_KINDS

    for kind in ("on_curve", "smooth", "curvature"):
        assert kind in solver._CONSTRAINT_TARGETS
        assert kind in _CONSTRAINT_KINDS


# --- Skizzen ändern: Trimmen, Spiegeln, Strecken, Splinepunkte, Flächenkontur ------------


def _line_hits_turned_ellipse(
    a: float, b: float, degrees: float, height: float
) -> list[tuple[float, float]]:
    """Wo die Waagerechte ``y = height`` eine gedrehte Ellipse um den Ursprung
    trifft — als quadratische Gleichung in x, unabhängig gelöst."""
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    # u = x·c + y·s, v = -x·s + y·c; u²/a² + v²/b² = 1.
    square = c * c / a**2 + s * s / b**2
    linear = 2.0 * height * s * c * (1.0 / a**2 - 1.0 / b**2)
    constant = height * height * (s * s / a**2 + c * c / b**2) - 1.0
    root = math.sqrt(linear * linear - 4.0 * square * constant)
    return sorted(((-linear + sign * root) / (2.0 * square), height) for sign in (-1.0, 1.0))


def test_a_line_is_trimmed_exactly_at_a_turned_ellipse() -> None:
    """Die Schnittpunkte mit der Ellipse selbst und nicht mit einer Sehnenkette:
    Trimmen innen lässt die beiden Außenstücke bis genau an die Kurve."""
    from app.core.sketch import edit

    ellipse = _ellipse_element(20.0, 8.0, 30.0, (0.0, 0.0))
    line = SketchElement("line", ((-40.0, 3.0), (40.0, 3.0)))
    sketch = Sketch("plane:xy", (ellipse, line))
    expected = _line_hits_turned_ellipse(20.0, 8.0, 30.0, 3.0)

    crossings = edit.crossings_on(sketch, 1)
    assert len(crossings) == 2
    for found, wanted in zip(crossings, expected, strict=True):
        assert found == pytest.approx(wanted, abs=1e-9)

    trimmed = edit.trim(sketch, 1, (0.0, 3.0))
    ends = sorted(element.points for element in trimmed.elements[1:])
    assert ends[0][1] == pytest.approx(expected[0], abs=1e-9)
    assert ends[1][0] == pytest.approx(expected[1], abs=1e-9)


def test_an_elliptical_arc_only_cuts_where_it_runs() -> None:
    """Die obere Hälfte einer Ellipse: Die senkrechte Linie trifft die volle
    Ellipse zweimal, den Bogen nur oben."""
    from app.core.sketch import edit

    arc = SketchElement(
        "elliptical_arc", ((0.0, 0.0), (20.0, 0.0), (0.0, 8.0), (20.0, 0.0), (-20.0, 0.0))
    )
    line = SketchElement("line", ((5.0, -20.0), (5.0, 20.0)))

    (crossing,) = edit.crossings_on(Sketch("plane:xy", (arc, line)), 1)

    assert crossing == pytest.approx((5.0, 8.0 * math.sqrt(1.0 - 25.0 / 400.0)), abs=1e-9)


def _crossing_height(x: float, a: float = 20.0, b: float = 8.0) -> float:
    return b * math.sqrt(1.0 - (x / a) ** 2)


def test_trimming_an_ellipse_between_two_crossings_leaves_its_other_side() -> None:
    """Weg ist die geklickte Seite; was bleibt, läuft gegen den Uhrzeigersinn
    von der Kreuzung hinter dem Klick zu der davor — hier über die linke Seite."""
    from app.core.sketch import edit
    from app.core.sketch.profile import _segment

    sketch = Sketch(
        "plane:xy",
        (
            SketchElement("ellipse", ((0.0, 0.0), (20.0, 0.0), (0.0, 8.0))),
            SketchElement("line", ((5.0, -20.0), (5.0, 20.0))),
        ),
        (SketchConstraint("diameter", (0, 1), "40"), SketchConstraint("fixed", (0,))),
    )

    trimmed = edit.trim(sketch, 0, (20.0, 0.0))

    arc, _line = trimmed.elements
    assert arc.kind == "elliptical_arc"
    centre, first, second, start, end = arc.points
    assert (centre, first, second) == ((0.0, 0.0), (20.0, 0.0), (0.0, 8.0))
    height = _crossing_height(5.0)
    assert start == pytest.approx((5.0, height), abs=1e-9)
    assert end == pytest.approx((5.0, -height), abs=1e-9)
    assert _segment("elliptical_arc", arc.points).via[0] < 0.0, "der Bogen läuft links herum"
    assert trimmed.constraints[:2] == sketch.constraints, "Maß und Fixierung bleiben"
    assert [entry.targets for entry in trimmed.constraints] == [(0, 1), (0,)]
    solve_sketch(trimmed)


def test_trimming_the_middle_of_an_arc_leaves_two_arcs_on_one_ellipse() -> None:
    """Zwei Bögen, eine Ellipse: Mitte und Achsen des zweiten sind mit denen
    des ersten gedeckt — und ein Zug an der Achse nimmt beide mit."""
    from app.core.sketch import edit

    sketch = Sketch(
        "plane:xy",
        (
            SketchElement(
                "elliptical_arc", ((0.0, 0.0), (20.0, 0.0), (0.0, 8.0), (20.0, 0.0), (-20.0, 0.0))
            ),
            SketchElement("line", ((5.0, -20.0), (5.0, 20.0))),
            SketchElement("line", ((-5.0, -20.0), (-5.0, 20.0))),
        ),
    )

    trimmed = edit.trim(sketch, 0, (0.0, 8.0))

    kinds = [element.kind for element in trimmed.elements]
    assert kinds == ["elliptical_arc", "elliptical_arc", "line", "line"]
    right, left = trimmed.elements[0].points, trimmed.elements[1].points
    height = _crossing_height(5.0)
    assert [*right[3], *right[4]] == pytest.approx([20.0, 0.0, 5.0, height], abs=1e-9)
    assert [*left[3], *left[4]] == pytest.approx([-5.0, height, -20.0, 0.0], abs=1e-9)
    links = [(entry.kind, entry.targets) for entry in trimmed.constraints]
    assert links == [("coincident", (0, 5)), ("coincident", (1, 6)), ("equal", (0, 2, 5, 7))]
    assert solve_sketch(trimmed).free_dof == 7 + 2 + 4 + 4
    dragged = solve_sketch(trimmed, dragged={1: (24.0, 0.0)}, start=edit.flat_points(trimmed))
    assert dragged.elements[1].points[1] == pytest.approx((24.0, 0.0), abs=1e-6)


def test_an_ellipse_crossed_once_cannot_be_trimmed_and_says_why() -> None:
    from app.core.sketch import edit

    sketch = Sketch(
        "plane:xy",
        (
            SketchElement("ellipse", ((0.0, 0.0), (20.0, 0.0), (0.0, 8.0))),
            SketchElement("line", ((0.0, 0.0), (0.0, 20.0))),
        ),
    )

    with pytest.raises(ValidationError) as refused:
        edit.trim(sketch, 0, (20.0, 0.0))

    assert refused.value.constraint == "too_few_crossings"
    assert refused.value.suggestions


def test_a_mirrored_elliptical_arc_encloses_the_same_segment() -> None:
    """Gespiegelt liefe der Bogen im Uhrzeigersinn; mit getauschten Enden läuft
    er wieder gegen ihn — um das gespiegelte Segment und nicht um den Rest der
    Ellipse."""
    from app.core.sketch import edit
    from app.core.sketch.profile import regions_of, signed_area

    a, b, begin, end = 18.0, 6.0, 0.3, 2.1
    original = _d_shape(a, b, 40.0, (40.0, 3.0), begin, end)

    mirrored = edit.mirror(original, (0, 1), "y")
    regions = regions_of(solve_sketch(mirrored))

    assert len(regions) == 2
    sweep = end - begin
    for region in regions:
        assert abs(signed_area(region)) == pytest.approx(
            a * b / 2.0 * (sweep - math.sin(sweep)), rel=1e-9
        )


def test_a_trimmed_line_keeps_its_smooth_joint() -> None:
    """*Glatt* nennt die Linie über ihren Anfang und hängt an beiden
    Linienpunkten — Trimmen warf solche Bedingungen als die ganze Linie
    meinend weg. Das Stück, das den Übergang trägt, behält ihn."""
    from app.core.sketch import edit

    sketch = _line_arc_joint((SketchConstraint("smooth", (1, 0, 3, 2)),))
    cutter = SketchElement("line", ((10.0, -5.0), (10.0, 5.0)))
    sketch = Sketch(sketch.plane, (*sketch.elements, cutter), sketch.constraints)

    trimmed = edit.trim(sketch, 0, (5.0, 0.0))

    assert SketchConstraint("smooth", (1, 0, 3, 2)) in trimmed.constraints
    assert trimmed.elements[0].points[0] == pytest.approx((10.0, 0.0), abs=1e-9)
    solved = solve_sketch(trimmed)
    (a, b), (centre, start, _end) = (element.points for element in solved.elements[:2])
    direction = (b[0] - a[0], b[1] - a[1])
    radius = (start[0] - centre[0], start[1] - centre[1])
    cosine = (direction[0] * radius[0] + direction[1] * radius[1]) / (
        math.hypot(*direction) * math.hypot(*radius)
    )
    assert cosine == pytest.approx(0.0, abs=1e-9)


def _dense_anchor(
    a: float, b: float, degrees: float, centre: tuple[float, float], begin: float, end: float
) -> tuple[float, float]:
    """Der Punkt des Hüllrechtecks eines Ellipsenstücks, der dem Nullpunkt am
    nächsten liegt — dicht abgetastet."""
    t = np.linspace(begin, end, 400_001)
    turn = math.radians(degrees)
    x, y = a * np.cos(t), b * np.sin(t)
    xs = centre[0] + x * math.cos(turn) - y * math.sin(turn)
    ys = centre[1] + x * math.sin(turn) + y * math.cos(turn)
    return (
        min(max(0.0, float(xs.min())), float(xs.max())),
        min(max(0.0, float(ys.min())), float(ys.max())),
    )


@pytest.mark.parametrize(("begin", "end"), [(0.0, 2.0 * math.pi), (-0.4, 1.9), (2.2, 5.6)])
def test_stretching_measures_an_ellipse_at_its_vertices(begin: float, end: float) -> None:
    """Gestreckt wird um den Bezugspunkt der Hülle (RM-391), und die reicht an
    einer gedrehten Ellipse bis zu ihren Scheiteln — nicht bis zu ihren
    gespeicherten Punkten. Die Ellipse liegt ganz neben dem Nullpunkt, damit
    der Bezugspunkt eine Ecke der Hülle ist und die Scheitel entscheiden."""
    from app.core.sketch import edit

    a, b, degrees, centre = 20.0, 6.0, 35.0, (40.0, -30.0)
    if end - begin >= 2.0 * math.pi:
        element = _ellipse_element(a, b, degrees, centre)
    else:
        element = SketchElement(
            "elliptical_arc",
            (
                centre,
                _turned(a, b, degrees, centre, 0.0),
                _turned(a, b, degrees, centre, math.pi / 2.0),
                _turned(a, b, degrees, centre, begin),
                _turned(a, b, degrees, centre, end),
            ),
        )
    anchor = _dense_anchor(a, b, degrees, centre, begin, end)

    bigger, _kept = edit.scaled(Sketch("plane:xy", (element,)), 2.0)

    moved = bigger.elements[0].points[0]
    assert moved == pytest.approx(
        (anchor[0] + 2.0 * (centre[0] - anchor[0]), anchor[1] + 2.0 * (centre[1] - anchor[1])),
        abs=1e-6,
    )


def _spline_sketch() -> Sketch:
    """Ein Spline (Punkte 0 bis 3), ein Punkt darauf (4), ein Punkt am Ende (5)."""
    return Sketch(
        "plane:xy",
        (
            SketchElement("spline", ((0.0, 0.0), (10.0, 8.0), (22.0, 3.0), (30.0, 9.0))),
            SketchElement("point", ((12.0, 9.0),)),
            SketchElement("point", ((30.0, 9.0),)),
        ),
        (
            SketchConstraint("fixed", (0,)),
            SketchConstraint("on_curve", (4, 0)),
            SketchConstraint("coincident", (3, 5)),
        ),
    )


def test_a_point_goes_into_a_spline_on_its_curve() -> None:
    """Der neue Punkt liegt auf der alten Kurve, die Kurve läuft weiter durch
    alle alten Punkte, und die Bedingungen hinter ihm rücken um eins auf."""
    from app.core.sketch import edit

    sketch = _spline_sketch()
    old = sketch.elements[0].points

    grown, added = edit.spline_point_added(sketch, 0, (16.0, 7.0))

    points = grown.elements[0].points
    assert len(points) == 5
    assert added == 2, "zwischen den Punkten 1 und 2"
    assert _spline_distance(old, points[added]) < 1e-9
    assert [point for at, point in enumerate(points) if at != added] == list(old)
    assert grown.constraints == (
        SketchConstraint("fixed", (0,)),
        SketchConstraint("on_curve", (5, 0)),
        SketchConstraint("coincident", (4, 6)),
    )
    solve_sketch(grown)


def test_removing_the_first_spline_point_keeps_what_names_the_whole_curve() -> None:
    """Fällt der erste Punkt, fällt seine Fixierung mit — *Punkt auf Kurve*
    bleibt, denn der nächste Punkt ist jetzt der erste, unter derselben Nummer."""
    from app.core.sketch import edit

    shrunk = edit.spline_point_removed(_spline_sketch(), 0)

    assert shrunk.elements[0].points == ((10.0, 8.0), (22.0, 3.0), (30.0, 9.0))
    assert shrunk.constraints == (
        SketchConstraint("on_curve", (3, 0)),
        SketchConstraint("coincident", (2, 4)),
    )
    solved = solve_sketch(shrunk)
    assert _spline_distance(solved.elements[0].points, solved.elements[1].points[0]) < 1e-9


def test_removing_an_inner_spline_point_keeps_its_neighbours_bound() -> None:
    from app.core.sketch import edit

    shrunk = edit.spline_point_removed(_spline_sketch(), 2)

    assert shrunk.elements[0].points == ((0.0, 0.0), (10.0, 8.0), (30.0, 9.0))
    assert shrunk.constraints == (
        SketchConstraint("fixed", (0,)),
        SketchConstraint("on_curve", (3, 0)),
        SketchConstraint("coincident", (2, 4)),
    )


@pytest.mark.parametrize(
    ("change", "constraint"),
    [
        ("remove_from_two", "least_points"),
        ("remove_a_line_point", "not_a_spline"),
        ("add_on_a_knot", "point_there"),
        ("add_to_a_line", "not_a_spline"),
    ],
)
def test_a_spline_point_change_says_why_it_cannot_be_done(change: str, constraint: str) -> None:
    from app.core.sketch import edit

    sketch = Sketch(
        "plane:xy",
        (
            SketchElement("spline", ((0.0, 0.0), (10.0, 5.0))),
            SketchElement("line", ((0.0, 10.0), (10.0, 10.0))),
            SketchElement("spline", ((0.0, 20.0), (10.0, 25.0), (20.0, 20.0))),
        ),
    )
    with pytest.raises(ValidationError) as refused:
        if change == "remove_from_two":
            edit.spline_point_removed(sketch, 1)
        elif change == "remove_a_line_point":
            edit.spline_point_removed(sketch, 2)
        elif change == "add_on_a_knot":
            edit.spline_point_added(sketch, 2, (10.0, 25.0))
        else:
            edit.spline_point_added(sketch, 1, (5.0, 10.0))

    assert refused.value.constraint == constraint
    assert refused.value.suggestions


def test_an_ellipse_from_three_clicks_stands_perpendicular() -> None:
    """Mitte, Achsende, und vom dritten Klick zählt nur die Höhe über der Achse."""
    from app.core.sketch import edit

    made = edit.ellipse_from_clicks((2.0, 1.0), (22.0, 11.0), (-1.0, 9.0))
    assert made is not None
    centre, first, second = made
    assert (centre, first) == ((2.0, 1.0), (22.0, 11.0))
    u = np.subtract(first, centre)
    w = np.subtract(second, centre)
    assert float(u @ w) == pytest.approx(0.0, abs=1e-12)
    click = np.subtract((-1.0, 9.0), centre)
    height = abs(float(u[0] * click[1] - u[1] * click[0])) / float(np.linalg.norm(u))
    assert float(np.linalg.norm(w)) == pytest.approx(height, rel=1e-12)
    assert solve_sketch(Sketch("plane:xy", (SketchElement("ellipse", made),))).free_dof == 5

    assert edit.ellipse_from_clicks((0.0, 0.0), (0.0, 0.0), (3.0, 4.0)) is None
    assert edit.ellipse_from_clicks((0.0, 0.0), (10.0, 0.0), (25.0, 0.0)) is None


def _plan_points(sketch: Sketch) -> list[tuple[float, float]]:
    return [point for element in solve_sketch(sketch).elements for point in element.points]


def test_the_tangent_between_a_line_and_an_arc_is_the_same_in_either_order() -> None:
    """Befund B2: Mit dem Bogen zuerst gewählt bot sich *Tangential* nicht an,
    mit der Linie zuerst entstand eine Bedingung mit fünf Zielen. Der Plan ist
    in beiden Reihenfolgen dieselbe Tangente mit vier."""
    from app.core.sketch import edit

    sketch = Sketch(
        "plane:xy",
        (
            SketchElement("line", ((0.0, 12.0), (30.0, 13.0))),
            SketchElement("arc", ((15.0, 0.0), (25.0, 0.0), (5.0, 0.0))),
        ),
    )
    points = _plan_points(sketch)

    forward = edit.tangent_plan(sketch, points, 0, 1)
    backward = edit.tangent_plan(sketch, points, 1, 0)

    assert forward == backward == edit.CurvePlan((SketchConstraint("tangent", (0, 1, 2, 3)),))
    solved = solve_sketch(edit.with_plan(sketch, forward))
    (a, b), (centre, start, _end) = (element.points for element in solved.elements)
    reach = abs(
        (b[0] - a[0]) * (centre[1] - a[1]) - (b[1] - a[1]) * (centre[0] - a[0])
    ) / math.dist(a, b)
    assert reach == pytest.approx(math.dist(centre, start), abs=1e-9)


def test_a_line_ending_on_an_arc_becomes_smooth_there() -> None:
    """Stoßen zwei Kurven aneinander, ist die Tangente der Übergang an dieser
    Stelle — *glatt* und nicht die Abstandstangente, die am Stoß einen
    doppelten Nullpunkt hat (``edit.fillet``)."""
    from app.core.sketch import edit

    sketch = _line_arc_joint()
    plan = edit.tangent_plan(sketch, _plan_points(sketch), 0, 1)

    assert plan == edit.CurvePlan((SketchConstraint("smooth", (1, 0, 3, 2)),))


def test_a_line_and_a_turned_ellipse_touch_through_a_helper_point() -> None:
    """Ohne Stoß kommt ein Berührpunkt mit: auf beiden Kurven, dort glatt.
    Nachgemessen an der Stützfunktion der Ellipse, wie im Lösertest."""
    from app.core.sketch import edit

    ellipse = _ellipse_element(15.0, 6.0, 30.0, (0.0, 0.0))
    line = SketchElement("line", ((-20.0, 14.0), (20.0, 12.0)))
    sketch = Sketch("plane:xy", (ellipse, line))

    plan = edit.tangent_plan(sketch, _plan_points(sketch), 0, 1)

    assert plan is not None and plan.helper is not None
    assert [entry.kind for entry in plan.constraints] == ["on_curve", "on_curve", "smooth"]
    solved = solve_sketch(edit.with_plan(sketch, plan))
    points, (a, b), (spot,) = (element.points for element in solved.elements)
    assert solved.elements[2].construction, "der Berührpunkt ist Hilfsgeometrie"
    (cx, cy), (mx, my), _n = points
    first, second, _turn = _axes(points)
    ux, uy = (mx - cx) / first, (my - cy) / first
    span = math.dist(a, b)
    nx, ny = -(b[1] - a[1]) / span, (b[0] - a[0]) / span
    reach = math.sqrt((first * (nx * ux + ny * uy)) ** 2 + (second * (-nx * uy + ny * ux)) ** 2)
    assert abs(nx * (cx - a[0]) + ny * (cy - a[1])) == pytest.approx(reach, abs=1e-8)
    assert _on_ellipse(points, spot) == pytest.approx(0.0, abs=1e-9)


def test_taking_a_touch_back_takes_its_helper_point_along() -> None:
    from app.core.sketch import edit

    sketch = Sketch(
        "plane:xy",
        (
            SketchElement("circle", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("circle", ((17.0, 3.0), (23.0, 3.0))),
        ),
        (SketchConstraint("fixed", (0,)),),
    )
    plan = edit.tangent_plan(sketch, _plan_points(sketch), 0, 1)
    assert plan is not None
    touched = edit.with_plan(sketch, plan)
    assert edit.curve_constraints_present(touched, "tangent", 0, 1)

    assert edit.taken_back(touched, "tangent", 0, 1) == sketch
    assert edit.taken_back(sketch, "tangent", 0, 1) is None


def test_a_spline_is_tangent_only_at_one_of_its_points() -> None:
    """Ohne Stoß gibt es keinen Plan; liegt ein Splinepunkt auf dem Kreis,
    wird er zur Stelle — mit *Punkt auf Kurve*, das ihn dort hält."""
    from app.core.sketch import edit

    circle = SketchElement("circle", ((0.0, 0.0), (10.0, 0.0)))
    away = SketchElement("spline", ((20.0, 0.0), (30.0, 5.0), (40.0, 0.0)))
    sketch = Sketch("plane:xy", (circle, away))
    assert edit.tangent_plan(sketch, _plan_points(sketch), 0, 1) is None

    touching = SketchElement("spline", ((10.0, 0.0), (20.0, 5.0), (30.0, 0.0)))
    sketch = Sketch("plane:xy", (circle, touching))
    plan = edit.tangent_plan(sketch, _plan_points(sketch), 0, 1)
    assert plan == edit.CurvePlan(
        (SketchConstraint("on_curve", (2, 0)), SketchConstraint("smooth", (2, 0, 2, 2)))
    )
    solved = solve_sketch(edit.with_plan(sketch, plan))
    _circle, spline = (element.points for element in solved.elements)
    tangent, _curvature = _spline_end_shape(spline, at_start=True)
    radius = np.subtract(spline[0], solved.elements[0].points[0])
    assert abs(float(tangent @ radius)) / float(np.linalg.norm(radius)) < 1e-6


def test_curvature_needs_a_spline_end_and_brings_smooth_along() -> None:
    from app.core.sketch import edit

    sketch = _spline_joint()
    points = _plan_points(sketch)

    plan = edit.curvature_plan(sketch, points, 1, 2)

    assert plan == edit.CurvePlan(
        (SketchConstraint("smooth", (5, 2, 7, 6)), SketchConstraint("curvature", (5, 2, 7, 6)))
    )
    smoothed = edit.with_plan(sketch, edit.CurvePlan((plan.constraints[0],)))
    assert edit.curvature_plan(smoothed, points, 1, 2) == edit.CurvePlan((plan.constraints[1],))
    assert edit.curvature_plan(sketch, points, 0, 2) is None, "Linie und Bogen: kein Spline"
    solved = solve_sketch(edit.with_plan(sketch, plan))
    _line, spline, arc = (element.points for element in solved.elements)
    _tangent, curvature = _spline_end_shape(spline, at_start=False)
    assert abs(curvature) == pytest.approx(1.0 / math.dist(arc[0], arc[1]), rel=1e-5)


def test_two_ellipses_become_equal_major_to_major() -> None:
    """Die zweite Ellipse ist mit der kurzen Achse zuerst gezeichnet — gleich
    groß paart trotzdem die lange mit der langen."""
    from app.core.sketch import edit

    first = _ellipse_element(12.0, 5.0, 0.0, (0.0, 0.0))
    turned = _ellipse_element(4.0, 9.0, 20.0, (40.0, 0.0))
    sketch = Sketch("plane:xy", (first, turned))

    plan = edit.equal_axes_plan(sketch, _plan_points(sketch), 0, 1)

    assert plan is not None
    assert plan.constraints == (
        SketchConstraint("equal", (0, 1, 3, 5)),
        SketchConstraint("equal", (0, 2, 3, 4)),
    )
    equalled = edit.with_plan(sketch, plan)
    assert len(edit.curve_constraints_present(equalled, "equal", 0, 1)) == 2
    solved = solve_sketch(equalled)
    one, other = (sorted(_axes(element.points)[:2]) for element in solved.elements)
    assert one == pytest.approx(other, abs=1e-9)


def test_a_point_on_its_own_curve_has_no_plan() -> None:
    from app.core.sketch import edit

    sketch = Sketch(
        "plane:xy",
        (SketchElement("line", ((0.0, 0.0), (10.0, 0.0))), SketchElement("point", ((3.0, 4.0),))),
    )
    assert edit.on_curve_plan(sketch, 2, 0) == edit.CurvePlan(
        (SketchConstraint("on_curve", (2, 0)),)
    )
    assert edit.on_curve_plan(sketch, 1, 0) is None


def _released(sketch: Sketch) -> Sketch:
    """Dieselbe Zeichnung, die Hilfslinien als Kontur — wie nach „Hilfslinie"."""
    from dataclasses import replace

    return replace(
        sketch,
        elements=tuple(replace(element, construction=False) for element in sketch.elements),
    )


def _cap_outlines(solid: object, name: str) -> list[object]:
    """Die Flächenkontur jeder waagerechten Fläche eines exakten Körpers."""
    from app.core.brep.features import features_of
    from app.core.sketch import edit
    from app.core.sketch.planes import feature_plane, frame_for_plane
    from app.core.types import SceneObject

    body = SceneObject(id="obj_1", name=name, mesh=solid, features=features_of(solid))  # type: ignore[arg-type]
    found: list[object] = []
    for key, feature in body.features.items():
        if feature.kind != "face" or abs(feature.params["normal"][2]) < 0.5:
            continue
        plane = feature_plane("obj_1", key)
        frame = frame_for_plane(plane, [body])
        assert frame is not None
        found.append(edit.face_outline(Sketch(plane, ()), [body], frame))
    return found


def test_a_wide_arc_that_reaches_over_the_axis_is_refused_with_its_reason() -> None:
    """Ein Bogen über 340°: Anfang, Ende und Stützpunkt liegen rechts der
    Achse, sein linker Scheitel bei x = -1 nicht. Die Achsprüfung sah nur die
    drei Punkte und ließ den Querschnitt durch; der Kern scheiterte danach mit
    „Aus diesem Querschnitt entsteht kein Drehkörper" statt mit dem Grund —
    dieselbe Lücke, die der Spline schon einmal hatte (Gesamtreview D-3)."""
    exact_kernel()

    from app.core.brep import profiles as brep_profiles
    from app.core.sketch.profile import regions_of

    centre, radius = (5.0, 0.0), 6.0

    def at(degrees: float) -> tuple[float, float]:
        turn = math.radians(degrees)
        return (centre[0] + radius * math.cos(turn), centre[1] + radius * math.sin(turn))

    sketch = Sketch(
        "plane:xz",
        (
            SketchElement("arc", (centre, at(100.0), at(80.0))),
            SketchElement("line", (at(80.0), at(100.0))),
        ),
    )
    region = regions_of(solve_sketch(sketch))[0]

    assert brep_profiles._leftmost(region) == pytest.approx(centre[0] - radius, abs=1e-9)
    with pytest.raises(ValidationError) as refused:
        brep_profiles.revolve(region, 360.0)
    assert refused.value.constraint == "crosses_axis"


def test_the_outline_of_an_exact_face_keeps_its_elliptical_arc() -> None:
    """Am exakten Körper kommt eine elliptische Kante als Ellipsenbogen in die
    Zeichnung und nicht als Sehnenkette — auf der Deck- und der Bodenfläche,
    deren Rahmen gespiegelt liegt, mit Achsen und Fläche aus der Formel."""
    exact_kernel()

    from app.core.brep import profiles as brep_profiles
    from app.core.sketch.profile import regions_of, signed_area

    a, b, begin, end = 18.0, 6.0, -1.0, 3.9
    region = regions_of(solve_sketch(_d_shape(a, b, 40.0, (2.0, 3.0), begin, end)))[0]
    caps = _cap_outlines(brep_profiles.extrude(region, 3.0), "D")

    assert len(caps) == 2
    sweep = end - begin
    for outline in caps:
        drawn = outline.sketch  # type: ignore[attr-defined]
        assert sorted(element.kind for element in drawn.elements) == ["elliptical_arc", "line"]
        (arc,) = [element for element in drawn.elements if element.kind == "elliptical_arc"]
        first, second, _turn = _axes(arc.points)
        assert sorted((first, second)) == pytest.approx([b, a], abs=1e-9)
        assert solve_sketch(drawn).free_dof == 0, "ganz feste Ellipsen sind bestimmt"
        (shape,) = regions_of(solve_sketch(_released(drawn)))
        assert abs(signed_area(shape)) == pytest.approx(
            a * b / 2.0 * (sweep - math.sin(sweep)), rel=1e-9
        )


def test_the_outline_of_an_exact_face_keeps_its_elliptical_hole() -> None:
    brep = exact_kernel()

    from app.core.brep import profiles as brep_profiles
    from app.core.sketch.profile import regions_of, signed_area

    opening = Sketch("plane:xy", (_ellipse_element(9.0, 4.0, 25.0, (3.0, 2.0)),))
    hole = brep_profiles.extrude(regions_of(solve_sketch(opening))[0], 20.0)
    drilled = brep.boolean(
        "difference", [brep.box(40.0, 30.0, 8.0), brep.moved(hole, (0.0, 0.0, -5.0))]
    )

    caps = _cap_outlines(drilled, "Platte")

    assert len(caps) == 2
    for outline in caps:
        drawn = outline.sketch  # type: ignore[attr-defined]
        assert sorted(element.kind for element in drawn.elements) == ["ellipse"] + ["line"] * 4
        (shape,) = regions_of(solve_sketch(_released(drawn)))
        material = abs(signed_area(shape)) - sum(abs(signed_area(h)) for h in shape.holes)
        assert material == pytest.approx(40.0 * 30.0 - math.pi * 9.0 * 4.0, rel=1e-9)
