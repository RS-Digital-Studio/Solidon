"""Stable feature identifiers, and what happens when they cannot be (§21.2, §21.3)."""

from __future__ import annotations

from pathlib import Path

import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import apply, translation
from app.core.ingest.loader import normalise
from app.core.perceive.features import detect_holes
from app.core.perceive.matching import (
    apply_mapping,
    cost,
    match,
    question_for,
)
from app.core.types import Feature

MESHES = Path(__file__).parent / "data" / "meshes"


def body(name: str) -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def holes_of(mesh: MeshData) -> dict[str, Feature]:
    return {hole.id: hole for hole in detect_holes(mesh)}


def one_hole_plate() -> MeshData:
    """A plate with a single bore in the middle — the "before" of the twin case."""
    plate = trimesh.creation.box(extents=(60.0, 30.0, 8.0))
    drill = trimesh.creation.cylinder(radius=2.6, height=40.0, sections=48)
    return MeshData.of(trimesh.boolean.difference([plate, drill]))


def test_identifiers_survive_an_operation_that_changes_nothing() -> None:
    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    new = holes_of(mesh)

    result = match(old, new, mesh.bounds.centre, mesh.bounds.diagonal)

    assert result.settled
    assert result.mapping == {identifier: identifier for identifier in old}


def test_moving_the_whole_body_does_not_orphan_its_features() -> None:
    """§21.2: position counts in the object's own frame, not the world's."""
    mesh = body("plate_holes.stl")
    moved = apply(mesh, translation((120.0, -40.0, 15.0)))

    result = match(
        holes_of(mesh),
        holes_of(moved),
        moved.bounds.centre,
        moved.bounds.diagonal,
        old_centre=mesh.bounds.centre,
    )

    assert result.settled, "a move is not a reason to lose every identifier"
    assert len(result.mapping) == 4


def test_a_vanished_feature_is_reported_as_orphaned() -> None:
    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    new = {"hole_1": old["hole_1"]}

    result = match(old, new, mesh.bounds.centre, mesh.bounds.diagonal)

    assert len(result.orphaned) == 3
    assert not result.settled


def test_a_new_feature_is_reported_as_fresh() -> None:
    mesh = body("plate_holes.stl")
    all_holes = holes_of(mesh)
    old = {"hole_1": all_holes["hole_1"]}

    result = match(old, all_holes, mesh.bounds.centre, mesh.bounds.diagonal)

    assert len(result.fresh) == 3


def test_two_identical_bores_close_together_are_ambiguous() -> None:
    """§40: plate_holes_twin is reported as ambiguous instead of guessed."""
    before = one_hole_plate()
    after = body("plate_holes_twin.stl")

    result = match(
        holes_of(before),
        holes_of(after),
        after.bounds.centre,
        after.bounds.diagonal,
        old_centre=before.bounds.centre,
    )

    assert result.ambiguous, "one bore in the middle fits both twins equally well"
    assert not result.settled
    candidates = next(iter(result.ambiguous.values()))
    assert len(candidates) >= 2


def test_the_ambiguity_becomes_a_question_with_choices() -> None:
    """§21.3: the evaluation stops there and asks over ctx.ask."""
    question, choices = question_for("hole_1", ("hole_1", "hole_2"))

    assert "hole_1" in question
    assert "hole_1" in choices and "hole_2" in choices
    assert len(choices) == 3, "the candidates plus the way out"


def test_a_different_kind_never_matches() -> None:
    mesh = body("plate_holes.stl")
    hole = next(iter(holes_of(mesh).values()))
    face = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"centre": hole.params["centre"], "normal": hole.params["axis"], "area": 10.0},
    )

    centre = mesh.bounds.centre
    assert cost(hole, face, centre, centre, mesh.bounds.diagonal) > 1000.0


def test_a_bore_that_changed_size_still_matches_if_it_stayed_put() -> None:
    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    widened = {
        identifier: Feature(
            id=identifier,
            kind="hole",
            provenance="detected",
            params={**feature.params, "diameter": feature.params["diameter"] + 0.2},
        )
        for identifier, feature in old.items()
    }

    result = match(old, widened, mesh.bounds.centre, mesh.bounds.diagonal)
    assert result.settled, "widening a hole by a fifth of a millimetre keeps its name"


