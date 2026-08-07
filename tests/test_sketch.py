"""Der Skizzen-Solver (Bauplan §30.1): deterministisch, Freiheitsgrade als
Zahl, Konflikte mit benanntem Paar, Maße über die Parametergrammatik."""

from __future__ import annotations

import math

import pytest

from app.core.errors import AppError, SketchConflictError, ValidationError
from app.core.sketch import solve_sketch
from app.core.types import Sketch, SketchConstraint, SketchElement

# Ein Rechteck aus vier Linien, absichtlich leicht verzogen: die Koinzidenzen
# ziehen die Ecken zusammen, die Maße kommen aus Projektparametern.
# Flache Punktindizes: unten (0,1), rechts (2,3), oben (4,5), links (6,7).


def rectangle(width_value: str = "@width", height_value: str = "@height") -> Sketch:
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.3, -0.2), (39.5, 0.4))),
            SketchElement("line", ((40.2, 0.1), (39.8, 19.7))),
            SketchElement("line", ((40.1, 20.3), (0.2, 19.8))),
            SketchElement("line", ((-0.3, 20.1), (0.1, 0.2))),
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
            SketchConstraint("distance", (0, 1), width_value),
            SketchConstraint("distance", (2, 3), height_value),
        ),
    )


PARAMS = {"width": 40.0, "height": 20.0}


def span(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])


def test_rectangle_solves_to_its_parameters() -> None:
    solved = solve_sketch(rectangle(), PARAMS)
    bottom = solved.elements[0]
    right = solved.elements[1]
    assert math.isclose(span(*bottom.points), 40.0, abs_tol=1e-6)
    assert math.isclose(span(*right.points), 20.0, abs_tol=1e-6)
    assert solved.max_residual <= 1e-6
    # Die Ecken sitzen aufeinander.
    assert math.isclose(span(bottom.points[1], right.points[0]), 0.0, abs_tol=1e-6)


def test_underdetermined_reports_degrees_of_freedom() -> None:
    # Nichts hält das Rechteck fest: es kann in der Ebene verschoben werden.
    solved = solve_sketch(rectangle(), PARAMS)
    assert solved.free_dof == 2


def test_fixed_corner_removes_the_last_freedom() -> None:
    sketch = rectangle()
    pinned = Sketch(
        plane=sketch.plane,
        elements=sketch.elements,
        constraints=(*sketch.constraints, SketchConstraint("fixed", (0,))),
    )
    solved = solve_sketch(pinned, PARAMS)
    assert solved.free_dof == 0
    # Der Anker heftet an die Eingangskoordinate der Ecke.
    assert math.isclose(solved.elements[0].points[0][0], 0.3, abs_tol=1e-6)
    assert math.isclose(solved.elements[0].points[0][1], -0.2, abs_tol=1e-6)


def test_same_input_solves_to_the_same_output() -> None:
    first = solve_sketch(rectangle(), PARAMS)
    second = solve_sketch(rectangle(), PARAMS)
    assert first == second


def test_a_dimension_takes_an_expression() -> None:
    solved = solve_sketch(rectangle(width_value="=@width/2 + 5"), PARAMS)
    assert math.isclose(span(*solved.elements[0].points), 25.0, abs_tol=1e-6)


def test_everything_outside_the_grammar_is_rejected() -> None:
    with pytest.raises(AppError):
        solve_sketch(rectangle(width_value="__import__('os').getcwd()"), PARAMS)


def test_conflicting_dimensions_name_the_pair() -> None:
    sketch = rectangle()
    conflicted = Sketch(
        plane=sketch.plane,
        elements=sketch.elements,
        constraints=(*sketch.constraints, SketchConstraint("distance", (0, 1), "50")),
    )
    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(conflicted, PARAMS)
    pair = {caught.value.first, caught.value.second}
    # Die beiden Maße auf derselben Strecke: 40 gegen 50.
    assert pair == {8, 10}
    assert caught.value.suggestions


def test_a_redundant_constraint_names_the_pair() -> None:
    sketch = rectangle()
    doubled = Sketch(
        plane=sketch.plane,
        elements=sketch.elements,
        constraints=(*sketch.constraints, SketchConstraint("horizontal", (0, 1))),
    )
    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(doubled, PARAMS)
    assert {caught.value.first, caught.value.second} == {4, 10}


