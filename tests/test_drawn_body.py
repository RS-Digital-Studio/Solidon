"""Körper mit drei Klicks aufziehen (RM-559) — Kern und Bedeutung der Klicks, ohne Fenster.

Die Klickfolge des Werkzeugs *Zeichnen* steht in ``app/ui/draw_tool.py`` und
wird hier über dieselben Methoden gefahren, die die Ansicht ruft. Die Körper
entstehen über das Register und werden gegen geschlossene Formeln gemessen
(Regel 6: ``is_close``/``approx``, nie ``==``) — nicht gegen ein selbst
erzeugtes Ergebnis.
"""

from __future__ import annotations

import math

import pytest

from app.core.errors import ValidationError
from app.core.knowledge.profiles import Profile
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.sketch import shapes
from app.core.sketch.edit import scaled, stretched
from app.core.sketch.planes import BASE_FRAMES
from app.core.sketch.serialize import sketch_from_text, sketch_to_text
from app.core.sketch.solver import solve_sketch
from app.core.types import SceneObject, Sketch, SketchElement
from app.core.units import is_close
from app.ui.draw_tool import (
    DrawDraft,
    DrawSurface,
    Lift,
    bed_surface,
    face_marks,
    face_outline,
    face_surface,
    lifted,
    picture,
    reach_inside,
    snapped,
)
from tests.helpers import exact_kernel
from tests.helpers import run_with_parameters as run

#: Grenzen der Höhe und der Tiefe, wie das Schema sie trägt (0,1 bis 1000 mm).
LIMITS = (0.1, 1000.0)


# --- Die Formen im Kern --------------------------------------------------------


def test_a_rectangle_between_two_corners_is_fully_measured() -> None:
    """Zwei Seiten als Maß und die erste Ecke fest: nichts darf wandern (E1)."""
    sketch = shapes.rectangle_between((40.0, 30.0), (0.0, 0.0))
    solved = solve_sketch(sketch)
    assert solved.free_dof == 0
    measures = sorted(
        float(entry.value) for entry in sketch.constraints if entry.kind == "distance"
    )
    assert measures == pytest.approx([30.0, 40.0])
    fixed = next(entry for entry in sketch.constraints if entry.kind == "fixed")
    flat = [point for element in sketch.elements for point in element.points]
    assert flat[fixed.targets[0]] == pytest.approx((40.0, 30.0)), "die erste Ecke steht fest"


def test_a_circle_around_a_centre_carries_its_diameter() -> None:
    sketch = shapes.circle_around((5.0, -2.0), 8.0, "feature:obj_1:face_6")
    assert sketch.plane == "feature:obj_1:face_6"
    kinds = {entry.kind: entry for entry in sketch.constraints}
    assert float(kinds["diameter"].value) == pytest.approx(8.0)
    assert solve_sketch(sketch).free_dof == 0


@pytest.mark.parametrize(
    ("sketch", "expected"),
    [
        (shapes.rectangle_between((0.0, 0.0), (10.0, 4.0)), "rectangle"),
        (shapes.rectangle(20.0, 10.0), "rectangle"),
        (shapes.circle_around((0.0, 0.0), 6.0), "circle"),
        (shapes.slot(20.0, 6.0), None),
        (shapes.polygon(20.0, 6), None),
    ],
)
def test_a_simple_shape_is_recognised_by_its_geometry(sketch: Sketch, expected: str | None) -> None:
    assert shapes.simple_shape(sketch) == expected


def test_an_l_profile_is_no_simple_shape() -> None:
    corners = [(0.0, 0.0), (20.0, 0.0), (20.0, 5.0), (5.0, 5.0), (5.0, 20.0), (0.0, 20.0)]
    elements = tuple(
        SketchElement("line", (corners[index], corners[(index + 1) % len(corners)]))
        for index in range(len(corners))
    )
    assert shapes.simple_shape(Sketch("plane:xy", elements)) is None


