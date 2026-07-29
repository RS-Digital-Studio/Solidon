"""The operations §25 names and the register was missing (§25, §10).

Spiegeln, Netz, Aushöhlen, Elefantenfuß, Senken, Verschließen, Beschriftung,
Zeichnungen. Every one of them is something people otherwise leave the
application for — and every one of them is measured here against a number that
can be worked out by hand, not looked at in a picture.
"""

from __future__ import annotations

import math

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom import mesh_ops
from app.core.geom.hollow import hollow
from app.core.geom.label_ops import outlines
from app.core.geom.mesh import MeshData
from app.core.geom.prepare import compensate_elephant_foot, countersink, plug
from app.core.ingest.outline import extrude, is_outline
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject

SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    b'<path d="M10,10 L90,10 L90,90 L10,90 Z M30,30 L30,70 L70,70 L70,30 Z"/></svg>'
)


def block(width: float = 40.0, depth: float = 40.0, height: float = 40.0) -> MeshData:
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation((0.0, 0.0, height / 2.0))
    return MeshData.of(body)


def run(op: str, entry: SceneObject | None, profile: Profile, **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}),
            inputs=[entry] if entry else [],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


# --- mirroring ------------------------------------------------------------------


def test_mirroring_turns_the_part_over_without_turning_it_inside_out(profile: Profile) -> None:
    """A mirror inverts every triangle — a body with inside-out normals is broken."""
    wedge = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    wedge.apply_translation((15.0, 0.0, 10.0))
    entry = SceneObject(id="obj_1", name="Rechts", mesh=MeshData.of(wedge))

    result = run("mirror_object", entry, profile, axis="x", about="origin")

    mirrored = result.outputs[0].mesh
    assert mirrored.volume == pytest.approx(8000.0), "positive, so not inside out"
    assert mirrored.is_watertight
    assert mirrored.bounds.centre[0] == pytest.approx(-15.0)


# --- the net --------------------------------------------------------------------


def test_decimation_keeps_the_shape_within_a_measured_bound(profile: Profile) -> None:
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=5, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=sphere)

    result = run("decimate_mesh", entry, profile, triangles=2000)

    after = result.outputs[0].mesh
    assert after.triangle_count == 2000
    assert mesh_ops.deviation(sphere, after) < 0.2, "under two tenths on a 40 mm ball"
    assert [finding.code for finding in result.findings] == ["mesh.deviation"]
    assert result.findings[0].values["deviation_mm"] > 0.0, "it says what it cost"


def test_a_small_body_is_left_alone() -> None:
    small = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    assert mesh_ops.decimate(small, 4).triangle_count == small.triangle_count


def test_smoothing_does_not_shrink_the_body(profile: Profile) -> None:
    """Taubin rather than Laplace — ten passes of the latter cost a fit."""
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=sphere)

    result = run("smooth_mesh", entry, profile, iterations=10)

    assert result.outputs[0].mesh.volume == pytest.approx(sphere.volume, rel=0.02)


def test_remeshing_splits_edges_without_moving_anything(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Würfel", mesh=block(20.0, 20.0, 20.0))

    result = run("remesh_mesh", entry, profile, edge=5.0)

    after = result.outputs[0].mesh
    assert after.triangle_count > 12
    assert after.volume == pytest.approx(8000.0), "the shape is untouched"
    assert after.is_watertight


# --- hollowing ------------------------------------------------------------------


def test_hollowing_leaves_the_wall_and_takes_the_rest(profile: Profile) -> None:
    result = hollow(block(), 2.0, vents=1)

    assert result.mesh.is_watertight
    assert result.removed > 30_000.0, "a 40 mm cube has plenty inside"
    assert result.mesh.volume < 64_000.0 * 0.4
    assert len(result.vents) == 1


def test_a_wall_thicker_than_the_body_leaves_nothing_to_take(profile: Profile) -> None:
    thin = MeshData.of(trimesh.creation.box(extents=(6.0, 6.0, 6.0)))

    result = hollow(thin, 5.0)

    assert result.mesh is thin
    assert [finding.code for finding in result.findings] == ["hollow.too_thin"]


def test_hollowing_without_a_vent_is_possible_and_says_nothing_extra(profile: Profile) -> None:
    result = hollow(block(), 2.0, vents=0)

    assert not result.vents
    assert "hollow.no_vent" not in {finding.code for finding in result.findings}


def test_hollow_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())

    result = run("hollow_object", entry, profile, wall=2.0, vents=1)

    assert result.outputs[0].mesh.volume < 30_000.0
    assert "hollow.done" in {finding.code for finding in result.findings}


# --- the first layer ------------------------------------------------------------


