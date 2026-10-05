"""Ein Sehnenzug wird Strecken, Bögen und Kreise (``app.core.sketch.traced``).

Der Nachbau zeichnet Querschnitte eines Netzes als Skizze nach. Die Sollwerte
kommen aus der Konstruktion der Züge im Test: Rundungen mit bekanntem Radius
und bekannter Mitte, Strecken mit bekannten Enden.
"""

from __future__ import annotations

import math

import pytest

from app.core.sketch.traced import traced_loop
from app.core.types import Point2, SketchElement


def _arc(centre: Point2, radius: float, first: float, last: float, chords: int) -> list[Point2]:
    """Die Ecken eines facettierten Bogens, wie ein Netz sie trägt (Winkel in Grad)."""
    return [
        (
            centre[0] + radius * math.cos(math.radians(first + (last - first) * step / chords)),
            centre[1] + radius * math.sin(math.radians(first + (last - first) * step / chords)),
        )
        for step in range(chords + 1)
    ]


def _rounded_rectangle(width: float, depth: float, radius: float, chords: int) -> list[Point2]:
    """Ein Rechteck mit gerundeten Ecken gegen den Uhrzeigersinn, mit Sehnenmitten."""
    half_x, half_y = width / 2.0 - radius, depth / 2.0 - radius
    corners = (
        ((half_x, -half_y), -90.0, 0.0),
        ((half_x, half_y), 0.0, 90.0),
        ((-half_x, half_y), 90.0, 180.0),
        ((-half_x, -half_y), 180.0, 270.0),
    )
    points: list[Point2] = []
    for centre, first, last in corners:
        points.extend(_arc(centre, radius, first, last, chords))
    # Ein Schnitt quer durch ein Netz trifft auch die Diagonalen der Seiten:
    # Punkte mitten auf einer Geraden, die wegfallen müssen.
    halved: list[Point2] = []
    for index, point in enumerate(points):
        after = points[(index + 1) % len(points)]
        halved.extend((point, ((point[0] + after[0]) / 2.0, (point[1] + after[1]) / 2.0)))
    return halved


def _kinds(elements: tuple[SketchElement, ...]) -> list[str]:
    return [element.kind for element in elements]


def _ends(element: SketchElement) -> tuple[Point2, Point2]:
    if element.kind == "arc":
        return element.points[1], element.points[2]
    return element.points[0], element.points[1]


@pytest.mark.parametrize("reverse", (False, True))
def test_a_rounded_rectangle_becomes_four_lines_and_four_arcs(reverse: bool) -> None:
    """Jede Seite eine Strecke, jede Ecke ein Bogen mit Mitte und Radius der Konstruktion.

    In beide Umlaufrichtungen: Ein Bogen läuft in der Skizze immer gegen den
    Uhrzeigersinn, gleich wie herum der Zug läuft.
    """
    ring = _rounded_rectangle(40.0, 20.0, 3.0, 8)
    elements = traced_loop(ring[::-1] if reverse else ring, 0.01, sag=0.05)

    assert sorted(_kinds(elements)) == ["arc"] * 4 + ["line"] * 4
    centres = sorted(
        (round(element.points[0][0], 6), round(element.points[0][1], 6))
        for element in elements
        if element.kind == "arc"
    )
    assert centres == [(-17.0, -7.0), (-17.0, 7.0), (17.0, -7.0), (17.0, 7.0)]
    for element in elements:
        if element.kind != "arc":
            continue
        centre, start, end = element.points
        assert math.dist(centre, start) == pytest.approx(3.0, abs=1e-9)
        assert math.dist(centre, start) == pytest.approx(math.dist(centre, end), abs=1e-12)
        # Gegen den Uhrzeigersinn von Anfang nach Ende: ein Viertelkreis.
        turn = (start[0] - centre[0]) * (end[1] - centre[1]) - (start[1] - centre[1]) * (
            end[0] - centre[0]
        )
        assert turn == pytest.approx(9.0, abs=1e-6)
    for element, following in zip(elements, (*elements[1:], elements[0]), strict=True):
        assert set(_ends(element)) & set(_ends(following)), "Nachbarn teilen ihre Enden genau"


def test_a_faceted_bore_becomes_one_circle() -> None:
    """Ein 48-Eck mit Punkten auf den Sehnen ist eine Bohrung: ein Kreis mit ihrer Mitte."""
    corners = _arc((5.0, 5.0), 2.6, 0.0, -360.0, 48)[:-1]
    ring: list[Point2] = []
    for index, corner in enumerate(corners):
        after = corners[(index + 1) % len(corners)]
        ring.extend((corner, (0.3 * corner[0] + 0.7 * after[0], 0.3 * corner[1] + 0.7 * after[1])))

    elements = traced_loop(ring, 0.01, sag=0.05)

    assert _kinds(elements) == ["circle"]
    centre, rim = elements[0].points
    assert centre == pytest.approx((5.0, 5.0), abs=1e-9)
    assert math.dist(centre, rim) == pytest.approx(2.6, abs=1e-9)


def test_a_hexagon_stays_six_lines_although_its_corners_lie_on_a_circle() -> None:
    """Sechzig Grad je Sehne sind Ecken, kein Bogen (``MAX_ARC_STEP``)."""
    hexagon = [
        (10.0 * math.cos(math.radians(60.0 * step)), 10.0 * math.sin(math.radians(60.0 * step)))
        for step in range(6)
    ]

    assert _kinds(traced_loop(hexagon, 0.01)) == ["line"] * 6


