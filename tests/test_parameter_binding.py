"""Feste Zahlen, die zu Projektmaßen passen, und ihre Bindung (Dateiaudit §4, RM-184).

Der Fall ist das Puppenhaus aus dem Audit (``helpers.dollhouse_document``):
Länge und Breite lasen nur den Boden; Wandring und Fenster standen mit festen
Zahlen da. Die Sollwerte folgen aus seinen Maßen (Länge 180, Breite 120, Wand 3,
Etage 90) — die Zahlen im Stapel sind genau diese Maße, ihre Hälften oder ihre
Differenzen.
"""

from __future__ import annotations

import random

import pytest

from app.core.bootstrap import load_operations
from app.core.scene import History
from app.core.scene.parameter_binding import (
    _FIRST,
    _SECOND,
    _SINGLE,
    MATCH,
    MOST_CHOICES,
    BindingChoice,
    BindingSpot,
    _rendered,
    binding_spots,
    bound_params,
    bound_sketch,
    matching_expressions,
)
from app.core.sketch.serialize import sketch_from_text, sketch_to_text
from app.core.types import Document, Operation, Parameter, Sketch, SketchConstraint, SketchElement
from tests.helpers import dollhouse_document, rectangle_ring


@pytest.fixture(autouse=True)
def operations() -> None:
    load_operations()


def _spot(spots: tuple[BindingSpot, ...], op_id: int, field: str, side: str = "") -> BindingSpot:
    return next(
        spot for spot in spots if spot.op_id == op_id and spot.field == field and spot.side == side
    )


def test_a_number_equal_to_a_parameter_is_offered_first() -> None:
    """Dieselbe Zahl vor der Hälfte, ein Maß vor zweien."""
    known = {"laenge": 180.0, "breite": 120.0, "wand": 3.0}
    assert [choice.expression for choice in matching_expressions(180.0, known)] == ["@laenge"]
    assert matching_expressions(180.0, known)[0].exact
    assert [choice.expression for choice in matching_expressions(90.0, known)] == ["=@laenge / 2"]
    assert [choice.expression for choice in matching_expressions(-60.0, known)] == ["=-@breite / 2"]
    # 180 - 2 * 3 = 174: kein Maß allein, also zwei.
    assert matching_expressions(174.0, known)[0].expression == "=@laenge - 2 * @wand"
    assert not matching_expressions(174.0, known)[0].exact
    assert matching_expressions(7.25, known) == ()


def _every_pair(value: float, known: dict[str, float]) -> tuple[BindingChoice, ...]:
    """Die volle Suche als Sollwert: jedes Maß, dann jedes Paar mit jedem Faktor.

    Je Maß nach dem Rang seines Faktors (stabil, sonst in Maßfolge), je Paar in
    der Folge der Schleifen.
    """
    reach = MATCH * max(1.0, abs(value))
    single = sorted(
        (
            (rank, BindingChoice(_rendered(((factor, name),)), (name,), factor == 1.0))
            for name, number in known.items()
            for rank, factor in enumerate(_SINGLE)
            if abs(factor * number - value) <= reach
        ),
        key=lambda entry: entry[0],
    )
    if single:
        return tuple(choice for _rank, choice in single[:MOST_CHOICES])
    double: list[BindingChoice] = []
    seen: set[frozenset[tuple[float, str]]] = set()
    for first, number_a in known.items():
        for second, number_b in known.items():
            for factor_a in _FIRST:
                for factor_b in _SECOND:
                    terms = ((factor_a, first), (factor_b, second))
                    if first == second or frozenset(terms) in seen:
                        continue
                    if abs(factor_a * number_a + factor_b * number_b - value) <= reach:
                        seen.add(frozenset(terms))
                        double.append(BindingChoice(_rendered(terms), (first, second), False))
    return tuple(double[:MOST_CHOICES])


def test_the_sorted_search_finds_what_the_full_search_finds() -> None:
    """Die sortierte Paarsuche gibt dieselben Vorschläge in derselben Folge wie die volle.

    Sollwert ist die volle Suche, oben ausgeschrieben. Die Maße sind ganze und
    halbe Zahlen, damit Summen oft zusammenfallen und die Folge entscheidet;
    dazu dieselben Zahlen ein halbes Millionstel daneben (passt noch) und ein
    Hunderttausendstel daneben (passt nicht mehr).
    """
    generator = random.Random(184)
    compared = with_choices = 0
    for _ in range(40):
        known = {
            f"p{index}": generator.choice((1.0, 2.0, 3.0, 0.5, 2.5)) * generator.randint(1, 60)
            for index in range(generator.randint(2, 20))
        }
        names = list(known)
        for _ in range(30):
            first, second = generator.choice(names), generator.choice(names)
            value = generator.choice(_FIRST) * known[first]
            value += generator.choice(_SECOND) * known[second]
            for candidate in (value, value * (1.0 + 5e-7), value * (1.0 + 1e-5)):
                if abs(candidate) <= MATCH:
                    continue
                expected = _every_pair(candidate, known)
                assert matching_expressions(candidate, known) == expected, (candidate, known)
                compared += 1
                with_choices += bool(expected)
    assert compared > 3000, compared
    assert compared / 3 < with_choices < compared, (with_choices, compared)


