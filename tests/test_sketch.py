"""Der Skizzen-Solver (Bauplan §30.1): deterministisch, Freiheitsgrade als
Zahl, Konflikte mit benanntem Paar, Maße über die Parametergrammatik."""

from __future__ import annotations

import math
import random
from dataclasses import replace
from itertools import pairwise

import numpy as np
import pytest

from app.core.brep.kernel import available as brep_available
from app.core.errors import AppError, SketchConflictError, ValidationError
from app.core.sketch import edit, solve_sketch
from app.core.sketch.planes import (
    axis_hit,
    frame_for_plane,
    frame_of,
    image_normal,
    ray_hit,
    to_plane,
    to_world,
)
from app.core.sketch.profile import _LEAST_STEPS, curves_of
from app.core.types import PlaneFrame, Sketch, SketchConstraint, SketchElement, SolvedSketch
from tests.helpers import assert_sketch_gradients, exact_kernel, rectangle

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
    """Dieselbe Skizze löst zur selben Geometrie — Struktur genau, Zahlen eng.

    **Nicht bitgleich, und das ist keine Aufweichung.** Der Löser ist ein
    iteratives Verfahren auf Fließkomma und bricht bei ``xtol=1e-10`` ab; ob
    zwei Läufe danach dieselben Bits tragen, entscheidet nicht der Code,
    sondern die Ausrichtung der Speicherblöcke und die Reihenfolge, in der die
    Vektoreinheit summiert. Auf dem Intel-Mac gemessen (08.09.2026):
    ``20.050000000002402`` gegen ``20.050000000002424`` — vier Größenordnungen
    **unter** der eigenen Abbruchschwelle des Lösers und zehn unter allem, was
    ein Drucker auflöst. Regel 6 sagt genau das allgemein: Fließkomma nie
    mit ``==``.

    Geprüft wird deshalb, was die Zusage ist: gleich viele Elemente, gleiche
    Art, gleiche Bauhilfen-Kennzeichnung, gleiche Freiheitsgrade — und die
    Koordinaten auf ein Milliardstel Millimeter genau. Ein Löser, der zwei
    verschiedene *Lösungen* fände, fiele hier weiterhin durch; ein Rechenwerk,
    das anders rundet, nicht mehr.
    """
    first = solve_sketch(rectangle(), PARAMS)
    second = solve_sketch(rectangle(), PARAMS)

    assert first.free_dof == second.free_dof
    assert first.max_residual == pytest.approx(second.max_residual, abs=1e-9)
    assert len(first.elements) == len(second.elements)
    for links, rechts in zip(first.elements, second.elements, strict=True):
        assert links.kind == rechts.kind
        assert links.construction == rechts.construction
        assert len(links.points) == len(rechts.points)
        for hier, dort in zip(links.points, rechts.points, strict=True):
            assert hier == pytest.approx(dort, abs=1e-9)


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


def test_a_reference_is_never_the_redundant_partner() -> None:
    # Referenzmaß zuerst, dann Koinzidenz und Horizontal auf denselben Punkten:
    # die Horizontale ist redundant (die Koinzidenz zieht beide Punkte
    # zusammen), und als Partnerin muss die Koinzidenz genannt werden — das
    # Referenzmaß legt nichts fest und kann an keiner Redundanz beteiligt sein.
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (4.0, 1.0))),),
        constraints=(
            SketchConstraint("reference", (0, 1)),
            SketchConstraint("coincident", (0, 1)),
            SketchConstraint("horizontal", (0, 1)),
        ),
    )
    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(sketch)
    assert {caught.value.first, caught.value.second} == {1, 2}


def test_a_shared_redundancy_blames_a_member_not_the_first() -> None:
    # Verteilt sich die Abhängigkeit über einen Verbund (jede Bedingung trägt
    # auch Eigenes bei), gab der Rückfall stumpf (0, 0) zurück — hier wäre das
    # das Referenzmaß. Benannt werden muss ein Mitglied des Verbunds.
    from app.core.sketch.solver import _Equation, _redundant_pair, _row_blocks

    constraints = (
        SketchConstraint("reference", (0, 1)),
        SketchConstraint("coincident", (0, 1)),
        SketchConstraint("coincident", (1, 2)),
    )
    silent = lambda values: ()  # noqa: E731 — nur die Blockform zählt hier
    equations = (
        _Equation(constraint=1, rows=2, fn=silent, grad=lambda values, into: None),
        _Equation(constraint=2, rows=2, fn=silent, grad=lambda values, into: None),
    )
    # Jeder Block hält eine eigene und eine geteilte Zeile: Rang 3 bei vier
    # Zeilen, aber kein Block ist allein entbehrlich.
    jacobian = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    first, second = _redundant_pair(
        constraints, equations, _row_blocks(equations), jacobian, rank=3
    )
    assert {first, second} == {1, 2}


def test_circle_radius_is_a_distance() -> None:
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("circle", ((0.0, 0.0), (3.0, 0.0))),),
        constraints=(SketchConstraint("distance", (0, 1), "@r"),),
    )
    solved = solve_sketch(sketch, {"r": 5.0})
    assert math.isclose(span(*solved.elements[0].points), 5.0, abs_tol=1e-6)
    # Mitte frei (2), Radius bemaßt: zwei Freiheitsgrade. Der Randpunkt darf auf
    # seinem Kreis wandern, aber das ist kein Freiheitsgrad des Kreises (02.09.2026).
    assert solved.free_dof == 2


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
            SketchConstraint("angle", (0, 1, 2, 3), "37"),
            SketchConstraint("equal", (0, 1, 2, 3)),
            SketchConstraint("midpoint", (9, 0, 3)),
        ),
    )
    assert_sketch_gradients(sketch, step=1e-7, atol=1e-5)


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


# --- Winkel, gleich groß, Mitte, konzentrisch (§30.1, W2) -----------------------


def two_lines_at_a_corner(angle: str = "60") -> Sketch:
    """Zwei Linien mit gemeinsamem Anfang, die erste waagerecht und fest.

    Damit bleibt genau ein Freiheitsgrad übrig — die Richtung der zweiten
    Linie —, und das Winkelmaß nimmt ihn. Länge und Ort stehen fest, sonst
    beantwortete der Test zwei Fragen auf einmal.
    """
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("line", ((0.0, 0.0), (8.0, 3.0))),
        ),
        constraints=(
            SketchConstraint("coincident", (0, 2)),
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("fixed", (0,)),
            SketchConstraint("distance", (0, 1), "10"),
            SketchConstraint("distance", (2, 3), "10"),
            SketchConstraint("angle", (0, 1, 2, 3), angle),
        ),
    )


def turn_between(first: SketchElement, second: SketchElement) -> float:
    """Der Winkel von der ersten zur zweiten Linie, in Grad."""
    ux = first.points[1][0] - first.points[0][0]
    uy = first.points[1][1] - first.points[0][1]
    vx = second.points[1][0] - second.points[0][0]
    vy = second.points[1][1] - second.points[0][1]
    return math.degrees(math.atan2(ux * vy - uy * vx, ux * vx + uy * vy))


def test_an_angle_holds_two_lines_at_the_typed_degrees() -> None:
    """Sechzig Grad sind sechzig Grad, und die Skizze ist bestimmt."""
    solved = solve_sketch(two_lines_at_a_corner("60"))
    assert solved.free_dof == 0, "Ort, Länge und Winkel stehen — nichts bleibt frei"
    assert math.isclose(turn_between(*solved.elements[:2]), 60.0, abs_tol=1e-6)
    assert solved.max_residual <= 1e-6


def test_an_angle_reads_its_degrees_from_a_project_parameter() -> None:
    """Ein Winkelmaß ist ein Ausdruck der Grammatik (§13) wie jedes Maß."""
    solved = solve_sketch(two_lines_at_a_corner("@neigung"), {"neigung": 30.0})
    assert math.isclose(turn_between(*solved.elements[:2]), 30.0, abs_tol=1e-6)


def test_an_angle_turns_two_free_lines_to_the_nearest_solution() -> None:
    """Ein Winkel zwischen zwei freien Linien dreht sie, er wirft sie nicht um.

    Das Residuum hat die Periode 180 Grad, und gemeint ist die Lösung, die der
    Zeichnung am nächsten liegt (``_angle_equation``). Der Löser hielt das
    nicht: Bei einer einzigen Bedingung zeigen Gradient und Gauß-Newton-Schritt
    in dieselbe Richtung, der Zweierraum von TRF mit ``lsmr`` entartet, und der
    erste Schritt lief bis an den Rand des Vertrauensbereichs — mit einem
    Anteil aus dem Rundungsrauschen. 48 von 717 Fällen landeten auf der
    anderen Lösung, Punkte wanderten bis 173 mm; auf dem Intel-Mac kippte so
    die erste Linie im Skizzentest um (Fensterauswahl, Lauf 37597388208).
    """
    for start in range(5, 90, 6):
        for target in (30, 45, 60, 100):
            first = SketchElement("line", ((0.0, 0.0), (10.0, 0.0)))
            angle = math.radians(start)
            second = SketchElement(
                "line", ((0.0, 0.0), (8.5 * math.cos(angle), 8.5 * math.sin(angle)))
            )
            sketch = Sketch(
                plane="plane:xy",
                elements=(first, second),
                constraints=(SketchConstraint("angle", (0, 1, 2, 3), str(target)),),
            )
            solved = solve_sketch(sketch)
            nearest = target if abs(start - target) <= abs(start - (target - 180)) else target - 180
            assert math.isclose(turn_between(*solved.elements), nearest, abs_tol=1e-4), (
                start,
                target,
                turn_between(*solved.elements),
            )
            moved = max(
                math.dist(before, after)
                for old, new in zip(sketch.elements, solved.elements, strict=True)
                for before, after in zip(old.points, new.points, strict=True)
            )
            # Drehen heißt: kein Punkt wandert weiter, als beide Linien
            # zusammen lang sind. Der alte Schritt kam hier auf 21,7 mm.
            assert moved <= 10.0 + 8.5, (
                f"von {start}° nach {target}° wandert ein Punkt {moved:.1f} mm"
            )


def _angle_pair(
    start: int, target: int, at: tuple[float, float], size: float, company: str
) -> Sketch:
    """Zwei freie Linien (10 und 8,5 lang, mal ``size``) mit einem Winkelmaß, an ``at``.

    ``company``: allein, neben vierzig freien Linien (dann rechnet die Skizze
    über ``lsmr``) oder neben einer bemaßten, schon gelösten Kette aus zwanzig
    Linien — die Lage, in der nur das Linienpaar unter Spannung steht.
    """
    dx, dy = at
    turn = math.radians(start)
    elements = [
        SketchElement("line", ((dx, dy), (10.0 * size + dx, dy))),
        SketchElement(
            "line",
            ((dx, dy), (8.5 * size * math.cos(turn) + dx, 8.5 * size * math.sin(turn) + dy)),
        ),
    ]
    constraints = [SketchConstraint("angle", (0, 1, 2, 3), str(target))]
    beside, held = _company(company, size, at)
    return Sketch(
        plane="plane:xy",
        elements=(*elements, *beside),
        constraints=(*constraints, *held),
    )


def _company(
    company: str, size: float, at: tuple[float, float]
) -> tuple[list[SketchElement], list[SketchConstraint]]:
    """Was neben zwei Linien (Punkte 0 bis 3) liegt: nichts (``alone``), vierzig
    freie Linien (``free``) oder eine bemaßte, gelöste Kette aus zwanzig Linien
    mit festem Anfang (``chain``) — je mal ``size``, an ``at``."""
    dx, dy = at
    if company == "free":
        return [
            SketchElement(
                "line",
                (
                    ((20.0 + i) * size + dx, 5.0 * size + dy),
                    ((21.0 + i) * size + dx, 7.0 * size + dy),
                ),
            )
            for i in range(40)
        ], []
    if company == "chain":
        elements = [
            SketchElement(
                "line",
                (
                    (10.0 * i * size + dx, 50.0 * size + dy),
                    (10.0 * (i + 1) * size + dx, 50.0 * size + dy),
                ),
            )
            for i in range(20)
        ]
        constraints = [
            SketchConstraint("distance", (4 + 2 * i, 5 + 2 * i), repr(10.0 * size))
            for i in range(20)
        ]
        constraints += [
            SketchConstraint("coincident", (3 + 2 * i, 4 + 2 * i)) for i in range(1, 20)
        ]
        constraints.append(SketchConstraint("fixed", (4,)))
        return elements, constraints
    return [], []


@pytest.mark.parametrize(
    ("company", "size"), [("alone", 1.0), ("alone", 0.01), ("free", 1.0), ("chain", 1.0)]
)
def test_a_sketch_solves_alike_wherever_it_lies(company: str, size: float) -> None:
    """Dieselbe Skizze tausend oder hunderttausend Millimeter daneben: dieselbe Lösung (RM-541).

    Der Löser rechnete in Koordinaten, und TRF beginnt mit dem
    Vertrauensradius ‖x₀‖ — der Entfernung der Zeichnung vom Nullpunkt. Der
    erste Schritt reichte so über beide Lösungen eines Winkels, und welche er
    traf, entschied die Rundung: 45° gesetzt, unter macOS Intel 135° bekommen
    (Lauf 37495714708). Neben einer bemaßten Kette rechnete alles über
    ``lsmr``, dessen Zweierraum bei einer einzelnen gespannten Bedingung aus
    Rauschen besteht. Am Stand davor (``78d39dec9``) kippten in diesem Raster
    5 von 60 Paaren schon am Nullpunkt und 9 von 180 versetzt, 16 Läufe
    endeten in einem Widerspruch, und versetzt landeten Punkte bis 150 m
    daneben; der Löser von 0.5.3 kippte auch zwei Paare ohne Begleiter.

    Die Versätze ersetzen den Intel-Rechner: Sie ändern die Rundung jeder
    Rechnung, wie eine andere Maschine es tut, und die Lösung darf sich davon
    nicht rühren. Soll ist die nächste Lösung — der Winkel auf der Seite, auf
    der die Zeichnung schon liegt, kein Punkt weiter als beide Linien lang.
    """
    from app.core.sketch.solver import EXACT_UP_TO
    from app.core.units import EPS_GEOM

    if company != "alone":
        assert (
            len(edit.flat_points(_angle_pair(5, 30, (0.0, 0.0), size, company))) * 2 > EXACT_UP_TO
        )
    for start in (5, 29, 53, 77, 89):
        for target in (30, 45, 100):
            nearest = target if abs(start - target) <= abs(start - (target - 180)) else target - 180
            drawn = _angle_pair(start, target, (0.0, 0.0), size, company)
            home = solve_sketch(drawn)
            assert math.isclose(turn_between(*home.elements[:2]), nearest, abs_tol=1e-4), (
                start,
                target,
                turn_between(*home.elements[:2]),
            )
            moved = max(
                math.dist(before, after)
                for old, new in zip(drawn.elements, home.elements, strict=True)
                for before, after in zip(old.points, new.points, strict=True)
            )
            assert moved <= (10.0 + 8.5) * size, (start, target, moved)
            for at in ((1000.0, 0.0), (-1000.0, 1000.0), (1e5, -1e5)):
                away = solve_sketch(_angle_pair(start, target, at, size, company))
                back = [(x - at[0], y - at[1]) for x, y in _flat(away)]
                gap = max(math.dist(a, b) for a, b in zip(back, _flat(home), strict=True))
                assert gap <= EPS_GEOM, (start, target, at, gap)


def _related_lines(kind: str, value: str, at: tuple[float, float], company: str) -> Sketch:
    """Zwei freie Linien mit genau einer Bedingung zwischen ihnen, an ``at``."""
    dx, dy = at
    beside, held = _company(company, 1.0, at)
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((dx, dy), (10.0 + dx, dy))),
            SketchElement("line", ((2.0 + dx, 3.0 + dy), (9.0 + dx, 7.5 + dy))),
            *beside,
        ),
        constraints=(SketchConstraint(kind, (0, 1, 2, 3), value), *held),
    )


def _placed(sketch: Sketch, points: list[tuple[float, float]]) -> Sketch:
    """Die Skizze mit diesen Punkten — so schreibt der Editor jeden Zugschritt zurück."""
    offsets = edit.offsets_of(sketch)
    return replace(
        sketch,
        elements=tuple(
            replace(element, points=tuple(points[begin : begin + len(element.points)]))
            for element, begin in zip(sketch.elements, offsets, strict=True)
        ),
    )


