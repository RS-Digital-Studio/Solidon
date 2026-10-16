"""Trimmen, Verlängern, Versetzen, Spiegeln (§30.1, Konzept Teil 4 E17).

Ohne Trimmen ist jede Kontur Handarbeit, die nicht aus einer Grundform kommt —
das war der Befund aus dem Vergleich mit Fusion, und es ist der Grund, warum
diese vier zusammengehören.

Geprüft werden Zahlen, nicht Klicks: die Werkzeuge rechnen im Kern, die
Oberfläche ruft sie nur. Erwartete Punkte stehen ausgerechnet da, damit ein
Vorzeichenfehler auffällt statt sich zu erklären.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest

from app.core.errors import ValidationError
from app.core.sketch import edit
from app.core.types import Sketch, SketchConstraint, SketchElement
from tests.helpers import exact_kernel


def flat(points: tuple[tuple[float, float], ...]) -> list[float]:
    """Punktpaare als flache Zahlenliste — ``pytest.approx`` kann keine
    verschachtelten Strukturen."""
    return [value for point in points for value in point]


def cross() -> Sketch:
    """Eine waagerechte Linie über eine senkrechte, Kreuzung im Ursprung."""
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((-10.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((0.0, -10.0), (0.0, 10.0))),
        ),
    )


# --- Schnittpunkte ---------------------------------------------------------------


def test_two_lines_meet_where_they_cross() -> None:
    point = edit.line_intersection(((-10.0, 0.0), (10.0, 0.0)), ((0.0, -10.0), (0.0, 10.0)))

    assert point is not None
    assert point == pytest.approx((0.0, 0.0))


def test_parallel_lines_meet_nowhere() -> None:
    assert edit.line_intersection(((0.0, 0.0), (10.0, 0.0)), ((0.0, 5.0), (10.0, 5.0))) is None


def test_a_line_through_a_circle_meets_it_twice() -> None:
    points = edit.circle_intersections(((-10.0, 0.0), (10.0, 0.0)), (0.0, 0.0), 4.0)

    assert len(points) == 2
    assert {round(point[0], 6) for point in points} == {-4.0, 4.0}


def test_a_line_beside_a_circle_misses_it() -> None:
    assert edit.circle_intersections(((-10.0, 9.0), (10.0, 9.0)), (0.0, 0.0), 4.0) == []


# --- Trimmen ---------------------------------------------------------------------


def test_trimming_removes_the_half_that_was_clicked() -> None:
    """Weg ist das Stück, auf das geklickt wurde — wie in jedem CAD."""
    trimmed = edit.trim(cross(), 0, (-5.0, 0.0))

    line = trimmed.elements[0]
    assert flat(line.points) == pytest.approx([0.0, 0.0, 10.0, 0.0])
    assert len(trimmed.elements) == 2, "die Kante, an der getrimmt wurde, bleibt"


def test_trimming_between_two_crossings_leaves_two_lines() -> None:
    """Ein Stück aus der Mitte zu nehmen macht aus einer Linie zwei."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((-10.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((-4.0, -5.0), (-4.0, 5.0))),
            SketchElement(kind="line", points=((4.0, -5.0), (4.0, 5.0))),
        ),
    )

    trimmed = edit.trim(sketch, 0, (0.0, 0.0))

    assert len(trimmed.elements) == 4
    assert flat(trimmed.elements[0].points) == pytest.approx([-10.0, 0.0, -4.0, 0.0])
    assert flat(trimmed.elements[1].points) == pytest.approx([4.0, 0.0, 10.0, 0.0])


def test_trimming_a_line_that_crosses_nothing_says_so() -> None:
    """Regel 17: ein Fehler endet nie mit „fehlgeschlagen"."""
    lonely = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),),
    )

    with pytest.raises(ValidationError) as raised:
        edit.trim(lonely, 0, (5.0, 0.0))

    assert raised.value.suggestions, "und er sagt, was jetzt möglich ist"


def test_trimming_keeps_the_constraints_of_untouched_elements() -> None:
    """Eine Bedingung auf einem Punkt, den es nicht mehr gibt, wäre ein
    Absturz beim nächsten Lauf — und eine Richtung, die das verbliebene Stück
    weiter hat, gilt weiter.

    Hier stand bis zum 22.09.2026 „die Waagerechte der getrimmten Linie geht
    mit ihr". Das beschrieb, was der Code tat, nicht was er soll: Das Stück,
    das bleibt, liegt auf derselben Geraden, und ohne die Bedingung kippt es
    beim nächsten Zug an seinem Ende.
    """
    sketch = Sketch(
        plane="plane:xy",
        elements=cross().elements,
        constraints=(
            SketchConstraint(kind="horizontal", targets=(0, 1)),
            SketchConstraint(kind="vertical", targets=(2, 3)),
        ),
    )

    trimmed = edit.trim(sketch, 0, (-5.0, 0.0))

    assert SketchConstraint("vertical", (2, 3)) in trimmed.constraints, "die andere Linie"
    assert SketchConstraint("horizontal", (0, 1)) in trimmed.constraints, (
        "das verbliebene Stück bleibt waagerecht"
    )
    total = sum(len(element.points) for element in trimmed.elements)
    for entry in trimmed.constraints:
        assert all(target < total for target in entry.targets), "und kein Ziel zeigt ins Leere"


def _outline() -> Sketch:
    """Ein Rechteck aus vier verbundenen Linien, wie der Editor es aus Linien baut."""
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((10.0, 0.0), (10.0, 10.0))),
            SketchElement(kind="line", points=((10.0, 10.0), (0.0, 10.0))),
            SketchElement(kind="line", points=((0.0, 10.0), (0.0, 0.0))),
        ),
        constraints=(
            SketchConstraint("coincident", (1, 2)),
            SketchConstraint("coincident", (3, 4)),
            SketchConstraint("coincident", (5, 6)),
            SketchConstraint("coincident", (7, 0)),
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("distance", (0, 1), "10"),
        ),
    )


def test_trimming_a_side_between_two_corners_removes_the_whole_side() -> None:
    """Die Enden einer Rechteckseite sind selbst Kreuzungen — dort setzen die
    Nachbarn an. Ein Klick auf die Seite ließ zwei Linien der Länge null
    stehen, deckungsgleich mit den Ecken (Durchsicht 22.09.2026); gemeint ist
    in jedem CAD die ganze Seite."""
    trimmed = edit.trim(_outline(), 0, (5.0, 0.0))

    assert len(trimmed.elements) == 3, "die Seite ist weg, und nichts ohne Länge blieb"
    for element in trimmed.elements:
        assert math.dist(*element.points) > 1.0
    assert trimmed.constraints == (
        SketchConstraint("coincident", (1, 2)),
        SketchConstraint("coincident", (3, 4)),
    ), "die Ecken zwischen den übrigen Seiten halten; Maß und Richtung der Seite fallen mit ihr"


def test_trimming_keeps_the_joint_at_the_untouched_end() -> None:
    """Ein Stück vom Ende einer Linie zu nehmen, riss die Ecke an ihrem
    anderen Ende auf: Die Deckung dort fiel mit weg, und der nächste Zug zog
    die Linie vom Nachbarn ab."""
    sketch = replace(
        _outline(),
        elements=(
            *_outline().elements,
            SketchElement(kind="line", points=((6.0, -5.0), (6.0, 5.0))),
        ),
    )

    trimmed = edit.trim(sketch, 0, (8.0, 0.0))

    bottom = trimmed.elements[0]
    assert flat(bottom.points) == pytest.approx([0.0, 0.0, 6.0, 0.0])
    assert SketchConstraint("coincident", (7, 0)) in trimmed.constraints, (
        "die Ecke am stehen gebliebenen Anfang hält"
    )
    assert SketchConstraint("horizontal", (0, 1)) in trimmed.constraints
    assert not any(entry.kind == "distance" for entry in trimmed.constraints), (
        "das Maß meinte die alte Länge"
    )
    joints = [entry for entry in trimmed.constraints if entry.kind == "coincident"]
    assert not any(1 in entry.targets for entry in joints), "am Schnittende hängt nichts mehr"


def test_extending_keeps_the_joint_at_the_end_that_stays() -> None:
    """Verlängern bewegt ein Ende; das andere bleibt, und mit ihm seine Deckung.

    Vorher fiel jede Bedingung der Linie weg — die Ecke am festen Ende war
    danach eine lose Berührung, die der nächste Zug auseinanderzog."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((-10.0, 0.0), (0.0, 0.0))),
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((30.0, -10.0), (30.0, 10.0))),
        ),
        constraints=(
            SketchConstraint("coincident", (1, 2)),
            SketchConstraint("horizontal", (2, 3)),
            SketchConstraint("distance", (2, 3), "10"),
        ),
    )

    grown = edit.extend(sketch, 1, (8.0, 0.0))

    assert flat(grown.elements[1].points) == pytest.approx([0.0, 0.0, 30.0, 0.0])
    assert grown.constraints == (
        SketchConstraint("coincident", (1, 2)),
        SketchConstraint("horizontal", (2, 3)),
    ), "Deckung und Richtung bleiben, das alte Maß nicht"


# --- Verlängern ------------------------------------------------------------------


def test_trimming_ignores_crossings_beyond_the_segment() -> None:
    """Eine Kante jenseits des Linienendes machte aus Trimmen ein Verlängern.

    Aus 0→10 mit einer Kante bei x = 30 wurde 30→10 — ein Stück, das
    vollständig außerhalb des Originals liegt, ohne Meldung (Gesamtreview
    25.08.2026, D-4). Kreuzt sonst nichts, sagt Trimmen das jetzt; kreuzt
    zusätzlich eine Kante innerhalb, zählt nur die.
    """
    beyond_only = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((30.0, -10.0), (30.0, 10.0))),
        ),
    )
    with pytest.raises(ValidationError):
        edit.trim(beyond_only, 0, (5.0, 0.0))

    also_inside = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((4.0, -10.0), (4.0, 10.0))),
            SketchElement(kind="line", points=((30.0, -10.0), (30.0, 10.0))),
        ),
    )
    trimmed = edit.trim(also_inside, 0, (5.0, 0.0))
    lines = [element for element in trimmed.elements if element.points[0][1] == 0.0]
    assert flat(lines[0].points) == pytest.approx([0.0, 0.0, 4.0, 0.0]), (
        "gekürzt an der Kante innerhalb — kein Phantomstück an der äußeren"
    )


def test_an_arc_and_a_spline_count_as_cutting_edges() -> None:
    """Bogen und Spline waren als Schnittkante unsichtbar (D-10).

    Ehrlich war das nur, wenn sonst nichts kreuzte; daneben trimmte die Linie
    an der falschen Stelle. Geschnitten wird über dieselbe Punktfolge, die
    auch das Profil rechnet.
    """
    with_spline = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="spline", points=((5.0, 5.0), (5.0, -5.0))),
        ),
    )
    trimmed = edit.trim(with_spline, 0, (7.0, 0.0))
    assert flat(trimmed.elements[0].points) == pytest.approx([0.0, 0.0, 5.0, 0.0], abs=1e-6)

    # Oberer Halbkreis um (5 | -1) mit r = 2: kreuzt y = 0 bei 5 ± √3.
    with_arc = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="arc", points=((5.0, -1.0), (7.0, -1.0), (3.0, -1.0))),
        ),
    )
    trimmed = edit.trim(with_arc, 0, (5.0, 0.0))
    pieces = [element for element in trimmed.elements if element.kind == "line"]
    assert len(pieces) == 2, "zwischen zwei Kreuzungen: zwei Stücke — der Bogen bleibt"
    assert pieces[0].points[1][0] == pytest.approx(5.0 - math.sqrt(3.0), abs=0.05)
    assert pieces[1].points[0][0] == pytest.approx(5.0 + math.sqrt(3.0), abs=0.05)


def test_extending_reaches_the_next_edge() -> None:
    """Geklickt wird auf die Hälfte, die wachsen soll."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (5.0, 0.0))),
            SketchElement(kind="line", points=((12.0, -5.0), (12.0, 5.0))),
        ),
    )

    extended = edit.extend(sketch, 0, (4.0, 0.0))

    assert flat(extended.elements[0].points) == pytest.approx([0.0, 0.0, 12.0, 0.0])


def test_extending_at_the_start_ignores_crossings_inside_the_line() -> None:
    """Ein innerer Treffer darf aus Verlängern kein Trimmen machen."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((2.0, -5.0), (2.0, 5.0))),
            SketchElement(kind="line", points=((-5.0, -5.0), (-5.0, 5.0))),
        ),
    )

    extended = edit.extend(sketch, 0, (1.0, 0.0))

    assert flat(extended.elements[0].points) == pytest.approx([-5.0, 0.0, 10.0, 0.0])


def test_extending_reaches_a_circle_like_trimming_does() -> None:
    """Verlängern sah nur Linien — ein Kreis als Ziel existierte nicht.

    Beim Trimmen zählte derselbe Kreis längst als Schnittkante
    (Gesamtreview D-10); die zwei Werkzeuge sind dieselbe Geste in zwei
    Richtungen und fragen deshalb dieselbe Schnittsuche.
    """
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (5.0, 0.0))),
            SketchElement(kind="circle", points=((12.0, 0.0), (14.0, 0.0))),
        ),
    )

    extended = edit.extend(sketch, 0, (4.0, 0.0))

    # Der nähere Schnitt mit dem Kreis (Radius 2 um x = 12) liegt bei x = 10.
    assert flat(extended.elements[0].points) == pytest.approx([0.0, 0.0, 10.0, 0.0])


def test_a_shared_crossing_point_counts_once() -> None:
    """Zwei Kanten durch denselben Punkt sind eine Stelle, nicht zwei.

    Dasselbe Muster wie der Knoten einer Punktfolge: Bogen und Spline
    schneiden über Teilstrecken, und ein Treffer auf deren Naht wurde von
    beiden Teilstrecken gemeldet — ein Klick zwischen die zwei Rauschkopien
    machte aus dem Trimmen ein Nullstück.
    """
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((5.0, -5.0), (5.0, 5.0))),
            # Kreuzt dieselbe Stelle (5, 0) aus anderer Richtung.
            SketchElement(kind="line", points=((0.0, -5.0), (10.0, 5.0))),
        ),
    )

    found = edit.crossings_on(sketch, 0)

    assert len(found) == 1, f"eine Stelle, nicht {len(found)}"
    assert found[0] == pytest.approx((5.0, 0.0))


def test_extending_without_an_edge_says_where_to_click() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=((0.0, 0.0), (5.0, 0.0))),),
    )

    with pytest.raises(ValidationError) as raised:
        edit.extend(sketch, 0, (4.0, 0.0))

    assert raised.value.suggestions


# --- Versetzen -------------------------------------------------------------------


def test_offsetting_a_line_moves_it_sideways() -> None:
    """Senkrecht zu sich selbst, um genau den Abstand."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),),
    )

    moved = edit.offset(sketch, (0,), 3.0)

    assert len(moved.elements) == 2, "die Vorlage bleibt"
    assert flat(moved.elements[1].points) == pytest.approx([0.0, 3.0, 10.0, 3.0])