def test_circle_radius_is_a_distance() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("circle", ((0.0, 0.0), (3.0, 0.0))),),
        constraints=(SketchConstraint("distance", (0, 1), "@r"),),
    )
    solved = solve_sketch(sketch, {"r": 5.0})
    assert math.isclose(span(*solved.elements[0].points), 5.0, abs_tol=1e-6)
    assert solved.free_dof == 3


def test_arc_legs_end_up_equally_long() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("arc", ((0.0, 0.0), (4.0, 0.0), (0.0, 5.0))),),
    )
    solved = solve_sketch(sketch)
    centre, start, end = solved.elements[0].points
    assert math.isclose(span(centre, start), span(centre, end), abs_tol=1e-6)


def test_perpendicular_and_parallel_hold() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (10.0, 1.0))),
            SketchElement("line", ((0.0, 5.0), (10.0, 4.0))),
        ),
        constraints=(
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("parallel", (0, 1, 2, 3)),
        ),
    )
    solved = solve_sketch(sketch)
    first, second = solved.elements
    assert math.isclose(first.points[0][1], first.points[1][1], abs_tol=1e-6)
    assert math.isclose(second.points[0][1], second.points[1][1], abs_tol=1e-6)


def test_wrong_target_count_is_rejected() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),),
        constraints=(SketchConstraint("distance", (0,), "10"),),
    )
    with pytest.raises(ValidationError):
        solve_sketch(sketch)


def test_a_target_outside_the_sketch_is_rejected() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),),
        constraints=(SketchConstraint("horizontal", (0, 7)),),
    )
    with pytest.raises(ValidationError):
        solve_sketch(sketch)


def test_a_dimension_without_a_value_is_rejected() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),),
        constraints=(SketchConstraint("distance", (0, 1)),),
    )
    with pytest.raises(ValidationError):
        solve_sketch(sketch)


def test_a_value_on_a_non_dimension_is_rejected() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),),
        constraints=(SketchConstraint("horizontal", (0, 1), "10"),),
    )
    with pytest.raises(ValidationError):
        solve_sketch(sketch)


def test_a_zero_radius_circle_is_rejected() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("circle", ((0.0, 0.0), (0.0, 0.0))),),
    )
    with pytest.raises(ValidationError):
        solve_sketch(sketch)


def test_an_empty_sketch_answers_quietly() -> None:
    solved = solve_sketch(Sketch(plane="plane:xy", elements=()))
    assert solved.elements == ()
    assert solved.free_dof == 0


def test_every_analytic_gradient_matches_central_differences() -> None:
    """Die Ranganalyse und das Budget aus §31 stehen auf den analytischen
    Ableitungen — eine falsche wäre ein stiller Fehler, der nur langsam
    konvergiert. Hier steht jede Bedingungsart einmal in allgemeiner Lage
    gegen zentrale Differenzen."""
    import numpy as np

    from app.core.sketch import solver

    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.1, 0.2), (10.3, 1.7))),
            SketchElement("line", ((1.5, 6.2), (11.8, 8.9))),
            SketchElement("circle", ((4.4, 12.1), (7.9, 13.6))),
            SketchElement("arc", ((20.2, 3.3), (24.9, 4.1), (21.0, 7.6))),
            SketchElement("point", ((15.5, 15.5),)),
        ),
        constraints=(
            SketchConstraint("distance", (0, 1), "10"),
            SketchConstraint("coincident", (1, 2)),
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("vertical", (2, 3)),
            SketchConstraint("parallel", (0, 1, 2, 3)),
            SketchConstraint("perpendicular", (0, 1, 2, 3)),
            SketchConstraint("tangent", (0, 1, 4, 5)),
            SketchConstraint("symmetric", (9, 3, 0, 1)),
            SketchConstraint("fixed", (9,)),
        ),
    )
    equations, anchors = solver._build_equations(sketch, {})
    pts = anchors.copy()
    total_rows = sum(equation.rows for equation in equations)

    analytic = np.zeros((total_rows, pts.shape[0], 2))
    begin = 0
    for equation in equations:
        equation.grad(pts, analytic[begin : begin + equation.rows])
        begin += equation.rows
    analytic_flat = analytic.reshape(total_rows, pts.size)

    def stacked(flat: np.ndarray) -> np.ndarray:
        shaped = flat.reshape(-1, 2)
        rows: list[float] = []
        for equation in equations:
            rows.extend(equation.fn(shaped))
        return np.asarray(rows)

    step = 1e-7
    flat = pts.reshape(-1).copy()
    numeric = np.zeros_like(analytic_flat)
    for column in range(flat.size):
        forward = flat.copy()
        backward = flat.copy()
        forward[column] += step
        backward[column] -= step
        numeric[:, column] = (stacked(forward) - stacked(backward)) / (2.0 * step)

    assert np.allclose(analytic_flat, numeric, atol=1e-5), (
        f"größte Abweichung: {float(np.max(np.abs(analytic_flat - numeric))):.2e}"
    )