@pytest.mark.parametrize("company", ["alone", "chain"])
@pytest.mark.parametrize(
    ("kind", "value"), [("parallel", ""), ("perpendicular", ""), ("equal", ""), ("angle", "30")]
)
def test_a_drag_solves_alike_wherever_it_lies(
    kind: str, value: str, company: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Linien mit einer Bedingung, am Ende gezogen wie mit der Maus: an jedem
    Ort dieselbe Lage (RM-541).

    Im Zug steht der gezogene Punkt fest, und übrig bleibt ein Teil mit genau
    einer gespannten Gleichung. Gerechnet wurde der Zug über ``lsmr``, dessen
    Zweierraum aus Gradient und Gauß-Newton-Schritt dort aus Rauschen besteht:
    Nach denselben zehn Mausschritten standen die Linien an den Versätzen 3,7
    bis 38 mm woanders (am Stand vor RM-541 bis 410 mm), und jeder Schritt
    brauchte alle erlaubten Auswertungen. Neben der bemaßten Kette ist die
    Skizze zu groß für die dichte Rechnung, das Linienpaar als Teil nicht.
    """
    from app.core.sketch import solver
    from app.core.units import EPS_GEOM

    evaluations = _counting_evaluations(monkeypatch)
    most: list[int] = []

    def dragged(at: tuple[float, float]) -> list[tuple[float, float]]:
        sketch = _related_lines(kind, value, at, company)
        points = _flat(solve_sketch(sketch))
        end = points[3]
        for step in range(1, 11):
            target = (end[0] + 0.2 * step, end[1] + 0.3 * step)
            evaluations.clear()
            solved = solve_sketch(_placed(sketch, points), dragged={3: target}, start=points)
            most.append(max(evaluations))
            points = _flat(solved)
            assert points[3] == pytest.approx(target, abs=1e-9), "der Punkt steht am Zeiger"
        return [(x - at[0], y - at[1]) for x, y in points]

    home = dragged((0.0, 0.0))
    for at in ((1000.0, 0.0), (-1000.0, 1000.0), (1e5, -1e5)):
        gap = max(math.dist(a, b) for a, b in zip(dragged(at), home, strict=True))
        assert gap <= EPS_GEOM, (at, gap)
    assert max(most) < solver.DRAG_REACH_TRIES, "jeder Schritt fertig gerechnet, nicht abgebrochen"


_PLACES = ((0.0, 0.0), (1000.0, 0.0), (-1000.0, 1000.0), (12.3, 45.6), (1e5, -1e5))


#: Gezeichnete Linienzüge, deren Bedingungen sich widersprechen oder doppeln —
#: gefunden mit der Versatzsonde des Reviews (Zufall, Startwert 541).
_UNSOLVABLE = {
    "doubled": (
        [
            ((0.0, 0.0), (11.418647258393689, 0.3772043893773367)),
            ((11.285466746204376, 0.899218288039189), (16.293232614750657, -4.357496513559995)),
            ((17.108752676676446, -3.942278154223121), (26.21207146796181, -10.406345899048521)),
            ((25.859323990146354, -9.342165871133291), (29.999900080820844, -15.29071108143754)),
            ((29.75531320742086, -16.3222559920441), (33.87201362244849, -15.303683963644536)),
            ((33.9113447279559, -13.994187644713586), (45.200920597562316, -17.662654690431836)),
            ((45.36394957757005, -16.81728831462031), (54.82377150029633, -10.834961268109309)),
        ],
        [
            *(("coincident", (2 * i + 1, 2 * i + 2), "") for i in range(6)),
            ("parallel", (2, 3, 0, 1), ""),
            ("angle", (4, 5, 0, 1), "53.0"),
            ("perpendicular", (10, 11, 0, 1), ""),
            ("perpendicular", (4, 5, 2, 3), ""),
            ("horizontal", (2, 3), ""),
            ("horizontal", (0, 1), ""),
            ("fixed", (0,), ""),
        ],
    ),
    "tie": (
        [
            ((0.0, 0.0), (13.262088307196882, -4.550809131545043)),
            ((13.336235830826372, -4.2756351403139385), (22.255488168818204, -11.268288758711247)),
            ((22.071495391607236, -10.595882361332968), (28.93925198415845, -9.78451098428803)),
        ],
        [
            ("coincident", (1, 2), ""),
            ("coincident", (3, 4), ""),
            ("perpendicular", (0, 1, 2, 3), ""),
            ("angle", (2, 3, 0, 1), "158.0"),
            ("fixed", (0,), ""),
        ],
    ),
    "two_lengths": (
        [
            ((0.0, 0.0), (15.625723629630487, 0.4279727516049222)),
            (
                (15.16567941857119, -0.0076338422054593735),
                (28.254185111112676, -0.7941997621835428),
            ),
            ((26.764897746283488, -1.5233581463318244), (31.643865642356563, -0.27159823207045775)),
            ((31.8981731418392, -1.166749604004128), (45.88623123394727, 3.0702546808660425)),
            ((45.125491952919035, 4.308004547546075), (57.4845150481231, -1.9466717087430885)),
        ],
        [
            *(("coincident", (2 * i + 1, 2 * i + 2), "") for i in range(4)),
            ("distance", (2, 3), "9.915"),
            ("distance", (2, 3), "11.118"),
            ("distance", (8, 9), "11.283"),
            ("fixed", (0,), ""),
        ],
    ),
}


def test_what_the_solver_does_not_move_keeps_its_numbers() -> None:
    """Der Löser rechnet um die Mitte der Zeichnung; zurück rückt nur, was sich
    bewegt hat (RM-541). Ein gelöstes Rechteck neben einem Kreis, der noch sein
    Maß bekommt, behält jede Zahl bitgleich — über die Mitte und zurück wäre
    aus 0,07 hier 0,06999999999999999 geworden, und der Editor schriebe
    Ecken zurück, die niemand bewegt hat."""
    corners = [(0.1, 0.07), (20.4, 0.07), (20.4, 10.17), (0.1, 10.17)]
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            *(SketchElement("line", (a, b)) for a, b in pairwise([*corners, corners[0]])),
            SketchElement("circle", ((40.1, 3.4), (41.2, 3.4))),
        ),
        constraints=(
            *(SketchConstraint("coincident", (2 * k + 1, (2 * k + 2) % 8)) for k in range(4)),
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("vertical", (2, 3)),
            SketchConstraint("horizontal", (4, 5)),
            SketchConstraint("vertical", (6, 7)),
            SketchConstraint("diameter", (8, 9), "4"),
        ),
    )
    drawn = edit.flat_points(sketch)
    points = _flat(solve_sketch(sketch))

    assert points[:8] == drawn[:8], "bitgleich, nicht nur nah"
    assert span(points[8], points[9]) == pytest.approx(2.0, abs=1e-9)


@pytest.mark.parametrize("case", sorted(_UNSOLVABLE))
def test_an_unsolvable_sketch_names_the_same_pair_wherever_it_lies(case: str) -> None:
    """Widerspruch oder Doppelung: an jedem Ort dieselbe Meldung mit demselben
    Paar (RM-541; Lagegleichheit heißt diskret gleich).

    Zwei Reste, die am wahren Minimum gleich sind, lagen am Abbruchpunkt
    4·10⁻⁸ auseinander, je nach Ort einmal so, einmal so herum (``tie``). An
    einer redundanten Zeichnung nahm ``dogbox`` Singulärwerte im
    Rundungsrauschen für Richtungen und rannte davon, und hunderttausend
    Millimeter neben dem Nullpunkt war das Rauschen der Ableitungen 10⁻¹²
    (``doubled``, ``two_lengths``). Ein vierter Fall stand hier als Doppelung
    mit Rauschanteil im Paar; er ist lösbar, und 0.5.3 löst ihn — er steht
    jetzt unter den gesunden Skizzen (Review H-A, ``zufall_14``).
    """
    lines, rules = _UNSOLVABLE[case]
    sketch = Sketch(
        plane="plane:xy",
        elements=tuple(SketchElement("line", line) for line in lines),
        constraints=tuple(SketchConstraint(kind, targets, value) for kind, targets, value in rules),
    )
    said: set[tuple[str, int, int]] = set()
    for dx, dy in (*_PLACES, (1e6, -1e6)):
        with pytest.raises(SketchConflictError) as caught:
            solve_sketch(_placed(sketch, [(x + dx, y + dy) for x, y in edit.flat_points(sketch)]))
        said.add((str(caught.value.title), caught.value.first, caught.value.second))
    assert len(said) == 1, said


def _random_sketch(rng: random.Random) -> Sketch:
    """Eine Zufallsskizze aus Linien und Kreisen mit gemischten Bedingungen —
    wie die Breitensonde der Nachprüfung zu RM-541, ohne Bögen."""
    elements: list[SketchElement] = []
    for _ in range(rng.randint(2, 5)):
        cx, cy = rng.uniform(-30, 30), rng.uniform(-30, 30)
        if rng.random() < 0.6:
            tip = (cx + rng.uniform(4, 20), cy + rng.uniform(-8, 8))
            elements.append(SketchElement("line", ((cx, cy), tip)))
        else:
            rim = (cx + rng.uniform(2, 9), cy + rng.uniform(-0.5, 0.5))
            elements.append(SketchElement("circle", ((cx, cy), rim)))
    lines = [2 * i for i, element in enumerate(elements) if element.kind == "line"]
    rounds = [2 * i for i, element in enumerate(elements) if element.kind == "circle"]
    points = 2 * len(elements)
    rules: list[SketchConstraint] = []
    for _ in range(rng.randint(2, 7)):
        kind = rng.choice(
            ["coincident", "distance", "horizontal", "vertical", "parallel", "perpendicular",
             "equal", "angle", "tangent", "midpoint", "diameter", "symmetric"]
        )  # fmt: skip
        if kind == "coincident":
            a, b = rng.randrange(points), rng.randrange(points)
            if a != b:
                rules.append(SketchConstraint(kind, (a, b)))
        elif kind == "distance" and lines:
            line = rng.choice(lines)
            rules.append(
                SketchConstraint(kind, (line, line + 1), repr(round(rng.uniform(5, 20), 2)))
            )
        elif kind in ("horizontal", "vertical") and lines:
            line = rng.choice(lines)
            rules.append(SketchConstraint(kind, (line, line + 1)))
        elif kind in ("parallel", "perpendicular", "equal", "angle") and len(lines) >= 2:
            a, b = rng.sample(lines, 2)
            value = repr(float(rng.randint(15, 165))) if kind == "angle" else ""
            rules.append(SketchConstraint(kind, (a, a + 1, b, b + 1), value))
        elif kind == "tangent" and lines and rounds:
            line, round_ = rng.choice(lines), rng.choice(rounds)
            rules.append(SketchConstraint(kind, (line, line + 1, round_, round_ + 1)))
        elif kind == "midpoint" and lines:
            line, point = rng.choice(lines), rng.randrange(points)
            if point not in (line, line + 1):
                rules.append(SketchConstraint(kind, (point, line, line + 1)))
        elif kind == "diameter" and rounds:
            round_ = rng.choice(rounds)
            rules.append(
                SketchConstraint(kind, (round_, round_ + 1), repr(round(rng.uniform(4, 16), 2)))
            )
        elif kind == "symmetric" and lines:
            line = rng.choice(lines)
            p, q = rng.randrange(points), rng.randrange(points)
            if len({p, q, line, line + 1}) == 4:
                rules.append(SketchConstraint(kind, (p, q, line, line + 1)))
    rules.append(SketchConstraint("fixed", (0,)))
    return Sketch(plane="plane:xy", elements=tuple(elements), constraints=tuple(rules))


def test_random_sketches_say_the_same_wherever_and_however_they_are_rounded() -> None:
    """Über eine Zufallsmenge: Ob eine Skizze lösbar ist, ändert weder der Ort
    noch das Rauschen eines anderen Rechners — und was eine unlösbare meldet,
    höchstens in so vielen Fällen, wie gemessen (RM-541, Nachprüfung G-B).
    Gelöst heißt dabei nie: eine Linie mit Richtungsbedingung oder ein Kreis
    auf einem Punkt (Review H-A).

    Die Meldung nennt das Paar an den Resten eines Laufs auf einen
    Widerspruch, und der endet in einem flachen Tal. Die Folge im Paar kommt
    deshalb aus dem Setzen, ein erfüllter Partner wird durch den mit den
    meisten gemeinsamen Zielpunkten ersetzt, und ob ein Weg ein Element
    schrumpfen lässt, entscheidet nicht mehr die Quelle der Meldung. Was
    bleibt, steht in der Begründung der Skizzenkarte; die Schranke hier ist
    die Messung, kein Wunsch.
    """
    from app.core.sketch.solver import SHRUNK_BELOW
    from tests.test_platform_identity import platform_noise

    def said(sketch: Sketch) -> str:
        try:
            solved = solve_sketch(sketch)
        except SketchConflictError as error:
            return f"{error.title} {error.first} {error.second}"
        starts = edit.offsets_of(sketch)
        shrunk = [
            index
            for index, element in enumerate(solved.elements)
            if math.dist(*element.points[:2]) < SHRUNK_BELOW
            and (element.kind == "circle" or _directed(sketch, starts[index]))
        ]
        return f"gelöst, geschrumpft {shrunk}" if shrunk else "gelöst"

    rng = random.Random(7541)
    unsolvable = 0
    wandering: list[str] = []
    for index in range(100):
        sketch = _random_sketch(rng)
        home = said(sketch)
        others = [
            said(_placed(sketch, [(x + dx, y + dy) for x, y in edit.flat_points(sketch)]))
            for dx, dy in ((12.3, 45.6), (1000.1, -0.7))
        ]
        for pattern in (0, 1):
            with platform_noise(pattern):
                others.append(said(sketch))
        assert "geschrumpft" not in home, (index, home)
        assert all((other == "gelöst") == (home == "gelöst") for other in others), (
            index,
            home,
            others,
        )
        if home != "gelöst":
            unsolvable += 1
            if any(other != home for other in others):
                wandering.append(f"{index}: {home} | {others}")
    assert unsolvable >= 40, "die Menge prüft zu wenig Unlösbares"
    assert len(wandering) * _WANDERING_SHARE <= unsolvable, wandering


#: Höchstens jede so vielte unlösbare Skizze darf je Ort oder Rauschen einen
#: anderen Partner nennen. Gemessen: hier keine von 50, in der Breitensonde
#: der Nachprüfung 4 von 195 (2 %); vor Review H-A waren es hier 3 von 44.
#: Die Schranke lässt einem anderen Rechner zwei Fälle.
_WANDERING_SHARE = 20

#: Bedingungen, deren Richtung an einer Linie der Länge null leer gilt — aus
#: dem, was :func:`_random_sketch` setzt, unabhängig vom Löser aufgezählt.
_DIRECTED = frozenset(
    {
        "horizontal",
        "vertical",
        "parallel",
        "perpendicular",
        "equal",
        "angle",
        "tangent",
        "symmetric",
    }
)


def _directed(sketch: Sketch, tail: int) -> bool:
    """Trägt die Linie ab Punkt ``tail`` eine Richtungsbedingung?"""
    return any(
        constraint.kind in _DIRECTED and {tail, tail + 1} & set(constraint.targets)
        for constraint in sketch.constraints
    )


#: Gezeichnete Skizzen aus der Nah- und Breitensonde der Nachprüfung zu
#: RM-541 (Startwerte 1541, 2541, 541, 7541): verdeckte Widersprüche und
#: gesunde Skizzen, die weit von ihrer Lösung gezeichnet sind.
_HIDDEN_CONTRADICTIONS = {
    "gross_17": (
        [
            (
                "line",
                (
                    (0.2769653161776989, -0.033188102882082515),
                    (17.80366998602637, -4.745685728719326),
                ),
            ),
            (
                "line",
                ((17.506970088380818, -5.040962604921895), (42.40577268841871, -6.963586610510137)),
            ),
            (
                "line",
                ((42.325470076958304, -7.056274341812847), (42.376853173186, -0.8043468061751797)),
            ),
            (
                "line",
                (
                    (42.35001073204633, -0.9019402293171869),
                    (35.74178030219399, -0.6320788532402484),
                ),
            ),
            ("line", ((35.58094665710971, -0.8736354513765043), (0.0, 0.0))),
        ],
        [
            ("coincident", (1, 2), ""),
            ("coincident", (3, 4), ""),
            ("coincident", (5, 6), ""),
            ("coincident", (7, 8), ""),
            ("coincident", (9, 0), ""),
            ("horizontal", (2, 3), ""),
            ("vertical", (4, 5), ""),
            ("horizontal", (6, 7), ""),
            ("distance", (8, 9), "36.0"),
            ("angle", (2, 3, 0, 1), "170.0"),
            ("horizontal", (0, 1), ""),
            ("fixed", (0,), ""),
        ],
    ),
    "gross_48": (
        [
            (
                "line",
                (
                    (0.11833932733172586, 0.11913394372708958),
                    (-1.1237988648267838, 10.910539792101602),
                ),
            ),
            (
                "line",
                (
                    (-1.0003842853971991, 10.826276382331407),
                    (-20.07536788467962, 15.238088657174657),
                ),
            ),
            (
                "line",
                (
                    (-19.856819540049013, 15.084030611616758),
                    (-19.763980654095253, 34.589913045170206),
                ),
            ),
            (
                "line",
                ((-20.043149342504158, 34.65419038468188), (-38.98328361884417, 40.34734524277671)),
            ),
            (
                "line",
                ((-38.87151520732539, 40.1419953386811), (-43.263066954471796, 14.224532909549243)),
            ),
            (
                "circle",
                (
                    (-45.80431841490346, 27.985923748752896),
                    (-41.05312874652748, 27.985923748752896),
                ),
            ),
        ],
        [
            ("coincident", (1, 2), ""),
            ("coincident", (3, 4), ""),
            ("coincident", (5, 6), ""),
            ("coincident", (7, 8), ""),
            ("vertical", (0, 1), ""),
            ("distance", (2, 3), "20.0"),
            ("vertical", (4, 5), ""),
            ("distance", (8, 9), "26.0"),
            ("angle", (0, 1, 6, 7), "65.0"),
            ("angle", (2, 3, 0, 1), "110.0"),
            ("tangent", (8, 9, 10, 11), ""),
            ("horizontal", (6, 7), ""),
            ("fixed", (0,), ""),
        ],
    ),
    "nah_108": (
        [
            (
                "line",
                (
                    (-0.23090393305917575, 0.23746339438242353),
                    (-7.118709581448391, -0.41524622325675153),
                ),
            ),
            (
                "line",
                (
                    (-7.000641374847483, -0.2631228044829941),
                    (-6.5205683961069685, 9.084506625910624),
                ),
            ),
            (
                "line",
                ((-6.619058597219485, 9.231063407574954), (1.1412831937353705, 33.99356504739975)),
            ),
            (
                "line",
                (
                    (0.8609262323290301, 34.20285764364691),
                    (-10.501032143549137, 38.231306408157884),
                ),
            ),
            (
                "line",
                ((-10.361316026362157, 38.1244840416892), (-37.92180336622332, 38.402833744630215)),
            ),
            ("line", ((-37.79689332645539, 38.35389628737731), (0.0, 0.0))),
        ],
        [
            ("coincident", (1, 2), ""),
            ("coincident", (3, 4), ""),
            ("coincident", (5, 6), ""),
            ("coincident", (7, 8), ""),
            ("coincident", (9, 10), ""),
            ("coincident", (11, 0), ""),
            ("horizontal", (0, 1), ""),
            ("vertical", (2, 3), ""),
            ("distance", (2, 3), "9.0"),
            ("horizontal", (8, 9), ""),
            ("distance", (10, 11), "54.0"),
            ("angle", (0, 1, 10, 11), "130.0"),
            ("angle", (2, 3, 10, 11), "50.0"),
            ("angle", (6, 7, 8, 9), "20.0"),
            ("fixed", (0,), ""),
        ],
    ),
    "zufall_76": (
        [
            ("line", ((0.0, 0.0), (10.464148542261844, -7.471285297880894))),
            (
                "line",
                ((10.791557358439597, -6.883787042713742), (25.2864210378375, 0.6259861680749528)),
            ),
            (
                "line",
                (
                    (24.484759248351214, 0.06123161232460883),
                    (36.620288835113215, -5.038929228211795),
                ),
            ),
            (
                "line",
                ((36.690248325708545, -4.533627067909887), (49.23345830478776, 0.8335017234553337)),
            ),
        ],
        [
            ("coincident", (1, 2), ""),
            ("coincident", (3, 4), ""),
            ("coincident", (5, 6), ""),
            ("angle", (0, 1, 4, 5), "68.0"),
            ("distance", (0, 1), "13.775"),
            ("horizontal", (4, 5), ""),
            ("vertical", (0, 1), ""),
            ("fixed", (0,), ""),
        ],
    ),
}

_HEALTHY_FAR_FROM_SOLVED = {
    "zufall_14": (
        [
            ("line", ((0.0, 0.0), (13.038228155485973, 3.686622409038357))),
            (
                "line",
                ((12.62008476354232, 3.0470259437952434), (20.581209906600456, 9.82646094252833)),
            ),
            (
                "line",
                ((20.74987795624194, 10.533310436169577), (28.76492657814943, 18.631618499728635)),
            ),
            (
                "line",
                ((27.64625695139281, 17.227911992561413), (42.46359282804533, 16.87148338794381)),
            ),
            (
                "line",
                ((43.257980091700865, 15.591185998675329), (55.37646756450006, 19.219615026275473)),
            ),
        ],
        [
            ("coincident", (1, 2), ""),
            ("coincident", (3, 4), ""),
            ("coincident", (5, 6), ""),
            ("coincident", (7, 8), ""),
            ("perpendicular", (8, 9, 6, 7), ""),
            ("angle", (2, 3, 8, 9), "103.0"),
            ("angle", (4, 5, 0, 1), "54.0"),
            ("vertical", (6, 7), ""),
            ("parallel", (0, 1, 6, 7), ""),
            ("fixed", (0,), ""),
        ],
    ),
    "gemischt_49": (
        [
            (
                "arc",
                (
                    (-4.322454540260516, 22.946870775382706),
                    (0.2470105598903114, 27.363594643867735),
                    (-10.501112085988346, 21.459708388633256),
                ),
            ),
            (
                "line",
                (
                    (-24.338860682064883, -9.239092338675402),
                    (-17.338289057894613, -2.0009469702504603),
                ),
            ),
            (
                "circle",
                (
                    (9.566989225048374, -22.755080872612297),
                    (15.498059927420368, -22.884928209777534),
                ),
            ),
        ],
        [
            ("horizontal", (3, 4), ""),
            ("symmetric", (6, 0, 3, 4), ""),
            ("fixed", (0,), ""),
        ],
    ),
    "gemischt_205": (
        [
            (
                "line",
                (
                    (10.434693650467239, -17.995286350306902),
                    (28.551284181954816, -22.34374780570176),
                ),
            ),
            (
                "arc",
                (
                    (-4.6956461536060985, -25.74871794450464),
                    (-1.556070402669513, -18.74649629064203),
                    (-10.920976472837062, -21.26170263339245),
                ),
            ),
        ],
        [
            ("tangent", (0, 1, 2, 3), ""),
            ("vertical", (0, 1), ""),
            ("fixed", (0,), ""),
        ],
    ),
    "gemischt_301": (
        [
            (
                "arc",
                (
                    (15.818403580212262, 11.01733052486911),
                    (21.664882742264783, 12.669591478280518),
                    (10.782040386089442, 14.415319728408068),
                ),
            ),
            (
                "line",
                (
                    (19.617687806248966, -27.07408524622863),
                    (29.374637901251738, -19.98524494447522),
                ),
            ),
            (
                "circle",
                (
                    (-21.468158497220262, -1.765161226362654),
                    (-16.659331354696366, -1.8362347446118998),
                ),
            ),
            (
                "arc",
                (
                    (15.60385951232358, 16.101903236967367),
                    (23.68622872580986, 19.987696621936283),
                    (6.65555730773473, 15.508632650194944),
                ),
            ),
        ],
        [
            ("diameter", (7, 8), "5.87"),
            ("coincident", (5, 2), ""),
            ("symmetric", (8, 0, 3, 4), ""),
            ("horizontal", (3, 4), ""),
            ("fixed", (0,), ""),
        ],
    ),
}


def _from_literal(
    elements: list[tuple[str, tuple[tuple[float, float], ...]]],
    rules: list[tuple[str, tuple[int, ...], str]],
) -> Sketch:
    return Sketch(
        plane="plane:xy",
        elements=tuple(SketchElement(kind, points) for kind, points in elements),
        constraints=tuple(SketchConstraint(kind, targets, value) for kind, targets, value in rules),
    )


_FAR_PLACES = (*_PLACES, (-7.77, 3.33), (1e6, -1e6))


@pytest.mark.parametrize("case", sorted(_HIDDEN_CONTRADICTIONS))
def test_a_contradiction_does_not_hide_behind_a_shrunk_line(case: str) -> None:
    """Ein Widerspruch wird gemeldet, nicht mit einer Linie der Länge null
    „gelöst“ — an jedem Ort mit demselben Paar (RM-541, Review H-A).

    ``gross_17``: zwei Linien *waagerecht*, dazwischen ein Winkel von 170°.
    An einer Linie ohne Länge gilt jede Richtung leer; der dichte Weg zog die
    erste dorthin, meldete „gelöst, Rest null“, und aus der Zeichnung wurde
    ein Umriss. 0.5.3 meldete den Widerspruch. In ``zufall_76`` schrumpfte
    die Linie nur auf 2·10⁻⁶ mm — dort erfüllt *waagerecht* bis ``_TOL``
    auch eine um 22° schräge Linie —, und wohin, hing je Ort um bis 15,8 mm
    an der Rundung. Gefunden mit der Nah- und Breitensonde der Nachprüfung.
    """
    sketch = _from_literal(*_HIDDEN_CONTRADICTIONS[case])
    said: set[tuple[int, int]] = set()
    for dx, dy in _FAR_PLACES:
        with pytest.raises(SketchConflictError) as caught:
            solve_sketch(_placed(sketch, [(x + dx, y + dy) for x, y in edit.flat_points(sketch)]))
        said.add((caught.value.first, caught.value.second))
    assert len(said) == 1, said
    if case == "gross_17":
        assert set(next(iter(said))) == {9, 10}, "waagerecht gegen den Winkel"


@pytest.mark.parametrize("case", sorted(_HEALTHY_FAR_FROM_SOLVED))
def test_a_healthy_sketch_drawn_far_from_its_solution_solves(case: str) -> None:
    """Eine gesunde Skizze, die 0.5.3 löst, löst auch hier — an jedem Ort
    gleich, und kein Element liegt danach auf einem Punkt (RM-541, Review H-A).

    Weit von der Lösung gezeichnet zog der dichte Weg eine Achse oder eine
    Richtungslinie auf null, und die Rangprüfung meldete eine Doppelung oder
    einen Widerspruch. Kein Weg trägt allein: ``zufall_14`` löst TRF dicht,
    ``gemischt_205`` und ``gemischt_301`` löst ``lsmr``, ``gemischt_49`` (eine
    Symmetrieachse, die jeder Weg schrumpfen ließ) erst mit der Achse auf
    ihrer gezeichneten Länge.
    """
    from app.core.sketch.solver import SHRUNK_BELOW
    from app.core.units import EPS_GEOM

    sketch = _from_literal(*_HEALTHY_FAR_FROM_SOLVED[case])
    home: list[tuple[float, float]] = []
    for dx, dy in _FAR_PLACES:
        solved = solve_sketch(
            _placed(sketch, [(x + dx, y + dy) for x, y in edit.flat_points(sketch)])
        )
        for element in solved.elements:
            assert math.dist(*element.points[:2]) > SHRUNK_BELOW, (dx, dy, element.kind)
        back = [(x - dx, y - dy) for x, y in _flat(solved)]
        if not home:
            home = back
        gap = max(math.dist(a, b) for a, b in zip(back, home, strict=True))
        assert gap <= EPS_GEOM, ((dx, dy), gap)


#: Zwei Widersprüche aus der Breitensonde der Nachprüfung zu RM-541
#: (Startwert 7541) und das Paar, das ein Mensch nennt — die zuletzt gesetzte
#: Bedingung vorn. ``gemischt_282``: eine Linie *waagerecht* und dreimal
#: *senkrecht*; ``gemischt_294``: zwei Linien gleich lang, im Winkel von 96°
#: und *parallel*.
_PAIR_RULES = {
    "gemischt_282": (
        [
            (
                "arc",
                (
                    (-18.264723443767274, -19.966994406082122),
                    (-17.560597558779875, -12.135356483081955),
                    (-24.403761919346657, -24.880501546021947),
                ),
            ),
            (
                "circle",
                (
                    (-29.742696847820575, -23.012407579931256),
                    (-25.088125403847734, -23.33727267457289),
                ),
            ),
            (
                "line",
                (
                    (-18.84833541389357, 4.887680967343762),
                    (-1.6217651125400288, -1.7071029624300031),
                ),
            ),
            (
                "arc",
                (
                    (25.920504053936426, 21.545932316202645),
                    (24.74991861446949, 25.466646752514286),
                    (22.17635486594806, 23.196271317826426),
                ),
            ),
        ],
        [
            ("horizontal", (5, 6), ""),
            ("vertical", (5, 6), ""),
            ("vertical", (5, 6), ""),
            ("vertical", (5, 6), ""),
            ("fixed", (0,), ""),
        ],
        (3, 0),
    ),
    "gemischt_294": (
        [
            (
                "line",
                ((2.785294079116703, 15.25433330805975), (20.987919322361034, 16.712307550003167)),
            ),
            (
                "arc",
                (
                    (-4.437472490871627, 7.5141977680853955),
                    (0.3569647979553583, 8.687926675356444),
                    (-6.71854210458402, 3.136870971779647),
                ),
            ),
            (
                "line",
                (
                    (-16.774294634647163, 22.48610766217903),
                    (-5.422926152454027, 16.327689380632215),
                ),
            ),
            (
                "line",
                (
                    (-6.737835650611526, -2.1904518256429704),
                    (11.441655070042533, -6.9026557464776435),
                ),
            ),
        ],
        [
            ("equal", (5, 6, 0, 1), ""),
            ("angle", (5, 6, 0, 1), "96.0"),
            ("parallel", (0, 1, 5, 6), ""),
            ("coincident", (8, 7), ""),
            ("coincident", (5, 2), ""),
            ("fixed", (0,), ""),
        ],
        (2, 1),
    ),
}


@pytest.mark.parametrize("case", sorted(_PAIR_RULES))
def test_a_contradiction_names_the_later_constraint_and_its_true_partner(case: str) -> None:
    """Das Paar einer Meldung ist an jedem Ort und unter dem Rauschen eines
    anderen Rechners dasselbe — die später gesetzte Bedingung vorn, und ein
    erfüllter Rest ist kein Partner (RM-541, Nachprüfung G-B).

    Ein Lauf auf einen Widerspruch endet in einem flachen Tal, und dort lag
    die Folge der Reste je Ort mal so, mal so herum (``gemischt_294``: der
    Winkel vor *parallel* an drei von neun Stellen). Die zweitgrößte von vier
    Achsenbedingungen war erfüllt bis auf Rauschen und kam je nach Ort als
    Partner ins Paar — einmal die Fixierung eines Bogens, die mit der Linie
    nichts zu tun hat (``gemischt_282``). In der Breitensonde wanderten ohne
    die Folge 8, ohne den Partner 6 und ohne beide 10 von 195 Paaren statt 4.
    """
    from tests.test_platform_identity import platform_noise

    elements, rules, pair = _PAIR_RULES[case]
    sketch = _from_literal(elements, rules)
    said: list[tuple[int, int]] = []
    for dx, dy in _FAR_PLACES:
        with pytest.raises(SketchConflictError) as caught:
            solve_sketch(_placed(sketch, [(x + dx, y + dy) for x, y in edit.flat_points(sketch)]))
        said.append((caught.value.first, caught.value.second))
    for pattern in (0, 1):
        with platform_noise(pattern), pytest.raises(SketchConflictError) as caught:
            solve_sketch(sketch)
        said.append((caught.value.first, caught.value.second))
    assert set(said) == {pair}, said


def _wobbled(sketch: Sketch, amount: float) -> Sketch:
    """Die Skizze mit ungelöst verschobenen Punkten — fest, ohne Zufall; ``fixed`` bleibt."""
    held = {
        constraint.targets[0] for constraint in sketch.constraints if constraint.kind == "fixed"
    }
    return _placed(
        sketch,
        [
            point
            if index in held
            else (
                point[0] + amount * ((index * 0.6180339887) % 1.0 - 0.5),
                point[1] + amount * ((index * 0.4142135623) % 1.0 - 0.5),
            )
            for index, point in enumerate(edit.flat_points(sketch))
        ],
    )


@pytest.mark.parametrize("amount", [0.0, 1.0])
@pytest.mark.parametrize("step", [(0.4, -0.3), (0.5, 0.5)])
@pytest.mark.parametrize("shape", ["slot", "polygon"])
def test_a_drag_the_shape_cannot_follow_lands_alike_wherever_it_lies(
    shape: str, step: tuple[float, float], amount: float
) -> None:
    """Langloch und Fünfeck an einer Ecke gezogen, die sie nicht ganz hergeben:
    an jedem Ort dieselbe Lage (RM-541, Review M-1).

    Die Formen halten sich selbst und bleiben doch biegsam; der Zeiger ist
    unerreichbar, also rutscht die zweite Stufe. Sie begann, wo die erste
    aufgehört hatte — in einem flachen Tal, wohin die Rundung sie trug. Nach
    zehn Mausschritten standen die Formen so je nach Ort bis 8,8 mm
    woanders. Jetzt beginnt sie am Stand vor dem Schritt.
    """
    from app.core.sketch import shapes
    from app.core.units import EPS_GEOM

    drawn = _wobbled(
        shapes.slot(30.0, 10.0) if shape == "slot" else shapes.polygon(30.0, 5), amount
    )

    def dragged(at: tuple[float, float]) -> list[tuple[float, float]]:
        sketch = _placed(drawn, [(x + at[0], y + at[1]) for x, y in edit.flat_points(drawn)])
        points = _flat(solve_sketch(sketch))
        corner = points[3]
        for count in range(1, 11):
            target = (corner[0] + step[0] * count, corner[1] + step[1] * count)
            points = _flat(solve_sketch(_placed(sketch, points), dragged={3: target}, start=points))
        return [(x - at[0], y - at[1]) for x, y in points]

    home = dragged((0.0, 0.0))
    for at in ((1000.0, 0.0), (-1000.0, 1000.0), (1e5, -1e5)):
        gap = max(math.dist(a, b) for a, b in zip(dragged(at), home, strict=True))
        assert gap <= EPS_GEOM, (at, gap)


@pytest.mark.parametrize("apart", [False, True])
def test_a_joint_follows_the_drag_even_a_rounding_apart(apart: bool) -> None:
    """Ein Gelenk aus zwei gedeckten Punkten folgt dem Zug, auch wenn beide um
    ein ULP auseinanderliegen — so liegen sie nach einem Lösen, je nach
    Rundung der Maschine (RM-541, Review H-1).

    Zwei Linien, gedeckt an der Ecke, die zweite senkrecht; gezogen wird ihr
    freies Ende. Im Zug steht es fest, und übrig bleibt ein Teil aus den
    beiden Gelenkpunkten. Sein erster Schritt maß sich an der Streuung dieser
    zwei Punkte, also am Rundungsrauschen der Deckung, und der Löser hörte
    nach der ersten Auswertung auf: Der Punkt blieb 0,27 mm hinter dem Zeiger,
    das Gelenk rückte 0,13 statt 0,4 mm — an jedem Ort.
    """
    for dx, dy in _PLACES:
        corner = (10.0 + dx, dy)
        other = (math.nextafter(corner[0], math.inf), corner[1]) if apart else corner
        sketch = Sketch(
            plane="plane:xy",
            elements=(
                SketchElement("line", ((dx, dy), corner)),
                SketchElement("line", (other, (10.0 + dx, 10.0 + dy))),
            ),
            constraints=(
                SketchConstraint("coincident", (1, 2)),
                SketchConstraint("vertical", (2, 3)),
            ),
        )
        start = edit.flat_points(sketch)
        target = (start[3][0] + 0.4, start[3][1] - 0.3)
        points = _flat(solve_sketch(sketch, dragged={3: target}, start=start))
        assert points[3] == pytest.approx(target, abs=1e-9), ((dx, dy), "der Punkt am Zeiger")
        assert points[2][0] - start[2][0] == pytest.approx(0.4, abs=1e-9), (dx, dy)
        assert math.dist(points[1], points[2]) <= 1e-9, (dx, dy)


def test_a_line_a_rounding_long_takes_its_measure_wherever_it_lies() -> None:
    """Eine Linie, deren Enden ein ULP auseinanderliegen, bekommt ihr Maß an
    jedem Ort (RM-541, Review H-1).

    Der erste Schritt maß sich an der Streuung der zwei Punkte. Um ein ULP
    gestreut war er so klein, dass der Löser stehen blieb — wo ein ULP
    10⁻¹⁵ mm ist, hieß das Widerspruch, wo es 10⁻¹¹ mm ist, gelöst."""
    for dx, dy in _PLACES:
        tail = (5.0 + dx, dy)
        head = (math.nextafter(tail[0], math.inf), dy)
        sketch = Sketch(
            plane="plane:xy",
            elements=(SketchElement("line", (tail, head)),),
            constraints=(SketchConstraint("distance", (0, 1), "10"),),
        )
        solved = solve_sketch(sketch)
        assert span(*solved.elements[0].points) == pytest.approx(10.0, abs=1e-9), (dx, dy)


def test_an_angle_outside_the_half_turn_is_refused() -> None:
    """Null und 180 Grad sind ``parallel``, und darüber wiederholt sich alles.

    Die Gleichung hat die Periode 180: 200 Grad wären dieselbe Bedingung wie
    20 und hießen trotzdem anders. Eine Zahl, die etwas anderes tut, als sie
    sagt, wird abgelehnt statt still umgedeutet (Regel 21).
    """
    for degrees in ("0", "180", "200", "-30"):
        with pytest.raises(ValidationError) as caught:
            solve_sketch(two_lines_at_a_corner(degrees))
        assert caught.value.constraint == "angle_range"
        assert caught.value.suggestions, "ein Fehler endet nie mit „fehlgeschlagen“"


def test_an_angle_without_a_value_is_refused() -> None:
    sketch = replace(
        two_lines_at_a_corner(),
        constraints=(SketchConstraint("angle", (0, 1, 2, 3)),),
    )
    with pytest.raises(ValidationError) as caught:
        solve_sketch(sketch)
    assert caught.value.constraint == "required"


def test_an_angle_that_fights_a_right_angle_names_the_pair() -> None:
    """Dreißig Grad gegen eine Senkrechte: Der Löser nennt beide Bedingungen."""
    sketch = two_lines_at_a_corner("30")
    fought = replace(
        sketch,
        constraints=(*sketch.constraints, SketchConstraint("perpendicular", (0, 1, 2, 3))),
    )
    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(fought)
    assert {caught.value.first, caught.value.second} == {5, 6}
    assert caught.value.suggestions


def test_a_dragged_point_keeps_the_angle_it_was_given() -> None:
    """Der Zug läuft auf dem Kreis, den der Winkel übrig lässt.

    Gezogen wird das freie Ende der zweiten Linie quer über die erste. Der
    Winkel hält, die Länge hält, und der Punkt landet so weit am Zeiger, wie
    beides zulässt — das ist die Zusage des Zugmodus.
    """
    sketch = two_lines_at_a_corner("60")
    start = [point for element in solve_sketch(sketch).elements for point in element.points]
    solved = solve_sketch(sketch, dragged={3: (2.0, 12.0)}, start=start)
    assert math.isclose(turn_between(*solved.elements[:2]), 60.0, abs_tol=1e-6)
    assert math.isclose(span(*solved.elements[1].points), 10.0, abs_tol=1e-6)


def test_equal_makes_two_lines_the_same_length() -> None:
    """Eine Linie ist bemaßt, die andere hängt an ihr."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("line", ((0.0, 5.0), (4.0, 5.0))),
        ),
        constraints=(
            SketchConstraint("fixed", (0,)),
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("horizontal", (2, 3)),
            SketchConstraint("fixed", (2,)),
            SketchConstraint("distance", (0, 1), "30"),
            SketchConstraint("equal", (0, 1, 2, 3)),
        ),
    )
    solved = solve_sketch(sketch)
    assert solved.free_dof == 0
    assert math.isclose(span(*solved.elements[0].points), 30.0, abs_tol=1e-6)
    assert math.isclose(span(*solved.elements[1].points), 30.0, abs_tol=1e-6)