# --- Klick für Klick -----------------------------------------------------------


def test_three_clicks_walk_through_the_phases_and_back() -> None:
    """Strg+Z im Entwurf geht Phase für Phase zurück (Abnahme 6)."""
    draft = DrawDraft()
    assert draft.phase == 0
    draft.begin(bed_surface(), (0.0, 0.0))
    assert draft.phase == 1
    assert draft.place((40.0, 30.0)) == ""
    assert draft.phase == 2
    assert draft.back() and draft.phase == 1
    assert draft.back() and draft.phase == 0
    assert not draft.back(), "vor dem ersten Klick gibt es nichts zurückzunehmen"


def test_a_second_click_on_the_first_keeps_the_first() -> None:
    """F-c: Zwei Klicks am selben Fleck geben keine Form, und der erste bleibt."""
    draft = DrawDraft()
    draft.begin(bed_surface(), (10.0, 10.0))
    refusal = draft.place((10.0, 10.0))
    assert refusal
    assert draft.phase == 1 and draft.first == (10.0, 10.0)


def test_the_shape_changes_only_before_the_base_stands() -> None:
    draft = DrawDraft()
    assert draft.choose("circle") and draft.shape == "circle"
    draft.begin(bed_surface(), (0.0, 0.0))
    draft.place((5.0, 0.0))
    assert not draft.choose("rectangle"), "nach Klick 2 steht die Grundfläche"


def test_typed_measures_grow_toward_the_pointer() -> None:
    """40 Tab 30: die Gegenecke liegt dort, wohin der Zeiger zuletzt zeigte."""
    draft = DrawDraft()
    draft.begin(bed_surface(), (0.0, 0.0))
    draft.aim((-3.0, 2.0))
    assert draft.type_size(40.0, 30.0) == ""
    assert draft.second == pytest.approx((-40.0, 30.0))


def test_a_mark_of_the_face_beats_the_grid() -> None:
    assert snapped((4.1, 0.2), 5.0) == pytest.approx((5.0, 0.0))
    assert snapped((4.1, 0.2), 5.0, ((3.9, 0.3),), reach=0.5) == pytest.approx((3.9, 0.3))
    assert snapped((4.1, 0.2), 5.0, ((2.0, 0.3),), reach=0.5) == pytest.approx((5.0, 0.0))


def test_downward_on_the_bed_stays_nothing_and_says_why() -> None:
    """F-e: Unter das Bett geht nichts — null bleibt null, kein Splitter (M2)."""
    lift = lifted(-6.0, 1.0, bed_surface(), LIMITS, LIMITS)
    assert lift.height == 0.0
    assert lift.note
    assert not lift.through
    draft = DrawDraft()
    draft.begin(bed_surface(), (0.0, 0.0))
    draft.place((40.0, 30.0))
    assert draft.step(lift) is None, "ein Klick in die falsche Richtung legt keinen Körper an"


def test_less_than_half_a_grid_step_is_no_height() -> None:
    """Ein Rohmaß unter einem halben Rasterschritt ist keine Höhe (M2)."""
    assert lifted(0.4, 1.0, bed_surface(), LIMITS, LIMITS) == Lift(0.0)
    assert lifted(0.6, 1.0, bed_surface(), LIMITS, LIMITS) == Lift(1.0)


def test_a_typed_width_takes_the_depth_from_the_pointer() -> None:
    """G1: 40 Enter bei einem Zeiger auf 40 × 12 gibt 40 × 12, kein Quadrat."""
    draft = DrawDraft()
    draft.begin(bed_surface(), (0.0, 0.0))
    draft.aim((40.0, 12.0))
    assert draft.type_size(40.0, None, (40.0, 12.0)) == ""
    assert draft.second == pytest.approx((40.0, 12.0))
    alone = DrawDraft()
    alone.begin(bed_surface(), (0.0, 0.0))
    assert alone.type_size(40.0) == ""
    assert alone.second == pytest.approx((40.0, 40.0)), "ohne Zeiger bleibt das Quadrat"