def test_offsetting_a_circle_changes_its_radius() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="circle", points=((0.0, 0.0), (5.0, 0.0))),),
    )

    moved = edit.offset(sketch, (0,), 2.0)

    centre, edge = moved.elements[1].points
    assert math.hypot(edge[0] - centre[0], edge[1] - centre[1]) == pytest.approx(7.0)


def test_a_circle_cannot_be_offset_into_nothing() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="circle", points=((0.0, 0.0), (5.0, 0.0))),),
    )

    with pytest.raises(ValidationError):
        edit.offset(sketch, (0,), -5.0)


def test_a_free_arc_moves_concentrically() -> None:
    """Ein freier Viertelbogen R5: Er bleibt um seine Mitte, von links gelesen
    liegt oben außen — +2 mm ergeben R7 an denselben Winkeln."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="arc", points=((0.0, 0.0), (5.0, 0.0), (0.0, 5.0))),),
    )

    centre, start, end = edit.offset(sketch, (0,), 2.0).elements[1].points

    assert centre == (0.0, 0.0)
    assert flat((start, end)) == pytest.approx([7.0, 0.0, 0.0, 7.0])


def test_a_full_arc_grows_like_a_circle() -> None:
    """Ein Bogen, dessen Enden aufeinander liegen, ist ein Kreis: +2 mm nach außen."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="arc", points=((1.0, 1.0), (6.0, 1.0), (6.0, 1.0))),),
    )

    copy = edit.offset(sketch, (0,), 2.0).elements[1]

    assert copy.kind == "arc"
    assert flat(copy.points) == pytest.approx([1.0, 1.0, 8.0, 1.0, 8.0, 1.0])


def test_offsetting_a_curve_is_refused_rather_than_guessed() -> None:
    """Der Versatz einer Kurve ist keine Verschiebung, sondern eine neue
    Form — und eine falsche wäre schlimmer als keine."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="spline", points=((0.0, 0.0), (5.0, 3.0), (10.0, 0.0))),),
    )

    with pytest.raises(ValidationError):
        edit.offset(sketch, (0,), 2.0)


def loop_of(corners: list[tuple[float, float]], *, clockwise: bool = False) -> Sketch:
    """Ein geschlossener Linienzug durch ``corners`` — linksherum wie das
    Werkzeug R, oder rechtsherum gezeichnet."""
    ordered = corners[::-1] if clockwise else corners
    count = len(ordered)
    return Sketch(
        plane="plane:xy",
        elements=tuple(
            SketchElement(kind="line", points=(ordered[at], ordered[(at + 1) % count]))
            for at in range(count)
        ),
    )


def copied_corners(before: Sketch, after: Sketch) -> list[tuple[float, float]]:
    """Die Ecken der Kopie: jeder Endpunkt der neuen Linien, gerundet."""
    fresh = after.elements[len(before.elements) :]
    assert all(element.kind == "line" for element in fresh)
    return sorted({(round(x, 9) + 0.0, round(y, 9) + 0.0) for e in fresh for x, y in e.points})


def shoelace(elements: tuple[SketchElement, ...]) -> float:
    """Die Fläche einer gleichsinnig gezeichneten, geschlossenen Linienkette —
    unabhängig von der Profilbildung, nur aus den Strecken."""
    return abs(
        sum(
            (e.points[0][0] * e.points[1][1] - e.points[1][0] * e.points[0][1]) / 2.0
            for e in elements
        )
    )


def assert_a_closed_chain(fresh: tuple[SketchElement, ...]) -> None:
    """Jedes Ende einer neuen Linie liegt auf genau einem Ende einer anderen,
    und keine zwei kreuzen sich — die Ecken sind geschnitten, nicht übereinander."""
    ends = [point for element in fresh for point in element.points]
    for at, point in enumerate(ends):
        partners = [
            other
            for other_at, other in enumerate(ends)
            if other_at // 2 != at // 2 and math.dist(point, other) < 1e-9
        ]
        assert len(partners) == 1, f"Ende {point} trifft {partners}"
    from app.core.sketch.profile import strictly_crossing

    for at, one in enumerate(fresh):
        for other in fresh[at + 1 :]:
            assert not strictly_crossing(*one.points, *other.points), (one, other)


RECTANGLE = [(0.0, 0.0), (40.0, 0.0), (40.0, 30.0), (0.0, 30.0)]


@pytest.mark.parametrize("clockwise", [False, True], ids=["ccw", "cw"])
@pytest.mark.parametrize("distance", [2.0, -2.0], ids=["outwards", "inwards"])
def test_a_closed_rectangle_grows_outwards_whichever_way_it_was_drawn(
    clockwise: bool, distance: float
) -> None:
    """N1: Positiv ist nach außen, negativ nach innen — wie beim Kreis, gleich
    ob die Kette links- oder rechtsherum läuft. Bis 0.6.0 landete +2 an einem
    Rechteck aus dem Werkzeug R innen, und die vier Kopien kreuzten sich an
    den Ecken."""
    sketch = loop_of(RECTANGLE, clockwise=clockwise)

    moved = edit.offset(sketch, (0, 1, 2, 3), distance)

    fresh = moved.elements[4:]
    assert len(fresh) == 4
    low, high_x, high_y = -distance, 40.0 + distance, 30.0 + distance
    assert copied_corners(sketch, moved) == sorted(
        [(low, low), (high_x, low), (high_x, high_y), (low, high_y)]
    )
    assert_a_closed_chain(fresh)
    # Soll von Hand: (40 + 2d) · (30 + 2d).
    assert shoelace(fresh) == pytest.approx((40.0 + 2 * distance) * (30.0 + 2 * distance))


def test_the_rectangle_from_the_tool_grows_outwards() -> None:
    """Genau der Weg aus dem Befund: Werkzeug R, ganze Kontur, +2 mm."""
    from app.core.sketch.shapes import rectangle_between

    sketch = rectangle_between((0.0, 0.0), (40.0, 30.0))

    moved = edit.offset(sketch, (0, 1, 2, 3), 2.0)

    assert copied_corners(sketch, moved) == [(-2.0, -2.0), (-2.0, 32.0), (42.0, -2.0), (42.0, 32.0)]


def test_an_offset_outline_is_a_frame_and_not_a_tangle() -> None:
    """Was *Fertig* fragt: Die Zeichnung ergibt danach einen Umriss — außen die
    Kopie, innen das Rechteck als Loch. Bis 0.6.0 blieben die Kopien vier lose,
    gekreuzte Linien, und *Fertig* lehnte mit „Erst einen geschlossenen Umriss
    zeichnen.“ ab."""
    from app.core.sketch.profile import regions_of, signed_area
    from app.core.sketch.shapes import rectangle_between
    from app.core.sketch.solver import solve_sketch

    moved = edit.offset(rectangle_between((0.0, 0.0), (40.0, 30.0)), (0, 1, 2, 3), 2.0)

    (region,) = regions_of(solve_sketch(moved))
    assert len(region.holes) == 1
    framed = abs(signed_area(region)) - abs(signed_area(region.holes[0]))
    assert framed == pytest.approx(44.0 * 34.0 - 40.0 * 30.0)


def test_the_copied_corners_stay_together_when_dragged() -> None:
    """Die Ecken der Kopie sind gedeckt wie die einer gezeichneten Kette —
    ein Zug an einer Ecke reißt den Umriss nicht auf."""
    sketch = loop_of(RECTANGLE)

    moved = edit.offset(sketch, (0, 1, 2, 3), 2.0)

    coincident = {
        frozenset(entry.targets) for entry in moved.constraints if entry.kind == "coincident"
    }
    # Die Kopie beginnt beim flachen Punkt 8: Linien (8, 9), (10, 11), (12, 13), (14, 15).
    assert coincident == {frozenset(pair) for pair in ((9, 10), (11, 12), (13, 14), (15, 8))}
    # Ein echter Zug an der Ecke (-2, -2) der Kopie nach (-6, -6), wie die
    # Zeichenfläche ihn rechnet (Review G3): Der Partner folgt, das Original nicht.
    from app.core.sketch.solver import solve_sketch

    pulled = solve_sketch(moved, dragged={8: (-6.0, -6.0)}, start=edit.flat_points(moved))
    points = [point for element in pulled.elements for point in element.points]
    assert flat((points[8], points[15])) == pytest.approx([-6.0, -6.0, -6.0, -6.0], abs=1e-6)
    assert flat(tuple(points[:8])) == pytest.approx(flat(tuple(edit.flat_points(sketch))))


L_PROFILE = [(0.0, 0.0), (30.0, 0.0), (30.0, 10.0), (10.0, 10.0), (10.0, 40.0), (0.0, 40.0)]


@pytest.mark.parametrize("clockwise", [False, True], ids=["ccw", "cw"])
def test_a_concave_l_profile_shrinks_inwards(clockwise: bool) -> None:
    """Ein L mit einer einspringenden Ecke, −2 mm: Die Innenecke wird
    verlängert, die Außenecken geschnitten. Soll von Hand:
    26 · 6 + 6 · 30 = 336 mm²."""
    sketch = loop_of(L_PROFILE, clockwise=clockwise)

    moved = edit.offset(sketch, tuple(range(6)), -2.0)

    fresh = moved.elements[6:]
    assert copied_corners(sketch, moved) == sorted(
        [(2.0, 2.0), (28.0, 2.0), (28.0, 8.0), (8.0, 8.0), (8.0, 38.0), (2.0, 38.0)]
    )
    assert_a_closed_chain(fresh)
    assert shoelace(fresh) == pytest.approx(26.0 * 6.0 + 6.0 * 30.0)


def test_a_concave_l_profile_grows_outwards() -> None:
    """Dasselbe L, +2 mm. Soll: 34 · 14 + 14 · 30 = 896 mm²."""
    sketch = loop_of(L_PROFILE)

    moved = edit.offset(sketch, tuple(range(6)), 2.0)

    assert copied_corners(sketch, moved) == sorted(
        [(-2.0, -2.0), (32.0, -2.0), (32.0, 12.0), (12.0, 12.0), (12.0, 42.0), (-2.0, 42.0)]
    )
    assert shoelace(moved.elements[6:]) == pytest.approx(34.0 * 14.0 + 14.0 * 30.0)


@pytest.mark.parametrize("distance", [-15.0, -20.0])
def test_an_outline_that_would_vanish_is_refused(distance: float) -> None:
    """30 mm hoch, 15 mm nach innen: Eine Kante fiele weg — eine Absage mit
    Weg statt einer Kopie, die sich umstülpt."""
    with pytest.raises(ValidationError) as raised:
        edit.offset(loop_of(RECTANGLE), (0, 1, 2, 3), distance)

    assert raised.value.suggestions


HOURGLASS = [(0.0, 0.0), (20.0, 0.0), (12.0, 10.0), (20.0, 20.0), (0.0, 20.0), (8.0, 10.0)]


def test_an_outline_whose_waist_would_cross_is_refused() -> None:
    """Eine Sanduhr mit 4 mm Taille: −3 mm schiebt die beiden Taillenecken
    aneinander vorbei (8,16 gegen 11,84), ohne dass eine Kante wegfällt."""
    with pytest.raises(ValidationError):
        edit.offset(loop_of(HOURGLASS), tuple(range(6)), -3.0)


def test_an_hourglass_with_room_shrinks() -> None:
    """−1 mm passt: Die Taillenecken landen bei 10,72 und 9,28."""
    sketch = loop_of(HOURGLASS)

    moved = edit.offset(sketch, tuple(range(6)), -1.0)

    xs = sorted(x for x, y in copied_corners(sketch, moved) if abs(y - 10.0) < 1e-9)
    # Soll von Hand: Die Gehrung rückt die Taillenecke um (10 + 6,4) / √164
    # = √164 / 10 nach innen.
    shift = math.sqrt(164.0) / 10.0
    assert xs == pytest.approx([8.0 + shift, 12.0 - shift], abs=1e-9)
    assert_a_closed_chain(moved.elements[6:])


CHAMFERED = [(0.0, 0.0), (40.0, 0.0), (40.0, 29.99), (39.99, 30.0), (0.0, 30.0)]


def test_a_tiny_chamfer_the_offset_eats_drops_out() -> None:
    """Eine Fase von 0,01 mm, 2 mm nach innen: Die Gehrung stülpte sie um.
    Sie bekommt keine Kopie, ihre Nachbarn treffen sich bei (38, 28)."""
    sketch = loop_of(CHAMFERED)

    moved = edit.offset(sketch, tuple(range(5)), -2.0)

    fresh = moved.elements[5:]
    assert len(fresh) == 4
    assert copied_corners(sketch, moved) == [(2.0, 2.0), (2.0, 28.0), (38.0, 2.0), (38.0, 28.0)]
    assert_a_closed_chain(fresh)
    assert shoelace(fresh) == pytest.approx(36.0 * 26.0)


def test_a_tiny_chamfer_grows_with_the_outline() -> None:
    """Nach außen bleibt die Fase. Soll von Hand für eine Gehrung:
    A₀ + P₀·d + d²·Σ tan(θ/2), drei rechte Winkel und zwei zu 45°."""
    sketch = loop_of(CHAMFERED)

    moved = edit.offset(sketch, tuple(range(5)), 2.0)

    fresh = moved.elements[5:]
    assert len(fresh) == 5
    assert_a_closed_chain(fresh)
    area = 40.0 * 30.0 - 0.01 * 0.01 / 2.0
    perimeter = 40.0 + 29.99 + 0.01 * math.sqrt(2.0) + 39.99 + 30.0
    turns = 3.0 + 2.0 * (math.sqrt(2.0) - 1.0)
    assert shoelace(fresh) == pytest.approx(area + 2.0 * perimeter + 4.0 * turns, abs=1e-9)


def test_a_rounding_smaller_than_the_offset_comes_out_sharp() -> None:
    """Fünf Sehnen einer Rundung R0,5 an einer Ecke, 2 mm nach innen: Alle
    fünf zehrt der Abstand auf, die Ecke der Kopie ist die des Rechtecks."""
    arc = [
        (39.5 + 0.5 * math.cos(math.radians(step)), 29.5 + 0.5 * math.sin(math.radians(step)))
        for step in (0.0, 18.0, 36.0, 54.0, 72.0, 90.0)
    ]
    sketch = loop_of([(0.0, 0.0), (40.0, 0.0), *arc, (0.0, 30.0)])

    moved = edit.offset(sketch, tuple(range(len(sketch.elements))), -2.0)

    fresh = moved.elements[len(sketch.elements) :]
    assert copied_corners(sketch, moved) == [(2.0, 2.0), (2.0, 28.0), (38.0, 2.0), (38.0, 28.0)]
    assert_a_closed_chain(fresh)


def test_a_notch_narrower_than_the_offset_closes() -> None:
    """Eine Kerbe 0,2 × 0,1 mm in der Unterkante, 2 mm nach außen: Ihr Boden
    fällt weg, ihre Wände laufen gegeneinander und fallen mit. Die Unterkante
    der Kopie ist gerade, die Fläche die des Rechtecks: 44 · 34 = 1496 mm²."""
    notched = [
        (0.0, 0.0),
        (20.0, 0.0),
        (20.0, 0.1),
        (20.2, 0.1),
        (20.2, 0.0),
        (40.0, 0.0),
        (40.0, 30.0),
        (0.0, 30.0),
    ]
    sketch = loop_of(notched)

    moved = edit.offset(sketch, tuple(range(8)), 2.0)

    fresh = moved.elements[8:]
    assert len(fresh) == 5, "beide Hälften der Unterkante, die drei anderen Seiten"
    assert copied_corners(sketch, moved) == [
        (-2.0, -2.0),
        (-2.0, 32.0),
        (20.1, -2.0),
        (42.0, -2.0),
        (42.0, 32.0),
    ]
    assert_a_closed_chain(fresh)
    assert shoelace(fresh) == pytest.approx(44.0 * 34.0)


def test_a_notch_in_an_open_line_closes_too() -> None:
    """Dieselbe Kerbe in einer offenen Linie, 2 mm nach oben: eine gerade Kopie."""
    corners = [(0.0, 0.0), (10.0, 0.0), (10.0, -0.1), (10.2, -0.1), (10.2, 0.0), (20.0, 0.0)]
    sketch = Sketch(
        plane="plane:xy",
        elements=tuple(
            SketchElement(kind="line", points=(corners[at], corners[at + 1])) for at in range(5)
        ),
    )

    moved = edit.offset(sketch, tuple(range(5)), 2.0)

    assert copied_corners(sketch, moved) == [(0.0, 2.0), (10.1, 2.0), (20.0, 2.0)]


def test_an_open_end_the_offset_would_eat_is_refused() -> None:
    """Ein offener Zug, dessen letztes Stück kürzer ist als der Abstand:
    Ein offenes Ende hat keinen Nachbarn, der die Lücke schlösse."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((10.0, 0.0), (10.0, 0.5))),
        ),
    )

    with pytest.raises(ValidationError):
        edit.offset(sketch, (0, 1), 2.0)