def test_equal_makes_two_circles_the_same_size() -> None:
    """Dieselbe Bedingung, dieselbe Gleichung — nur heißt die Spanne hier
    Radius. Genau deshalb gibt es keine zweite Art ``equal_radius``."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("circle", ((0.0, 0.0), (5.0, 0.0))),
            SketchElement("circle", ((20.0, 0.0), (23.0, 0.0))),
        ),
        constraints=(
            SketchConstraint("diameter", (0, 1), "10"),
            SketchConstraint("equal", (0, 1, 2, 3)),
        ),
    )
    solved = solve_sketch(sketch)
    assert math.isclose(span(*solved.elements[0].points), 5.0, abs_tol=1e-6)
    assert math.isclose(span(*solved.elements[1].points), 5.0, abs_tol=1e-6)


def test_equal_holds_an_arc_to_the_radius_of_a_circle() -> None:
    """Beim Bogen sind Mitte und Anfang die Spanne — die zwei Punkte, die
    seinen Radius tragen. Dass er drei führt, geht die Bedingung nichts an."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("circle", ((0.0, 0.0), (4.0, 0.0))),
            SketchElement("arc", ((20.0, 0.0), (27.0, 0.0), (20.0, 7.0))),
        ),
        constraints=(
            SketchConstraint("diameter", (0, 1), "8"),
            SketchConstraint("equal", (0, 1, 2, 3)),
        ),
    )
    solved = solve_sketch(sketch)
    centre, begin, end = solved.elements[1].points
    assert math.isclose(span(centre, begin), 4.0, abs_tol=1e-6)
    assert math.isclose(span(centre, end), 4.0, abs_tol=1e-6), "der zweite Schenkel zieht mit"