def test_the_first_layers_are_pulled_in_by_the_profile_value(profile: Profile) -> None:
    """Rule 7: the value comes from the material, never from a guess."""
    body = block(40.0, 40.0, 10.0)
    entry = SceneObject(id="obj_1", name="Klotz", mesh=body)

    result = run("compensate_first_layer", entry, profile, height=0.6)

    corrected = result.outputs[0].mesh
    assert corrected.volume < body.volume
    lost = body.volume - corrected.volume
    expected = (40.0**2 - (40.0 - 2 * profile.material.elephant_foot) ** 2) * 0.6
    assert lost == pytest.approx(expected, rel=0.15)
    assert "prepare.elephant_foot" in {finding.code for finding in result.findings}


def test_without_a_measured_value_nothing_happens(profile: Profile) -> None:
    import dataclasses

    flat = dataclasses.replace(
        profile, material=dataclasses.replace(profile.material, elephant_foot=0.0)
    )
    body = block()

    corrected, findings = compensate_elephant_foot(body, flat)

    assert corrected is body and not findings


# --- holes ----------------------------------------------------------------------


def test_a_countersink_takes_off_the_cone_of_the_head(profile: Profile) -> None:
    body = block(40.0, 40.0, 10.0)
    diameter, angle = 8.0, 90.0

    result = countersink(body, position=(0.0, 0.0, 10.0), axis="z", diameter=diameter, angle=angle)

    depth = diameter / 2.0 / math.tan(math.radians(angle / 2.0))
    cone = math.pi * (diameter / 2.0) ** 2 * depth / 3.0
    assert body.volume - result.mesh.volume == pytest.approx(cone, rel=0.05)


def test_a_plug_fills_a_bore_and_stays_inside_the_part(profile: Profile) -> None:
    from app.core.geom.prepare import drill

    body = block(40.0, 40.0, 10.0)
    drilled = drill(body, position=(0.0, 0.0, 5.0), axis="z", diameter=6.0, profile=profile).mesh
    assert drilled.volume < body.volume

    filled = plug(drilled, position=(0.0, 0.0, 5.0), axis="z", diameter=6.5)

    assert filled.mesh.volume == pytest.approx(body.volume, rel=0.01)
    assert filled.mesh.bounds.size[2] == pytest.approx(10.0, abs=0.01), "no plug sticking out"


def test_the_hole_operations_are_in_the_register() -> None:
    for name in ("countersink_hole", "plug_hole"):
        assert REGISTRY.get(name).category == "holes"


# --- labels ---------------------------------------------------------------------


def test_a_letter_with_a_hole_comes_out_with_a_hole() -> None:
    """ "o" is two rings, and which one is the hole follows from containment."""
    shapes = outlines("o", 10.0)

    assert shapes
    assert sum(len(entry.interiors) for entry in shapes) == 1


def test_raised_text_adds_exactly_its_own_volume(profile: Profile) -> None:
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate))
    area = sum(shape.area for shape in outlines("M4", 8.0))

    result = run("label_text", entry, profile, text="M4", size=8.0, depth=0.6, z=4.0)

    added = result.outputs[0].mesh.volume - 3200.0
    assert added == pytest.approx(area * 0.6, rel=0.01)
    assert result.outputs[0].mesh.bounds.size[2] == pytest.approx(4.6, abs=0.01)


def test_engraved_text_takes_away_the_same_volume(profile: Profile) -> None:
    """The bug this test is about: a cut that only reaches the overlap is a scratch."""
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate))
    area = sum(shape.area for shape in outlines("M4", 8.0))

    result = run(
        "label_text", entry, profile, text="M4", size=8.0, depth=0.6, mode="engraved", z=4.0
    )

    removed = 3200.0 - result.outputs[0].mesh.volume
    assert removed == pytest.approx(area * 0.6, rel=0.01)
    assert result.outputs[0].mesh.bounds.size[2] == pytest.approx(4.0, abs=0.01), "nothing proud"


def test_a_label_without_text_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Platte", mesh=block())

    with pytest.raises(ValidationError) as problem:
        run("label_text", entry, profile, text="   ", size=8.0)

    assert problem.value.field == "text"


def test_lettering_can_carry_its_own_slot(profile: Profile) -> None:
    """§20: two colours in one file instead of two files.

    The letters go into the union already wearing their slot, and the attribute
    transfer of the boolean brings it out the other side (P9). What the printer
    reads is a 3MF with two groups.
    """
    from app.core.geom.attributes import counts, used_slots

    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Deckel", mesh=MeshData.of(plate))

    result = run("label_text", entry, profile, text="RS", size=10.0, z=4.0, slot=1)

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1)
    assert counts(output.mesh)[1] > 0, "the letters are in the second slot"
    assert [(slot.index, str(slot.name)) for slot in output.material_slots] == [
        (0, "Körper"),
        (1, "Schrift"),
    ]


def test_without_a_slot_the_lettering_stays_one_colour(profile: Profile) -> None:
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Deckel", mesh=MeshData.of(plate))

    result = run("label_text", entry, profile, text="RS", size=10.0, z=4.0)

    assert not result.outputs[0].mesh.slots