@pytest.mark.parametrize("backwards", [False, True], ids=["rightwards", "leftwards"])
def test_an_open_line_goes_up_whichever_way_it_was_drawn(backwards: bool) -> None:
    """Eine offene Linie hat kein Außen: Positiv ist oben, fest und gleich,
    wie herum sie gezeichnet wurde."""
    ends = ((0.0, 0.0), (10.0, 0.0))
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=ends[::-1] if backwards else ends),),
    )

    moved = edit.offset(sketch, (0,), 3.0)

    assert copied_corners(sketch, moved) == [(0.0, 3.0), (10.0, 3.0)]


@pytest.mark.parametrize("backwards", [False, True], ids=["upwards", "downwards"])
def test_an_upright_open_line_goes_right(backwards: bool) -> None:
    ends = ((0.0, 0.0), (0.0, 10.0))
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=ends[::-1] if backwards else ends),),
    )

    assert copied_corners(sketch, edit.offset(sketch, (0,), 3.0)) == [(3.0, 0.0), (3.0, 10.0)]
    assert copied_corners(sketch, edit.offset(sketch, (0,), -3.0)) == [(-3.0, 0.0), (-3.0, 10.0)]


@pytest.mark.parametrize(
    "lean", [1e-6, -1e-6, 4.0, -4.0], ids=["hair-r", "hair-l", "steep-r", "steep-l"]
)
@pytest.mark.parametrize("backwards", [False, True], ids=["upwards", "downwards"])
def test_a_steep_free_line_goes_right(lean: float, backwards: bool) -> None:
    """Review G1: Eine fast senkrechte, von Hand gezogene Linie (10⁻⁶ mm
    Neigung) sprang nach links. Steiler als 45° gilt jetzt „rechts“, gleich wohin
    sie sich neigt und wie herum sie gezeichnet wurde."""
    ends = ((0.0, 0.0), (lean, 10.0))
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=ends[::-1] if backwards else ends),),
    )

    copy = edit.offset(sketch, (0,), 3.0).elements[1]

    assert min(x for x, _y in copy.points) > min(0.0, lean)
    assert sum(x for x, _y in copy.points) / 2.0 > lean / 2.0 + 2.5


@pytest.mark.parametrize("backwards", [False, True], ids=["rightwards", "leftwards"])
def test_a_flat_free_line_goes_up(backwards: bool) -> None:
    """Flacher als 45° gilt „oben“: eine Linie mit 30° Steigung, beide Richtungen."""
    ends = ((0.0, 0.0), (10.0, 5.0))
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=ends[::-1] if backwards else ends),),
    )

    copy = edit.offset(sketch, (0,), 3.0).elements[1]

    # Die Normale nach oben links: (-5, 10)/√125, um 3 mm.
    shift = 3.0 / math.sqrt(125.0)
    expected = sorted([(-5.0 * shift, 10.0 * shift), (10.0 - 5.0 * shift, 5.0 + 10.0 * shift)])
    assert flat(tuple(sorted(copy.points))) == pytest.approx(flat(tuple(expected)))


KINKED = (
    SketchElement(
        "arc",
        (
            (21.018168850036787, 5.6110970280561),
            (19.895916729704798, 4.9712182678527155),
            (20.75526155769133, 4.346275141393535),
        ),
    ),
    SketchElement(
        "arc",
        (
            (-27.950379104037033, -38.281679753718166),
            (19.895916729704798, 4.9712182678527155),
            (-13.373003669281664, 24.548100905683647),
        ),
    ),
    SketchElement(
        "arc",
        (
            (15.371067962147546, 9.463616316973445),
            (-13.373003669281664, 24.548100905683647),
            (8.379991083844727, -22.23635487136407),
        ),
    ),
    SketchElement(
        "line", ((8.379991083844727, -22.23635487136407), (20.75526155769133, 4.346275141393535))
    ),
)


def _sampled(elements: tuple[SketchElement, ...]) -> list[tuple[float, float]]:
    """Punkte entlang von Strecken und Bögen, unabhängig von der Profilbildung."""
    points: list[tuple[float, float]] = []
    for element in elements:
        if element.kind == "line":
            (ax, ay), (bx, by) = element.points
            points.extend((ax + (bx - ax) * k / 50, ay + (by - ay) * k / 50) for k in range(51))
            continue
        centre, start, end = element.points
        radius = math.dist(centre, start)
        first = math.atan2(start[1] - centre[1], start[0] - centre[0])
        sweep = (math.atan2(end[1] - centre[1], end[0] - centre[0]) - first) % (2 * math.pi)
        points.extend(
            (
                centre[0] + radius * math.cos(first + sweep * k / 200),
                centre[1] + radius * math.sin(first + sweep * k / 200),
            )
            for k in range(201)
        )
    return points


def test_a_kinked_hollow_arc_the_offset_eats_keeps_the_distance() -> None:
    """Review G2 (Sonde `sonde_knick`, Fall 219): Ein kleiner hohler Bogen mit
    Knick fällt bei +2 mm weg. Die Verlängerungen seiner Nachbarn kamen dem
    Original bis 1,77 mm nahe. Jetzt entweder eine Absage oder überall
    mindestens der Abstand — gemessen an abgetasteten Kurven."""
    from shapely.geometry import LineString, Point

    sketch = Sketch(plane="plane:xy", elements=KINKED)
    try:
        moved = edit.offset(sketch, (0, 1, 2, 3), 2.0)
    except ValidationError as error:
        assert error.suggestions
        return

    original = LineString(_sampled(KINKED))
    nearest = min(original.distance(Point(p)) for p in _sampled(moved.elements[4:]))
    assert nearest >= 2.0 - 1e-3


def test_a_selection_that_crosses_itself_says_so() -> None:
    """Review G7: Eine Acht hat bei keinem Abstand eine Seite — die Absage
    sagt es, statt zu weniger Abstand zu raten."""
    sketch = loop_of([(0.0, 0.0), (20.0, 10.0), (20.0, 0.0), (0.0, 6.0)])

    with pytest.raises(ValidationError) as raised:
        edit.offset(sketch, (0, 1, 2, 3), 0.5)

    assert "kreuzt sich selbst" in str(raised.value.detail)
    assert "Weniger" not in str(raised.value.detail)


NOSE_CENTRE = (10.0 + 2.0 / math.sqrt(2.0), 10.0 + 2.0 / math.sqrt(2.0))
NOSE_ONE = (NOSE_CENTRE[0] + math.sqrt(4.0 - (NOSE_CENTRE[1] - 10.0) ** 2), 10.0)
NOSE_TWO = (10.0, NOSE_CENTRE[1] + math.sqrt(4.0 - (NOSE_CENTRE[0] - 10.0) ** 2))


def test_a_corner_where_line_and_arc_miss_each_other_says_so() -> None:
    """Review G7 (Sonde `sonde_nase`): ein L mit runder Nase in der Innenecke,
    −0,5 mm. Versetzte Linie und versetzter Kreis treffen sich nicht; ab −2 mm
    geht es wieder. Die Absage rät deshalb nicht zu weniger Abstand."""
    elements = (
        SketchElement("line", ((0.0, 0.0), (30.0, 0.0))),
        SketchElement("line", ((30.0, 0.0), (30.0, 10.0))),
        SketchElement("line", ((30.0, 10.0), NOSE_ONE)),
        SketchElement("arc", (NOSE_CENTRE, NOSE_ONE, NOSE_TWO)),
        SketchElement("line", (NOSE_TWO, (10.0, 40.0))),
        SketchElement("line", ((10.0, 40.0), (0.0, 40.0))),
        SketchElement("line", ((0.0, 40.0), (0.0, 0.0))),
    )
    sketch = Sketch(plane="plane:xy", elements=elements)

    with pytest.raises(ValidationError) as raised:
        edit.offset(sketch, tuple(range(7)), -0.5)

    assert "anderen Abstand" in str(raised.value.detail)
    assert edit.offset(sketch, tuple(range(7)), -2.5).elements[7:]