def test_a_pocket_preview_starts_at_the_top_of_the_body() -> None:
    """Unter einem Körper beginnt die Drahtform nach innen an seiner Oberkante (cut_top)."""
    surface = DrawSurface(
        plane="plane:xy",
        frame=BASE_FRAMES["plane:xy"],
        body="obj_1",
        joins=True,
        cut_top=20.0,
        through_depth=20.0,
    )
    draft = DrawDraft()
    draft.begin(surface, (0.0, 0.0))
    draft.place((10.0, 10.0))
    shown = picture(draft, None, Lift(-5.0))
    heights = [point[2] for pair in shown.dashed for point in pair]
    assert max(heights) == pytest.approx(20.0)
    assert min(heights) == pytest.approx(15.0)


# --- Ein Maß im Schrittdialog wächst vom Ansatz weg (M1) ---------------------------


def test_a_drawn_rectangle_grows_from_its_first_corner() -> None:
    """Erste Ecke oben rechts (30, 40), Breite 20 auf 25: Die Ecke bleibt stehen."""
    sketch = shapes.rectangle_between((30.0, 40.0), (10.0, 10.0))
    anchor = shapes.held_point(sketch)
    assert anchor == pytest.approx((30.0, 40.0))
    grown = stretched(sketch, 25.0 / 20.0, 0, None, anchor).sketch
    points = [point for element in grown.elements for point in element.points]
    assert any(math.dist(point, (30.0, 40.0)) < 1e-9 for point in points)
    assert min(x for x, _y in points) == pytest.approx(5.0)
    assert max(x for x, _y in points) == pytest.approx(30.0)


def test_a_drawn_circle_grows_around_its_centre() -> None:
    """Kreis Ø 20 um (50, 50) auf Ø 30: Die Mitte bleibt stehen (M1)."""
    sketch = shapes.circle_around((50.0, 50.0), 20.0)
    grown, _kept = scaled(sketch, 1.5, shapes.held_point(sketch))
    centre, rim = grown.elements[0].points
    assert centre == pytest.approx((50.0, 50.0))
    assert 2.0 * math.dist(centre, rim) == pytest.approx(30.0)


def test_a_sketch_without_one_fixed_point_has_none() -> None:
    assert shapes.held_point(Sketch("plane:xy", ())) is None


def test_inward_reaches_the_opposite_wall_as_through() -> None:
    surface = _box_top()
    assert surface.through_depth == pytest.approx(20.0)
    assert lifted(-19.6, 1.0, surface, LIMITS, LIMITS) == Lift(-20.0, through=True)
    assert lifted(-5.2, 1.0, surface, LIMITS, LIMITS) == Lift(-5.0)
    assert lifted(7.4, 1.0, surface, LIMITS, LIMITS) == Lift(7.0)


def test_height_and_depth_differ_without_colour() -> None:
    """Regel 18 (Abnahme 11): außen durchgezogen und *Höhe*, innen gestrichelt und *Tiefe*."""
    draft = DrawDraft()
    draft.begin(_box_top(), (-5.0, -5.0))
    draft.place((5.0, 5.0))
    outward = picture(draft, None, Lift(4.0))
    inward = picture(draft, None, Lift(-4.0))
    assert outward.solid and not outward.dashed and not outward.inward
    assert inward.dashed and inward.inward
    assert any("Höhe" in text for _point, text in outward.labels)
    assert any("Tiefe" in text for _point, text in inward.labels)
    assert any(
        "Durchgehend" in text for _point, text in picture(draft, None, Lift(-20.0, True)).labels
    )