def test_the_dollhouse_offers_its_walls_and_window(document: Document) -> None:
    """Wandring 180 × 120 und 174 × 114, das Fenster 30 bei y = -58,5 und z = 45."""
    spots = binding_spots(dollhouse_document(document))
    outer_width = _spot(spots, 2, "sketch", "width")
    assert outer_width.rectangle == 0
    assert outer_width.value == pytest.approx(180.0)
    assert outer_width.choices[0].expression == "@haus_laenge"
    assert outer_width.certain
    inner_height = next(
        spot for spot in spots if spot.op_id == 2 and spot.rectangle == 1 and spot.side == "height"
    )
    assert inner_height.value == pytest.approx(114.0)
    assert inner_height.choices[0].expression == "=@haus_breite - 2 * @wand"
    assert not inner_height.certain
    assert _spot(spots, 3, "length").choices[0].expression == "@fenster"
    assert _spot(spots, 3, "z").choices[0].expression == "=@etage / 2"
    # -58,5 = -(120 / 2) + 3 / 2: zwei Maße, also kein sicherer Vorschlag.
    assert _spot(spots, 3, "y").choices[0].expression == "=-@haus_breite / 2 + @wand / 2"
    # Schon gebundene Felder kommen nicht vor.
    assert all(spot.op_id != 1 for spot in spots)


def test_a_position_is_never_preselected(document: Document) -> None:
    """Dieselbe Zahl als Größe steht vor, als Lage nicht.

    Im Puppenhaus des Audits liegt die Tür bei z = 30, und das Fenster ist 30
    breit: Eine Lage fällt zu leicht auf ein Maß. Größe heißt, das Feld lässt
    nichts unter null zu (Länge ab 0,1); die Lage darf negativ sein.
    """
    document.parameters = {"fenster": Parameter(name="fenster", value=30.0)}
    document.ops = [
        Operation(
            id=1,
            op="sketch_pocket",
            inputs=("obj_1",),
            outputs=("obj_1",),
            params={
                "shape": "rectangle",
                "length": 30.0,
                "width": 12.0,
                "through": True,
                "z": 30.0,
            },
        )
    ]
    spots = binding_spots(document)
    length, height = _spot(spots, 1, "length"), _spot(spots, 1, "z")
    assert length.choices[0].expression == height.choices[0].expression == "@fenster"
    assert length.choices[0].exact and height.choices[0].exact
    assert length.certain
    assert not height.certain


def test_a_bound_dollhouse_follows_its_length_and_width(document: Document, profile) -> None:
    """Gebunden wächst der Wandring mit dem Haus, und die Öffnung bleibt in der Vorderwand.

    Soll: Wandring L × B außen, (L - 6) × (B - 6) innen, 90 hoch. Die Tasche
    schneidet, wie im Audit gespeichert, von oben durch die ganze Höhe
    (``through``), 30 breit und 30 tief; gebunden liegt sie mittig auf der
    3 mm Vorderwand (y = -75 bis -72) und nimmt 30 × 3 × 90 heraus. Die
    ungebundene Gegenprobe ist der Befund des Audits: Nur der Boden wächst,
    der Wandring bleibt 180 × 120.
    """
    import copy

    from app.core.scene.evaluate import evaluate

    def ring(length: float, width: float) -> float:
        return 90.0 * (length * width - (length - 6.0) * (width - 6.0))

    dollhouse_document(document)
    unbound = copy.deepcopy(document)
    spots = binding_spots(document)
    chosen = {spot.key: spot.choices[0].expression for spot in spots if spot.op_id in (2, 3)}
    History(document).bind_parameters(bound_params(document, chosen))
    scenes = []
    for case in (document, unbound):
        for name, value in (("haus_laenge", 240.0), ("haus_breite", 150.0)):
            case.parameters[name] = Parameter(name=name, value=value)
        result = evaluate(case, profile)
        assert result.complete, [str(finding.message) for finding in result.scene.report.findings]
        scenes.append(result.scene.objects)
    bound_wall, unbound_wall = (objects["obj_2"].mesh for objects in scenes)
    opening = 30.0 * 3.0 * 90.0
    assert tuple(bound_wall.bounds.size) == pytest.approx((240.0, 150.0, 90.0), abs=1e-6)
    assert bound_wall.volume == pytest.approx(ring(240.0, 150.0) - opening, rel=1e-9)
    assert tuple(scenes[1]["obj_1"].mesh.bounds.size) == pytest.approx((240.0, 150.0, 4.0))
    assert tuple(unbound_wall.bounds.size) == pytest.approx((180.0, 120.0, 90.0), abs=1e-6)
    assert unbound_wall.volume == pytest.approx(ring(180.0, 120.0) - opening, rel=1e-9)