def test_many_free_lines_find_their_partners_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review G4: Die Ringsuche baute die Partner aller Enden je offener Kette
    neu (2000 freie Linien: 15 s). Jetzt einmal je Art und Aufruf."""
    calls: list[int] = []
    real = edit._partners

    def counted(ends: dict[tuple[int, int], tuple[float, float]]) -> object:
        calls.append(len(ends))
        return real(ends)

    monkeypatch.setattr(edit, "_partners", counted)
    sketch = Sketch(
        plane="plane:xy",
        elements=tuple(
            SketchElement(kind="line", points=((3.0 * k, 0.0), (3.0 * k + 1.0, 1.0)))
            for k in range(300)
        ),
    )

    edit.offset(sketch, tuple(range(300)), 0.5)

    assert len(calls) == 2, "einmal die Auswahl, einmal die Zeichnung"


@pytest.mark.parametrize("backwards", [False, True], ids=["forwards", "backwards"])
def test_an_open_chain_keeps_its_corner(backwards: bool) -> None:
    """Ein offener Zug wandert als Ganzes auf dieselbe Seite, die Ecke
    dazwischen wird geschnitten: unten nach oben, rechts nach innen."""
    corners = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
    if backwards:
        corners.reverse()
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=(corners[0], corners[1])),
            SketchElement(kind="line", points=(corners[1], corners[2])),
        ),
    )

    moved = edit.offset(sketch, (0, 1), 2.0)

    assert copied_corners(sketch, moved) == [(0.0, 2.0), (8.0, 2.0), (8.0, 10.0)]
    assert len([c for c in moved.constraints if c.kind == "coincident"]) == 1


def slot(radius: float = 5.0, length: float = 20.0) -> Sketch:
    """Ein Langloch linksherum: Unterkante, rechter Bogen, Oberkante, linker Bogen."""
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, -radius), (length, -radius))),
            SketchElement(kind="arc", points=((length, 0.0), (length, -radius), (length, radius))),
            SketchElement(kind="line", points=((length, radius), (0.0, radius))),
            SketchElement(kind="arc", points=((0.0, 0.0), (0.0, radius), (0.0, -radius))),
        ),
    )


@pytest.mark.parametrize("clockwise", [False, True], ids=["ccw", "cw"])
@pytest.mark.parametrize("distance", [2.0, -2.0], ids=["outwards", "inwards"])
def test_a_single_edge_of_an_outline_follows_the_outline(clockwise: bool, distance: float) -> None:
    """Die Unterkante eines Rechtecks allein gewählt: Sie gehört zum Umriss,
    +2 mm schiebt sie nach unten, nicht nach oben wie eine freie Linie —
    gleich wie herum der Umriss gezeichnet ist."""
    sketch = loop_of(RECTANGLE, clockwise=clockwise)
    bottom = next(
        at for at, element in enumerate(sketch.elements) if {y for _x, y in element.points} == {0.0}
    )

    moved = edit.offset(sketch, (bottom,), distance)

    assert copied_corners(sketch, moved) == [(0.0, -distance), (40.0, -distance)]


def test_two_edges_of_an_outline_keep_their_corner_outside() -> None:
    """Unterkante und rechte Seite: beide nach außen, die Ecke auf Gehrung bei (42, −2)."""
    sketch = loop_of(RECTANGLE)

    moved = edit.offset(sketch, (0, 1), 2.0)

    assert copied_corners(sketch, moved) == [(0.0, -2.0), (42.0, -2.0), (42.0, 30.0)]


def loop_area(elements: tuple[SketchElement, ...]) -> float:
    """Die Fläche einer geschlossenen Kette aus Strecken und Bögen — über die
    Verkettung der Profilbildung, die dabei auch prüft, dass sie schließt."""
    from app.core.sketch.profile import Profile, _one_loop, _segment, signed_area

    loop = _one_loop([_segment(element.kind, element.points) for element in elements])
    return abs(signed_area(Profile(segments=loop)))


@pytest.mark.parametrize("clockwise", [False, True], ids=["ccw", "cw"])
@pytest.mark.parametrize("distance", [2.0, -2.0], ids=["outwards", "inwards"])
def test_a_slot_keeps_its_round_ends(clockwise: bool, distance: float) -> None:
    """Ein Langloch R5, 20 mm zwischen den Mitten, ganz gewählt: Die Bögen
    wandern konzentrisch und schließen tangential an die Linien an.
    Soll von Hand: 20 · 2(5 + d) + π(5 + d)²."""
    sketch = slot()
    if clockwise:
        sketch = replace(
            sketch,
            elements=tuple(
                replace(element, points=element.points[::-1]) if element.kind == "line" else element
                for element in sketch.elements
            ),
        )

    moved = edit.offset(sketch, (0, 1, 2, 3), distance)

    fresh = moved.elements[4:]
    radius = 5.0 + distance
    arcs = [element for element in fresh if element.kind == "arc"]
    assert len(fresh) == 4 and len(arcs) == 2
    assert sorted(arc.points[0] for arc in arcs) == [(0.0, 0.0), (20.0, 0.0)]
    for arc in arcs:
        centre, start, end = arc.points
        assert [math.dist(centre, start), math.dist(centre, end)] == pytest.approx([radius] * 2)
    assert loop_area(fresh) == pytest.approx(20.0 * 2.0 * radius + math.pi * radius * radius)


@pytest.mark.parametrize("distance", [-5.0, -6.0])
def test_a_slot_offset_past_its_radius_is_refused(distance: float) -> None:
    """−5 mm an R5: Die Bögen hätten keinen Radius mehr, die Linien liefen
    aufeinander — es bliebe nichts."""
    with pytest.raises(ValidationError):
        edit.offset(slot(), (0, 1, 2, 3), distance)


ROUNDED = (
    SketchElement(kind="line", points=((0.0, 0.0), (40.0, 0.0))),
    SketchElement(kind="line", points=((40.0, 0.0), (40.0, 29.0))),
    SketchElement(kind="arc", points=((39.0, 29.0), (40.0, 29.0), (39.0, 30.0))),
    SketchElement(kind="line", points=((39.0, 30.0), (0.0, 30.0))),
    SketchElement(kind="line", points=((0.0, 30.0), (0.0, 0.0))),
)


def test_a_rounding_grows_with_its_outline() -> None:
    """Rechteck 40 × 30 mit Verrundung R1, +2 mm: R3 um dieselbe Mitte.
    Soll von Hand: 44 · 34 − 3² + π·3²/4 = 1487 + 2,25π."""
    sketch = Sketch(plane="plane:xy", elements=ROUNDED)

    moved = edit.offset(sketch, tuple(range(5)), 2.0)

    fresh = moved.elements[5:]
    (arc,) = [element for element in fresh if element.kind == "arc"]
    assert arc.points[0] == (39.0, 29.0)
    assert math.dist(arc.points[0], arc.points[1]) == pytest.approx(3.0)
    assert loop_area(fresh) == pytest.approx(1487.0 + 2.25 * math.pi)


def test_a_rounding_smaller_than_the_offset_drops_out() -> None:
    """Dieselbe Verrundung R1, −2 mm: Ihr Radius fiele unter null, sie fällt
    weg wie eine aufgezehrte Linie, die Ecke wird scharf bei (38, 28)."""
    sketch = Sketch(plane="plane:xy", elements=ROUNDED)

    moved = edit.offset(sketch, tuple(range(5)), -2.0)

    fresh = moved.elements[5:]
    assert [element.kind for element in fresh] == ["line"] * 4
    assert copied_corners(sketch, moved) == [(2.0, 2.0), (2.0, 28.0), (38.0, 2.0), (38.0, 28.0)]
    assert loop_area(fresh) == pytest.approx(36.0 * 26.0)


HALF_DISC = (
    SketchElement(kind="line", points=((-5.0, 0.0), (5.0, 0.0))),
    SketchElement(kind="arc", points=((0.0, 0.0), (5.0, 0.0), (-5.0, 0.0))),
)


@pytest.mark.parametrize(
    ("distance", "radius", "chord"),
    [(1.0, 6.0, -1.0), (-1.0, 4.0, 1.0)],
    ids=["outwards", "inwards"],
)
def test_a_half_disc_meets_its_line_where_the_circle_cuts_it(
    distance: float, radius: float, chord: float
) -> None:
    """Ein Halbkreis R5 über seinem Durchmesser: An der Ecke treffen sich die
    versetzte Linie und der versetzte Kreis. Soll von Hand: Ecken bei
    x = ±√(R² − h²), Fläche des Kreisabschnitts über der Sehne y = h,
    R²·acos(h/R) − h·√(R² − h²)."""
    sketch = Sketch(plane="plane:xy", elements=HALF_DISC)

    moved = edit.offset(sketch, (0, 1), distance)

    fresh = moved.elements[2:]
    half = math.sqrt(radius * radius - chord * chord)
    (line,) = [element for element in fresh if element.kind == "line"]
    assert sorted(flat(line.points)) == pytest.approx(sorted([-half, chord, half, chord]))
    expected = radius * radius * math.acos(chord / radius) - chord * half
    assert loop_area(fresh) == pytest.approx(expected)


def test_an_edge_of_a_slot_follows_the_slot() -> None:
    """Die Unterkante eines Langlochs: Der Umriss schließt sich über die Bögen,
    außen ist unten."""
    sketch = slot()

    moved = edit.offset(sketch, (0,), 2.0)

    assert copied_corners(sketch, moved) == [(0.0, -7.0), (20.0, -7.0)]


def test_a_line_beside_an_outline_keeps_the_rule_of_a_free_line() -> None:
    """Eine Linie, die keinen Umriss mit schließt, wandert weiter nach oben."""
    sketch = replace(
        loop_of(RECTANGLE),
        elements=(
            *loop_of(RECTANGLE).elements,
            SketchElement(kind="line", points=((50.0, 0.0), (60.0, 0.0))),
        ),
    )

    moved = edit.offset(sketch, (4,), 2.0)

    assert copied_corners(sketch, moved) == [(50.0, 2.0), (60.0, 2.0)]


def test_the_grid_finds_the_same_partners_as_every_pair() -> None:
    """Punkt 3: Die Endensuche über das Gitter gibt dieselben Partner in
    derselben Folge wie der Vergleich jedes Paars — an Zufallsenden mit festem
    Startwert, viele davon knapp unter und über der Fangweite."""
    import random

    from app.core.sketch.profile import _JOIN_TOL, _joins

    chance = random.Random(20261011)
    ends: dict[tuple[int, int], tuple[float, float]] = {}
    for index in range(600):
        for side in (0, 1):
            if ends and chance.random() < 0.5:
                x, y = chance.choice(list(ends.values()))
                spread = _JOIN_TOL * chance.choice((0.3, 0.9, 1.1, 2.5))
                point = (x + chance.uniform(-spread, spread), y + chance.uniform(-spread, spread))
            else:
                point = (chance.uniform(-50, 50), chance.uniform(-50, 50))
            ends[(index, side)] = point
    keys = list(ends)
    expected: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for at, key in enumerate(keys):
        for other in keys[at + 1 :]:
            if other[0] != key[0] and _joins(ends[key], ends[other]):
                expected.setdefault(key, []).append(other)
                expected.setdefault(other, []).append(key)

    found = edit._partners(ends)

    assert list(found.items()) == list(expected.items())
    assert sum(len(others) for others in found.values()) > 100


def test_a_circle_beside_an_outline_grows_with_it() -> None:
    """Kreis und Umriss in einer Auswahl: beide nach außen."""
    sketch = replace(
        loop_of(RECTANGLE),
        elements=(
            *loop_of(RECTANGLE).elements,
            SketchElement(kind="circle", points=((20.0, 15.0), (25.0, 15.0))),
        ),
    )

    moved = edit.offset(sketch, (0, 1, 2, 3, 4), 2.0)

    circles = [element for element in moved.elements[5:] if element.kind == "circle"]
    assert len(circles) == 1
    centre, edge = circles[0].points
    assert math.dist(centre, edge) == pytest.approx(7.0)
    assert min(x for element in moved.elements[5:] for x, _y in element.points) == pytest.approx(
        -2.0
    )


# --- Spiegeln --------------------------------------------------------------------


def test_mirroring_at_the_x_axis_flips_the_sign_of_y() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=((1.0, 2.0), (3.0, 4.0))),),
    )

    both = edit.mirror(sketch, (0,), "x")

    assert flat(both.elements[1].points) == pytest.approx([1.0, -2.0, 3.0, -4.0])


def test_mirroring_an_arc_keeps_it_running_the_same_way() -> None:
    """Ein Bogen läuft gegen den Uhrzeigersinn; gespiegelt liefe er
    andersherum. Anfang und Ende zu tauschen dreht ihn zurück."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="arc", points=((0.0, 0.0), (5.0, 0.0), (0.0, 5.0))),),
    )

    both = edit.mirror(sketch, (0,), "y")

    centre, start, end = both.elements[1].points
    assert flat((centre,)) == pytest.approx([0.0, 0.0])
    assert flat((start,)) == pytest.approx([0.0, 5.0]), "vertauscht, damit die Drehrichtung stimmt"
    assert flat((end,)) == pytest.approx([-5.0, 0.0])


def test_mirroring_needs_an_axis_it_knows() -> None:
    with pytest.raises(ValidationError):
        edit.mirror(cross(), (0,), "diagonal")


# --- Hilfsgeometrie und Projizieren (E18) ---------------------------------------


def test_construction_geometry_carries_constraints_but_no_profile() -> None:
    """Eine Mittellinie, an der zwei Bohrungen symmetrisch hängen, soll nicht
    als Kante im extrudierten Körper landen."""
    from app.core.sketch.profile import regions_of
    from app.core.sketch.solver import solve_sketch

    square = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((-5.0, -5.0), (5.0, -5.0))),
            SketchElement(kind="line", points=((5.0, -5.0), (5.0, 5.0))),
            SketchElement(kind="line", points=((5.0, 5.0), (-5.0, 5.0))),
            SketchElement(kind="line", points=((-5.0, 5.0), (-5.0, -5.0))),
            # Die Mittellinie quer durch — sie schlösse den Umriss nicht, sie
            # verzweigte ihn, und ohne das Kennzeichen wäre die Skizze kaputt.
            SketchElement(kind="line", points=((-5.0, 0.0), (5.0, 0.0)), construction=True),
        ),
    )

    regions = regions_of(solve_sketch(square))

    assert len(regions) == 1, "die Hilfslinie bildet keinen eigenen Umriss"


def test_the_four_tools_keep_the_construction_flag() -> None:
    """Trimmen, Verlängern, Versetzen und Spiegeln bauen Elemente neu — und
    verloren dabei das Kennzeichen: Aus einer getrimmten Mittellinie wurde
    eine Profilkante, und der extrudierte Körper bekam eine Trennung mitten
    hindurch, ohne Meldung (Gesamtreview 25.08.2026, J-3). Was aus einer
    Hilfslinie entsteht, bleibt eine.
    """
    helper = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((-10.0, 0.0), (10.0, 0.0)), construction=True),
            SketchElement(kind="line", points=((0.0, -10.0), (0.0, 10.0))),
        ),
    )

    trimmed = edit.trim(helper, 0, (5.0, 0.0))
    assert trimmed.elements[0].construction, "getrimmt bleibt Hilfsgeometrie"

    short = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((-10.0, 0.0), (-5.0, 0.0)), construction=True),
            SketchElement(kind="line", points=((0.0, -10.0), (0.0, 10.0))),
        ),
    )
    extended = edit.extend(short, 0, (-5.0, 0.0))
    assert extended.elements[0].construction, "verlängert bleibt Hilfsgeometrie"

    moved = edit.offset(helper, (0,), 3.0)
    assert moved.elements[-1].construction, "die versetzte Kopie bleibt Hilfsgeometrie"

    mirrored = edit.mirror(helper, (0,), "x")
    assert mirrored.elements[-1].construction, "die gespiegelte Kopie bleibt Hilfsgeometrie"


def test_the_solver_keeps_the_construction_flag() -> None:
    """Gerechnet wird sie wie jede andere Linie — nur die Profilbildung
    übergeht sie, und die sieht ausschließlich das gelöste Ergebnis."""
    from app.core.sketch.solver import solve_sketch

    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0)), construction=True),),
    )

    assert solve_sketch(sketch).elements[0].construction


def test_the_flag_survives_a_round_trip() -> None:
    """Eine Skizze reist als Text im Op-Parameter; was der Text nicht trägt,
    ist beim nächsten Öffnen weg."""
    from app.core.sketch.serialize import sketch_from_text, sketch_to_text

    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0)), construction=True),
            SketchElement(kind="line", points=((0.0, 1.0), (10.0, 1.0))),
        ),
    )

    again = sketch_from_text(sketch_to_text(sketch))

    assert [element.construction for element in again.elements] == [True, False]


def test_a_sketch_without_construction_writes_the_old_text() -> None:
    """Jede bestehende Projektdatei liest sich unverändert — und schreibt sich
    unverändert zurück."""
    from app.core.sketch.serialize import sketch_to_text

    plain = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),),
    )

    assert "construction" not in sketch_to_text(plain)


