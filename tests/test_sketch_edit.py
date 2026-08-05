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

import pytest

from app.core.errors import ValidationError
from app.core.sketch import edit
from app.core.types import Sketch, SketchConstraint, SketchElement


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
    Absturz beim nächsten Lauf."""
    sketch = Sketch(
        plane="plane:xy",
        elements=cross().elements,
        constraints=(
            SketchConstraint(kind="horizontal", targets=(0, 1)),
            SketchConstraint(kind="vertical", targets=(2, 3)),
        ),
    )

    trimmed = edit.trim(sketch, 0, (-5.0, 0.0))

    kinds = {entry.kind for entry in trimmed.constraints}
    assert "vertical" in kinds, "die Bedingung der anderen Linie bleibt"
    assert "horizontal" not in kinds, "die der getrimmten geht mit ihr"
    total = sum(len(element.points) for element in trimmed.elements)
    for entry in trimmed.constraints:
        assert all(target < total for target in entry.targets), "und kein Ziel zeigt ins Leere"


# --- Verlängern ------------------------------------------------------------------


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


def test_offsetting_an_arc_is_refused_rather_than_guessed() -> None:
    """Der Versatz eines Bogens ist keine Verschiebung, sondern eine neue
    Kurve — und eine falsche wäre schlimmer als keine."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="arc", points=((0.0, 0.0), (5.0, 0.0), (0.0, 5.0))),),
    )

    with pytest.raises(ValidationError):
        edit.offset(sketch, (0,), 2.0)


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