def test_a_long_edge_between_two_small_rounds_stays_a_line() -> None:
    """Die Punkte allein beweisen keinen Bogen (Besenhalter, 0.5.2).

    Eine 67 mm lange Kante zwischen zwei Rundungen R 1,36: Ein Kreis mit
    226 mm Radius ging durch alle Punkte und stand 2,5 mm neben der Kante.
    Die Sehnenhöhe zwischen zwei Punkten hält ihn ab.
    """
    left = _arc((-33.3, 21.0), 1.36, 180.0, 90.0, 6)
    right = _arc((33.3, 21.0), 1.36, 90.0, 0.0, 6)
    ring = [*left, *right, (34.66, 0.0), (-34.66, 0.0)]

    elements = traced_loop(ring[::-1], 0.01, sag=0.05)

    lines = [element for element in elements if element.kind == "line"]
    top = [line for line in lines if abs(line.points[0][1] - 22.36) < 1e-6]
    assert len(top) == 1, _kinds(elements)
    assert sorted(point[0] for point in top[0].points) == [
        pytest.approx(-33.3),
        pytest.approx(33.3),
    ]
    radii = sorted(
        math.dist(element.points[0], element.points[1])
        for element in elements
        if element.kind == "arc"
    )
    assert radii == [pytest.approx(1.36), pytest.approx(1.36)]


def test_a_straight_edge_does_not_tilt_towards_the_bend_behind_it() -> None:
    """Eine Kante nimmt keinen Punkt der Biegung dahinter mit (Besenhalter, 0.5.2).

    Der erste Punkt hinter der 20 mm langen Kante liegt 0,009 mm über ihr —
    eine Strecke bis dorthin trüge alle Punkte innerhalb von 0,01 mm, stünde
    aber am Ende der Kante um 0,009 mm schief. Am Besenhalter deckte die so
    gekippte Wand die Senkbohrung darin mit einer Haut zu.
    """
    ring = [(0.0, 0.0), (20.0, 0.0), (20.3, 0.009), (20.6, 0.5), (20.6, 10.0), (0.0, 10.0)]

    elements = traced_loop(ring, 0.01, sag=0.05)

    bottom = [
        element
        for element in elements
        if element.kind == "line"
        and (0.0, 0.0) in element.points
        and any(point[0] > 1.0 and abs(point[1]) < 0.1 for point in element.points)
    ]
    assert len(bottom) == 1, elements
    assert sorted(bottom[0].points) == [(0.0, 0.0), (20.0, 0.0)]


@pytest.mark.parametrize(
    ("after", "corner"),
    (
        # Hinter dem Stück ein Bogen: Die Strecke behält ihr Ende, der Bogen rückt.
        (_arc((20.012, 3.012), 3.0, -90.0, 0.0, 8), (20.0, 0.0)),
        # Hinter dem Stück eine Strecke: Beide treffen sich in ihrem Schnittpunkt.
        ([(20.012, 0.012), (20.012, 10.0)], (20.012, 0.0)),
    ),
)
def test_a_short_piece_collapses_without_tilting_the_edge_beside_it(
    after: list[Point2], corner: Point2
) -> None:
    """Eine Strecke unter ``shortest`` fällt weg, ohne die lange Kante daneben zu drehen."""
    ring = [(0.0, 0.0), (20.0, 0.0), *after, (after[-1][0], 10.0), (0.0, 10.0)]

    elements = traced_loop(_without_repeats(ring), 0.01, sag=0.05, shortest=0.025)

    bottom = [
        element
        for element in elements
        if element.kind == "line"
        and (0.0, 0.0) in element.points
        and all(abs(point[1]) < 0.1 for point in element.points)
    ]
    assert len(bottom) == 1, elements
    ends = sorted(bottom[0].points)
    assert ends[0] == (0.0, 0.0)
    assert ends[1] == pytest.approx(corner, abs=1e-12)
    assert all(
        math.dist(*_ends(element)) >= 0.025 for element in elements if element.kind == "line"
    )


def _without_repeats(ring: list[Point2]) -> list[Point2]:
    kept: list[Point2] = []
    for point in ring:
        if not kept or math.dist(point, kept[-1]) > 1e-9:
            kept.append(point)
    return kept


def test_an_arc_leaving_a_line_almost_tangentially_leaves_it_exactly_tangentially() -> None:
    """Die Mitte eines fast tangentialen Bogens liegt genau auf der Normalen der Strecke.

    Die Ecken der Rundung tragen ein festes Rauschen von zwei Mikrometern, wie
    ein Netz in einfacher Genauigkeit; die eingepasste Mitte liegt dann um
    Bruchteile neben der Normalen, und am Besenhalter tauchte der Kreis
    neben dem gemeinsamen Punkt um 0,4 µm über die Strecke — die Skizze
    kreuzte sich selbst.
    """
    corner = _arc((0.0, 3.0), 3.0, -90.0, 0.0, 8)
    noisy = [
        (
            x + 2e-6 * (1 if index % 2 else -1) * (x - 0.0) / 3.0,
            y + 2e-6 * (1 if index % 2 else -1) * (y - 3.0) / 3.0,
        )
        for index, (x, y) in enumerate(corner)
    ]
    noisy[0] = (0.0, 0.0)
    ring = [(-20.0, 0.0), *noisy, (3.0, 10.0), (-20.0, 10.0)]

    elements = traced_loop(ring, 0.01, sag=0.05)

    arcs = [element for element in elements if element.kind == "arc"]
    assert len(arcs) == 1, _kinds(elements)
    centre = arcs[0].points[0]
    # Die Strecke davor läuft längs x und endet in (0, 0): Tangential heißt,
    # die Mitte liegt genau über diesem Punkt.
    assert abs(centre[0]) < 1e-12
    assert centre[1] == pytest.approx(3.0, abs=1e-4)