def test_projecting_brings_the_body_edge_into_the_sketch() -> None:
    """Bei Weg 1 ist das der Normalfall: eine Bohrung soll auf die vorhandene
    Kante ausgerichtet werden, und ohne die Kante bleibt nur Abmessen."""
    import trimesh

    from app.core.geom.mesh import MeshData

    box = MeshData.of(trimesh.creation.box(extents=(20.0, 10.0, 6.0)))
    empty = Sketch(plane="plane:xy", elements=())

    projected = edit.project(empty, box)

    assert projected.elements, "der Schnitt liefert Kanten"
    assert all(element.construction for element in projected.elements), (
        "als Hilfsgeometrie — was aus dem Körper kommt, ist zum Anlehnen da"
    )
    xs = [point[0] for element in projected.elements for point in element.points]
    ys = [point[1] for element in projected.elements for point in element.points]
    assert max(xs) == pytest.approx(10.0), "die halbe Breite des Quaders"
    assert max(ys) == pytest.approx(5.0)


def test_projecting_beside_the_body_says_so() -> None:
    """Regel 17: ein Schnitt ins Leere ist eine Aussage, kein leeres
    Ergebnis."""
    import trimesh

    from app.core.geom.mesh import MeshData

    box = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 4.0)))
    box.raw.apply_translation((0.0, 0.0, 50.0))
    empty = Sketch(plane="plane:xy", elements=())

    with pytest.raises(ValidationError):
        edit.project(empty, box)


def _exact_plate() -> object:
    """Platte 60 x 40 x 10 mit einer Bohrung Ø 8 bei (−10 | 5) und einem Langloch."""
    exact_kernel()

    from app.core.brep import edit as brep_edit

    plate = brep_edit.box(60.0, 40.0, 10.0)
    plate = brep_edit.cut_bore(
        plate, position=(-10.0, 5.0, 5.0), direction=(0.0, 0.0, 1.0), diameter=8.0, depth=12.0
    )
    return brep_edit.slot_bore(
        plate,
        position=(15.0, -5.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=10.0,
        length=16.0,
        angle_deg=0.0,
        overlap=0.0,
    )


def test_a_section_through_an_exact_body_keeps_its_circles_and_arcs() -> None:
    """P3.5: Der exakte Körper wird exakt geschnitten, nicht seine Vernetzung.

    Am Netz kam die Bohrung als Vieleck aus kurzen Strecken in die Zeichnung
    — ohne Mitte, an der eine Bemaßung hängen könnte. Jetzt ist sie ein Kreis
    mit Mittelpunkt und Radius, das Langloch zwei Halbkreise, der Rand vier
    Strecken, und alles ist Hilfsgeometrie. Sollwerte aus den Baumaßen oben.
    """
    plate = _exact_plate()
    empty = Sketch(plane="plane:xy", elements=())
    frame_origin = (0.0, 0.0, 5.0)

    class _Frame:
        origin = frame_origin
        normal = (0.0, 0.0, 1.0)
        x_axis = (1.0, 0.0, 0.0)
        y_axis = (0.0, 1.0, 0.0)

    projected = edit.project(empty, plate, _Frame())

    kinds = sorted(element.kind for element in projected.elements)
    assert kinds == ["arc", "arc", "circle", "line", "line", "line", "line", "line", "line"]
    assert all(element.construction for element in projected.elements)
    (circle,) = [element for element in projected.elements if element.kind == "circle"]
    centre, rim = circle.points
    assert centre == pytest.approx((-10.0, 5.0), abs=1e-9)
    assert math.dist(centre, rim) == pytest.approx(4.0, abs=1e-9)
    arcs = [element for element in projected.elements if element.kind == "arc"]
    assert sorted(round(arc.points[0][0], 9) for arc in arcs) == pytest.approx([10.0, 20.0])
    for arc in arcs:
        middle, start, end = arc.points
        assert math.dist(middle, start) == pytest.approx(3.0, abs=1e-9)
        assert math.dist(middle, end) == pytest.approx(3.0, abs=1e-9)
        # Gegen den Uhrzeigersinn von Anfang nach Ende — der Halbkreis zeigt
        # vom Langloch weg, also liegt seine Wölbung außen.
        sweep = (
            math.atan2(end[1] - middle[1], end[0] - middle[0])
            - math.atan2(start[1] - middle[1], start[0] - middle[0])
        ) % math.tau
        assert sweep == pytest.approx(math.pi, abs=1e-9)
        bulge_angle = math.atan2(start[1] - middle[1], start[0] - middle[0]) + sweep / 2.0
        outward = 1.0 if middle[0] > 15.0 else -1.0
        assert math.cos(bulge_angle) * outward == pytest.approx(1.0, abs=1e-9)
    xs = [
        point[0]
        for element in projected.elements
        if element.kind == "line"
        for point in element.points
    ]
    assert max(xs) == pytest.approx(30.0, abs=1e-9) and min(xs) == pytest.approx(-30.0, abs=1e-9)


def test_an_oblique_section_of_an_exact_cylinder_becomes_a_curve() -> None:
    """Was weder Strecke noch Kreis ist — die Ellipse eines schräg geschnittenen
    Zylinders —, kommt als Kurve durch Punkte auf der echten Schnittlinie."""
    exact_kernel()

    from app.core.brep import edit as brep_edit

    tilt = math.radians(30.0)

    class _Frame:
        origin = (0.0, 0.0, 15.0)
        normal = (0.0, -math.sin(tilt), math.cos(tilt))
        x_axis = (1.0, 0.0, 0.0)
        y_axis = (0.0, math.cos(tilt), math.sin(tilt))

    cylinder = brep_edit.cylinder(20.0, 30.0)
    projected = edit.project(Sketch(plane="plane:xy", elements=()), cylinder, _Frame())

    assert [element.kind for element in projected.elements] == ["spline"]
    for x, y in projected.elements[0].points:
        # Die Ellipse mit den Halbachsen 10 und 10 / cos 30°.
        assert (x / 10.0) ** 2 + (y * math.cos(tilt) / 10.0) ** 2 == pytest.approx(1.0, abs=1e-6)


def test_section_ends_within_the_kernels_own_tolerance_become_one_point() -> None:
    """Am Körper aus einem Netz (P4.0) schließen Nachbarflächen nur innerhalb
    der Toleranz ihrer Eckpunkte aneinander; am Besenhalter aus Roberts Test
    lagen die Schnittkanten 0,0001 bis 0,0002 mm auseinander, und die Skizze
    nahm den Umriss als offen nicht an. Zusammengelegt wird, was näher liegt
    als beide Eckpunkttoleranzen zusammen — nicht mehr: Bei Toleranzen eines
    sauberen Körpers bleibt dieselbe Lücke stehen. Doppelte Kanten und
    Strecken ohne Länge entfallen."""
    exact_kernel()
    from app.core.brep.section import SectionCurve, _joined

    loose = 1.5e-4
    bend = [
        SectionCurve("line", ((0.0, 0.0), (10.0, 0.0))),
        SectionCurve("line", ((10.0 + loose, 0.0), (10.0, 10.0))),
        SectionCurve("arc", ((10.0, 15.0), (10.0, 10.0 + loose), (15.0, 15.0))),
        SectionCurve("line", ((10.0, 10.0), (10.0 + loose, 0.0))),
        SectionCurve("line", ((0.0, 0.0), (loose / 2.0, 0.0))),
    ]
    sewn = [(1e-4, 1e-4)] * len(bend)
    clean = [(1e-7, 1e-7)] * len(bend)

    joined = _joined(bend, sewn)
    corner = {curve.points[-1] for curve in joined[:1]} | {joined[1].points[0]}
    assert len(corner) == 1, "die Ecke bei x = 10 ist ein Punkt"
    assert joined[2].points[1] == joined[1].points[1], "der Bogen schließt an die Strecke an"
    assert len(joined) == 3, "die rückwärts doppelte Kante und die Strecke ohne Länge entfallen"

    kept = _joined(bend, clean)
    assert kept[0].points[1] != kept[1].points[0], "bei sauberen Toleranzen bleibt die Lücke"

    # Rückt ein Bogenende auf das Ende einer Strecke, bleibt der Bogen ein
    # Bogen: Seine Schenkel sind gleich lang, sonst nähme der Löser die
    # Skizze mit festen Punkten als Widerspruch nicht an.
    quarter = [
        SectionCurve("line", ((5.0, -5.0), (0.0, 5.0 + loose))),
        SectionCurve("arc", ((0.0, 0.0), (0.0, 5.0), (-5.0, 0.0))),
    ]
    welded = _joined(quarter, [(1e-4, 1e-4)] * 2)
    centre, start, end = welded[1].points
    assert start == welded[0].points[1]
    assert math.dist(centre, start) == pytest.approx(math.dist(centre, end), abs=1e-12)
    assert math.dist(centre, (0.0, 0.0)) <= loose


def test_a_section_beside_an_exact_body_says_so() -> None:
    """Regel 17 gilt auch am exakten Weg: kein Schnitt, eine Aussage."""
    plate = _exact_plate()

    class _Frame:
        origin = (0.0, 0.0, 50.0)
        normal = (0.0, 0.0, 1.0)
        x_axis = (1.0, 0.0, 0.0)
        y_axis = (0.0, 1.0, 0.0)

    with pytest.raises(ValidationError):
        edit.project(Sketch(plane="plane:xy", elements=()), plate, _Frame())


# --- Verrunden und Fase -----------------------------------------------------------


def box() -> Sketch:
    """Ein Rechteck aus vier Linien mit Deckung, waagerecht und senkrecht —
    ohne Maße und ohne Festpunkt, so wie der Editor es zeichnet."""
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (40.0, 0.0))),
            SketchElement(kind="line", points=((40.0, 0.0), (40.0, 20.0))),
            SketchElement(kind="line", points=((40.0, 20.0), (0.0, 20.0))),
            SketchElement(kind="line", points=((0.0, 20.0), (0.0, 0.0))),
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
        ),
    )


def test_a_corner_is_two_lines_meeting_at_the_same_spot() -> None:
    """Gesucht wird über die gelösten Punkte, nicht über die Deckung: Beide
    Enden liegen am selben Ort, und das reicht. Ein Punkt mitten auf einer
    Linie ist keine Ecke, und ein Bogenende auch nicht."""
    sketch = box()
    points = edit.flat_points(sketch)

    corner = edit.corner_at(sketch, points, 3)
    assert corner is not None
    assert corner.spot == (40.0, 20.0)
    assert {corner.first[0], corner.second[0]} == {1, 2}

    # Dieselbe Ecke, über den anderen der zwei deckungsgleichen Punkte.
    assert edit.corner_at(sketch, points, 4) == corner
    assert edit.corner_at(sketch, points, 99) is None

    lonely = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),),
    )
    assert edit.corner_at(lonely, edit.flat_points(lonely), 1) is None, "eine Linie ist keine Ecke"


def test_a_construction_line_makes_no_corner() -> None:
    """Eine Hilfslinie, die auf ein Linienende trifft, ist kein Eckenschenkel.

    Sie ist ``kind == "line"`` mit ``construction``; als Schenkel gezählt
    würde sie gekürzt und der Bogen entstünde ohne Kennzeichen — eine
    Profilkante aus Hilfsgeometrie (Fund des Reviews vom 14.09.2026).
    """
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),
            SketchElement(kind="line", points=((10.0, 0.0), (10.0, 10.0)), construction=True),
        ),
    )
    points = edit.flat_points(sketch)
    assert edit.corner_at(sketch, points, 1) is None, "ein Ende und eine Hilfslinie: keine Ecke"
    with pytest.raises(ValidationError):
        edit.fillet(sketch, points, 1, 2.0)


def test_a_fillet_replaces_the_corner_with_a_tangent_arc() -> None:
    """Radius 5 an der rechten oberen Ecke: Beide Linien enden fünf Millimeter
    vor der Ecke, der Bogen sitzt um (35 | 15) und läuft von (40 | 15) nach
    (35 | 20). Die Zahlen stehen ausgerechnet da — ein Vorzeichenfehler
    setzte die Mitte außerhalb."""
    sketch = box()
    rounded = edit.fillet(sketch, edit.flat_points(sketch), 3, 5.0)

    assert len(rounded.elements) == 6, "vier Linien, der Bogen, der Hilfspunkt der alten Ecke"
    assert rounded.elements[5] == SketchElement("point", ((40.0, 20.0),), construction=True)
    assert rounded.elements[1].points == ((40.0, 0.0), (40.0, 15.0))
    assert rounded.elements[2].points[0] == pytest.approx((35.0, 20.0))
    arc = rounded.elements[4]
    assert arc.kind == "arc"
    assert flat(arc.points) == pytest.approx(flat(((35.0, 15.0), (40.0, 15.0), (35.0, 20.0))))

    kinds = [entry.kind for entry in rounded.constraints]
    assert kinds.count("coincident") == 5, "die Ecke ist weg, zwei Bogenenden sind dazu"
    assert kinds.count("perpendicular") == 2, "die Tangente als Senkrechte zum Radiusstrahl"
    assert kinds.count("radius") == 1
    assert kinds.count("horizontal") == 3 and kinds.count("vertical") == 3, (
        "der Hilfspunkt liegt auf beiden verlängerten Schenkeln — hier achsparallel"
    )
    assert any(
        entry.kind == "coincident" and set(entry.targets) == {3, 4} for entry in box().constraints
    ), "vorher gab es die Eckdeckung — sonst prüft die nächste Zeile nichts"
    assert not any(
        entry.kind == "coincident" and set(entry.targets) == {3, 4} for entry in rounded.constraints
    ), "die alte Eckdeckung ist gelöst"


def test_a_fillet_solves_determined_and_survives_a_drag() -> None:
    """Der Beleg dafür, dass die Bedingungen tragen: Der Löser nimmt die
    verrundete Skizze ohne Widerspruch an, zählt dieselben vier freien Grade
    wie vorher — und wer danach an einer Ecke zieht, nimmt die Rundung mit,
    statt sie zu zerreißen."""
    from app.core.sketch.profile import regions_of
    from app.core.sketch.solver import solve_sketch

    sketch = box()
    rounded = edit.fillet(sketch, edit.flat_points(sketch), 3, 5.0)
    solved = solve_sketch(rounded)
    assert solved.free_dof == 4, "Lage und zwei Seiten bleiben frei, die Rundung nicht"
    assert len(regions_of(solved)) == 1, "und der Umriss ist geschlossen"

    # Gezogen wird in kleinen Schritten, wie die Maus es tut: Ein einziger
    # Sprung um zehn Millimeter lässt die nichtlinearen Bedingungen (Radius,
    # Senkrechte) beim Gauß-Newton-Schritt um 2·10⁻⁴ mm im Nullraum driften;
    # fünfzig Schritte à 0,2 mm bleiben unter 10⁻⁸ — gemessen 13.09.2026.
    points = [point for element in solved.elements for point in element.points]
    for step in range(1, 51):
        dragged = solve_sketch(rounded, dragged={5: (0.0, 20.0 + 0.2 * step)}, start=points)
        points = [point for element in dragged.elements for point in element.points]
    assert points[8] == pytest.approx((35.0, 25.0), abs=1e-6), "die Bogenmitte ist mitgewandert"
    assert math.dist(points[8], points[9]) == pytest.approx(5.0), "und der Radius hält"
    assert points[1] == pytest.approx((40.0, 0.0), abs=1e-6), "die andere Seite blieb stehen"