def test_a_midpoint_sits_halfway_along_its_line() -> None:
    """Drei Ziele: der Punkt, dann Anfang und Ende der Linie."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (10.0, 4.0))),
            SketchElement("point", ((1.0, 1.0),)),
        ),
        constraints=(
            SketchConstraint("fixed", (0,)),
            SketchConstraint("fixed", (1,)),
            SketchConstraint("midpoint", (2, 0, 1)),
        ),
    )
    solved = solve_sketch(sketch)
    assert solved.free_dof == 0
    assert solved.elements[1].points[0] == pytest.approx((5.0, 2.0), abs=1e-6)


def test_a_midpoint_that_fights_a_fixed_point_names_the_pair() -> None:
    """Ein festgenagelter Punkt neben der Mitte, die woanders liegt."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("point", ((1.0, 0.0),)),
        ),
        constraints=(
            SketchConstraint("fixed", (0,)),
            SketchConstraint("fixed", (1,)),
            SketchConstraint("fixed", (2,)),
            SketchConstraint("midpoint", (2, 0, 1)),
        ),
    )
    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(sketch)
    assert {caught.value.first, caught.value.second} == {2, 3}
    assert caught.value.suggestions


def test_concentric_is_the_coincidence_of_two_centres() -> None:
    """Konzentrisch braucht keine eigene Art (siehe ``SketchConstraintKind``).

    Zwei Kreise auf derselben Mitte sind die Deckung ihrer Mittelpunkte — und
    das kann das Datenmodell seit je. Was fehlte, war das Wort an einem Knopf,
    und das ist eine Frage der Oberfläche.
    """
    sketch = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("circle", ((0.0, 0.0), (5.0, 0.0))),
            SketchElement("circle", ((3.0, 1.0), (10.0, 1.0))),
        ),
        constraints=(
            SketchConstraint("fixed", (0,)),
            SketchConstraint("coincident", (0, 2)),
            SketchConstraint("diameter", (0, 1), "10"),
            SketchConstraint("diameter", (2, 3), "20"),
        ),
    )
    solved = solve_sketch(sketch)
    assert solved.elements[0].points[0] == pytest.approx(solved.elements[1].points[0], abs=1e-6)
    assert math.isclose(span(*solved.elements[0].points), 5.0, abs_tol=1e-6)
    assert math.isclose(span(*solved.elements[1].points), 10.0, abs_tol=1e-6)


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
    assert solved.free_dof == 0, (
        "nichts wackelt — die Drehung eines Randpunkts ist kein Freiheitsgrad"
    )

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
    assert solved.free_dof == 0, (
        "nichts wackelt — die Drehung eines Randpunkts ist kein Freiheitsgrad"
    )

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
    exact_kernel()
    from app.core.brep import profiles as brep_profiles
    from app.core.sketch.profile import profile_of
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch, SketchElement

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


@pytest.mark.parametrize(
    ("corner", "centre"),
    [((0.0, 0.0), (10.0, 10.0)), ((-60.0, 35.0), (-45.0, 42.0)), ((120.0, -80.0), (150.0, -70.0))],
)
def test_a_hole_away_from_the_origin_stays_a_hole(
    corner: tuple[float, float], centre: tuple[float, float]
) -> None:
    """Ein Loch bleibt ein Loch, gleich wo die Platte liegt (Durchsicht P6.6).

    Die Verschachtelung fragte den exakten Kern mit einem **ebenen** Punkt
    (``gp_Pnt2d``) — und der liest ihn in den Parametern der Fläche. Die Ebene
    einer Fläche aus einem Draht hat ihren Ursprung aber in der Mitte des
    Drahts: Eine Platte von (0 | 0) bis (40 | 20) trägt ihn bei (20 | 10), und
    der Kreis bei (10 | 10) wurde bei (30 | 20) gesucht — auf dem Rand, also
    „nicht innen". Aus Platte und Loch wurden zwei Umrisse nebeneinander, der
    Kreis ein eigener Körper **in** der Platte, und das Loch war weg: 4000 mm³
    statt 3367 an der Beispieldatei. Die Tests darüber zeichnen um den
    Ursprung, dort fällt beides zusammen. Seit v0.3.5 ausgeliefert.
    """
    from app.core.sketch.profile import regions_of
    from app.core.types import SketchElement

    x, y = corner
    plate = (
        SketchElement("line", ((x, y), (x + 40.0, y))),
        SketchElement("line", ((x + 40.0, y), (x + 40.0, y + 20.0))),
        SketchElement("line", ((x + 40.0, y + 20.0), (x, y + 20.0))),
        SketchElement("line", ((x, y + 20.0), (x, y))),
    )
    hole = SketchElement("circle", (centre, (centre[0] + 4.0, centre[1])))
    regions = regions_of(solve_sketch(Sketch(plane="plane:xy", elements=(*plate, hole))))

    assert len(regions) == 1, "Platte und Loch sind ein Umriss"
    assert len(regions[0].holes) == 1, "und der Kreis ist sein Loch"
    if brep_available():
        from app.core.brep import profiles as brep_profiles

        body = brep_profiles.extrude(regions[0], 5.0)
        assert body.volume == pytest.approx((40.0 * 20.0 - math.pi * 16.0) * 5.0, rel=1e-9)


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
    exact_kernel()
    from app.core.brep import profiles as brep_profiles
    from app.core.sketch.profile import regions_of
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch

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


def test_a_degenerate_arc_is_a_full_circle() -> None:
    """Regel 6: Der Löser liefert Bogenenden mit Restfehler um 1e-12 —
    `== 0.0` fing den Vollkreisfall nie, der Stützpunkt landete auf dem
    Startpunkt, und der B-Rep-Kern baute einen Bogen ohne Ausdehnung."""
    from app.core.sketch.profile import _arc_midpoint

    exact = _arc_midpoint((0.0, 0.0), (10.0, 0.0), (10.0, 0.0))
    assert exact == pytest.approx((-10.0, 0.0), abs=1e-6)

    jittered = _arc_midpoint((0.0, 0.0), (10.0, 0.0), (10.0, 1e-10))
    assert jittered == pytest.approx((-10.0, 0.0), abs=1e-3)


def test_a_sketch_without_area_is_a_user_error_not_a_crash() -> None:
    """Ein Umriss ohne Fläche ist eine Eingabe, kein Programmfehler.

    **Der Fall ist lösbar und trotzdem unbrauchbar.** Wer *horizontal* und
    *vertikal* auf dieselbe Linie setzt, hat keinen Widerspruch gebaut: Die
    Linie schrumpft auf einen Punkt, und dann ist sie beides. Der Solver hat
    recht, er meldet zwei Freiheitsgrade und ein Restfehler von null.

    Nur wird daraus ein Profil mit der Fläche null, und OpenCASCADE kann
    daraus keinen Körper bauen: ``StdFail_NotDone: BRep_API: command not
    done``. Die C++-Ausnahme wurde zum ``InternalError``, und der Nutzer las
    „Im Programm ist ein unerwarteter Fehler aufgetreten" samt Knopf für den
    Fehlerbericht — für zwei Bedingungen, die er selbst gesetzt hat.

    Geprüft wird hier die Stelle, an der das Profil entsteht: Sie deckt alle
    vier Skizzen-Operationen auf einmal ab, weil alle vier durch sie gehen.
    """
    from app.core.errors import GeometryError
    from app.core.sketch.profile import profile_of
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch, SketchConstraint, SketchElement

    line = SketchElement(kind="line", points=((0.0, 0.0), (10.0, 0.0)))
    degenerate = Sketch(
        plane="plane:xy",
        elements=(line,),
        constraints=(
            SketchConstraint(kind="horizontal", targets=(0, 1)),
            SketchConstraint(kind="vertical", targets=(0, 1)),
        ),
    )
    # Seit RM-541 (Review H-A) löst der Solver das nicht mehr auf eine Linie
    # der Länge null, sondern nennt den Widerspruch: An einer Linie ohne
    # Länge gilt jede Richtung leer, und 0.5.3 meldete daraus „gelöst“.
    with pytest.raises(SketchConflictError) as conflict:
        solve_sketch(degenerate)
    assert {conflict.value.first, conflict.value.second} == {0, 1}

    # Die Profilprüfung bleibt für jeden anderen Weg zu einem Umriss ohne
    # Fläche — hier eine Linie, die so gezeichnet wurde.
    collapsed = SolvedSketch(
        elements=(SketchElement(kind="line", points=((5.0, 0.0), (5.0, 0.0))),),
        free_dof=4,
        max_residual=0.0,
    )
    with pytest.raises(GeometryError) as caught:
        profile_of(collapsed)
    assert caught.value.suggestions, "ein Fehler ohne Ausweg ist fehlgeschlagen mit mehr Worten"


def test_a_degenerate_loop_beside_a_good_one_is_dropped() -> None:
    """Was keine Fläche hat, fliegt heraus — der Rest bleibt.

    **Der Mischfall, gefunden beim Review des eigenen Fixes.** Erst stand
    hier ``all(...)``: geworfen wurde nur, wenn *keine* Kette trug. Ein
    Rechteck von 1200 mm² neben einer auf einen Punkt geschrumpften Linie
    ging damit durch, und die leere Kette wanderte weiter in den exakten
    Kern — dorthin, wo sie denselben ``StdFail_NotDone`` ausgelöst hätte,
    gegen den die Prüfung gebaut wurde.

    Richtig ist das Verwerfen: Eine Kette ohne Fläche ist keine Region.
    """
    import dataclasses

    from app.core.sketch import shapes
    from app.core.sketch.profile import _outline, regions_of
    from app.core.sketch.solver import solve_sketch
    from app.core.types import SketchElement
    from app.core.units import ring_area

    rectangle = shapes.rectangle(40.0, 30.0)
    # Die Linie liegt gezeichnet auf einem Punkt: *Waagerecht* und *senkrecht*
    # zugleich nennt der Solver seit RM-541 als Widerspruch (Review H-A).
    mixed = dataclasses.replace(
        rectangle,
        elements=(
            *rectangle.elements,
            SketchElement(kind="line", points=((60.0, 0.0), (60.0, 0.0))),
        ),
    )

    regions = regions_of(solve_sketch(mixed))

    assert len(regions) == 1, "die geschrumpfte Kette ist keine Region"
    assert ring_area(_outline(regions[0])) == pytest.approx(1200.0)


# --- Ebenenkoordinaten (§30.1, Konzept „Die Skizze in den Raum", P0) --------
#
# Diese vier Tests brauchen ausdrücklich **kein** OpenCASCADE. Das ist ihr
# Zweck: Die Zeichenfläche muss dieselbe Umrechnung machen wie die Auswertung,
# und sie muss es können, wenn der B-Rep-Kern gar nicht installiert ist.
# `test_sketch_ops.py` überspringt sich ohne OCC komplett — dort wären sie
# stumm.


def tilted_frame() -> PlaneFrame:
    """Ein Rahmen, der nicht auf einer Hauptebene liegt.

    Die 45°-Neigung ist der interessante Fall: Auf XY stimmt jede Rechnung,
    die x und y einfach durchreicht, und würde einen Vorzeichenfehler in der
    dritten Achse nie zeigen.
    """
    return frame_of((1.0, 0.0, 1.0), (5.0, -2.0, 3.0))


def test_a_drawing_point_lands_where_the_frame_says() -> None:
    """Der Ursprung der Zeichnung ist der Ursprung des Rahmens."""
    frame = tilted_frame()
    assert to_world(frame, (0.0, 0.0)) == pytest.approx(frame.origin)

    # Eine Einheit entlang der ersten Achse ist eine Einheit im Raum — sonst
    # wäre die Skizze skaliert, und zwar unauffällig.
    along = to_world(frame, (1.0, 0.0))
    moved = tuple(along[axis] - frame.origin[axis] for axis in range(3))
    assert moved == pytest.approx(frame.x_axis)


def test_the_two_directions_are_each_others_reverse() -> None:
    """Hin und zurück muss denselben Punkt ergeben.

    Die teure Variante dieses Fehlers ist keine Ausnahme, sondern eine
    Zeichnung, die beim Speichern und Öffnen langsam wandert.
    """
    frame = tilted_frame()
    for point in ((0.0, 0.0), (12.5, -7.25), (-40.0, 40.0)):
        assert to_plane(frame, to_world(frame, point)) == pytest.approx(point)


def test_a_point_off_the_plane_drops_its_distance() -> None:
    """Was der Zeiger im Raum trifft, liegt nie exakt auf der Ebene.

    Der Abstand entlang der Normalen fällt weg, und das ist der Zweck: Die
    Zeichnung rechnet mit zwei Zahlen. Ohne diese Zusage müsste jeder Aufrufer
    selbst projizieren — und einer würde es vergessen.
    """
    frame = tilted_frame()
    on_plane = to_world(frame, (3.0, 4.0))
    above = tuple(on_plane[axis] + 17.0 * frame.normal[axis] for axis in range(3))
    assert to_plane(frame, above) == pytest.approx((3.0, 4.0))


def test_the_flat_plane_keeps_the_drawing_unturned() -> None:
    """Auf einer waagerechten Fläche ist der Zeichenpunkt der Weltpunkt.

    Die Zusage aus ``frame_of``: dieselbe Skizze liegt auf dem Tisch und auf
    dem Deckel gleich herum. Eine Zahl dafür, nicht nur ein Satz.
    """
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 10.0))
    assert to_world(frame, (7.0, -3.0)) == pytest.approx((7.0, -3.0, 10.0))


def test_a_ray_straight_down_hits_where_it_points() -> None:
    """Der einfache Fall, an dem sich das Vorzeichen prüfen lässt."""
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 10.0))
    assert ray_hit(frame, (3.0, -4.0, 60.0), (0.0, 0.0, -1.0)) == pytest.approx((3.0, -4.0))


def test_the_length_of_the_ray_does_not_change_where_it_lands() -> None:
    """Die Ansicht reicht den Schritt von der nahen zur fernen Ebene herein.

    Der ist hunderte Millimeter lang und nicht normiert. Käme dabei ein
    anderer Punkt heraus als bei derselben Richtung in Einheitslänge, hinge
    die Zeichnung an der Tiefe des Sichtvolumens.
    """
    frame = tilted_frame()
    short = ray_hit(frame, (20.0, 5.0, 40.0), (-0.6, 0.0, -0.8))
    long = ray_hit(frame, (20.0, 5.0, 40.0), (-600.0, 0.0, -800.0))
    assert short is not None
    assert long == pytest.approx(short)


def test_a_grazing_ray_finds_no_place_to_point_at() -> None:
    """Der Blick fast entlang der Ebene ergibt keine brauchbare Stelle.

    **Und dieser Test misst die Prüfung, nicht nur den Fall.** Die erste
    Fassung von ``ray_hit`` verglich das rohe Skalarprodukt gegen die
    Schwelle. Bei diesem Strahl ist es 0,5 — tausendfach über 1e-3 —, obwohl
    der Winkel zur Ebene ein halbes Tausendstel beträgt. Die Prüfung hätte
    nie ausgelöst, und die Zeichnung bekäme einen Punkt einen Kilometer
    daneben. Gemessen wird deshalb der Winkel.
    """
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    assert ray_hit(frame, (0.0, 0.0, 5.0), (1000.0, 0.0, -0.5)) is None


def test_a_plane_behind_the_viewer_is_not_a_target() -> None:
    """Rückwärts wird nicht getroffen.

    Ohne diese Bedingung liefert der Schnitt brav eine Zahl — die Ebene liegt
    ja auf der Geraden, nur eben in die andere Richtung. Auf dem Schirm wäre
    das eine Stelle hinter dem Betrachter.
    """
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 10.0))
    assert ray_hit(frame, (0.0, 0.0, 60.0), (0.0, 0.0, 1.0)) is None