def test_a_reference_measure_reports_without_driving() -> None:
    """Ein Referenzmaß misst, es treibt nicht (§30.1, D13).

    SindriCADs Sketcher hat es, unserer hatte es nicht: jedes Maß legte fest.
    Wer nur wissen wollte, wie lang die Diagonale gerade ist, musste sie
    festlegen — und hatte damit eine Bedingung mehr, als er wollte.

    Also darf es die Freiheitsgrade nicht ändern und nie in einen Konflikt
    geraten: es hat keine Gleichung, über die es sich mit einer anderen
    streiten könnte.
    """
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch, SketchConstraint, SketchElement

    line = SketchElement(kind="line", points=((0.0, 0.0), (30.0, 40.0)))
    plain = Sketch(plane="plane:xy", elements=(line,))
    before = solve_sketch(plain)

    with_reference = Sketch(
        plane="plane:xy",
        elements=(line,),
        constraints=(SketchConstraint(kind="reference", targets=(0, 1)),),
    )
    after = solve_sketch(with_reference)

    assert after.free_dof == before.free_dof, "ein Referenzmaß nimmt keinen Freiheitsgrad"
    assert after.elements == before.elements, "und bewegt nichts"

    # Auch neben einem echten Maß auf derselben Strecke: kein Widerspruch,
    # keine Überbestimmung — es steht ausserhalb des Gleichungssystems.
    both = Sketch(
        plane="plane:xy",
        elements=(line,),
        constraints=(
            SketchConstraint(kind="fixed", targets=(0,)),
            SketchConstraint(kind="distance", targets=(0, 1), value="50"),
            SketchConstraint(kind="reference", targets=(0, 1)),
        ),
    )
    solved = solve_sketch(both)
    # Vier Freiheitsgrade hat die Linie, ``fixed`` nimmt zwei, das Maß einen.
    assert solved.free_dof == 1, "die Richtung bleibt frei, das Referenzmaß ändert daran nichts"


# --- Skizzenmuster (§30.1, D9) --------------------------------------------------


def test_a_bolt_circle_places_its_holes_on_the_pitch_diameter() -> None:
    """Der häufigste Fall am Druckteil: ein Deckel mit Lochkreis.

    Von Hand hieß das, sechs Kreise einzeln zu setzen und ihre Mittelpunkte
    auszurechnen — mit einem Rechenfehler je Gelegenheit.

    Das Muster ist **nicht assoziativ**: es erzeugt echte Elemente mit echten
    Bedingungen. Die Parametrik liegt in Solidon eine Ebene höher — Maße sind
    Ausdrücke, und ein Projektparameter dreht den Teilkreis. Ein zweiter
    Mechanismus daneben wäre der Fehler, den SindriCADs eigenes Audit als
    Datenkorruption führt: dort backt jede Bearbeitung die abgeleiteten Kopien
    in die gespeicherten Elemente.
    """
    import itertools
    import math

    from app.core.sketch import shapes
    from app.core.sketch.solver import solve_sketch

    sketch = shapes.bolt_circle(pitch_diameter=50.0, count=6, hole_diameter=4.0)
    assert len(sketch.elements) == 6, "sechs Löcher, sechs Kreise"

    solved = solve_sketch(sketch)
    # Ein Kreis behält den Freiheitsgrad, um den sein Randpunkt rotieren darf —
    # so ist es bei ``circle`` seit jeher, und wo der Randpunkt sitzt, ändert am
    # Kreis nichts. Bestimmt ist, worauf es ankommt: Ort und Radius.
    assert solved.free_dof == 6, "je Loch die Drehung seines Randpunkts, sonst nichts"

    centres = [element.points[0] for element in solved.elements]
    for x, y in centres:
        assert math.hypot(x, y) == pytest.approx(25.0, abs=1e-6), "auf dem Teilkreis"

    angles = sorted(math.degrees(math.atan2(y, x)) % 360.0 for x, y in centres)
    steps = [round(b - a, 6) for a, b in itertools.pairwise(angles)]
    assert all(step == pytest.approx(60.0, abs=1e-6) for step in steps), "gleichmäßig verteilt"