def test_a_fillet_names_the_largest_radius_that_fits() -> None:
    """Zwanzig Millimeter ist die kurze Seite: Ein Radius von 30 passt nicht,
    und die Absage nennt die Grenze (Regel 17).

    **Die Grenze selbst passt nicht** — bei Radius 20 bliebe eine Linie ohne
    Länge —, und deshalb sagt der Satz „kleiner als 20", nicht „höchstens
    20": Wer die genannte Zahl eintippte, bekam dieselbe Absage noch einmal
    (Fund des Reviews vom 14.09.2026). Knapp darunter geht es.
    """
    sketch = box()
    with pytest.raises(ValidationError) as caught:
        edit.fillet(sketch, edit.flat_points(sketch), 3, 30.0)
    assert caught.value.values["most_mm"] == pytest.approx(20.0)
    assert "20" in str(caught.value.detail)
    with pytest.raises(ValidationError):
        edit.fillet(sketch, edit.flat_points(sketch), 3, 20.0)
    assert len(edit.fillet(sketch, edit.flat_points(sketch), 3, 19.99).elements) == 6
    # ``maximum`` ist eine Bereichsgrenze, und nur die trägt den Titel „außerhalb
    # des zulässigen Bereichs"; ein unbekannter Wert bekäme den vagen Satz.
    assert caught.value.constraint == "maximum"
    assert caught.value.title is ValidationError.default_title

    with pytest.raises(ValidationError):
        edit.fillet(sketch, edit.flat_points(sketch), 3, 0.0)


def test_a_chamfer_cuts_the_corner_with_a_straight_edge() -> None:
    """Fase 5: beide Linien um fünf gekürzt, dazwischen die Schräge. Das Maß
    steht, wie getippt, von der alten Ecke aus — fünf auf dem einen Schenkel,
    gleich lang auf dem anderen —, und nicht als Länge der Schräge (5·√2),
    deren Winkel dann frei blieb (Bedienabnahme Zeichnen, F3)."""
    from app.core.sketch.profile import regions_of
    from app.core.sketch.solver import solve_sketch

    sketch = box()
    cut = edit.chamfer(sketch, edit.flat_points(sketch), 3, 5.0)

    assert len(cut.elements) == 6
    edge = cut.elements[4]
    assert edge.kind == "line"
    assert flat(edge.points) == pytest.approx(flat(((40.0, 15.0), (35.0, 20.0))))
    assert cut.elements[5] == SketchElement("point", ((40.0, 20.0),), construction=True)
    measure = [entry for entry in cut.constraints if entry.kind == "distance"]
    assert len(measure) == 1
    assert float(measure[0].value) == pytest.approx(5.0)
    assert 10 in measure[0].targets, "gemessen vom Hilfspunkt der alten Ecke"
    assert solve_sketch(cut).free_dof == solve_sketch(sketch).free_dof, "kein Grad mehr frei"

    solved = solve_sketch(cut)
    assert len(regions_of(solved)) == 1, "der Umriss bleibt geschlossen"

    with pytest.raises(ValidationError) as caught:
        edit.chamfer(sketch, edit.flat_points(sketch), 3, 25.0)
    assert caught.value.values["most_mm"] == pytest.approx(20.0)
    assert caught.value.constraint == "maximum"
    assert caught.value.title is ValidationError.default_title
    with pytest.raises(ValidationError):
        edit.chamfer(sketch, edit.flat_points(sketch), 3, 20.0)
    assert len(edit.chamfer(sketch, edit.flat_points(sketch), 3, 19.99).elements) == 6


def _typed_rectangle(anchored: bool = False) -> Sketch:
    """Ein Rechteck 80 × 50 mit der unteren linken Ecke im Ursprung, beide
    Maße getippt — wie ``SketchCanvas._finish_rectangle`` es nach „80 Tab 50
    Enter" baut: waagerecht, senkrecht, Deckung, zwei Maße, kein Festpunkt."""
    from app.core.sketch import shapes

    rectangle = edit.move(shapes.rectangle(80.0, 50.0), (0, 1, 2, 3), 40.0, 25.0)
    return replace(
        rectangle,
        constraints=tuple(
            entry for entry in rectangle.constraints if anchored or entry.kind != "fixed"
        ),
    )


def _drawn_extent(solved) -> tuple[tuple[float, float], tuple[float, float]]:
    """Hülle der gezeichneten Linienenden — Hilfsgeometrie zählt nicht."""
    points = [
        point
        for element in solved.elements
        if element.kind == "line" and not element.construction
        for point in element.points
    ]
    xs, ys = [point[0] for point in points], [point[1] for point in points]
    return (min(xs), min(ys)), (max(xs), max(ys))


@pytest.mark.parametrize("flat_index", [1, 3, 5, 7])
@pytest.mark.parametrize("tool", ["fillet", "chamfer"])
def test_breaking_a_corner_keeps_a_typed_rectangle_at_its_size(tool: str, flat_index: int) -> None:
    """Bedienabnahme Zeichnen, F3: 80 × 50 getippt, R 5 an einer Ecke — und
    die Platte kam 80 × 55 aus dem Dialog, um 3,2 mm nach unten gewandert.

    Das Maß der gekürzten Seite zeigte danach auf das Reststück. Soll: die
    Hülle bleibt (0 | 0)–(80 | 50) auf 10⁻⁶, an jeder der vier Ecken und mit
    beiden Werkzeugen (Sollwert aus dem Bericht, Abschnitt F3).
    """
    from app.core.sketch.solver import solve_sketch

    sketch = _typed_rectangle()
    points = edit.flat_points(sketch)
    broken = getattr(edit, tool)(sketch, points, flat_index, 5.0)
    solved = solve_sketch(broken)

    low, high = _drawn_extent(solved)
    assert low == pytest.approx((0.0, 0.0), abs=1e-6)
    assert high == pytest.approx((80.0, 50.0), abs=1e-6)
    assert solved.free_dof == solve_sketch(sketch).free_dof, "nur die Lage bleibt frei"


def test_a_fully_dimensioned_rectangle_stays_determined_after_a_chamfer() -> None:
    """Mit Festpunkt und beiden Maßen ist das Rechteck bestimmt — und die Fase
    daran auch. Vorher blieb ihr Winkel ein freier Grad; die Zeile sagte
    „Noch ein Maß fehlt" über etwas, das vollständig eingegeben war. Der
    Festpunkt sitzt an der unteren linken Ecke, und genau die wird gebrochen:
    Er wandert auf den Hilfspunkt und hält weiter."""
    from app.core.sketch.solver import solve_sketch

    sketch = _typed_rectangle(anchored=True)
    assert solve_sketch(sketch).free_dof == 0
    for tool in ("fillet", "chamfer"):
        broken = getattr(edit, tool)(sketch, edit.flat_points(sketch), 0, 4.0)
        solved = solve_sketch(broken)
        assert solved.free_dof == 0, tool
        low, high = _drawn_extent(solved)
        assert low == pytest.approx((0.0, 0.0), abs=1e-6), tool
        assert high == pytest.approx((80.0, 50.0), abs=1e-6), tool


def test_what_hung_at_the_corner_moves_to_the_virtual_corner() -> None:
    """Eine Hilfslinie von der Ecke zur Mitte bleibt an der Ecke — auch wenn
    die Ecke nur noch ein Hilfspunkt ist. Ohne Umhängen zeigte ihre Deckung
    auf das gekürzte Linienende und zog die Hilfslinie mit dem Bogen weg."""
    from app.core.sketch.solver import solve_sketch

    sketch = box()
    diagonal = SketchElement("line", ((40.0, 20.0), (20.0, 10.0)), construction=True)
    sketch = replace(
        sketch,
        elements=(*sketch.elements, diagonal),
        constraints=(*sketch.constraints, SketchConstraint("coincident", (3, 8))),
    )
    rounded = edit.fillet(sketch, edit.flat_points(sketch), 3, 5.0)
    virtual = len(edit.flat_points(rounded)) - 1
    assert SketchConstraint("coincident", (virtual, 8)) in rounded.constraints
    solved = solve_sketch(rounded)
    assert solved.elements[4].points[0] == pytest.approx((40.0, 20.0), abs=1e-9)


def test_an_oblique_corner_keeps_its_virtual_corner_on_both_legs() -> None:
    """Ohne Achse liegt der Hilfspunkt über ``parallel`` auf den Schenkeln —
    und ein Maß von einem fernen Ende bis zur alten Ecke hält auch dort."""
    from app.core.sketch.solver import solve_sketch

    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (30.0, 10.0))),
            SketchElement("line", ((30.0, 10.0), (10.0, 30.0))),
        ),
        constraints=(
            SketchConstraint("coincident", (1, 2)),
            SketchConstraint("distance", (0, 1), str(math.hypot(30.0, 10.0))),
            SketchConstraint("fixed", (0,)),
        ),
    )
    rounded = edit.fillet(sketch, edit.flat_points(sketch), 1, 3.0)
    assert [entry.kind for entry in rounded.constraints].count("parallel") == 2
    solved = solve_sketch(rounded)
    virtual = solved.elements[-1].points[0]
    assert virtual == pytest.approx((30.0, 10.0), abs=1e-6), "die alte Ecke steht"


def test_breaking_needs_a_corner() -> None:
    """Ein Punkt, an dem keine zwei Linien enden, ist keine Ecke — beide
    Werkzeuge sagen das, statt still nichts zu tun."""
    lonely = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0))),),
    )
    with pytest.raises(ValidationError):
        edit.fillet(lonely, edit.flat_points(lonely), 1, 1.0)
    with pytest.raises(ValidationError):
        edit.chamfer(lonely, edit.flat_points(lonely), 1, 1.0)


# --- Vieleck und Langloch aus zwei Klicks (§30.1, W2) ----------------------------


@pytest.mark.parametrize("corners", [3, 4, 5, 6, 8, 12])
def test_a_drawn_polygon_stays_regular_under_the_solver(corners: int) -> None:
    """Alle Seiten gleich lang, alle Ecken auf dem Umkreis — und das gerechnet,
    nicht bloß hingeschrieben.

    Die Konstruktion ist der Prüfling: Wer die Punkte ausrechnet und sie
    danach wieder ausliest, hat die Bedingungen nicht geprüft. Der Löser läuft
    also über eine **verzogene** Ausgangslage, und erst sein Ergebnis wird
    gemessen.
    """
    from app.core.sketch import solve_sketch

    sketch = edit.polygon_at((2.0, 3.0), (12.0, 3.0), corners)
    # Eine Ecke aus der Reihe: Ohne sie beginnt der Löser in der Lösung, und
    # der Test bestätigte die Konstruktion statt der Bedingungen.
    pulled = list(sketch.elements)
    first = pulled[0]
    pulled[0] = SketchElement(
        kind="line",
        points=((first.points[0][0] + 1.7, first.points[0][1] - 0.9), first.points[1]),
        construction=first.construction,
    )
    solved = solve_sketch(
        Sketch(plane=sketch.plane, elements=tuple(pulled), constraints=sketch.constraints)
    )

    hub, rim = solved.elements[-1].points
    radius = math.dist(hub, rim)
    sides = [math.dist(*element.points) for element in solved.elements[:corners]]
    wanted = 2.0 * radius * math.sin(math.pi / corners)

    assert solved.max_residual <= 1e-6
    assert sides == pytest.approx([wanted] * corners, abs=1e-6)
    for element in solved.elements[:corners]:
        assert math.dist(hub, element.points[0]) == pytest.approx(radius, abs=1e-6)
    assert solved.free_dof == 3, "Mitte und Radius bleiben frei, die Drehung ist die Eichung"


def test_a_drawn_polygon_is_determined_by_its_centre_and_one_radius() -> None:
    """Die Zusage des Werkzeugs, in einer Zahl: Mitte fest, Umkreis bemaßt,
    null Freiheitsgrade."""
    from app.core.sketch import solve_sketch

    sketch = edit.polygon_at((0.0, 0.0), (10.0, 0.0), 6)
    hub = len(edit.flat_points(sketch)) - 2
    bound = Sketch(
        plane=sketch.plane,
        elements=sketch.elements,
        constraints=(
            *sketch.constraints,
            SketchConstraint(kind="fixed", targets=(hub,)),
            SketchConstraint(kind="diameter", targets=(hub, hub + 1), value="20"),
        ),
    )
    solved = solve_sketch(bound)
    assert solved.free_dof == 0
    assert math.dist(*solved.elements[-1].points) == pytest.approx(10.0, abs=1e-6)


def test_the_construction_circle_of_a_polygon_is_no_outline() -> None:
    """Der Umkreis trägt die Regelmäßigkeit und bildet kein Profil — sonst
    stünde im Körper ein Rohr um das Vieleck."""
    from app.core.sketch import solve_sketch
    from app.core.sketch.profile import regions_of

    sketch = edit.polygon_at((0.0, 0.0), (10.0, 0.0), 6)
    assert sketch.elements[-1].construction, "der Hilfskreis ist Hilfsgeometrie"
    regions = regions_of(solve_sketch(sketch))
    assert len(regions) == 1
    assert len(regions[0].segments) == 6, "sechs Kanten, kein Kreis dazwischen"


def test_a_polygon_needs_at_least_three_corners() -> None:
    with pytest.raises(ValidationError) as caught:
        edit.polygon_at((0.0, 0.0), (10.0, 0.0), 2)
    assert caught.value.constraint == "corner_count"
    assert caught.value.suggestions


def test_a_polygon_needs_two_different_points() -> None:
    """Mitte und Ecke am selben Fleck geben keinen Umkreis."""
    with pytest.raises(ValidationError):
        edit.polygon_at((4.0, 4.0), (4.0, 4.0), 6)