def test_the_base_shows_two_measures_and_the_circle_one() -> None:
    draft = DrawDraft()
    draft.begin(bed_surface(), (0.0, 0.0))
    assert len(picture(draft, (40.0, 30.0)).labels) == 2
    round_draft = DrawDraft("circle")
    round_draft.begin(bed_surface(), (0.0, 0.0))
    (label,) = picture(round_draft, (4.0, 0.0)).labels
    assert "8" in label[1], "Durchmesser, nicht Radius — die Vorgabe ist Ø"


# --- Die Körper über das Register (Abnahme 2 bis 5) -----------------------------


def _box() -> SceneObject:
    exact_kernel()
    entry = run("create_brep_box", width=40, depth=30, height=20).outputs[0]
    entry.id = "obj_1"
    return entry


def _box_top() -> object:
    entry = _box()
    top = next(
        key
        for key, feature in entry.features.items()
        if feature.kind == "face" and feature.params["normal"][2] > 0.9
    )
    surface = face_surface(entry, top)
    assert surface is not None
    return surface


def _made(draft: DrawDraft, lift: Lift, entry: SceneObject | None = None) -> SceneObject:
    step = draft.step(lift)
    assert step is not None
    return run(step.op, entry, **step.params).outputs[0]


def test_a_typed_block_on_the_bed_is_forty_by_thirty_by_ten() -> None:
    """Abnahme 2, zuerst geschrieben: 12 000 mm³, Hülle 40 × 30 × 10, Unterseite auf z = 0."""
    exact_kernel()
    draft = DrawDraft()
    draft.begin(bed_surface(), (0.0, 0.0))
    draft.type_size(40.0, 30.0)
    step = draft.step(lifted(10.0, 0.0, bed_surface(), LIMITS, LIMITS))
    assert step is not None and step.op == "sketch_extrude" and step.inputs == ()
    body = run(step.op, None, **step.params).outputs[0].mesh
    assert is_close(body.volume, 12000.0, 1e-6)
    box = body.bounds
    assert is_close(box.minimum[2], 0.0) and is_close(box.maximum[2], 10.0)
    assert is_close(box.maximum[0] - box.minimum[0], 40.0)
    assert is_close(box.maximum[1] - box.minimum[1], 30.0)


def test_outward_on_a_face_joins_the_body() -> None:
    """Abnahme 3: ``sketch_join``, ein Körper, Volumen gleich der Summe."""
    entry = _box()
    draft = DrawDraft()
    draft.begin(_box_top(), (-5.0, -5.0))
    draft.place((5.0, 5.0))
    step = draft.step(Lift(5.0))
    assert step is not None and step.op == "sketch_join" and step.inputs == ("obj_1",)
    joined = run(step.op, entry, **step.params).outputs
    assert len(joined) == 1
    assert joined[0].mesh.volume == pytest.approx(24000.0 + 500.0, rel=1e-9)


def test_inward_on_a_face_cuts_a_pocket_or_through() -> None:
    """Abnahme 4: Tasche 5 mm, bis zur Gegenwand durchgehend."""
    entry = _box()
    draft = DrawDraft()
    draft.begin(_box_top(), (-5.0, -5.0))
    draft.place((5.0, 5.0))
    step = draft.step(Lift(-5.0))
    assert step is not None and step.op == "sketch_pocket"
    assert step.params["through"] is False
    assert _made(draft, Lift(-5.0), entry).mesh.volume == pytest.approx(24000.0 - 500.0, rel=1e-9)
    through = _made(draft, Lift(-20.0, through=True), entry).mesh.volume
    assert through == pytest.approx(24000.0 - 100.0 * 20.0, rel=1e-9)