def test_a_grid_of_holes_counts_rows_times_columns() -> None:
    """Ein Lochraster — Lüftungsgitter, Steckplatte, Lochblech."""
    from app.core.sketch import shapes
    from app.core.sketch.solver import solve_sketch

    sketch = shapes.hole_grid(columns=4, rows=3, spacing=10.0, hole_diameter=3.0)
    assert len(sketch.elements) == 12

    solved = solve_sketch(sketch)
    assert solved.free_dof == 12, "je Loch die Drehung seines Randpunkts"

    centres = {(round(x, 6), round(y, 6)) for x, y in (e.points[0] for e in solved.elements)}
    assert len(centres) == 12, "kein Loch liegt auf einem anderen"
    xs = sorted({x for x, _ in centres})
    assert xs[-1] - xs[0] == pytest.approx(30.0, abs=1e-6), "drei Abstände zwischen vier Spalten"


def test_a_pattern_rejects_a_count_below_two() -> None:
    """Ein Muster aus einem Element ist kein Muster, sondern ein Kreis."""
    from app.core.errors import ValidationError
    from app.core.sketch import shapes

    with pytest.raises(ValidationError):
        shapes.bolt_circle(pitch_diameter=50.0, count=1, hole_diameter=4.0)
    with pytest.raises(ValidationError):
        shapes.hole_grid(columns=1, rows=1, spacing=10.0, hole_diameter=3.0)


# --- Spline (§30.1, D11) ---------------------------------------------------------


def test_a_spline_carries_as_many_points_as_it_was_drawn_with() -> None:
    """Der Spline bricht die feste Punktzahl je Elementart — und nur die.

    Bis hierher trug jede Art eine feste Zahl: ein Punkt einen, eine Linie
    zwei, ein Bogen drei. Ein Spline hat so viele, wie jemand geklickt hat.
    Die tragende Invariante bleibt trotzdem stehen: **alle Freiheitsgrade sind
    Punktkoordinaten**, der Solver kennt weiter genau eine Sorte Variable.
    """
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch, SketchConstraint, SketchElement

    points = ((0.0, 0.0), (10.0, 8.0), (20.0, -4.0), (30.0, 0.0))
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement(kind="spline", points=points),),
        constraints=(SketchConstraint(kind="fixed", targets=(0,)),),
    )

    solved = solve_sketch(sketch)
    assert solved.elements[0].points == points, "ohne Bedingungen bleibt er, wo er gezeichnet wurde"
    assert solved.free_dof == 6, "vier Punkte, acht Freiheitsgrade, zwei nimmt der Festpunkt"


def test_a_spline_needs_at_least_two_points() -> None:
    """Ein Spline durch einen Punkt ist ein Punkt."""
    from app.core.errors import ValidationError
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch, SketchElement

    single = Sketch(
        plane="plane:xy", elements=(SketchElement(kind="spline", points=((0.0, 0.0),)),)
    )
    with pytest.raises(ValidationError):
        solve_sketch(single)


def test_a_spline_closes_a_profile_and_becomes_a_body() -> None:
    """Der Umriss nimmt den Spline auf, und der Kern baut ihn als exakte Kurve.

    Gemessen wird an der Hüllbox: die Fläche unter einer Freiform hat keine
    geschlossene Formel, ihre Ausdehnung schon. Der Spline geht durch seine
    Punkte, also ist die Breite genau der Abstand von erstem zu letztem.
    """
    from app.core.brep.kernel import available
    from app.core.sketch.profile import profile_of
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch, SketchElement

    if not available():
        pytest.skip("ohne B-Rep-Kern gibt es keinen Körper")

    from app.core.brep import profiles as brep_profiles

    # Ein Deckel mit gewölbter Oberkante: Spline hin, Linie zurück.
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement(
                kind="spline", points=((0.0, 0.0), (10.0, 6.0), (20.0, 6.0), (30.0, 0.0))
            ),
            SketchElement(kind="line", points=((30.0, 0.0), (0.0, 0.0))),
        ),
    )
    profile = profile_of(solve_sketch(sketch))
    body = brep_profiles.extrude(profile, 5.0)

    size = body.bounds.size
    assert size[0] == pytest.approx(30.0, abs=1e-6), "so breit wie der Spline lang ist"
    assert size[2] == pytest.approx(5.0, abs=1e-6), "und fünf hoch"
    assert body.volume > 0.0