@pytest.mark.parametrize("turn", [0.0, 0.4, 1.2, 2.9])
def test_a_drawn_slot_keeps_its_shape_in_every_direction(turn: float) -> None:
    """Zwei runde Enden gleicher Größe, zwei Flanken quer dazu — gleich, ob
    das Langloch waagerecht liegt oder schräg.

    Das Langloch der Grundformen hält seine Achse mit ``horizontal``; dieses
    hier entsteht zwischen zwei Klicks und darf jede Richtung haben. Geprüft
    wird deshalb in vier Richtungen und nicht in einer.
    """
    from app.core.sketch import solve_sketch

    first = (1.0, 2.0)
    second = (1.0 + 20.0 * math.cos(turn), 2.0 + 20.0 * math.sin(turn))
    solved = solve_sketch(edit.slot_between(first, second, 6.0))

    low, right, high, left = solved.elements
    assert [element.kind for element in solved.elements] == ["line", "arc", "line", "arc"]
    assert math.dist(right.points[0], right.points[1]) == pytest.approx(3.0, abs=1e-6)
    assert math.dist(left.points[0], left.points[1]) == pytest.approx(3.0, abs=1e-6)
    assert math.dist(left.points[0], right.points[0]) == pytest.approx(20.0, abs=1e-6)
    assert math.dist(*low.points) == pytest.approx(20.0, abs=1e-6)
    assert math.dist(*high.points) == pytest.approx(20.0, abs=1e-6)
    assert solved.max_residual <= 1e-6
    assert solved.free_dof == 5, "beide Mitten und die Breite"


def test_a_slot_closes_into_one_outline() -> None:
    from app.core.sketch import solve_sketch
    from app.core.sketch.profile import regions_of

    regions = regions_of(solve_sketch(edit.slot_between((0.0, 0.0), (20.0, 0.0), 6.0)))
    assert len(regions) == 1
    assert len(regions[0].segments) == 4


def test_a_slot_needs_a_length_and_a_width() -> None:
    with pytest.raises(ValidationError):
        edit.slot_between((0.0, 0.0), (0.0, 0.0), 6.0)
    with pytest.raises(ValidationError):
        edit.slot_between((0.0, 0.0), (20.0, 0.0), 0.0)


def test_the_two_drawn_shapes_become_bodies_with_the_volume_they_promise() -> None:
    """Die analytische Gegenrechnung, am Körper und nicht an der Zeichnung.

    Sechseck über Ø 20 mm: ``3·√3/2 · 10² · 10`` = 2598,076 mm³.
    Langloch 20 mm Mittenabstand, 6 mm breit: ``(20 · 6 + π · 3²) · 10``
    = 1482,743 mm³.
    """
    exact_kernel()
    from app.core.brep import profiles as brep_profiles
    from app.core.sketch import solve_sketch
    from app.core.sketch.profile import regions_of

    polygon = regions_of(solve_sketch(edit.polygon_at((0.0, 0.0), (10.0, 0.0), 6)))[0]
    assert brep_profiles.extrude(polygon, 10.0).volume == pytest.approx(
        3.0 * math.sqrt(3.0) / 2.0 * 10.0**2 * 10.0, rel=1e-9
    )

    slot = regions_of(solve_sketch(edit.slot_between((0.0, 0.0), (20.0, 0.0), 6.0)))[0]
    assert brep_profiles.extrude(slot, 10.0).volume == pytest.approx(
        (20.0 * 6.0 + math.pi * 3.0**2) * 10.0, rel=1e-9
    )


# --- Lochraster und Lochkreis mit zwei Klicks (16.09.2026) ---------------------


def _pulled(sketch: Sketch, index: int, by: tuple[float, float]) -> Sketch:
    """Ein Kreis aus der Reihe gezogen — Mitte und Randpunkt gemeinsam.

    Ohne den Zug beginnt der Löser in der Lösung, und der Test bestätigte die
    Konstruktion statt der Bedingungen (dasselbe Muster wie beim Vieleck).
    """
    elements = list(sketch.elements)
    circle = elements[index]
    elements[index] = SketchElement(
        kind=circle.kind,
        points=tuple((x + by[0], y + by[1]) for x, y in circle.points),
        construction=circle.construction,
    )
    return Sketch(plane=sketch.plane, elements=tuple(elements), constraints=sketch.constraints)


def test_a_drawn_hole_grid_stays_a_grid_under_the_solver() -> None:
    """Zeilen waagerecht, Spalten senkrecht, Abstände gleich, Löcher gleich —
    gerechnet über eine verzogene Ausgangslage, nicht hingeschrieben.

    Vier Spalten und drei Zeilen zwischen (5 | 5) und (35 | 25): Abstand zehn
    in x, zehn in y. Frei bleiben die Lage, die beiden Abstände und der
    Radius — fünf Freiheitsgrade; den Durchmesser bemaßt erst die Leiste.
    """
    from app.core.sketch import solve_sketch

    sketch = edit.hole_grid_between((5.0, 5.0), (35.0, 25.0), 4, 3, 4.0)
    assert [element.kind for element in sketch.elements] == ["circle"] * 12
    assert not any(element.construction for element in sketch.elements)

    solved = solve_sketch(_pulled(sketch, 5, (1.3, -0.8)))
    assert solved.max_residual <= 1e-6
    centres = [element.points[0] for element in solved.elements]
    radii = [math.dist(*element.points) for element in solved.elements]

    def at(column: int, row: int) -> tuple[float, float]:
        return centres[row * 4 + column]

    for row in range(3):
        assert {round(at(column, row)[1], 6) for column in range(4)} == {round(at(0, row)[1], 6)}
    for column in range(4):
        assert {round(at(column, row)[0], 6) for row in range(3)} == {round(at(column, 0)[0], 6)}
    across = [at(column + 1, 0)[0] - at(column, 0)[0] for column in range(3)]
    upward = [at(0, row + 1)[1] - at(0, row)[1] for row in range(2)]
    assert across == pytest.approx([across[0]] * 3, abs=1e-6)
    assert upward == pytest.approx([upward[0]] * 2, abs=1e-6)
    assert radii == pytest.approx([radii[0]] * 12, abs=1e-6)
    assert solved.free_dof == 5, "Lage, zwei Abstände und ein Radius bleiben frei"


def test_a_single_column_grid_has_only_one_spacing() -> None:
    """Eine Spalte, drei Zeilen: kein waagerechter Abstand, den man frei ließe."""
    from app.core.sketch import solve_sketch

    sketch = edit.hole_grid_between((0.0, 0.0), (7.0, 20.0), 1, 3, 3.0)
    solved = solve_sketch(_pulled(sketch, 1, (0.6, 0.4)))
    assert solved.max_residual <= 1e-6
    xs = {round(element.points[0][0], 6) for element in solved.elements}
    assert len(xs) == 1, "eine Spalte steht senkrecht, der Zug nach rechts zählt nicht"
    assert solved.free_dof == 4, "Lage, ein Abstand und ein Radius"


def test_a_hole_grid_refuses_what_is_no_grid() -> None:
    with pytest.raises(ValidationError):
        edit.hole_grid_between((0.0, 0.0), (10.0, 10.0), 1, 1, 3.0)
    with pytest.raises(ValidationError):
        edit.hole_grid_between((0.0, 0.0), (0.0, 10.0), 2, 2, 3.0)
    with pytest.raises(ValidationError):
        edit.hole_grid_between((0.0, 0.0), (10.0, 10.0), 2, 2, 10.0)
    with pytest.raises(ValidationError):
        edit.hole_grid_between((0.0, 0.0), (10.0, 10.0), 0, 2, 3.0)


def test_a_hole_grid_in_one_line_says_what_is_missing() -> None:
    """Zwei Klicks in einer Flucht sind nicht „aufeinander".

    Wer für vier Spalten und drei Zeilen senkrecht unter den ersten Klick
    klickte, las „Die beiden Klicks liegen aufeinander" — sie lagen zwanzig
    Millimeter auseinander, nur ohne Abstand quer (Durchsicht 22.09.2026).
    """
    with pytest.raises(ValidationError) as in_line:
        edit.hole_grid_between((0.0, 0.0), (0.0, 20.0), 4, 3, 2.0)
    assert in_line.value.constraint == "grid_in_line"
    assert "Flucht" in str(in_line.value.detail)

    with pytest.raises(ValidationError) as same_spot:
        edit.hole_grid_between((5.0, 5.0), (5.0, 5.0), 4, 3, 2.0)
    assert same_spot.value.constraint != "grid_in_line", "am selben Fleck bleibt es der alte Satz"

    one_column = edit.hole_grid_between((0.0, 0.0), (0.0, 20.0), 1, 3, 2.0)
    assert len(one_column.elements) == 3, "eine Spalte braucht keinen Abstand quer"


@pytest.mark.parametrize("count", [2, 3, 6])
def test_a_drawn_bolt_circle_stays_regular_under_the_solver(count: int) -> None:
    """Alle Mitten auf dem Teilkreis, gleich weit auseinander, alle Löcher
    gleich — und der Teilkreis reist als Hilfskreis mit, wie beim Vieleck.

    Frei bleiben Mitte, Teilkreis und Lochradius: vier Freiheitsgrade; die
    Drehung ist die Eichfreiheit des Randpunkts auf seinem Kreis.
    """
    from app.core.sketch import solve_sketch

    sketch = edit.bolt_circle_at((2.0, 3.0), (22.0, 3.0), count, 4.0)
    assert [element.kind for element in sketch.elements] == ["circle"] * (count + 1)
    assert sketch.elements[-1].construction, "der Teilkreis ist Hilfsgeometrie"

    solved = solve_sketch(_pulled(sketch, 1 if count > 2 else 0, (1.1, -0.7)))
    assert solved.max_residual <= 1e-6
    hub, rim = solved.elements[-1].points
    pitch = math.dist(hub, rim)
    centres = [element.points[0] for element in solved.elements[:count]]
    for centre in centres:
        assert math.dist(hub, centre) == pytest.approx(pitch, abs=1e-6)
    chords = [math.dist(centres[k], centres[(k + 1) % count]) for k in range(count)]
    assert chords == pytest.approx([2.0 * pitch * math.sin(math.pi / count)] * count, abs=1e-6)
    radii = [math.dist(*element.points) for element in solved.elements[:count]]
    assert radii == pytest.approx([radii[0]] * count, abs=1e-6)
    assert solved.free_dof == 4, "Mitte, Teilkreis und Lochradius bleiben frei"


def test_a_bolt_circle_refuses_too_few_or_too_big_holes() -> None:
    with pytest.raises(ValidationError):
        edit.bolt_circle_at((0.0, 0.0), (10.0, 0.0), 1, 3.0)
    with pytest.raises(ValidationError):
        edit.bolt_circle_at((0.0, 0.0), (10.0, 0.0), 6, 12.0)
    with pytest.raises(ValidationError):
        edit.bolt_circle_at((4.0, 4.0), (4.0, 4.0), 6, 3.0)


@pytest.mark.parametrize(
    ("value", "written"),
    [
        (1234.5678, "1234.5678"),
        (123.4567, "123.4567"),
        (0.00005, "0.00005"),
        (2_000_000.0, "2000000"),
        (50 * 1.2, "60"),
        (0.05, "0.05"),
        (-0.0000001, "0"),
    ],
)
def test_a_written_measure_keeps_its_decimals_and_stays_readable(
    value: float, written: str
) -> None:
    """Ein Maß im Datenformat: sechs Nachkommastellen, nie eine Exponentenzahl.

    ``f"{wert:g}"`` stand hier und hieß sechs *gültige Ziffern*: Ein auf
    1234,5678 mm gestrecktes Maß kam als 1234,57 an, und unter 10⁻⁴ oder ab
    einer Million stand ``5e-05`` beziehungsweise ``2e+06`` in der Datei —
    eine Zahl, die die Grammatik aus §13 nicht liest (Durchsicht 22.09.2026).
    """
    from app.core.expressions import evaluate

    assert edit.written_measure(value) == written
    assert evaluate(edit.written_measure(value), {}) == pytest.approx(round(value, 6), abs=1e-12)


def test_a_stretched_drawing_keeps_the_measure_that_was_typed() -> None:
    """Der Weg, auf dem es der Kunde trifft: Der Dialog streckt die Zeichnung
    auf die getippte Länge, und das Maß muss danach genau diese Zahl tragen."""
    drawing = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="line", points=((0.0, 0.0), (50.0, 0.0))),),
        constraints=(SketchConstraint("distance", (0, 1), "50"),),
    )

    bigger, _kept = edit.scaled(drawing, 1234.5678 / 50.0)

    assert bigger.constraints[0].value == "1234.5678"


def test_a_stretched_circle_stays_where_it_was_drawn() -> None:
    """Gestreckt wird um die Mitte der Geometrie, nicht um den Schwerpunkt der Punkte.

    Ein Kreis trägt Mitte und einen Randpunkt; ihr Schwerpunkt liegt auf
    halbem Radius neben der Mitte. Gemessen am 22.09.2026 im Dialog
    *Zwischen zwei Umrissen aufspannen*: Kreis Ø 30 um (0 | 0) kam als Ø 40
    um (−2,5 | 0) zurück — der Körper stand danach neben seiner Zeichnung.
    """
    circle = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="circle", points=((0.0, 0.0), (15.0, 0.0))),),
    )

    bigger, _kept = edit.scaled(circle, 40.0 / 30.0)

    centre, rim = bigger.elements[0].points
    assert centre == pytest.approx((0.0, 0.0), abs=1e-12)
    assert math.dist(centre, rim) == pytest.approx(20.0)


def test_a_stretched_arc_is_measured_at_its_bulge() -> None:
    """Auch ein Bogen misst an seinem Scheitel und nicht an seinen drei Punkten.

    Ein Halbkreis um (0 | −5) mit Radius 10 reicht bis y = 5 und schließt den
    Nullpunkt ein; seine drei Punkte liegen alle auf y = −5. Der Bezugspunkt
    ist der Punkt der Hülle, der dem Nullpunkt am nächsten liegt (RM-391) —
    an der Geometrie gemessen also der Nullpunkt selbst, an den Punkten
    gemessen (0 | −5). Verdoppelt wandert die Mitte deshalb nach (0 | −10).
    """
    arc = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(kind="arc", points=((0.0, -5.0), (10.0, -5.0), (-10.0, -5.0))),
            SketchElement(kind="line", points=((-10.0, -5.0), (10.0, -5.0))),
        ),
    )

    bigger, _kept = edit.scaled(arc, 2.0)

    centre = bigger.elements[0].points[0]
    assert centre == pytest.approx((0.0, -10.0), abs=1e-12), (
        "gestreckt um den Nullpunkt, der in der Hülle des Bogens liegt"
    )


