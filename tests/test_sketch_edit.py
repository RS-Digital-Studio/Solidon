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

    assert len(rounded.elements) == 5
    assert rounded.elements[1].points == ((40.0, 0.0), (40.0, 15.0))
    assert rounded.elements[2].points[0] == pytest.approx((35.0, 20.0))
    arc = rounded.elements[4]
    assert arc.kind == "arc"
    assert flat(arc.points) == pytest.approx(flat(((35.0, 15.0), (40.0, 15.0), (35.0, 20.0))))

    kinds = [entry.kind for entry in rounded.constraints]
    assert kinds.count("coincident") == 5, "die Ecke ist weg, zwei Bogenenden sind dazu"
    assert kinds.count("perpendicular") == 2, "die Tangente als Senkrechte zum Radiusstrahl"
    assert kinds.count("radius") == 1
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
    assert caught.value.values["most"] == "20"
    assert "20" in str(caught.value.detail)
    with pytest.raises(ValidationError):
        edit.fillet(sketch, edit.flat_points(sketch), 3, 20.0)
    assert len(edit.fillet(sketch, edit.flat_points(sketch), 3, 19.99).elements) == 5
    # ``maximum`` ist eine Bereichsgrenze, und nur die trägt den Titel „außerhalb
    # des zulässigen Bereichs"; ein unbekannter Wert bekäme den vagen Satz.
    assert caught.value.constraint == "maximum"
    assert caught.value.title is ValidationError.default_title

    with pytest.raises(ValidationError):
        edit.fillet(sketch, edit.flat_points(sketch), 3, 0.0)


def test_a_chamfer_cuts_the_corner_with_a_straight_edge() -> None:
    """Fase 5: beide Linien um fünf gekürzt, dazwischen die Schräge mit ihrer
    Länge als Maß — 5·√2 an der rechten Ecke."""
    from app.core.sketch.profile import regions_of
    from app.core.sketch.solver import solve_sketch

    sketch = box()
    cut = edit.chamfer(sketch, edit.flat_points(sketch), 3, 5.0)

    assert len(cut.elements) == 5
    edge = cut.elements[4]
    assert edge.kind == "line"
    assert flat(edge.points) == pytest.approx(flat(((40.0, 15.0), (35.0, 20.0))))
    measure = [entry for entry in cut.constraints if entry.kind == "distance"]
    assert len(measure) == 1
    assert float(measure[0].value) == pytest.approx(5.0 * math.sqrt(2.0), abs=1e-5)

    solved = solve_sketch(cut)
    assert len(regions_of(solved)) == 1, "der Umriss bleibt geschlossen"

    with pytest.raises(ValidationError) as caught:
        edit.chamfer(sketch, edit.flat_points(sketch), 3, 25.0)
    assert caught.value.values["most"] == "20"
    assert caught.value.constraint == "maximum"
    assert caught.value.title is ValidationError.default_title
    with pytest.raises(ValidationError):
        edit.chamfer(sketch, edit.flat_points(sketch), 3, 20.0)
    assert len(edit.chamfer(sketch, edit.flat_points(sketch), 3, 19.99).elements) == 5


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
    from app.core.brep import profiles as brep_profiles
    from app.core.brep.kernel import available
    from app.core.sketch import solve_sketch
    from app.core.sketch.profile import regions_of

    if not available():
        pytest.skip("ohne B-Rep-Kern gibt es keinen Körper")

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