@pytest.mark.parametrize(
    ("height", "through", "change"),
    [(6.0, False, 1), (-4.0, False, -1), (-20.0, True, -1)],
)
def test_a_circle_takes_the_same_three_ways_and_stays_a_curve(
    height: float, through: bool, change: int
) -> None:
    """Abnahme 5: Zylinder gegen π·r²·h — am exakten Körper bleibt der Kreis eine Kurve."""
    entry = _box()
    draft = DrawDraft("circle")
    draft.begin(_box_top(), (0.0, 0.0))
    draft.place((4.0, 0.0))
    made = _made(draft, Lift(height, through=through), entry)
    cylinder = math.pi * 16.0 * abs(height)
    assert made.mesh.volume == pytest.approx(24000.0 + change * cylinder, rel=1e-9)


def test_a_circle_cut_into_an_imported_mesh_stays_within_the_facets() -> None:
    """Am Netz entsteht der Kreis als Sehnenzug — das Volumen trifft π·r²·h bis auf die Facetten."""
    entry = run("create_box", width=40, depth=30, height=20).outputs[0]
    entry.id = "obj_1"
    top = next(key for key, value in entry.features.items() if value.kind == "face")
    surface = face_surface(entry, top)
    assert surface is not None and surface.cuts
    draft = DrawDraft("circle")
    draft.begin(surface, (0.0, 0.0))
    draft.place((4.0, 0.0))
    made = _made(draft, Lift(-4.0), entry)
    assert made.mesh.volume == pytest.approx(24000.0 - math.pi * 16.0 * 4.0, rel=1e-3)


def test_a_cylinder_on_the_bed_is_a_new_body() -> None:
    exact_kernel()
    draft = DrawDraft("circle")
    draft.begin(bed_surface(), (10.0, 10.0))
    draft.type_size(8.0)
    step = draft.step(Lift(5.0))
    assert step is not None and step.op == "sketch_extrude"
    body = run(step.op, None, **step.params).outputs[0].mesh
    assert body.volume == pytest.approx(math.pi * 16.0 * 5.0, rel=1e-9)


def test_the_drawing_of_a_step_is_a_simple_shape() -> None:
    """Der Schritt trägt sein Rechteck so, dass der Dialog es als Einfachform erkennt (E11)."""
    draft = DrawDraft()
    draft.begin(bed_surface(), (0.0, 0.0))
    draft.place((40.0, 30.0))
    step = draft.step(Lift(10.0))
    assert step is not None
    assert shapes.simple_shape(sketch_from_text(step.params["sketch"])) == "rectangle"


def test_the_face_offers_its_corners_and_edge_middles() -> None:
    entry = _box()
    surface = _box_top()
    face = next(
        key
        for key, value in entry.features.items()
        if value.kind == "face" and value.params["normal"][2] > 0.9
    )
    marks = face_marks(entry.mesh, entry.features[face].face_indices, surface.frame)
    for corner in ((-20.0, -15.0), (20.0, 15.0), (0.0, 15.0), (20.0, 0.0)):
        assert any(math.dist(mark, corner) < 1e-6 for mark in marks), corner


def test_the_face_lights_up_with_its_outline() -> None:
    """Phase 0: Füllung **und** Umriss (Regel 18) — der Umriss läuft um die Fläche herum."""
    entry = _box()
    face = next(
        key
        for key, value in entry.features.items()
        if value.kind == "face" and value.params["normal"][2] > 0.9
    )
    outline = face_outline(entry.mesh, entry.features[face].face_indices)
    assert outline, "ohne Umriss leuchtete nur die Farbe"
    length = sum(math.dist(start, end) for start, end in outline)
    assert length == pytest.approx(2 * (40.0 + 30.0), rel=1e-6)
    assert all(start[2] == pytest.approx(20.0) for start, _end in outline)


def test_the_wall_lies_as_deep_as_the_body_reaches() -> None:
    entry = _box()
    surface = _box_top()
    assert reach_inside(entry.mesh.bounds, surface.frame) == pytest.approx(20.0)


def test_the_three_operations_still_exist_in_the_register() -> None:
    for name in ("sketch_extrude", "sketch_join", "sketch_pocket"):
        assert REGISTRY.has(name)