def test_a_drawing_beside_the_origin_grows_away_from_it() -> None:
    """Liegt die Zeichnung ganz neben dem Nullpunkt, bleibt ihre zugewandte
    Ecke stehen — ein Rechteck von (10 | 20) bis (30 | 30) wächst nach rechts
    oben und rückt nicht über den Nullpunkt (RM-391)."""
    from app.core.sketch import shapes

    plate = shapes.rectangle(20.0, 10.0)
    moved = replace(
        plate,
        elements=tuple(
            replace(element, points=tuple((x + 20.0, y + 25.0) for x, y in element.points))
            for element in plate.elements
        ),
    )

    bigger, _kept = edit.scaled(moved, 1.5)

    corners = [point for element in bigger.elements for point in element.points]
    assert min(x for x, _y in corners) == pytest.approx(10.0)
    assert min(y for _x, y in corners) == pytest.approx(20.0)
    assert max(x for x, _y in corners) == pytest.approx(40.0)
    assert max(y for _x, y in corners) == pytest.approx(35.0)


# --- Flächenkontur (RM-188 P3.4) ---------------------------------------------------


def _plate() -> object:
    """``plate_holes.stl`` als Szenenobjekt mit seinen erkannten Merkmalen.

    80 × 50 × 8, vier Durchgangsbohrungen Ø 5,2 als 48-Ecke; ``face_2`` ist
    die Deckfläche bei z = 4, ``face_3`` eine Seite.
    """
    from pathlib import Path

    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    data = Path(__file__).parent / "data" / "meshes" / "plate_holes.stl"
    mesh = normalise(read_mesh(data.read_bytes(), ".stl"), "mm").mesh
    return SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))


def _outline_on(plane: str, objects: list[object]) -> edit.FaceOutline:
    from app.core.sketch.planes import frame_for_plane

    frame = frame_for_plane(plane, objects)  # type: ignore[arg-type]
    assert frame is not None, plane
    return edit.face_outline(Sketch(plane, ()), objects, frame)  # type: ignore[arg-type]


def _released(sketch: Sketch) -> Sketch:
    """Dieselbe Zeichnung, die Hilfslinien als Kontur — wie nach „Hilfslinie" im Editor."""
    return replace(
        sketch,
        elements=tuple(replace(element, construction=False) for element in sketch.elements),
    )


def test_the_outline_of_a_mesh_face_takes_its_rim_and_its_holes() -> None:
    """Die Deckfläche einer Lochplatte: außen vier Strecken, innen vier Kreise.

    *Projizieren* endete an genau dieser Fläche mit „Diese Ebene schneidet den
    Körper nicht" — die Zeichenebene liegt auf der Fläche, und ein Schnitt dort
    trifft nichts (Konzept vollwertiges CAD §6). Die Kreise kommen aus den
    erkannten Bohrungen; sie liegen um die Sehnenhöhe des 48-Ecks neben dem
    Netz, und genau das wird als Abweichung genannt.
    """
    from app.core.sketch import solve_sketch
    from app.core.sketch.planes import feature_plane
    from app.core.sketch.profile import regions_of, signed_area

    plate = _plate()
    outline = _outline_on(feature_plane("obj_1", "face_2"), [plate])

    kinds = [element.kind for element in outline.sketch.elements]
    assert sorted(kinds) == ["circle"] * 4 + ["line"] * 4
    assert all(element.construction for element in outline.sketch.elements), "Hilfsgeometrie"
    assert (outline.loops, outline.circles, outline.exact) == (5, 4, False)
    radii = [
        math.dist(*element.points)
        for element in outline.sketch.elements
        if element.kind == "circle"
    ]
    assert radii == pytest.approx([2.6] * 4, abs=1e-6)
    assert outline.deviation == pytest.approx(2.6 * (1.0 - math.cos(math.pi / 48.0)), rel=1e-3)
    fixed = {constraint.targets[0] for constraint in outline.sketch.constraints}
    assert fixed == set(range(len(edit.flat_points(outline.sketch)))), "jeder Punkt fest"
    assert solve_sketch(outline.sketch).free_dof == 0, "die Kontur fehlt keinem Maß"

    (region,) = regions_of(solve_sketch(_released(outline.sketch)))
    assert len(region.holes) == 4
    material = abs(signed_area(region)) - sum(abs(signed_area(hole)) for hole in region.holes)
    assert material == pytest.approx(80.0 * 50.0 - 4.0 * math.pi * 2.6**2, rel=1e-3)


def test_the_outline_on_a_parallel_plane_above_the_face_is_the_same_rim() -> None:
    """Eine Versatzebene über der Fläche bekommt denselben Rand — parallel
    verschoben ändert sich an den zwei Zahlen der Zeichnung nichts."""
    from app.core.sketch.planes import feature_plane, offset_plane

    plate = _plate()
    on_face = _outline_on(feature_plane("obj_1", "face_2"), [plate])
    above = _outline_on(offset_plane(feature_plane("obj_1", "face_2"), 5.0), [plate])

    assert [element.kind for element in above.sketch.elements] == [
        element.kind for element in on_face.sketch.elements
    ]
    for first, second in zip(above.sketch.elements, on_face.sketch.elements, strict=True):
        for mine, theirs in zip(first.points, second.points, strict=True):
            assert mine == pytest.approx(theirs, abs=1e-9)


def test_the_outline_of_a_side_face_is_its_rectangle() -> None:
    from app.core.sketch.planes import feature_plane

    outline = _outline_on(feature_plane("obj_1", "face_3"), [_plate()])

    assert [element.kind for element in outline.sketch.elements] == ["line"] * 4
    spans = sorted(math.dist(*element.points) for element in outline.sketch.elements)
    assert spans == pytest.approx([8.0, 8.0, 80.0, 80.0], abs=1e-6)


def test_taking_the_outline_twice_adds_nothing() -> None:
    """Derselbe Rand ein zweites Mal übernommen kommt nicht doppelt — sonst
    stünden zwei feste Konturen übereinander, und die zweite fiele erst beim
    Löschen auf."""
    from app.core.sketch.planes import feature_plane, frame_for_plane

    plate = _plate()
    plane = feature_plane("obj_1", "face_2")
    first = _outline_on(plane, [plate])
    frame = frame_for_plane(plane, [plate])  # type: ignore[list-item]
    assert frame is not None

    again = edit.face_outline(first.sketch, [plate], frame)  # type: ignore[list-item]

    assert again.loops == 0
    assert again.sketch == first.sketch


def test_a_badly_fitting_feature_makes_no_circle() -> None:
    """Ein Merkmal, das neben dem Ring liegt, macht keinen Kreis daraus.

    Hier behauptet jede Bohrung 0,2 mm mehr Durchmesser, als das Netz hat —
    der Kreis läge überall 0,1 mm neben dem Rand, doppelt so weit, wie eine
    Rundung neben ihren Facetten liegen darf. Der Ring bleibt das 48-Eck.
    """
    from dataclasses import replace as changed

    from app.core.sketch.planes import feature_plane

    plate = _plate()
    wider = {
        name: changed(feature, params={**feature.params, "diameter": 5.4})
        if feature.kind == "hole"
        else feature
        for name, feature in plate.features.items()  # type: ignore[attr-defined]
    }
    plate = changed(plate, features=wider)  # type: ignore[type-var]

    outline = _outline_on(feature_plane("obj_1", "face_2"), [plate])

    assert outline.circles == 0
    kinds = [element.kind for element in outline.sketch.elements]
    assert kinds.count("circle") == 0
    assert kinds.count("line") == 4 + 4 * 48


@pytest.mark.parametrize(
    ("plane", "constraint"),
    [
        ("plane:xy", "not_on_a_face"),
        ("through:0,0,0;1,0,0;0,1,0", "not_on_a_face"),
        ("tilt:feature:obj_1:face_2:x:30", "tilted_to_face"),
        ("feature:obj_1:face_99", "unknown_feature"),
    ],
)
def test_the_outline_says_why_it_cannot_be_taken(plane: str, constraint: str) -> None:
    """Keine Fläche unter der Zeichnung, eine gekippte Ebene, eine verschwundene
    Fläche — jedes mit eigenem Grund und einem Weg weiter (Regel 17)."""
    from app.core.sketch.planes import BASE_FRAMES, frame_for_plane

    plate = _plate()
    frame = frame_for_plane(plane, [plate]) or BASE_FRAMES["plane:xy"]  # type: ignore[list-item]

    with pytest.raises(ValidationError) as caught:
        edit.face_outline(Sketch(plane, ()), [plate], frame)  # type: ignore[list-item]

    assert caught.value.constraint == constraint
    assert caught.value.suggestions, "Regel 17"


def test_the_outline_of_an_exact_face_keeps_its_circle_and_its_arcs() -> None:
    """Am exakten Körper kommt der Rand aus den Kurven: eine Bohrung als Kreis,
    die Rundung einer Ecke als Bogen — und zwar richtig herum, auf der Deck-
    wie auf der Bodenfläche, deren Rahmen gespiegelt liegt. Geprüft an der
    Fläche, die der gelöste Umriss einschließt."""
    brep = exact_kernel()
    from app.core.brep.features import features_of
    from app.core.sketch import solve_sketch
    from app.core.sketch.planes import feature_plane
    from app.core.sketch.profile import regions_of, signed_area
    from app.core.types import SceneObject

    rounded = brep.fillet(brep.box(40.0, 30.0, 8.0), 5.0, "vertical")
    body = SceneObject(id="obj_1", name="Runde", mesh=rounded, features=features_of(rounded))
    caps = [
        name
        for name, feature in body.features.items()
        if feature.kind == "face" and abs(feature.params["normal"][2]) > 0.5
    ]
    assert len(caps) == 2
    for name in caps:
        outline = _outline_on(feature_plane("obj_1", name), [body])
        kinds = sorted(element.kind for element in outline.sketch.elements)
        assert kinds == ["arc"] * 4 + ["line"] * 4, name
        assert outline.exact
        assert solve_sketch(outline.sketch).free_dof == 0, "ganz feste Bögen sind bestimmt"
        (region,) = regions_of(solve_sketch(_released(outline.sketch)))
        assert abs(signed_area(region)) == pytest.approx(40.0 * 30.0 - (4.0 - math.pi) * 25.0)

    drilled = brep.boolean(
        "difference",
        [brep.box(40.0, 30.0, 8.0), brep.moved(brep.cylinder(6.0, 20.0), (-10.0, 0.0, -5.0))],
    )
    body = SceneObject(id="obj_2", name="Klotz", mesh=drilled, features=features_of(drilled))
    top = next(
        name
        for name, feature in body.features.items()
        if feature.kind == "face" and feature.params["normal"][2] > 0.5
    )
    outline = _outline_on(feature_plane("obj_2", top), [body])
    (circle,) = [element for element in outline.sketch.elements if element.kind == "circle"]
    assert math.dist(*circle.points) == pytest.approx(3.0, abs=1e-9), "der Kreis selbst, exakt"


def test_projected_edges_are_fixed_and_come_once() -> None:
    """Projizieren kommt fest wie die Flächenkontur, ohne Punkte auf Geraden
    und ohne Doppeltes.

    Gemessen an der Lochplatte, Schnitt bei z = 0: vorher 392 freie Strecken
    (die Außenkante allein 200), „noch 1568 Maße fehlen", und ein zweiter
    Druck legte dieselben 392 noch einmal darüber. Jetzt 4 + 4 · 48 Strecken,
    jeder Punkt fest, nichts fehlt, und der zweite Druck sagt, dass sie schon
    dastehen.
    """
    from app.core.sketch import solve_sketch

    plate = _plate()
    projected = edit.project(Sketch("plane:xy", ()), plate.mesh)  # type: ignore[attr-defined]

    assert len(projected.elements) == 4 + 4 * 48
    assert all(element.construction for element in projected.elements)
    fixed = {constraint.targets[0] for constraint in projected.constraints}
    assert fixed == set(range(len(edit.flat_points(projected)))), "jeder Punkt fest"
    assert solve_sketch(projected).free_dof == 0
    with pytest.raises(ValidationError) as caught:
        edit.project(projected, plate.mesh)  # type: ignore[attr-defined]
    assert caught.value.constraint == "already_there"


def test_the_outline_of_an_exact_plate_with_a_slot_keeps_its_hole() -> None:
    """Die Deckfläche einer exakten Platte mit Langloch: ein Umriss mit einem Loch.

    Die Naht des rechten Zylinders teilt den Halbkreis in zwei Bögen, deren
    Enden im letzten Bit auseinanderliegen; die Kreuzungsprüfung hielt sie für
    ein gemeinsames Stück, und der übernommene Rand ergab nach „Hilfslinie"
    keinen Umriss (gefunden an der Platte, 23.09.2026). Soll ist die Analytik:
    40·30 − (12·6 + π·3²), an Deck- und Bodenfläche.
    """
    brep = exact_kernel()
    from app.core.brep.features import features_of
    from app.core.sketch import solve_sketch
    from app.core.sketch.planes import feature_plane
    from app.core.sketch.profile import regions_of, signed_area
    from app.core.types import SceneObject

    tool = brep.boolean(
        "union",
        [
            brep.moved(brep.cylinder(6.0, 20.0), (-6.0, 0.0, -5.0)),
            brep.moved(brep.cylinder(6.0, 20.0), (6.0, 0.0, -5.0)),
            brep.moved(brep.box(12.0, 6.0, 20.0), (0.0, 0.0, -5.0)),
        ],
    )
    plate = brep.boolean("difference", [brep.box(40.0, 30.0, 8.0), tool])
    body = SceneObject(id="obj_1", name="Platte", mesh=plate, features=features_of(plate))
    caps = [
        name
        for name, feature in body.features.items()
        if feature.kind == "face" and abs(feature.params["normal"][2]) > 0.5
    ]
    assert len(caps) == 2
    for name in caps:
        outline = _outline_on(feature_plane("obj_1", name), [body])
        (region,) = regions_of(solve_sketch(_released(outline.sketch)))
        assert len(region.holes) == 1
        material = abs(signed_area(region)) - abs(signed_area(region.holes[0]))
        assert material == pytest.approx(40.0 * 30.0 - (12.0 * 6.0 + math.pi * 9.0))
