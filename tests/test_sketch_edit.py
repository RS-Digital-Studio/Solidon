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