def test_renaming_carries_the_old_identifiers_over() -> None:
    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    new = {f"detected_{index}": feature for index, feature in enumerate(old.values(), start=1)}

    result = match(old, new, mesh.bounds.centre, mesh.bounds.diagonal)
    renamed = apply_mapping(new, result)

    assert set(renamed) == set(old), "the stack keeps referring to the same names"
    for identifier, feature in renamed.items():
        assert feature.id == identifier


def test_matching_against_nothing_is_not_a_crash() -> None:
    mesh = body("plate_holes.stl")
    holes = holes_of(mesh)

    assert match({}, holes, mesh.bounds.centre, mesh.bounds.diagonal).fresh == tuple(holes)
    assert match(holes, {}, mesh.bounds.centre, mesh.bounds.diagonal).orphaned == tuple(holes)
    assert match({}, {}, mesh.bounds.centre, mesh.bounds.diagonal).settled


def test_identifiers_survive_ten_operations(document, profile) -> None:
    """§40 for P3: after ten steps the bores still carry the names they started with."""
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source
    from app.i18n import _

    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()

    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    sources = ProjectSources(project)
    before = set(evaluate(document, profile, sources=sources).scene.objects["obj_1"].features)

    steps: list[OperationDraft] = [
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 5.0}),
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dy": -3.0}),
        OperationDraft(op="rotate_object", inputs=("obj_1",), params={"axis": "z", "angle": 15.0}),
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dz": 2.0}),
        OperationDraft(op="rotate_object", inputs=("obj_1",), params={"axis": "z", "angle": -15.0}),
        OperationDraft(op="place_on_bed", inputs=("obj_1",), params={}),
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": -5.0}),
        OperationDraft(op="translate_object", inputs=("obj_1",), params={"dy": 3.0}),
        OperationDraft(op="scale_object", inputs=("obj_1",), params={"factor": 1.0}),
        OperationDraft(op="place_on_bed", inputs=("obj_1",), params={}),
    ]
    for step in steps:
        history.apply(_("Schritt"), [step])

    result = evaluate(document, profile, sources=sources)

    assert result.complete
    assert set(result.scene.objects["obj_1"].features) == before
    assert "perceive.orphaned" not in {finding.code for finding in result.scene.report.findings}


def test_features_travel_with_the_motion_the_operation_reports() -> None:
    """§21.2: a turned body is the same body, and the op is what says so."""
    from app.core.geom.ops import as_transform
    from app.core.geom.transform import rotation
    from app.core.perceive.matching import moved_features

    mesh = body("plate_holes.stl")
    old = holes_of(mesh)
    turned = apply(mesh, rotation("z", 15.0))

    carried = moved_features(old, as_transform(rotation("z", 15.0)))
    result = match(carried, holes_of(turned), turned.bounds.centre, turned.bounds.diagonal)

    assert result.settled, "carried along first, every bore finds itself again"
    assert not result.orphaned


def test_without_the_motion_a_rotation_would_lose_them() -> None:
    """Why the matrix is worth carrying: the same case without it."""
    from app.core.geom.transform import rotation

    mesh = body("plate_holes.stl")
    turned = apply(mesh, rotation("z", 40.0))

    result = match(holes_of(mesh), holes_of(turned), turned.bounds.centre, turned.bounds.diagonal)

    assert result.orphaned, "positions alone cannot follow a turn"


def test_a_transform_operation_reports_what_it_did() -> None:
    """The matrix comes from the operation, not from a comparison afterwards."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    mesh = body("cube_clean.stl")
    entry = SceneObject(id="obj_1", name="x", mesh=mesh)
    spec = REGISTRY.get("translate_object")
    context = OpContext(
        scene=Scene(objects={"obj_1": entry}),
        inputs=[entry],
        params=spec.params(dx=5.0, dy=0.0, dz=0.0),
        profile=None,
        quality="fine",
        seed=None,
        progress=lambda fraction, text: None,
        ask=lambda question, choices: choices[0],
        cancelled=NeverCancelled(),
    )

    result = spec.fn(context)

    assert result.transform is not None
    assert result.transform[0][3] == 5.0