def test_a_ray_hits_a_tilted_plane_where_to_world_would_put_it() -> None:
    """Die Gegenprobe gegen die Umrechnung: beide müssen dasselbe sagen.

    Ein Punkt wird über ``to_world`` in den Raum gelegt, ein Strahl von weit
    außen genau darauf gerichtet — und ``ray_hit`` muss den Zeichenpunkt
    zurückgeben, mit dem angefangen wurde. Ein Vorzeichenfehler in einer der
    beiden Richtungen fällt hier auf, in keiner der beiden allein.
    """
    frame = tilted_frame()
    target = to_world(frame, (11.0, -6.5))
    start = tuple(target[axis] + 250.0 * frame.normal[axis] for axis in range(3))
    direction = tuple(-frame.normal[axis] for axis in range(3))
    assert ray_hit(frame, start, direction) == pytest.approx((11.0, -6.5))


# --- Die Achse, an der der Ziehgriff hängt (§30.1) ---------------------------


def test_a_sideways_look_reads_the_height_off_the_axis() -> None:
    """Der Fall, für den ``axis_hit`` gebaut ist: die Querschau.

    Gezeichnet ist auf XY, gesehen wird von vorn — der Blick läuft waagerecht
    an der Ebene vorbei, zwanzig Millimeter über ihr. Genau diese zwanzig soll
    der Ziehgriff als Höhe zeigen.
    """
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    assert axis_hit(frame, (0.0, 0.0), (0.0, -100.0, 20.0), (0.0, 200.0, 0.0)) == pytest.approx(
        20.0
    )


def test_the_axis_runs_through_the_grip_and_not_through_the_origin() -> None:
    """Gezogen wird dort, wo die Hand ist.

    Die Achse läuft durch den gegriffenen Punkt. Liefe sie durch den Ursprung
    der Skizze, hinge die Zahl am Zeiger an einem Ort, den niemand angefasst
    hat — bei einem Umriss weit neben dem Ursprung wäre sie sichtbar falsch.
    """
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    # Der Strahl trifft die Achse über (30 | 0) auf Höhe 7,5.
    reach = axis_hit(frame, (30.0, 0.0), (30.0, -100.0, 7.5), (0.0, 200.0, 0.0))
    assert reach == pytest.approx(7.5)


def test_a_ray_that_meets_the_axis_reads_the_height_of_the_meeting_point() -> None:
    """Der Testfall, der hier wirklich zählt — und der zuerst fehlte.

    Trifft der Strahl die Aufzugsachse **exakt**, steht der Sollwert ohne
    Rechnung fest: Es ist die Höhe des Durchtritts. Jeder andere Fall braucht
    eine Herleitung, und eine Herleitung kann denselben Fehler haben wie der
    Prüfling.

    **Und genau dieser Fall hat einen Vorzeichenfehler gefangen**
    (Review-Sitzung, 27.08.2026): Die erste Fassung gab hier 90 statt 10
    zurück. Sichtbar war das in keinem der fünf Sollwert-Tests daneben, denn
    alle blickten quer zur Achse — dort ist ``n·d`` null und der Fehlerterm
    ``2 s (n·d)`` verschwindet. Der Strahl hier läuft schräg: von vorn unten
    nach hinten oben, durch ``(0 | 0 | 10)``.
    """
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    assert axis_hit(frame, (0.0, 0.0), (0.0, -100.0, 50.0), (0.0, 100.0, -40.0)) == (
        pytest.approx(10.0)
    )


def test_a_slanted_look_reads_the_closest_approach_and_not_a_shifted_one() -> None:
    """Und ein Strahl, der die Achse **verfehlt**, mit nachrechenbarem Sollwert.

    Von ``(10 | 5 | 0)`` in Richtung ``(-1 | 0 | 1)``: Bei Schrittweite zehn
    steht der Strahl auf ``(0 | 5 | 10)``, also fünf Millimeter neben der Achse
    und auf deren Höhe zehn. Näher kommt er nicht — das ist die Stelle, die der
    Ziehgriff meint, und die Zahl daran ist zehn.

    Zwei Tests und nicht einer: Der exakte Treffer darüber prüft die Formel, der
    Fehlschuss hier prüft, dass sie auch dann noch das Lot fällt.
    """
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    assert axis_hit(frame, (0.0, 0.0), (10.0, 5.0, 0.0), (-1.0, 0.0, 1.0)) == (pytest.approx(10.0))


def test_the_length_of_the_ray_does_not_change_the_height() -> None:
    """Dieselbe Zusage wie bei ``ray_hit``: Die Richtung kommt unnormiert.

    Sie ist der Schritt von der nahen zur fernen Ebene und damit hunderte
    Millimeter lang. Käme eine andere Höhe heraus als bei Einheitslänge, hinge
    der Ziehgriff an der Tiefe des Sichtvolumens.

    **Dieser Test allein sieht ein falsches Vorzeichen nicht.** Er vergleicht
    zwei Läufe gegeneinander, und der Fehlerterm ``2 s (n·d)`` ist von der Länge
    unabhängig — er steckt in beiden gleich. Wer die Formel prüfen will, prüft
    sie gegen einen **Sollwert**; die beiden Tests darüber tun das.
    """
    frame = tilted_frame()
    short = axis_hit(frame, (4.0, -2.0), (60.0, 20.0, 55.0), (-0.6, 0.0, -0.8))
    long = axis_hit(frame, (4.0, -2.0), (60.0, 20.0, 55.0), (-600.0, 0.0, -800.0))
    assert short is not None
    assert long == pytest.approx(short)


def test_a_look_along_the_axis_reads_no_height() -> None:
    """Und die Gegenfrage zu ``ray_hit``: der Blick **auf** die Ebene.

    Von oben senkrecht auf die Zeichnung gesehen liegt die Aufzugsachse als
    Punkt im Bild — keine Mausbewegung könnte dort eine Höhe bedeuten. Genau
    dieser Fall ist der, in dem ``ray_hit`` seine Stelle findet: Die beiden
    Prüfungen sind komplementär, und dieselbe Schwelle entscheidet sie.
    """
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    assert ray_hit(frame, (3.0, -4.0, 60.0), (0.0, 0.0, -1.0)) is not None
    assert axis_hit(frame, (3.0, -4.0), (3.0, -4.0, 60.0), (0.0, 0.0, -1.0)) is None


def test_the_height_is_signed_and_follows_the_extrusion_direction() -> None:
    """Nach oben positiv, nach unten negativ — und „oben" ist die Normale.

    Das ist die Zusage, an der die Übergabe hängt: ``profiles.extrude`` zieht
    entlang ``frame.normal`` auf, also ist der Rückgabewert unmittelbar die
    Höhe der Operation. Ein Vorzeichenfehler hier baute den Körper auf der
    falschen Seite der Zeichnung.
    """
    frame = frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))
    above = axis_hit(frame, (0.0, 0.0), (0.0, -100.0, 12.0), (0.0, 200.0, 0.0))
    below = axis_hit(frame, (0.0, 0.0), (0.0, -100.0, -12.0), (0.0, 200.0, 0.0))
    assert above == pytest.approx(12.0)
    assert below == pytest.approx(-12.0)


def test_a_tilted_plane_measures_its_height_along_its_own_normal() -> None:
    """Auf einer schrägen Fläche ist „hoch" nicht Welt-Z.

    Die Gegenprobe über ``to_world``: Ein Punkt der Ebene, um eine bekannte
    Strecke entlang ihrer Normalen verschoben, und ein Strahl quer darauf. Was
    ``axis_hit`` zurückgibt, muss genau diese Strecke sein — sonst zieht der
    Griff auf einer angeklickten Fläche eine Höhe in eine andere Richtung, als
    die Operation sie später aufzieht.
    """
    frame = tilted_frame()
    base = (8.0, -3.0)
    lifted = tuple(to_world(frame, base)[axis] + 15.0 * frame.normal[axis] for axis in range(3))
    across = frame.x_axis
    start = tuple(lifted[axis] - 200.0 * across[axis] for axis in range(3))
    reach = axis_hit(frame, base, start, across)
    assert reach == pytest.approx(15.0)

    # **Und noch einmal schräg**, damit der Fall nicht wieder in der Lücke
    # liegt: ``across`` steht quer zur Normalen, dort ist ``n·d`` null. Ein
    # Strahl, der die Achse trotzdem exakt trifft, muss dieselbe Höhe geben.
    slanted = tuple(across[axis] + 0.5 * frame.normal[axis] for axis in range(3))
    start = tuple(lifted[axis] - 200.0 * slanted[axis] for axis in range(3))
    assert axis_hit(frame, base, start, slanted) == pytest.approx(15.0)


# --- Die Skizze als Kurve im Raum (§30.1, P2) --------------------------------


def solved_with(*elements: SketchElement) -> SolvedSketch:
    """Ein gelöstes Ergebnis ohne den Solver — hier zählt die Abtastung."""
    return SolvedSketch(elements=elements, free_dof=0, max_residual=0.0)


def flat_frame() -> PlaneFrame:
    """Die XY-Ebene auf Höhe null, als Rahmen."""
    return frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 0.0))


def test_a_line_keeps_its_two_ends() -> None:
    """Eine Strecke wird nicht abgetastet — sie ist schon eine."""
    curves = curves_of(solved_with(SketchElement("line", ((0.0, 0.0), (10.0, 4.0)))), flat_frame())

    assert len(curves) == 1
    assert curves[0].points[0] == pytest.approx((0.0, 0.0, 0.0))
    assert curves[0].points[1] == pytest.approx((10.0, 4.0, 0.0))


def test_a_circle_closes_on_its_own_first_point() -> None:
    """Sonst bliebe eine Lücke, und „geschlossen" wäre nicht ablesbar.

    Der letzte Punkt ist derselbe wie der erste, damit die Ansicht keinen
    zusätzlichen Merker braucht — den man vergessen könnte zu setzen.
    """
    curves = curves_of(
        solved_with(SketchElement("circle", ((5.0, 5.0), (15.0, 5.0)))), flat_frame()
    )
    points = curves[0].points

    assert points[0] == pytest.approx(points[-1]), "der Kreis schließt sich"
    for point in points:
        assert math.hypot(point[0] - 5.0, point[1] - 5.0) == pytest.approx(10.0)
        assert point[2] == pytest.approx(0.0)


def test_an_arc_runs_counterclockwise_from_start_to_end() -> None:
    """Die Laufrichtung steht im Vertrag von ``SketchElement``, und sie zählt.

    Ein Viertelkreis von (10, 0) nach (0, 10) um den Ursprung geht **gegen**
    den Uhrzeigersinn über 45°, nicht im Uhrzeigersinn über 315°. Wer das
    Vorzeichen dreht, bekommt denselben Anfang, dasselbe Ende und dazwischen
    drei Viertel Kreis — eine Kontur, die den langen Weg nimmt.
    """
    curves = curves_of(
        solved_with(SketchElement("arc", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)))), flat_frame()
    )
    points = curves[0].points

    assert tuple(points[0]) == pytest.approx((10.0, 0.0, 0.0))
    assert tuple(points[-1]) == pytest.approx((0.0, 10.0, 0.0))
    # **Jeder** Punkt liegt im ersten Quadranten, nicht nur der in der Mitte
    # der Liste: Bei gerader Punktzahl ist die Listenmitte nicht die
    # Bogenmitte, und ein Test, der sie dafür nimmt, prüft die Punktzahl mit.
    # Der lange Weg über 315 Grad verließe den Quadranten sofort.
    for point in points:
        assert point[0] >= -1e-9, f"{point} liegt links der Achse"
        assert point[1] >= -1e-9, f"{point} liegt unter der Achse"


def test_a_full_turn_is_not_a_line_of_length_zero() -> None:
    """Ein Bogen, dessen Ende auf seinem Anfang liegt, ist ein voller Umlauf.

    Die Winkeldifferenz ist dort null, und ohne diesen Fall käme eine Folge
    aus lauter identischen Punkten heraus — im Bild nichts.
    """
    curves = curves_of(
        solved_with(SketchElement("arc", ((0.0, 0.0), (10.0, 0.0), (10.0, 0.0)))), flat_frame()
    )
    points = curves[0].points

    assert len(points) > _LEAST_STEPS, "ein voller Umlauf braucht seine Punkte"
    assert max(point[1] for point in points) == pytest.approx(10.0, abs=0.1), "er geht ganz herum"


def test_a_bigger_circle_gets_more_points() -> None:
    """Die Feinheit folgt dem Radius, nicht einer festen Zahl.

    Eine feste Zahl ist bei einer M3-Bohrung Verschwendung und bei einem
    Ring von zweihundert Millimetern ein Vieleck.
    """
    small = curves_of(solved_with(SketchElement("circle", ((0.0, 0.0), (1.0, 0.0)))), flat_frame())
    large = curves_of(
        solved_with(SketchElement("circle", ((0.0, 0.0), (200.0, 0.0)))), flat_frame()
    )

    assert len(large[0].points) > len(small[0].points)


def test_every_point_lies_in_the_tilted_plane() -> None:
    """Auf einer geneigten Fläche darf nichts danebenliegen.

    Gemessen am Abstand entlang der Normalen — das ist die Zahl, die null
    sein muss, und die einzige, die ein Fehler in ``to_world`` verrät.
    """
    frame = tilted_frame()
    curves = curves_of(
        solved_with(
            SketchElement("circle", ((3.0, -2.0), (9.0, -2.0))),
            SketchElement("line", ((0.0, 0.0), (5.0, 5.0))),
        ),
        frame,
    )

    for curve in curves:
        for point in curve.points:
            gap = tuple(point[axis] - frame.origin[axis] for axis in range(3))
            along = sum(gap[axis] * frame.normal[axis] for axis in range(3))
            assert along == pytest.approx(0.0, abs=1e-9)


def test_construction_geometry_travels_with_its_mark() -> None:
    """Sie steht im Bild, nur anders gezeichnet — verlöre sie die Marke,
    sähe eine Mittellinie aus wie eine Kante."""
    curves = curves_of(
        solved_with(
            SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("line", ((0.0, 5.0), (10.0, 5.0)), construction=True),
        ),
        flat_frame(),
    )

    assert [curve.construction for curve in curves] == [False, True]


def test_a_point_stays_a_single_place() -> None:
    """Ein Punkt hat keine Länge, und die Folge der Länge eins sagt das."""
    curves = curves_of(solved_with(SketchElement("point", ((2.0, 3.0),))), flat_frame())

    assert len(curves[0].points) == 1, "ein Punkt ist eine Folge der Laenge eins"
    assert curves[0].points[0] == pytest.approx((2.0, 3.0, 0.0))


# --- Rahmen für jede Ebene (§30.1, P4) ---------------------------------------


def test_every_plane_has_a_frame_and_an_unknown_one_has_none() -> None:
    """`frame_for` beantwortet nur Flächen; die Anzeige braucht alle vier."""
    for plane in ("plane:xy", "plane:xz", "plane:yz"):
        assert frame_for_plane(plane) is not None, plane
    assert frame_for_plane("plane:zz") is None, "eine Angabe ohne Ebene ergibt keinen Rahmen"
    assert frame_for_plane("feature:face_99") is None, "eine Fläche, die es nicht gibt, auch nicht"


def test_the_base_frames_agree_with_the_kernel_to_the_last_digit() -> None:
    """Zwei Tabellen für dieselben drei Ebenen, und sie müssen gleich sein.

    ``BASE_FRAMES`` ist von ``brep.profiles.PLANES`` **abgeschrieben** und
    nicht gerechnet — wer sie aus der Normalen ableitet, bekommt bei
    ``plane:xz`` eine gespiegelte erste Achse (``frame_of((0, 1, 0))`` liefert
    ``(-1, 0, 0)``). Dieser Test ist der Grund, warum das Abschreiben
    vertretbar ist: Er hält beide zusammen, und ohne ihn driften sie beim
    nächsten Nachbessern auseinander — die Anzeige zeigte dann etwas anderes,
    als der Kern baut.
    """
    exact_kernel()
    from app.core.brep.profiles import PLANES

    for plane, (lift, normal) in PLANES.items():
        frame = frame_for_plane(plane)
        assert frame is not None, plane
        assert frame.normal == pytest.approx(normal), f"{plane}: Normale weicht ab"
        for point in ((0.0, 0.0), (3.0, 0.0), (0.0, 5.0), (-2.5, 7.25)):
            wanted = lift(point)
            assert to_world(frame, point) == pytest.approx((wanted.X(), wanted.Y(), wanted.Z())), (
                f"{plane}: {point} landet woanders als im Kern"
            )


def test_the_image_normal_turns_around_where_the_frame_is_left_handed() -> None:
    """Sonst sieht die Kamera von hinten auf die Zeichnung.

    ``frame.normal`` ist die Richtung, in die extrudiert wird. Bei
    ``plane:xz`` zeigt sie nach hinten — man zeichnet von vorn und zieht nach
    hinten auf. Wer die Kamera dorthin stellt, zeigt die Skizze
    spiegelverkehrt.
    """
    flat = frame_for_plane("plane:xy")
    front = frame_for_plane("plane:xz")
    side = frame_for_plane("plane:yz")
    assert flat is not None and front is not None and side is not None

    assert image_normal(flat) == pytest.approx(flat.normal), "XY ist rechtshändig"
    assert image_normal(side) == pytest.approx(side.normal), "YZ auch"
    assert image_normal(front) == pytest.approx((0.0, -1.0, 0.0)), "XZ sieht man von vorn"
    assert front.normal == pytest.approx((0.0, 1.0, 0.0)), "extrudiert wird nach hinten"


def test_a_face_frame_needs_no_turn() -> None:
    """Bei einer Fläche zeigt die Normale nach außen, und dorthin sieht man.

    Die Gegenprobe zum Test darüber: Wäre ``image_normal`` einfach das
    Gegenteil der Normalen, wäre er auch grün — hier fiele es auf.
    """
    frame = frame_of((1.0, 0.0, 1.0), (5.0, -2.0, 3.0))
    assert image_normal(frame) == pytest.approx(frame.normal)


# --- Bogen aus drei Punkten (§30.1, Klickreihenfolge seit 24.08.2026) ------------


def test_an_arc_through_three_points_keeps_the_stored_order() -> None:
    """Geklickt wird Anfang, Ende, Wölbung — gespeichert bleibt Mitte, Anfang, Ende.

    Die Reihenfolge im **Datenmodell** ist unangetastet: Sie steht so in jeder
    Projektdatei, im Langloch (``shapes.slot``) und in dem, was der Löser
    liest. Geändert hat sich, wie man sie erzeugt — vorher war der erste Klick
    die Mitte, ein Punkt, der auf keiner Kante liegt und den beim Zeichnen
    eines Umrisses niemand im Kopf hat. Fusion und Onshape fragen Anfang, Ende
    und dann die Wölbung.
    """
    from app.core.sketch.edit import arc_through

    stored = arc_through((40.0, 20.0), (0.0, 20.0), (20.0, 40.0))
    assert stored is not None
    centre, start, end = stored
    assert centre == pytest.approx((20.0, 20.0))
    for point in (start, end):
        assert math.dist(centre, point) == pytest.approx(20.0), "alle drei liegen auf dem Kreis"