# --- Mehrere Umrisse in einer Skizze (D14, „Region") ---------------------------


def _square(size: float, at: tuple[float, float] = (0.0, 0.0)) -> tuple[object, ...]:
    """Vier Linien um einen Mittelpunkt — als Elemente, nicht als Skizze.

    Für diese Tests braucht es Skizzen, die aus mehreren solchen bestehen, und
    ``shapes.rectangle`` liefert immer genau eine.
    """
    from app.core.types import SketchElement

    half = size / 2.0
    x, y = at
    corners = [
        (x - half, y - half),
        (x + half, y - half),
        (x + half, y + half),
        (x - half, y + half),
    ]
    return tuple(
        SketchElement(kind="line", points=(corners[index], corners[(index + 1) % 4]))
        for index in range(4)
    )


def test_a_sketch_with_a_hole_becomes_one_region() -> None:
    """Außenkontur und Loch sind zusammen ein Umriss, nicht zwei.

    Bis hierher lehnte die Verkettung so etwas ab („der Umriss verzweigt sich"
    kam nicht einmal — die zweite Kette blieb einfach übrig). Eine Platte mit
    einem Loch ist der häufigste Fall überhaupt, und ihn nicht zu können hieß,
    für jedes Loch eine zweite Operation zu brauchen.
    """
    from app.core.sketch.profile import regions_of
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch

    sketch = Sketch(plane="plane:xy", elements=_square(40.0) + _square(10.0))
    regions = regions_of(solve_sketch(sketch))

    assert len(regions) == 1, "ein Außenumriss"
    assert len(regions[0].holes) == 1, "und ein Loch darin"


def test_two_separate_shapes_stay_two_regions() -> None:
    """Nebeneinander ist nicht ineinander.

    Der Unterschied entscheidet über alles Weitere: verschachtelt wird
    abgezogen, nebeneinander wird nebeneinander gebaut. Wer nur zählt, wie
    viele Ketten es gibt, kann beide nicht auseinanderhalten.
    """
    from app.core.sketch.profile import regions_of
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch

    sketch = Sketch(
        plane="plane:xy", elements=_square(10.0, (-20.0, 0.0)) + _square(10.0, (20.0, 0.0))
    )
    regions = regions_of(solve_sketch(sketch))

    assert len(regions) == 2
    assert all(not region.holes for region in regions)


def test_a_plate_with_a_hole_has_the_volume_of_both() -> None:
    """Und am Körper gemessen: 40 × 40 minus 10 × 10, fünf hoch.

    Die Zahl ist der eigentliche Beweis. Eine Fläche mit einem inneren Ring,
    den der Kern nicht als Loch nimmt, sieht in jeder Ansicht richtig aus und
    wiegt trotzdem zu viel.
    """
    from app.core.brep import profiles as brep_profiles
    from app.core.brep.kernel import available
    from app.core.sketch.profile import regions_of
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch

    if not available():
        pytest.skip("ohne B-Rep-Kern gibt es keinen Körper")

    sketch = Sketch(plane="plane:xy", elements=_square(40.0) + _square(10.0))
    region = regions_of(solve_sketch(sketch))[0]
    body = brep_profiles.extrude(region, 5.0)

    assert body.volume == pytest.approx((40.0 * 40.0 - 10.0 * 10.0) * 5.0, rel=1e-6)


def test_a_single_shape_still_comes_back_as_one_profile() -> None:
    """Was vorher ging, geht unverändert.

    ``profile_of`` ist der Weg jeder bestehenden Operation. Es gibt jetzt einen
    zweiten daneben, und der erste darf sich davon nicht ändern — auch nicht
    darin, was er bei einer mehrdeutigen Skizze tut.
    """
    from app.core.sketch import shapes
    from app.core.sketch.profile import profile_of
    from app.core.sketch.solver import solve_sketch

    profile = profile_of(solve_sketch(shapes.rectangle(40.0, 20.0)))
    assert len(profile.segments) == 4
    assert not profile.holes