def test_a_label_can_be_a_body_of_its_own(profile: Profile) -> None:
    """The other way to two colours: a second file for a printer without an AMS."""
    result = run("create_label", None, profile, text="RS", size=10.0, depth=2.0)

    body = result.outputs[0]
    assert body.name == "RS"
    assert body.mesh.bounds.size[2] == pytest.approx(2.0)
    assert body.mesh.triangle_count > 0


def test_an_empty_label_body_is_a_user_error(profile: Profile) -> None:
    with pytest.raises(ValidationError) as problem:
        run("create_label", None, profile, text="  ", size=10.0)

    assert problem.value.field == "text"


# --- the test piece -------------------------------------------------------------


def drilled_plate() -> MeshData:
    plate = trimesh.creation.box(extents=(80.0, 50.0, 8.0))
    plate.apply_translation((0.0, 0.0, 4.0))
    drill = trimesh.creation.cylinder(radius=3.0, height=40.0)
    drill.apply_translation((25.0, 15.0, 0.0))
    return MeshData.of(trimesh.boolean.difference([plate, drill]))


def test_a_test_piece_is_a_cut_out_of_the_real_part(profile: Profile) -> None:
    """A piece that prints differently from the part would be worse than none."""
    body = drilled_plate()
    entry = SceneObject(id="obj_1", name="Halterung", mesh=body)

    result = run("test_piece", entry, profile, size=20.0, x=25.0, y=15.0, z=4.0)

    piece = result.outputs[0].mesh
    assert piece.bounds.size[0] == pytest.approx(20.0)
    assert piece.bounds.size[2] == pytest.approx(8.0), "the plate is thinner than the window"
    assert piece.is_watertight
    assert piece.volume < body.volume * 0.15, "a tenth of the print time"


def test_the_test_piece_lands_on_the_bed(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Halterung", mesh=drilled_plate())

    result = run("test_piece", entry, profile, size=20.0, x=25.0, y=15.0, z=4.0, on_bed=True)

    assert result.outputs[0].mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)


def test_the_bore_is_still_in_the_piece(profile: Profile) -> None:
    """Otherwise it is a cube, and a cube proves nothing about a fit."""
    entry = SceneObject(id="obj_1", name="Halterung", mesh=drilled_plate())

    result = run("test_piece", entry, profile, size=20.0, x=25.0, y=15.0, z=4.0)

    solid = 20.0 * 20.0 * 8.0
    assert result.outputs[0].mesh.volume < solid * 0.98, "a hole is missing from it"


def test_a_window_over_thin_air_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Halterung", mesh=drilled_plate())

    with pytest.raises(ValidationError) as problem:
        run("test_piece", entry, profile, size=10.0, x=500.0, y=0.0, z=0.0)

    assert problem.value.constraint == "empty"


# --- drawings -------------------------------------------------------------------


def test_a_drawing_becomes_a_body_with_its_holes() -> None:
    result = extrude(SVG, ".svg", 5.0)

    assert result.contours == 1
    assert result.mesh.volume == pytest.approx((80.0**2 - 40.0**2) * 5.0)
    assert result.mesh.is_watertight
    assert result.mesh.bounds.minimum[2] == pytest.approx(0.0), "on the plate"


def test_a_target_width_scales_the_plane_and_not_the_height() -> None:
    result = extrude(SVG, ".svg", 5.0, width=40.0)

    assert result.mesh.bounds.size[0] == pytest.approx(40.0)
    assert result.mesh.bounds.size[2] == pytest.approx(5.0), "the height was asked for in mm"


def test_a_drawing_with_no_closed_area_says_so() -> None:
    open_path = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0,0 L10,10"/></svg>'
    )

    with pytest.raises(ValidationError) as problem:
        extrude(open_path, ".svg", 2.0)

    assert problem.value.constraint == "no_area"


def test_a_drawing_reaches_the_scene_through_load_outline(profile: Profile) -> None:
    """§25: the same way in as every other file — a source and an operation."""
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = SVG
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/logo.svg", sha256=""
    )
    History(project.document).apply(
        "Zeichnung",
        [OperationDraft(op="load_outline", params={"source": "src_1", "height": 4.0})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    entry = result.scene.objects["obj_1"]
    assert entry.mesh.bounds.size[2] == pytest.approx(4.0)
    assert "ingest.extruded" in {finding.code for finding in result.scene.report.findings}


def test_only_flat_formats_go_this_way() -> None:
    assert is_outline(".SVG") and is_outline(".dxf")
    assert not is_outline(".stl")

    with pytest.raises(ValidationError):
        extrude(SVG, ".stl", 2.0)


# --- the register ---------------------------------------------------------------


def test_every_category_of_the_plan_has_something_in_it() -> None:
    """§25 lists what the application can do; an empty category is a gap."""
    filled = {spec.category for spec in REGISTRY.all()}
    for category in ("transform", "mesh", "prepare", "holes", "label", "import", "colour"):
        assert category in filled, category