# --- Die Art wechselt am Schritt (H1, History.change_kind) ------------------------


def _drawn_history() -> tuple[Project, History, int]:
    """Ein Projekt mit einem aufgezogenen Rechteck 10 … 20 × 0 … 30, Höhe 5, auf dem Bett."""
    exact_kernel()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    text = sketch_to_text(shapes.rectangle_between((10.0, 0.0), (20.0, 30.0)))
    history.apply(
        "Aufziehen",
        [OperationDraft(op="sketch_extrude", params={"sketch": text, "height": 5.0})],
    )
    return project, history, project.document.ops[-1].id


def _volumes(project: Project, profile: Profile) -> list[float]:
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [finding.message for finding in result.scene.report.findings]
    return sorted(float(entry.mesh.volume) for entry in result.scene.objects.values())


def test_a_drawn_block_turns_into_a_revolved_body_in_the_same_step(profile: Profile) -> None:
    """Art Rotationskörper: derselbe Schritt, dieselbe Kennung, Volumen π·(R² − r²)·h."""
    project, history, op_id = _drawn_history()
    before = project.document.ops[-1]
    text = before.params["sketch"]
    # Über ``change_kernel``: Vorschau und Übernehmen des Dialogs gehen diesen Weg.
    changed = history.change_kernel(op_id, "sketch_revolve", {"sketch": text})
    assert changed.op == "sketch_revolve"
    assert len(project.document.ops) == 1
    assert changed.outputs == before.outputs, "der Körper behält seine Kennung"
    (volume,) = _volumes(project, profile)
    assert volume == pytest.approx(math.pi * (20.0**2 - 10.0**2) * 30.0, rel=1e-6)
    history.undo()
    assert project.document.ops[-1].op == "sketch_extrude"


def test_a_drawing_on_the_bed_has_no_body_for_a_pocket() -> None:
    project, history, op_id = _drawn_history()
    assert history.kind_inputs(op_id, "sketch_revolve") == ()
    assert history.kind_inputs(op_id, "sketch_pocket") is None
    with pytest.raises(ValidationError):
        history.change_kind(op_id, "sketch_pocket", {"sketch": "", "depth": 2.0})
    assert project.document.ops[-1].op == "sketch_extrude", "abgelehnt heißt unverändert"


def test_a_drawing_on_a_face_cuts_its_body_as_a_pocket(profile: Profile) -> None:
    """Gezeichnet auf der Deckfläche eines Quaders: Die Tasche nimmt diesen Quader."""
    exact_kernel()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [OperationDraft(op="create_brep_box", params={"width": 40, "depth": 30, "height": 20})],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    ((body, entry),) = result.scene.objects.items()
    top = next(
        key
        for key, feature in entry.features.items()
        if feature.kind == "face" and feature.params["normal"][2] > 0.9
    )
    plane = f"feature:{body}:{top}"
    text = sketch_to_text(shapes.rectangle_between((-5.0, -5.0), (5.0, 5.0), plane))
    history.apply(
        "Aufziehen",
        [OperationDraft(op="sketch_extrude", params={"sketch": text, "height": 5.0})],
    )
    op_id = project.document.ops[-1].id
    assert history.kind_inputs(op_id, "sketch_pocket") == (body,)
    changed = history.change_kind(op_id, "sketch_pocket", {"sketch": text, "depth": 5.0})
    assert changed.inputs == (body,) and changed.outputs == (body,)
    (volume,) = _volumes(project, profile)
    assert volume == pytest.approx(40.0 * 30.0 * 20.0 - 10.0 * 10.0 * 5.0, rel=1e-6)


def test_only_drawings_change_their_kind() -> None:
    project = new_project()
    history = History(project.document)
    history.apply("Quader", [OperationDraft(op="create_box", params={"width": 30.0})])
    with pytest.raises(ValidationError):
        history.change_kind(project.document.ops[0].id, "sketch_revolve", {})