def test_the_arc_takes_the_half_the_bulge_points_at() -> None:
    """Durch zwei Punkte gehen zwei Bögen — die Wölbung entscheidet welcher.

    Der Kern läuft immer gegen den Uhrzeigersinn von Anfang zu Ende
    (``sweep = (finish - begin) % 2π``). Liegt die geklickte Wölbung auf der
    anderen Hälfte, sind es die Enden andersherum — sonst zeichnet die
    Anwendung den Bogen, den niemand gemeint hat.
    """
    from app.core.sketch.edit import arc_through

    oben = arc_through((40.0, 20.0), (0.0, 20.0), (20.0, 40.0))
    unten = arc_through((40.0, 20.0), (0.0, 20.0), (20.0, 0.0))
    assert oben is not None and unten is not None
    assert oben[0] == pytest.approx(unten[0]), "derselbe Kreis"
    assert (oben[1], oben[2]) == ((40.0, 20.0), (0.0, 20.0))
    assert (unten[1], unten[2]) == ((0.0, 20.0), (40.0, 20.0)), "die Enden tauschen"

    # **Und die Probe aufs Exempel am abgetasteten Bogen.** Nicht an
    # ``solve_sketch``: das gibt die drei Stützpunkte zurück, und die liegen
    # bei beiden Bögen gleich — der Test wäre grün, ohne etwas zu prüfen.
    # ``curves_of`` tastet die Kurve ab, und dort trennen sich die Hälften.
    from app.core.sketch.planes import frame_for_plane
    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch as PlainSketch
    from app.core.types import SketchElement as Element

    frame = frame_for_plane("plane:xy")
    assert frame is not None
    for stored, bulge in ((oben, (20.0, 40.0)), (unten, (20.0, 0.0))):
        solved = solve_sketch(PlainSketch(plane="plane:xy", elements=(Element("arc", stored),)))
        kurven = curves_of(solved, frame)
        punkte = [(p[0], p[1]) for kurve in kurven for p in kurve.points]
        assert len(punkte) > 3, "der Bogen muss abgetastet sein, nicht nur seine Stützpunkte"
        nächster = min(math.dist(bulge, p) for p in punkte)
        assert nächster < 1.0, f"der Bogen läuft durch {bulge}, nächster Punkt {nächster:.2f} mm"


def test_three_points_on_a_line_are_no_arc() -> None:
    """Kollinear heißt: kein Kreis. Und das sagt die Funktion, statt zu raten.

    Der Vergleich läuft gegen die Kantenlängen und nicht gegen eine feste
    Zahl — drei Punkte im Abstand von Metern sind bei derselben absoluten
    Abweichung noch krumm, drei im Zehntelmillimeter nicht mehr.
    """
    from app.core.sketch.edit import arc_through

    assert arc_through((0.0, 0.0), (10.0, 0.0), (5.0, 0.0)) is None
    assert arc_through((0.0, 0.0), (0.0, 0.0), (5.0, 5.0)) is None, "zwei gleiche Punkte"
    assert arc_through((0.0, 0.0), (1000.0, 0.0), (500.0, 1e-9)) is None, "über einem Meter krumm"
    assert arc_through((0.0, 0.0), (1.0, 0.0), (0.5, 0.05)) is not None, "leicht gewölbt zählt"


def test_a_self_crossing_chain_is_refused_with_a_place_to_look() -> None:
    """Eine Kette, die sich selbst kreuzt, umschließt keine eindeutige Fläche.

    Vorher lief sie bis in den Kern: extrudiert kam ein Körper heraus, dessen
    Netz nicht wasserdicht war (``is_closed`` sagte sogar True) — er ging ohne
    Befund in STL-Export und Schichtanalyse. Der Fehler gehört an die
    Zeichnung, nicht an den Export.
    """
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    crossing = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (10.0, 10.0))),
            SketchElement("line", ((10.0, 10.0), (10.0, 0.0))),
            SketchElement("line", ((10.0, 0.0), (0.0, 20.0))),
            SketchElement("line", ((0.0, 20.0), (0.0, 0.0))),
        ),
    )
    with pytest.raises(GeometryError) as caught:
        regions_of(solve_sketch(crossing))
    assert caught.value.suggestions
    assert "kreuzt" in str(caught.value.detail)


def test_a_chain_crossing_its_arc_is_refused() -> None:
    """Ein Bogen ist an derselben Eindeutigkeitsgrenze wie eine Linie."""
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    crossing = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("arc", ((0.0, 0.0), (1.0, 0.0), (-1.0, 0.0))),
            SketchElement("line", ((-1.0, 0.0), (0.0, 2.0))),
            SketchElement("line", ((0.0, 2.0), (1.0, 0.0))),
        ),
    )

    with pytest.raises(GeometryError, match="kreuzt"):
        regions_of(solve_sketch(crossing))


def test_a_chain_crossing_a_two_point_spline_is_refused() -> None:
    """Auch ein exakt gerader Spline darf nicht aus der Prüfung fallen."""
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    crossing = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("spline", ((0.0, 0.0), (10.0, 10.0))),
            SketchElement("line", ((10.0, 10.0), (10.0, 0.0))),
            SketchElement("line", ((10.0, 0.0), (0.0, 20.0))),
            SketchElement("line", ((0.0, 20.0), (0.0, 0.0))),
        ),
    )

    with pytest.raises(GeometryError, match="kreuzt"):
        regions_of(solve_sketch(crossing))


def _spike() -> Sketch:
    """Ein Umriss mit einer Spitze ohne Breite: Die untere Linie läuft bis 10
    und kehrt auf sich selbst bis 5 zurück, dann geht es hinauf und zurück."""
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("line", ((10.0, 0.0), (5.0, 0.0))),
            SketchElement("line", ((5.0, 0.0), (5.0, 5.0))),
            SketchElement("line", ((5.0, 5.0), (0.0, 0.0))),
        ),
    )


def test_a_chain_that_runs_back_on_itself_is_refused() -> None:
    """Zwei Stücke, die aufeinander liegen, sind eine Spitze ohne Breite.

    OpenCASCADE meldet so etwas nicht als Schnittpunkt, sondern als
    gemeinsames Stück — und die Prüfung zählte nur Punkte. Der Umriss ging
    durch, der Kern baute daraus einen Körper mit richtigem Volumen, den
    seine eigene Prüfung (``BRepCheck_Analyzer``) für ungültig hielt
    (Durchsicht 22.09.2026).
    """
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    with pytest.raises(GeometryError, match="kreuzt"):
        regions_of(solve_sketch(_spike()))


def test_the_fallback_without_the_exact_kernel_sees_the_spike_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ohne B-Rep-Kern prüft die Punktfolge — und auch dort ist ein Stück, das
    auf einem anderen liegt, kein Berühren (``strictly_crossing`` sah es
    nicht, weil kollinear für das Kreuzprodukt „berührt" heißt)."""
    from app.core.brep import kernel
    from app.core.errors import GeometryError
    from app.core.sketch.profile import _overlapping, regions_of

    monkeypatch.setattr(kernel, "available", lambda: False)
    with pytest.raises(GeometryError, match="kreuzt"):
        regions_of(solve_sketch(_spike()))

    assert not _overlapping((0.0, 0.0), (5.0, 0.0), (5.0, 0.0), (9.0, 0.0)), (
        "ein gemeinsamer Endpunkt allein ist kein gemeinsames Stück"
    )
    assert not _overlapping((0.0, 0.0), (5.0, 0.0), (0.0, 1.0), (5.0, 1.0)), "parallel daneben"


def test_a_branching_outline_says_more_than_two_edges_meet() -> None:
    """Eine Acht aus sechs Linien trifft sich an einem Punkt mit vier Kanten —
    die Meldung sprach von drei."""
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    eight = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("line", ((10.0, 0.0), (5.0, 5.0))),
            SketchElement("line", ((5.0, 5.0), (10.0, 10.0))),
            SketchElement("line", ((10.0, 10.0), (0.0, 10.0))),
            SketchElement("line", ((0.0, 10.0), (5.0, 5.0))),
            SketchElement("line", ((5.0, 5.0), (0.0, 0.0))),
        ),
    )
    with pytest.raises(GeometryError, match="mehr als zwei Kanten"):
        regions_of(solve_sketch(eight))


def test_a_self_crossing_exact_spline_is_refused() -> None:
    """Geprüft wird dieselbe B-Spline-Kurve, die der B-Rep-Kern extrudiert."""
    from app.core.errors import GeometryError
    from app.core.sketch.profile import regions_of

    # Echte Kreuzung der gezeichneten Catmull-Rom-Kurve; das alte Beispiel
    # kreuzte nur die abweichende PointsToBSpline-Interpolation.
    points = ((-10.0, -5.0), (10.0, 5.0), (-10.0, 5.0), (10.0, -5.0))
    crossing = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("spline", points),
            SketchElement("line", (points[-1], points[0])),
        ),
    )

    with pytest.raises(GeometryError, match="kreuzt"):
        regions_of(solve_sketch(crossing))


def test_a_narrow_but_valid_arc_outline_is_not_rejected_by_its_chords() -> None:
    """Eine Sehne darf keine Kreuzung erfinden, die der exakte Bogen nicht besitzt."""
    from app.core.sketch.profile import regions_of

    radius = 100.0
    inner_radius = radius - 0.01
    count = 8
    angles = [math.pi, *(math.pi * (1.0 - (index + 0.5) / count) for index in range(count)), 0.0]
    inner = tuple(
        (inner_radius * math.cos(angle), inner_radius * math.sin(angle)) for angle in angles
    )
    elements = [
        SketchElement("arc", ((0.0, 0.0), (radius, 0.0), (-radius, 0.0))),
        SketchElement("line", ((-radius, 0.0), inner[0])),
        *(SketchElement("line", (start, end)) for start, end in pairwise(inner)),
        SketchElement("line", (inner[-1], (radius, 0.0))),
    ]

    assert len(regions_of(solve_sketch(Sketch("plane:xy", tuple(elements))))) == 1


def test_a_concave_outline_is_not_a_crossing() -> None:
    """Ein Pfeilvierling ist konkav, aber ehrlich — er kreuzt sich nicht.

    Die Kreuzungsprüfung darf nur echte Schnitte melden: nicht benachbarte
    Kanten, die einander nahekommen, sind kein Fehler.
    """
    from app.core.sketch.profile import regions_of

    dart = Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (10.0, 0.0))),
            SketchElement("line", ((10.0, 0.0), (5.0, 3.0))),
            SketchElement("line", ((5.0, 3.0), (0.0, 10.0))),
            SketchElement("line", ((0.0, 10.0), (0.0, 0.0))),
        ),
    )
    assert len(regions_of(solve_sketch(dart))) == 1


def test_an_island_inside_a_hole_is_material_again() -> None:
    """Kasten im Kasten im Kasten: der innerste steht wieder als Material.

    Vorher fiel die dritte Ebene still weg — nicht „nicht gebohrt", sondern
    weggeworfen: Die Zeichnung zeigte die Insel, der Körper hatte sie nicht,
    und keine Zeile sagte es. Am Volumen gemessen, wie beim Loch darüber.
    """
    exact_kernel()
    from app.core.brep import profiles as brep_profiles
    from app.core.brep.edit import boolean
    from app.core.sketch.profile import regions_of

    sketch = Sketch(plane="plane:xy", elements=_square(40.0) + _square(20.0) + _square(10.0))
    regions = regions_of(solve_sketch(sketch))
    bodies = [brep_profiles.extrude(region, 5.0) for region in regions]
    body = bodies[0] if len(bodies) == 1 else boolean("union", bodies)

    expected = ((40.0 * 40.0 - 20.0 * 20.0) + 10.0 * 10.0) * 5.0
    assert body.volume == pytest.approx(expected, rel=1e-6)


def test_a_hole_in_an_island_stays_a_hole() -> None:
    """Und die vierte Ebene bohrt wieder: Loch, Insel, Loch — abwechselnd.

    Die Zuordnung ist rekursiv, nicht zweistufig mit Rest: gerade Tiefe ist
    Material, ungerade Tiefe ist Loch, auf jeder Ebene.
    """
    exact_kernel()
    from app.core.brep import profiles as brep_profiles
    from app.core.brep.edit import boolean
    from app.core.sketch.profile import regions_of

    sketch = Sketch(
        plane="plane:xy",
        elements=_square(40.0) + _square(30.0) + _square(20.0) + _square(10.0),
    )
    regions = regions_of(solve_sketch(sketch))
    bodies = [brep_profiles.extrude(region, 5.0) for region in regions]
    body = bodies[0] if len(bodies) == 1 else boolean("union", bodies)

    expected = ((40.0 * 40.0 - 30.0 * 30.0) + (20.0 * 20.0 - 10.0 * 10.0)) * 5.0
    assert body.volume == pytest.approx(expected, rel=1e-6)


def test_a_diameter_measures_the_whole_circle_and_a_radius_half_of_it() -> None:
    """Der Kunde denkt in Durchmesser, der Kreis maß Radius (Z7a).

    Ein Kreis wird über Mittelpunkt und Randpunkt bemaßt. Bis Format 18 war das
    eine ``distance`` und hieß in der Oberfläche „Abstand" — wer für eine
    M3-Bohrung 3,2 tippte, bekam ein Loch mit **6,4 mm**, und das Wort „Radius"
    kam in der ganzen Bedienung nicht vor.

    Beide neuen Arten rechnen dieselbe Gleichung; sie unterscheiden sich in
    einem Faktor und darin, was sie **heißen**. Geprüft wird deshalb nicht die
    Gleichung, sondern das Ergebnis — und **jede Zahl trägt hier ihr Maß**:
    Derselbe Wert 3,2 ergibt als Radius-Bedingung einen Kreis mit **Radius**
    3,2, als Durchmesser-Bedingung einen mit **Radius 1,6**, und der misst dann
    3,2 im Durchmesser, wie der Kunde es getippt hat.

    Hier stand zuerst „Ø 3,2 ist ein Kreis von 1,6", und das ist genau der
    Fehler, gegen den dieses Paket gebaut ist: eine Zahl ohne ihr Maß. Ein
    Kreis mit Ø 3,2 **ist** ein Kreis von 3,2 — 1,6 ist sein Radius. Robert hat
    den Satz beim Lesen gefangen (31.08.2026).
    """
    import math

    from app.core.sketch.solver import solve_sketch
    from app.core.types import Sketch, SketchConstraint, SketchElement

    def radius_of(kind: str, value: str) -> float:
        """Der Abstand vom Mittelpunkt zum Rand — also der **Radius**.

        Der Name nennt das Maß, und das ist keine Förmlichkeit: ``circle_of``
        hieß er zuerst, und aus „ein Kreis von 1,6" wurde dadurch ein Satz, der
        zwei Maße verwechselt.
        """
        sketch = Sketch(
            plane="xy",
            elements=(SketchElement("circle", ((0.0, 0.0), (1.0, 0.0))),),
            constraints=(
                SketchConstraint("fixed", (0,)),
                SketchConstraint(kind, (0, 1), value=value),  # type: ignore[arg-type]
            ),
        )
        solved = solve_sketch(sketch, {})
        centre, rim = solved.elements[0].points
        return math.hypot(rim[0] - centre[0], rim[1] - centre[1])

    assert abs(radius_of("radius", "3.2") - 3.2) < 1e-6, "R 3,2 muss einen Radius von 3,2 ergeben"
    assert abs(radius_of("diameter", "3.2") - 1.6) < 1e-6, (
        "Ø 3,2 muss einen Radius von 1,6 ergeben — der Kreis misst dann 3,2 im Durchmesser"
    )
    # Und die alte Art bleibt, was sie war — sonst änderte die Migration doch
    # noch Geometrie, nur an anderer Stelle.
    assert abs(radius_of("distance", "3.2") - 3.2) < 1e-6, (
        "der alte Abstand bleibt einer: 3,2 vom Mittelpunkt zum Rand"
    )


def test_a_diameter_survives_the_way_into_the_project_file() -> None:
    """Die Zusage lautete „bis in die Projektdatei" — hier wird sie gefahren.

    Der Test darüber prüft die **Rechnung**: Ø 3,2 ergibt Radius 1,6. Das
    beantwortet aber nur die halbe Frage. Eine Bemaßung, die im Löser stimmt
    und beim Speichern zu einer ``distance`` zurückfällt, wäre beim nächsten
    Öffnen wieder das Loch mit 6,4 mm — und **kein bestehender Test würde es
    sehen**, weil keiner die Art durch ``sketch_to_text`` fährt.

    Gemessen wird deshalb der ganze Weg: lösen, schreiben, lesen, wieder
    lösen. Die zweite Zahl muss die erste sein, und die Art muss sie
    überleben — eine Skizze, die richtig rechnet und falsch gespeichert wird,
    ist schlimmer als eine, die gleich falsch rechnet.
    """
    import math

    from app.core.sketch.serialize import sketch_from_text, sketch_to_text

    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("circle", ((0.0, 0.0), (5.0, 0.0))),),
        constraints=(
            SketchConstraint("fixed", (0,)),
            SketchConstraint("diameter", (0, 1), value="3.2"),
        ),
    )

    def diameter_of(what: Sketch) -> float:
        centre, rim = solve_sketch(what, {}).elements[0].points
        return 2 * math.hypot(rim[0] - centre[0], rim[1] - centre[1])

    before = diameter_of(sketch)
    assert abs(before - 3.2) < 1e-6, "Ø 3,2 muss einen Kreis von 3,2 mm ergeben"

    text = sketch_to_text(sketch)
    assert '"diameter"' in text, "die Art steht wörtlich in der Datei, nicht als Zahl"

    reloaded = sketch_from_text(text)
    kinds = [c.kind for c in reloaded.constraints]
    assert "diameter" in kinds, f"die Art ging beim Laden verloren: {kinds}"

    assert abs(diameter_of(reloaded) - before) < 1e-9, (
        "derselbe Kreis vor und nach dem Speichern — sonst wandert die Bemaßung"
    )

    # Und der Wert bleibt der Ausdruck, den der Kunde getippt hat. Wäre er
    # beim Schreiben ausgerechnet worden, hinge er nicht mehr am Parameter.
    values = [c.value for c in reloaded.constraints if c.kind == "diameter"]
    assert values == ["3.2"], f"der Wert reist als Ausdruck, nicht als Zahl: {values}"