def test_one_undo_takes_every_binding_back(document: Document) -> None:
    """Alle gewählten Stellen sind eine Transaktion (Regel 16)."""
    dollhouse_document(document)
    before = [dict(operation.params) for operation in document.ops]
    history = History(document)
    spots = binding_spots(document)
    chosen = {spot.key: spot.choices[0].expression for spot in spots}
    history.bind_parameters(bound_params(document, chosen))
    assert document.ops[2].params["z"] == "=@etage / 2"
    assert '"distance"' in document.ops[1].params["sketch"]
    history.undo()
    assert [dict(operation.params) for operation in document.ops] == before


def test_binding_is_refused_before_anything_is_written(document: Document) -> None:
    """Keine Wahl, ein unbekanntes Maß, ein falsches Feld: Absage, und der Stapel bleibt."""
    from app.core.errors import ValidationError

    dollhouse_document(document)
    history = History(document)
    before = [dict(operation.params) for operation in document.ops]
    count = len(document.transactions)
    for params, constraint in (
        ({}, "empty"),
        ({3: {"length": "@fenster", "width": "@gibt_es_nicht"}}, "unknown_parameter"),
    ):
        with pytest.raises(ValidationError) as refused:
            history.bind_parameters(params)
        assert refused.value.constraint == constraint
        assert refused.value.suggestions
    with pytest.raises(ValidationError):
        history.bind_parameters({3: {"kein_feld": "@fenster"}})
    assert [dict(operation.params) for operation in document.ops] == before
    assert len(document.transactions) == count


def test_a_bound_rectangle_keeps_its_corners_and_follows_its_dimensions() -> None:
    """Gedeckte Ecken, waagerecht, senkrecht, Mitte im Ursprung — der Löser hält das Rechteck."""
    from app.core.sketch.solver import solve_sketch

    text = bound_sketch(
        rectangle_ring((90.0, 60.0), (87.0, 57.0)), {(0, "width"): "@a", (0, "height"): "@b"}
    )
    sketch = sketch_from_text(text)
    assert sketch.elements[-1] == SketchElement("point", ((0.0, 0.0),), construction=True)
    solved = solve_sketch(sketch, {"a": 200.0, "b": 100.0})
    xs = [point[0] for element in solved.elements[:4] for point in element.points]
    ys = [point[1] for element in solved.elements[:4] for point in element.points]
    assert (min(xs), max(xs), min(ys), max(ys)) == pytest.approx((-100.0, 100.0, -50.0, 50.0))
    # Das innere Rechteck war nicht gewählt und steht, wo es stand.
    inner = [point for element in solved.elements[4:8] for point in element.points]
    assert max(abs(point[0]) for point in inner) == pytest.approx(87.0)


def test_binding_keeps_the_solver_of_an_older_drawing() -> None:
    """Eine Zeichnung aus einer älteren Datei rechnet nach dem Binden wie vorher
    mit ihrer Fassung des Lösers (RM-541, Review G-1).

    Alle anderen Umschreiber eines Skizzentexts behalten die Fassung; das
    Binden baute die Skizze neu und stellte sie still auf die heutige um —
    ohne dass jemand die Zeichnung im Editor geändert hätte."""
    from dataclasses import replace

    older = replace(sketch_from_text(rectangle_ring((90.0, 60.0), (87.0, 57.0))), solver=1)
    text = bound_sketch(sketch_to_text(older), {(0, "width"): "@a"})
    assert sketch_from_text(text).solver == 1


def test_drawings_with_dimensions_or_off_the_origin_are_left_alone(document: Document) -> None:
    """Wer schon gemaßt hat oder außermittig zeichnet, bekommt keinen Vorschlag."""
    corners = ((0.0, 0.0), (180.0, 0.0), (180.0, 120.0), (0.0, 120.0))
    shifted = sketch_to_text(
        Sketch(
            plane="plane:xy",
            elements=tuple(
                SketchElement("line", (corner, corners[(index + 1) % 4]))
                for index, corner in enumerate(corners)
            ),
        )
    )
    measured = sketch_from_text(rectangle_ring((90.0, 60.0), (87.0, 57.0)))
    measured = Sketch(
        plane=measured.plane,
        elements=measured.elements,
        constraints=(SketchConstraint("distance", (0, 1), "180"),),
    )
    document.parameters = {"haus_laenge": Parameter(name="haus_laenge", value=180.0)}
    document.ops = [
        Operation(id=1, op="sketch_extrude", params={"sketch": shifted, "height": 10.0}),
        Operation(
            id=2, op="sketch_extrude", params={"sketch": sketch_to_text(measured), "height": 10.0}
        ),
    ]
    spots = binding_spots(document)
    # Das außermittige Rechteck hätte 180 = haus_laenge; es bleibt, wie es ist.
    assert all(spot.op_id != 1 for spot in spots)
    # Im zweiten ist das äußere Rechteck gemaßt — seine 180 wären sonst die
    # sichere Wahl; das innere (174) passt zu keinem einzelnen Maß.
    assert [spot for spot in spots if spot.op_id == 2] == []