def test_both_lists_of_constraint_kinds_stay_the_same() -> None:
    """Zwei Listen derselben Arten, und keine kennt die andere.

    Der Löser braucht zu jeder Art die Zahl ihrer Zielpunkte, der Serializer
    prüft eine **fremde Datei**, bevor daraus ein Modell wird. Beide führen
    deshalb eine eigene Aufzählung — und laufen auseinander, sobald jemand nur
    eine anfasst. Beim Einbau von ``radius`` und ``diameter`` ist genau das
    passiert: Der Löser konnte rechnen, und das Einlesen wies die Datei ab.
    """
    from app.core.sketch.serialize import _CONSTRAINT_KINDS
    from app.core.sketch.solver import _CONSTRAINT_TARGETS

    assert set(_CONSTRAINT_TARGETS) == set(_CONSTRAINT_KINDS), (
        "nur im Löser: "
        f"{sorted(set(_CONSTRAINT_TARGETS) - set(_CONSTRAINT_KINDS))}, "
        "nur beim Einlesen: "
        f"{sorted(set(_CONSTRAINT_KINDS) - set(_CONSTRAINT_TARGETS))}"
    )


def test_a_sketch_beyond_the_solver_budget_is_named_not_allocated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Gesamtreview 05.09.2026, G-09: Eine Skizze mit 10 000 Punkten und
    10 000 Fixierungen ist 958 KB Projektdatei — und forderte im Löser eine
    dichte Matrix von 3,2 GB an, bevor eine Zeile gerechnet war. Der Löser
    rechnet seither dünn besetzt; was danach dicht bleiben muss, hat ein
    Budget, und eine Skizze darüber wird benannt statt gerechnet."""
    from app.core.sketch import solver

    monkeypatch.setattr(solver, "MAX_JACOBIAN_BYTES", 64)

    with pytest.raises(ValidationError) as refused:
        solve_sketch(rectangle(), {"width": 40.0, "height": 20.0})

    assert refused.value.constraint == "too_large"
    assert refused.value.values["points"] == sum(len(e.points) for e in rectangle().elements)
    assert refused.value.suggestions, "Regel 17"


def test_the_sparse_jacobian_matches_the_dense_one() -> None:
    """Die Ableitungen schreiben unverändert ``out[zeile, punkt, koordinate]``;
    der dünn besetzte Sammler muss dieselbe Matrix ergeben wie der dichte
    Block, den es bis zum 05.09.2026 gab."""
    from app.core.sketch import solver

    equations, anchors = solver._build_equations(rectangle(), {"width": 40.0, "height": 20.0})
    solved = solve_sketch(rectangle(), {"width": 40.0, "height": 20.0})
    x = np.asarray(
        [point for element in solved.elements for point in element.points], dtype=float
    ).reshape(-1)
    total_rows = sum(equation.rows for equation in equations)
    dense = np.zeros((total_rows, anchors.size // 2, 2))
    begin = 0
    for equation in equations:
        equation.grad(x.reshape(-1, 2), dense[begin : begin + equation.rows])
        begin += equation.rows

    _solution, _residuals, jacobian = solver._solve(equations, x.reshape(-1, 2))

    assert jacobian.shape == (total_rows, anchors.size)
    assert np.allclose(jacobian.toarray(), dense.reshape(total_rows, anchors.size))


# --- Der Zugmodus des Lösers ----------------------------------------------------------


def _drawn_box() -> Sketch:
    """Ein Rechteck aus vier Linien mit Deckung, waagerecht und senkrecht —
    ohne Maße und ohne Festpunkt, so wie der Editor es zeichnet."""
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.0, 0.0), (40.0, 0.0))),
            SketchElement("line", ((40.0, 0.0), (40.0, 20.0))),
            SketchElement("line", ((40.0, 20.0), (0.0, 20.0))),
            SketchElement("line", ((0.0, 20.0), (0.0, 0.0))),
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


def _flat(solved: SolvedSketch) -> list[tuple[float, float]]:
    return [point for element in solved.elements for point in element.points]


def test_a_dragged_point_lands_on_the_pointer_and_the_neighbours_follow() -> None:
    """Der Fund vom 13.09.2026: Die Ecke (40 | 20) nach (60 | 30) gezogen kam
    bei (45 | 22,5) an — der Löser fand die *nächste* Lösung und glich die
    Deckung hälftig aus. Mit ``dragged`` steht die Ecke am Zeiger, und das
    Rechteck wird 60 mal 30."""
    sketch = _drawn_box()
    before = list(edit.flat_points(sketch))

    solved = solve_sketch(sketch, dragged={3: (60.0, 30.0)}, start=before)

    points = _flat(solved)
    assert points[3] == pytest.approx((60.0, 30.0)), "die Ecke steht exakt am Zeiger"
    assert points[4] == pytest.approx((60.0, 30.0)), "ihr Deckungspartner auch"
    assert points[1] == pytest.approx((60.0, 0.0)), "die rechte Seite ist mitgegangen"
    assert points[5] == pytest.approx((0.0, 30.0)), "die obere auch"
    assert points[0] == pytest.approx((0.0, 0.0)), "die gegenüberliegende Ecke blieb"
    assert solved.free_dof == 4


def test_a_dragged_line_stretches_the_box_instead_of_moving_it() -> None:
    """Beide Enden der unteren Linie um zehn nach unten: Die Senkrechten
    werden länger, die obere Linie bleibt, wo sie war."""
    sketch = _drawn_box()
    before = list(edit.flat_points(sketch))

    solved = solve_sketch(sketch, dragged={0: (0.0, -10.0), 1: (40.0, -10.0)}, start=before)

    points = _flat(solved)
    assert points[0] == pytest.approx((0.0, -10.0))
    assert points[1] == pytest.approx((40.0, -10.0))
    assert points[3] == pytest.approx((40.0, 20.0)), "die obere Kante steht"
    assert points[5] == pytest.approx((0.0, 20.0))


def test_a_measured_box_moves_as_a_whole_and_a_fixed_one_not_at_all() -> None:
    """Mit beiden Maßen, aber ohne Festpunkt, ist ein Zug an der Ecke eine
    Verschiebung des Ganzen. Mit Festpunkt geht nichts — und die Nachbarn
    bleiben trotzdem, wo sie waren: Der Zug reißt nichts halb mit."""
    from app.core.sketch import shapes

    measured = shapes.rectangle(40.0, 20.0)
    free = replace(
        measured, constraints=tuple(c for c in measured.constraints if c.kind != "fixed")
    )
    before = list(edit.flat_points(free))
    moved = _flat(solve_sketch(free, dragged={3: (30.0, 20.0)}, start=before))
    for (bx, by), (ax, ay) in zip(before, moved, strict=True):
        assert (ax, ay) == pytest.approx((bx + 10.0, by + 10.0)), "verschoben, nicht verzogen"

    nailed = _flat(solve_sketch(measured, dragged={3: (30.0, 20.0)}, start=before))
    for (bx, by), (ax, ay) in zip(before, nailed, strict=True):
        assert (ax, ay) == pytest.approx((bx, by), abs=1e-6), "der Festpunkt hält alles"


@pytest.mark.parametrize("steps", [1, 10])
def test_a_drag_the_drawing_holds_back_moves_nothing(steps: int) -> None:
    """Hält die Zeichnung den gezogenen Punkt ganz fest, bleibt alles stehen —
    auch was biegsam ist (RM-541).

    Das Vieleck der Grundformen hält gleich lange Seiten, die untere Kante
    waagerecht und eine Ecke fest; biegen lässt es sich trotzdem. An der Ecke
    neben der festen gezogen, kommt diese zurück. Die zweite Stufe begann
    aber, wo die erste auf der Suche nach dem unerreichbaren Zeiger aufgehört
    hatte, und was die erste dabei verbog, blieb verbogen: über ``lsmr`` bis
    0,26 mm an einer Ecke, über die dichte Rechnung bis 10,7 mm.
    """
    from app.core.sketch import shapes

    sketch = shapes.polygon(40.0, 6)
    before = _flat(solve_sketch(sketch))
    corner = before[1]
    points = before
    for step in range(1, steps + 1):
        target = (corner[0] + 5.0 * step / steps, corner[1] + 5.0 * step / steps)
        points = _flat(solve_sketch(_placed(sketch, points), dragged={1: target}, start=points))
    for was, now in zip(before, points, strict=True):
        assert now == pytest.approx(was, abs=1e-9), "nichts verbogen"


def test_a_point_held_by_a_constraint_slides_as_far_as_it_may() -> None:
    """Die zweite Stufe des Zugs: Ein Punkt auf einer Waagerechten folgt dem
    Zeiger seitlich und bleibt in der Höhe; ein Punkt an einem festen Maß
    läuft auf seinem Kreis. Fusion tut dasselbe."""
    horizontal = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (30.0, 0.0))),),
        constraints=(SketchConstraint("fixed", (0,)), SketchConstraint("horizontal", (0, 1))),
    )
    slid = _flat(
        solve_sketch(horizontal, dragged={1: (50.0, 12.0)}, start=[(0.0, 0.0), (30.0, 0.0)])
    )
    assert slid[1] == pytest.approx((50.0, 0.0))

    measured = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (30.0, 0.0))),),
        constraints=(SketchConstraint("fixed", (0,)), SketchConstraint("distance", (0, 1), "30")),
    )
    turned = _flat(
        solve_sketch(measured, dragged={1: (30.0, 30.0)}, start=[(0.0, 0.0), (30.0, 0.0)])
    )
    assert turned[1] == pytest.approx((30.0 / math.sqrt(2.0), 30.0 / math.sqrt(2.0)))
    assert turned[0] == pytest.approx((0.0, 0.0)), "der feste Anfang bleibt"


def test_a_fixed_point_does_not_follow_the_drag() -> None:
    """*Fest* heftet an die gespeicherte Koordinate, und die ändert ein Zug
    nicht — der Punkt bleibt, und die Zeile des Editors sagt, warum."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (30.0, 0.0))),),
        constraints=(SketchConstraint("fixed", (1,)),),
    )
    points = _flat(solve_sketch(sketch, dragged={1: (50.0, 12.0)}, start=[(0.0, 0.0), (30.0, 0.0)]))
    assert points[1] == pytest.approx((30.0, 0.0), abs=1e-6)
    assert points[0] == pytest.approx((0.0, 0.0), abs=1e-6)


def test_a_circle_rim_drags_the_radius_and_the_centre_drags_the_circle() -> None:
    circle = Sketch(
        plane="plane:xy", elements=(SketchElement("circle", ((0.0, 0.0), (10.0, 0.0))),)
    )
    start = [(0.0, 0.0), (10.0, 0.0)]

    wider = _flat(solve_sketch(circle, dragged={1: (15.0, 0.0)}, start=start))
    assert wider == [pytest.approx((0.0, 0.0)), pytest.approx((15.0, 0.0))]

    moved = _flat(solve_sketch(circle, dragged={0: (5.0, 5.0), 1: (15.0, 5.0)}, start=start))
    assert moved == [pytest.approx((5.0, 5.0)), pytest.approx((15.0, 5.0))]


def test_a_dragged_point_outside_the_sketch_is_rejected() -> None:
    with pytest.raises(ValidationError):
        solve_sketch(_drawn_box(), dragged={99: (0.0, 0.0)})


def test_a_drag_keeps_a_contradiction_a_contradiction() -> None:
    """Was vor dem Zug ein Widerspruch war, bleibt einer — die zweite Stufe
    heilt nichts, sie rutscht nur."""
    sketch = Sketch(
        plane="plane:xy",
        elements=(SketchElement("line", ((0.0, 0.0), (30.0, 0.0))),),
        constraints=(
            SketchConstraint("fixed", (0,)),
            SketchConstraint("fixed", (1,)),
            SketchConstraint("distance", (0, 1), "40"),
        ),
    )
    with pytest.raises(SketchConflictError):
        solve_sketch(sketch, dragged={1: (40.0, 0.0)}, start=[(0.0, 0.0), (30.0, 0.0)])


# --- Der Zug bleibt auch dort bedienbar, wo er nicht hinkommt (Durchsicht 22.09.2026) ---


def _chain(count: int) -> Sketch:
    """Eine Kette bemaßter Linien, die erste am Anfang festgenagelt — gelöst
    liegt sie gestreckt, also bis zum Anschlag."""
    elements = tuple(
        SketchElement("line", ((i * 10.0, 0.3), (i * 10.0 + 9.5, -0.2))) for i in range(count)
    )
    constraints = (
        *(SketchConstraint("coincident", (2 * i + 1, 2 * i + 2)) for i in range(count - 1)),
        *(SketchConstraint("distance", (2 * i, 2 * i + 1), "10") for i in range(count)),
        SketchConstraint("fixed", (0,)),
    )
    return Sketch(plane="plane:xy", elements=elements, constraints=constraints)


def _counting_evaluations(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Zählt die Auswertungen jedes Lösers — die Zahl ist gleich auf jeder Maschine."""
    from app.core.sketch import solver

    evaluations: list[int] = []
    real = solver.least_squares

    def counted(*args: object, **kwargs: object) -> object:
        result = real(*args, **kwargs)
        evaluations.append(int(result.nfev))
        return result

    monkeypatch.setattr(solver, "least_squares", counted)
    return evaluations


@pytest.mark.parametrize("count", [20, 40])
def test_a_drag_beyond_reach_stays_bounded_and_lands_alike_wherever_it_lies(
    count: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine gestreckte Kette über ihre Länge hinaus zu ziehen, hielt das Fenster an.

    Gemessen am 22.09.2026: Die erste Zugstufe suchte ohne Grenze nach einem
    Ort, den es nicht gibt — an zwanzig Linien 646 Auswertungen, an hundert 103
    Sekunden je Mausereignis. Gezählt wird hier nicht die Zeit, sondern die
    Arbeit: Sie ist auf jeder Maschine dieselbe. Und die Zeichnung wird kein
    Widerspruch.

    Eine lange Kette rechnet über ``lsmr`` und steht gestreckt singulär; im
    Sprung so weit über ihre Reichweite findet die zweite Stufe in
    :data:`DRAG_SLIDE_TRIES` keine Lage — wie 0.5.3 (RM-541, Reviews M-1 und
    M-C). Zugesagt ist, was an jedem Ort gilt: begrenzte Arbeit — erste und
    zweite Stufe —, kein Widerspruch, nie weiter vom Zeiger und an jedem Ort
    dieselbe Lage; in Mausschritten folgt sie (unten).
    """
    from app.core.sketch import solver
    from app.core.units import EPS_GEOM

    evaluations = _counting_evaluations(monkeypatch)
    home: list[tuple[float, float]] = []
    for dx, dy in ((0.0, 0.0), (1000.0, 0.0), (1e5, -1e5)):
        sketch = _placed(
            _chain(count), [(x + dx, y + dy) for x, y in edit.flat_points(_chain(count))]
        )
        start = _flat(solve_sketch(sketch))
        end = len(start) - 1
        target = (start[end][0] + 3.0, start[end][1] + 4.0)
        evaluations.clear()

        solved = solve_sketch(sketch, dragged={end: target}, start=start)
        points = _flat(solved)
        landed = points[end]

        bound = solver.DRAG_REACH_TRIES + solver.DRAG_SLIDE_TRIES
        assert sum(evaluations) <= bound, evaluations
        assert solved.max_residual <= 1e-6
        assert points[0] == pytest.approx(start[0], abs=1e-6), "der feste Anfang bleibt"
        assert math.dist(start[0], landed) <= 10.0 * count + 1e-6, "weiter als die Kette reicht nie"
        assert math.dist(landed, target) <= math.dist(start[end], target) + 1e-9, "nie weiter weg"
        back = [(x - dx, y - dy) for x, y in points]
        if not home:
            home = back
        gap = max(math.dist(a, b) for a, b in zip(back, home, strict=True))
        assert gap <= EPS_GEOM, ((dx, dy), gap)


@pytest.mark.parametrize("count", [17, 20])
def test_a_long_chain_follows_the_mouse_beyond_its_reach(count: int) -> None:
    """Das Ende einer langen gestreckten Kette, mit der Maus seitlich jenseits
    ihrer Reichweite geführt, läuft auf seinem Kreis zum Zeiger hin — an
    jedem Ort gleich (RM-541, Review M-C).

    Seit die zweite Stufe am Stand vor dem Schritt beginnt (M-1), fand sie
    an einer Kette über ``lsmr`` (ab siebzehn Gliedern) in fünfzig
    Auswertungen keine Lage, und die Kette rührte sich nicht, wo 0.5.3 sie
    folgen ließ. Mit hundert folgt sie bis auf Hundertstel Grad.
    """
    from app.core.units import EPS_GEOM

    home: list[tuple[float, float]] = []
    for dx, dy in ((0.0, 0.0), (1000.0, 0.0)):
        drawn = _chain(count)
        sketch = _placed(drawn, [(x + dx, y + dy) for x, y in edit.flat_points(drawn)])
        points = _flat(solve_sketch(sketch))
        anchor = points[0]
        reach = math.dist(anchor, points[-1])
        end = len(points) - 1
        target = anchor
        for step in range(1, 11):
            target = (anchor[0] + reach + 2.0, anchor[1] + 0.5 * step)
            solved = solve_sketch(_placed(sketch, points), dragged={end: target}, start=points)
            points = _flat(solved)
        wanted = math.atan2(target[1] - anchor[1], target[0] - anchor[0])
        reached = math.atan2(points[end][1] - anchor[1], points[end][0] - anchor[0])
        assert reached >= 0.95 * wanted, (count, math.degrees(reached), math.degrees(wanted))
        back = [(x - dx, y - dy) for x, y in points]
        if not home:
            home = back
        gap = max(math.dist(a, b) for a, b in zip(back, home, strict=True))
        assert gap <= EPS_GEOM, ((dx, dy), gap)


def test_a_reachable_drag_is_untouched_by_the_bound(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Grenze gilt dem Unerreichbaren: Nach innen gezogen folgt das Ende
    der Kette weiter exakt dem Zeiger, mit wenigen Auswertungen."""
    from app.core.sketch import solver

    sketch = _chain(20)
    start = _flat(solve_sketch(sketch))
    end = len(start) - 1
    target = (start[end][0] - 3.0, start[end][1] + 4.0)
    evaluations = _counting_evaluations(monkeypatch)

    solved = solve_sketch(sketch, dragged={end: target}, start=start)

    assert _flat(solved)[end] == pytest.approx(target, abs=1e-9)
    assert len(evaluations) == 1 and evaluations[0] < solver.DRAG_REACH_TRIES


@pytest.mark.parametrize("count", [5, 10])
def test_a_short_chain_still_slides_as_far_as_it_may(count: int) -> None:
    """Die zweite Stufe beginnt am Stand vor dem Schritt und rutscht: Das Ende
    einer kurzen Kette folgt über ihre Länge gezogen dem Zeiger, so weit die
    Kette reicht — gemessen in vier Auswertungen (RM-541)."""
    sketch = _chain(count)
    start = _flat(solve_sketch(sketch))
    end = len(start) - 1
    target = (start[end][0] + 3.0, start[end][1] + 4.0)

    solved = solve_sketch(sketch, dragged={end: target}, start=start)
    landed = _flat(solved)[end]

    assert math.dist(start[0], landed) <= 10.0 * count + 1e-6, "weiter als die Kette reicht nie"
    assert landed[1] > start[end][1] + 1.0, "in Richtung des Zeigers gedreht"
    assert math.dist(landed, target) < math.dist(start[end], target), "näher am Zeiger"
    assert solved.max_residual <= 1e-6


def test_the_redundancy_search_decomposes_the_matrix_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """„Legt fest, was schon festliegt" kostete eine Zerlegung je Bedingung.

    An der Kette aus §31 mit einem doppelten Maß waren das 201 Zerlegungen und
    3,5 Sekunden im Qt-Hauptthread (Durchsicht 22.09.2026). Der linke Nullraum
    beantwortet dieselbe Frage für alle Bedingungen aus einer.
    """
    sketch = _chain(100)
    doubled = replace(
        sketch, constraints=(*sketch.constraints, SketchConstraint("distance", (0, 1), "10"))
    )
    real = np.linalg.matrix_rank
    calls: list[int] = []

    def counted(matrix: object, *args: object, **kwargs: object) -> object:
        calls.append(1)
        return real(matrix, *args, **kwargs)

    monkeypatch.setattr(np.linalg, "matrix_rank", counted)
    with pytest.raises(SketchConflictError) as caught:
        solve_sketch(doubled)
    assert {caught.value.first, caught.value.second} == {99, 200}
    assert len(calls) <= 2, f"{len(calls)} Rangberechnungen"


@pytest.mark.parametrize("seed", range(6))
def test_the_single_decomposition_answers_like_the_rank_of_each_rest(seed: int) -> None:
    """Die schnelle Antwort ist dieselbe wie die langsame: je Block der
    Rangverlust, wenn man seine Zeilen herausnimmt — an zufälligen,
    absichtlich abhängigen Matrizen gegen ``matrix_rank`` gerechnet."""
    from app.core.sketch.solver import _losses

    generator = np.random.default_rng(seed)
    base = generator.normal(size=(6, 7))
    # Zwei Zeilen, die nichts Neues sagen: Rang 6 bei acht Zeilen.
    matrix = np.vstack([base, base[1] + base[4], base[2] - 2.0 * base[5]])
    blocks = [range(2), range(2, 3), range(3, 5), range(5, 6), range(6, 7), range(7, 8)]
    rank = int(np.linalg.matrix_rank(matrix))
    assert rank == 6

    expected = [
        rank - int(np.linalg.matrix_rank(np.delete(matrix, list(block), axis=0)))
        for block in blocks
    ]
    answered = _losses(matrix, rank, blocks)
    assert [loss for loss, _share in answered] == expected
    for (loss, share), block in zip(answered, blocks, strict=True):
        # Beteiligt ist, wessen Zeilen der Nullraum trägt — nie mehr als eins.
        assert 0.0 <= share <= 1.0 + 1e-12, (block, share)
        if loss < len(block):
            assert share > 1e-6, (block, share)


def _fixed_ring(count: int) -> Sketch:
    """Ein Ring aus Hilfslinien, jeder Punkt mit ``fixed`` — so kommt eine
    übernommene Flächenkontur in die Zeichnung (RM-188 P3.4)."""
    elements = []
    constraints = []
    for index in range(count):
        first = 2.0 * math.pi * index / count
        second = 2.0 * math.pi * (index + 1) / count
        elements.append(
            SketchElement(
                "line",
                (
                    (20.0 * math.cos(first), 20.0 * math.sin(first)),
                    (20.0 * math.cos(second), 20.0 * math.sin(second)),
                ),
                construction=True,
            )
        )
        constraints += [
            SketchConstraint("fixed", (2 * index,)),
            SketchConstraint("fixed", (2 * index + 1,)),
        ]
    return Sketch("plane:xy", tuple(elements), tuple(constraints))


def test_fixed_points_leave_the_decomposition_only_what_the_drawing_decides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Jede Zeile von ``fixed`` hält genau eine Koordinate und wird vor der
    Zerlegung abgeschält; zerlegt wird nur, was die Zeichnung selbst festlegt.

    Die dichte Zerlegung über alle Zeilen kostete bei 512 festen Linien
    1,8 Sekunden je Lösung, bei jedem Klick (gemessen 23.09.2026). Hier hängt
    ein Kreis mit seiner Mitte an einem Punkt der Kontur: Die Deckung wird im
    zweiten Schälgang zur Einerzeile, übrig bleibt der Randpunkt des Kreises.
    """
    ring = _fixed_ring(64)
    rim = len(ring.elements) * 2 + 1
    sketch = replace(
        ring,
        # Der Randpunkt schräg zur Mitte: Maß und Eichzeile tragen dann beide
        # Koordinaten, und es bleibt eine echte Zerlegung übrig.
        elements=(
            *ring.elements,
            SketchElement("circle", ((20.0, 0.0), (20.0 + 3.0 * 0.6, 3.0 * 0.8))),
        ),
        constraints=(
            *ring.constraints,
            SketchConstraint("coincident", (0, rim - 1)),
            SketchConstraint("diameter", (rim - 1, rim), "6"),
        ),
    )
    real = np.linalg.svd
    shapes: list[tuple[int, ...]] = []

    def recorded(matrix: np.ndarray, *args: object, **kwargs: object) -> object:
        shapes.append(np.shape(matrix))
        return real(matrix, *args, **kwargs)

    monkeypatch.setattr(np.linalg, "svd", recorded)
    solved = solve_sketch(sketch)

    assert solved.free_dof == 0, "Kontur fest, Kreis an ihr, Durchmesser bemaßt"
    assert shapes, "der Kreis bleibt zu zerlegen"
    assert max(rows for rows, _columns in shapes) <= 2, shapes


@pytest.mark.parametrize("seed", range(8))
def test_the_peeled_rank_is_the_rank(seed: int) -> None:
    """Abschälen ist exakt: an zufälligen Matrizen mit Einerzeilen, doppelten
    Einerzeilen auf einer Spalte, Nullzeilen und Zeilen, die erst nach einem
    Schälgang zu Einerzeilen werden — gegen ``matrix_rank`` über alles."""
    from app.core.sketch.solver import _matrix_rank

    generator = np.random.default_rng(seed)
    columns = 12
    rows: list[np.ndarray] = []
    for _ in range(18):
        row = np.zeros(columns)
        width = int(generator.integers(0, 4))
        chosen = generator.choice(columns, size=width, replace=False) if width else []
        row[chosen] = generator.normal(size=width)
        rows.append(row)
    # Eine abhängige Zeile obendrauf, damit der Rest nicht immer voll ist.
    rows.append(rows[3] + 2.0 * rows[7])
    matrix = np.vstack(rows)

    assert _matrix_rank(matrix) == int(np.linalg.matrix_rank(matrix))
    from scipy.sparse import csr_matrix

    assert _matrix_rank(csr_matrix(matrix)) == int(np.linalg.matrix_rank(matrix)), "auch dünn"


def _separate_circles(count: int) -> Sketch:
    """``count`` getrennte Kreise mit Durchmesser 4, gezeichnet zu klein."""
    elements = []
    constraints = []
    for index in range(count):
        x, y = 12.0 * (index % 20), 12.0 * (index // 20)
        rim = (x + 2.0 + 0.3 * (index % 4), y + 0.2)
        elements.append(SketchElement("circle", ((x, y), rim)))
        constraints.append(SketchConstraint("diameter", (2 * index, 2 * index + 1), "4"))
    return Sketch(plane="plane:xy", elements=tuple(elements), constraints=tuple(constraints))


def test_many_separate_parts_solve_in_few_steps_each(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zweihundert getrennte Kreise mit Durchmesser: wenige Auswertungen je
    Kreis, und eine schon gelöste Zeichnung rechnet gar nicht nach (RM-541).

    Seit je Teil gerechnet wird, lief jeder Kreis allein — über dichtes TRF,
    das bei weniger Gleichungen als Unbekannten jeden Schritt auf den Rand
    des Vertrauensbereichs setzt: 57 Auswertungen je Kreis, zusammen
    2,8 Sekunden statt der 100 ms aus §31. Schon gelöst rechnete jeder Kreis
    mit der Genauigkeit 10⁻¹⁴ im Rundungsrauschen nach, bis zu 49
    Auswertungen. Gezählt wird die Arbeit, sie ist auf jeder Maschine
    dieselbe.
    """
    sketch = _separate_circles(200)
    evaluations = _counting_evaluations(monkeypatch)

    solved = solve_sketch(sketch)

    assert len(evaluations) == 200, "je Kreis ein Lauf"
    assert max(evaluations) <= 6, max(evaluations)
    for element in solved.elements:
        assert span(*element.points) == pytest.approx(2.0, abs=1e-9)

    evaluations.clear()
    solve_sketch(_placed(sketch, _flat(solved)))
    assert evaluations == [], "gelöst ist gelöst"


def test_separate_rectangles_are_decomposed_one_by_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Rangprüfung zerlegt getrennte Teile einzeln (RM-541): Hundertfünfzig
    bemaßte Rechtecke kosteten im Ganzen rund zehn Sekunden je Lösung, auch
    schon gelöst — die Zerlegung wächst mit der dritten Potenz."""
    sketch = Sketch(
        plane="plane:xy",
        elements=tuple(
            SketchElement("line", (a, b))
            for index in range(150)
            for a, b in pairwise(
                [
                    (30.0 * (index % 15) + x, 30.0 * (index // 15) + y)
                    for x, y in ((0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0), (0.0, 0.0))
                ]
            )
        ),
        constraints=tuple(
            constraint
            for index in range(150)
            for base in (8 * index,)
            for constraint in (
                *(
                    SketchConstraint("coincident", (base + 2 * k + 1, base + (2 * k + 2) % 8))
                    for k in range(4)
                ),
                SketchConstraint("horizontal", (base, base + 1)),
                SketchConstraint("vertical", (base + 2, base + 3)),
                SketchConstraint("horizontal", (base + 4, base + 5)),
                SketchConstraint("vertical", (base + 6, base + 7)),
                SketchConstraint("distance", (base, base + 1), "20"),
                SketchConstraint("distance", (base + 2, base + 3), "10"),
            )
        ),
    )
    shapes: list[tuple[int, ...]] = []
    for name in ("svd", "matrix_rank"):
        real = getattr(np.linalg, name)

        def recorded(
            matrix: np.ndarray, *args: object, _real: object = real, **kwargs: object
        ) -> object:
            shapes.append(np.shape(matrix))
            return _real(matrix, *args, **kwargs)  # type: ignore[operator]

        monkeypatch.setattr(np.linalg, name, recorded)
    solved = solve_sketch(sketch)

    assert solved.free_dof == 2 * 150, "jedes Rechteck darf noch wandern"
    assert shapes, "zerlegt wird"
    assert max(rows for rows, _columns in shapes) <= 14, "höchstens ein Rechteck je Zerlegung"


@pytest.mark.parametrize("seed", range(6))
def test_a_rank_taken_block_by_block_counts_like_the_whole(seed: int) -> None:
    """Getrennte Blöcke werden einzeln zerlegt, gezählt wird mit der Schranke
    der ganzen Matrix (RM-541): Ein Block, dessen kleinster Singulärwert nur
    neben einem viel größeren Block verschwindet, zählt wie in
    ``matrix_rank`` über alles — einzeln zerlegt hätte er eigene Maßstäbe.

    Zerlegt im Ganzen kosteten hundertfünfzig getrennte Rechtecke rund zehn
    Sekunden je Lösung."""
    from scipy.linalg import block_diag

    from app.core.sketch.solver import _matrix_rank

    generator = np.random.default_rng(seed)
    blocks = []
    for index in range(5):
        height, width = int(generator.integers(2, 6)), int(generator.integers(2, 7))
        block = generator.random((height, width)) * 2.0 - 1.0
        if index == 1:
            block *= 1000.0
        if index == 3:
            # Fast abhängig: neben dem großen Block unter der Schranke, allein nicht.
            block[-1] = block[0] + 1e-13 * (generator.random(width) * 2.0 - 1.0)
        blocks.append(block)
    whole = block_diag(*blocks)
    rows = generator.permutation(whole.shape[0])
    columns = generator.permutation(whole.shape[1])
    mixed = whole[rows][:, columns]

    assert _matrix_rank(mixed) == int(np.linalg.matrix_rank(mixed))


def test_an_arc_with_all_three_points_fixed_is_determined_not_redundant() -> None:
    """Ein Bogen mit drei festen Punkten ist bestimmt — keine Doppelung.

    Seine eigene Gleichung war die siebte Zeile über sechs Koordinaten, und
    der Löser meldete „Eine Bedingung legt fest, was schon festliegt": an
    jedem Bogen einer übernommenen Kontur und an jedem, dessen letzten Punkt
    jemand festnagelt.
    """
    arc = SketchElement("arc", ((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)), construction=True)
    sketch = Sketch(
        "plane:xy", (arc,), tuple(SketchConstraint("fixed", (index,)) for index in range(3))
    )

    solved = solve_sketch(sketch)

    assert solved.free_dof == 0
    assert solved.elements[0].points == arc.points


def test_a_fixed_arc_whose_ends_disagree_stays_a_contradiction() -> None:
    """Liegen die festen Enden nicht auf einem Kreis, bleibt die Gleichung —
    und der Widerspruch wird gemeldet wie vorher."""
    arc = SketchElement("arc", ((0.0, 0.0), (10.0, 0.0), (0.0, 12.0)))
    sketch = Sketch(
        "plane:xy", (arc,), tuple(SketchConstraint("fixed", (index,)) for index in range(3))
    )

    with pytest.raises(SketchConflictError):
        solve_sketch(sketch)


def test_one_answer_for_how_far_an_arc_runs() -> None:
    """Wie weit ein Bogen läuft, beantwortet profile.arc_sweep für alle —
    und zusammenfallende Enden sind ein Vollkreis, kein Nullbogen."""
    from app.core.sketch.profile import arc_sweep

    assert arc_sweep((0.0, 0.0), (10.0, 0.0), (0.0, 10.0)) == pytest.approx(math.pi / 2.0)
    assert arc_sweep((0.0, 0.0), (0.0, 10.0), (10.0, 0.0)) == pytest.approx(1.5 * math.pi)
    assert arc_sweep((0.0, 0.0), (10.0, 0.0), (10.0, 1e-12)) == pytest.approx(2.0 * math.pi)


def test_an_outline_of_thousands_of_fixed_edges_stays_solvable() -> None:
    """Eine übernommene Kontur mit 2624 festen Strecken ist lösbar.

    So viele hat eine Seitenfläche des Besenhalters aus ``F:\\3D Dateien``
    (``broomholdervcd_d35mm.stl``, gemessen 23.09.2026). Der Löser zählte die
    Zeilen von ``fixed`` ins Budget der dichten Matrix — 881 MB — und sagte
    „mehr Punkte und Bedingungen, als der Löser verarbeitet" über Geometrie,
    die sich nicht bewegen kann. Sie fällt beim Schälen heraus, bevor etwas
    dicht wird, und zählt deshalb nicht mehr.
    """
    solved = solve_sketch(_fixed_ring(2624))

    assert solved.free_dof == 0
    assert len(solved.elements) == 2624


def _slot_with_a_seam() -> SolvedSketch:
    """Die innere Kette der Flächenkontur einer exakten Platte mit Langloch 12 × 6.

    **Die Zahlen sind gemessen, nicht ausgedacht** (23.09.2026, Platte
    40 × 30 × 8 minus Langloch, ``edit.face_outline`` auf der Deckfläche,
    gelöst): Die Naht des rechten Zylinders teilt den Halbkreis in zwei
    Viertel, deren Enden bei y = -8,4·10⁻¹⁶ und -1,6·10⁻¹⁵ liegen. Mit runden
    Zahlen trifft die Kette den Fall nicht — OpenCASCADE meldet das
    gemeinsame Stück nur an diesen Bits.
    """
    return SolvedSketch(
        elements=(
            SketchElement("line", ((6.0, 2.999999999999999), (-6.0, 2.999999999999999))),
            SketchElement(
                "arc",
                (
                    (6.0, -8.446327622338112e-16),
                    (9.0, -8.446327622338112e-16),
                    (6.0, 2.999999999999999),
                ),
            ),
            SketchElement(
                "arc",
                (
                    (6.0, -8.446327622338112e-16),
                    (5.999999999999999, -3.000000000000001),
                    (9.0, -1.5794208417222232e-15),
                ),
            ),
            SketchElement("line", ((6.0, -3.000000000000001), (-6.0, -3.000000000000001))),
            SketchElement(
                "arc",
                (
                    (-6.0, -8.446327622338112e-16),
                    (-6.0, 2.999999999999999),
                    (-6.000000000000001, -3.000000000000001),
                ),
            ),
        ),
        free_dof=0,
        max_residual=0.0,
    )


def test_two_arcs_of_one_circle_that_meet_at_a_seam_do_not_cross() -> None:
    """Zwei Bögen desselben Kreises, die nur aneinanderstoßen, sind kein Kreuzen.

    OpenCASCADE meldet sie als gemeinsames Stück, sobald ihre Enden im letzten
    Bit auseinanderliegen — so teilt die Naht eines exakten Zylinders den Rand
    einer Bohrung. Die Flächenkontur einer Platte mit Langloch galt damit als
    „kreuzt sich selbst" (23.09.2026). Gezählt wird ein gemeinsames Stück erst
    mit Länge; das Gegenstück steht darunter.
    """
    exact_kernel()
    from app.core.sketch.profile import regions_of, signed_area

    (region,) = regions_of(_slot_with_a_seam())

    assert abs(signed_area(region)) == pytest.approx(12.0 * 6.0 + math.pi * 9.0, rel=1e-6)


def test_an_arc_that_runs_back_along_its_own_circle_still_crosses() -> None:
    """Das Gegenstück: Läuft ein Bogen auf seinem Kreis zurück, teilen sich die
    zwei Bögen ein Stück mit Länge — eine Spitze ohne Breite, die abgewiesen
    wird wie die Linie, die auf sich selbst zurückläuft."""
    from app.core.sketch.profile import regions_of

    sketch = Sketch(
        plane="plane:xy",
        elements=(
            # Oben herum von 0° nach 180° …
            SketchElement("arc", ((0.0, 0.0), (10.0, 0.0), (-10.0, 0.0))),
            # … und auf demselben Kreis zurück bis 90°.
            SketchElement("arc", ((0.0, 0.0), (0.0, 10.0), (-10.0, 0.0))),
            SketchElement("line", ((0.0, 10.0), (10.0, 0.0))),
        ),
    )

    with pytest.raises(AppError):
        regions_of(solve_sketch(sketch))
