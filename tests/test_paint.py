"""Flächen färben (Bauplan §20, Konzept Filamente).

Bis zum 26.08.2026 stand hier ein Pinsel mit Radius, und der schwere Teil war,
ihn an Kanten anzuhalten. Die Füllung braucht das nicht: Die Grenze der Fläche
kommt aus der Erkennung, und was sie färbt, sind genau deren Dreiecke. Der
größte Teil dieser Datei misst seitdem, dass sie **nur** die färbt — und dass
die Farbe, die ein Filament ohne eigene bekommt, nicht wie eine Auswahl
aussieht.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.attributes import counts, used_slots
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.paint import fill_feature
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import MaterialSlot, OpContext, Profile, Scene, SceneObject
from tests.helpers import exact_kernel


def plate() -> MeshData:
    body = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    body.apply_translation((0.0, 0.0, 5.0))
    return MeshData.of(body)


def ball(subdivisions: int = 3) -> MeshData:
    return MeshData.of(trimesh.creation.icosphere(subdivisions=subdivisions, radius=20.0))


def run(op: str, entry: SceneObject, profile: Profile, *, quality="fine", **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality=quality,
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def _with_top_face(entry: SceneObject, indices: tuple[int, ...]) -> SceneObject:
    """Das Objekt mit einem erkannten Flächenmerkmal über ``indices``."""
    import dataclasses

    from app.core.types import Feature

    face = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"area": 1600.0},
        face_indices=indices,
    )
    return dataclasses.replace(entry, features={"face_1": face})


def _exact_filament_cylinder() -> tuple[SceneObject, str]:
    """Ein exakter Zylinder; die gewählte Deckfläche liegt nachweislich bei z = 20."""
    edit = exact_kernel()
    from app.core.brep.features import features_of

    solid = edit.cylinder(24.0, 20.0)
    features = features_of(solid)
    top = next(
        feature
        for feature in features.values()
        if feature.kind == "face" and feature.params["normal"][2] > 0.9
    )
    return SceneObject("obj_1", "Zylinder", solid, kind="brep", features=features), top.id


def _assert_cylinder_filaments(mesh, top_slot: int, other_slot: int) -> None:
    """Der Sollbereich kommt aus den Koordinaten, nicht aus der nativen Flächenkarte."""
    import numpy as np

    from app.core.geom.mesh import as_mesh_data
    from app.core.units import EPS_GEOM

    data = as_mesh_data(mesh)
    top = np.all(np.abs(data.raw.triangles[:, :, 2] - 20.0) <= EPS_GEOM, axis=1)
    assert top.any() and (~top).any()
    slots = np.asarray(data.slot_indices or (0,) * data.triangle_count)
    assert np.all(slots[top] == top_slot)
    assert np.all(slots[~top] == other_slot)


@pytest.mark.parametrize("quality", ["coarse", "fine"])
def test_exact_filaments_follow_retessellation_and_clear_without_changing_source(
    profile: Profile, quality: str
) -> None:
    """Körper- und Flächenzuweisung bleiben exakt, auch mit vollständig neuen Dreiecken."""
    import io
    import math

    exact_kernel()
    from OCP.BRepTools import BRepTools

    from app.core.brep import step
    from app.core.brep.kernel import Solid

    source, top = _exact_filament_cylinder()
    original = io.BytesIO()
    BRepTools.Write_s(source.mesh.shape, original)
    assigned = run("assign_slot", source, profile, quality=quality, slot=2, name="Blau").outputs[0]
    assert isinstance(assigned.mesh, Solid)
    _assert_cylinder_filaments(assigned.mesh, 2, 2)
    painted = run(
        "paint_slot", assigned, profile, quality=quality, slot=3, name="Rot", at_feature=top
    ).outputs[0]
    assert isinstance(painted.mesh, Solid)
    assert painted.mesh.volume == pytest.approx(math.pi * 12.0**2 * 20.0)
    _assert_cylinder_filaments(painted.mesh, 3, 2)
    coarse = dataclasses.replace(painted.mesh, deflection=0.5)
    fine = dataclasses.replace(painted.mesh, deflection=0.005)
    assert coarse.triangle_count != fine.triangle_count
    _assert_cylinder_filaments(coarse, 3, 2)
    _assert_cylinder_filaments(fine, 3, 2)
    partial = run("clear_filament", painted, profile, quality=quality, at_feature=top).outputs[0]
    assert isinstance(partial.mesh, Solid)
    _assert_cylinder_filaments(dataclasses.replace(partial.mesh, deflection=0.005), 0, 2)
    cleared = run("clear_filament", painted, profile, quality=quality).outputs[0]
    assert isinstance(cleared.mesh, Solid)
    _assert_cylinder_filaments(dataclasses.replace(cleared.mesh, deflection=0.005), 0, 0)
    assert cleared.material_slots == [] and cleared.material is None
    assert step.read(step.write(painted.mesh)).volume == pytest.approx(source.mesh.volume)
    unchanged = io.BytesIO()
    BRepTools.Write_s(source.mesh.shape, unchanged)
    assert unchanged.getvalue() == original.getvalue()
    assert source.mesh.mesh.slots == () and source.material_slots == []
    _assert_cylinder_filaments(assigned.mesh, 2, 2)


@pytest.mark.parametrize("operation", ["paint_slot", "clear_filament"])
def test_exact_filament_never_expands_a_partial_native_face(
    profile: Profile, operation: str
) -> None:
    """Ein einzelnes Dreieck wird beim Qualitätswechsel nicht zur ganzen Deckfläche."""
    source, top = _exact_filament_cylinder()
    face = source.features[top]
    assert len(face.face_indices) > 1
    partial = dataclasses.replace(face, face_indices=face.face_indices[:1])
    source = dataclasses.replace(source, features={**source.features, top: partial})
    # Slot null ist bereits neutral; auch diese Auswahl muss als Teilfläche erkannt werden.
    params = {"at_feature": top, **({"slot": 3} if operation == "paint_slot" else {})}
    with pytest.raises(ValidationError) as failure:
        run(operation, source, profile, **params)
    assert failure.value.suggestions
    assert source.mesh.mesh.slots == ()


def test_exact_clear_preserves_a_used_zero_definition_outside_the_face(profile: Profile) -> None:
    from app.core.brep.kernel import Solid

    source, top = _exact_filament_cylinder()
    assigned = run("assign_slot", source, profile, slot=0, name="Weiß").outputs[0]
    cleared = run("clear_filament", assigned, profile, at_feature=top).outputs[0]
    assert isinstance(cleared.mesh, Solid)
    assert [(slot.index, slot.name) for slot in cleared.material_slots] == [(1, "Weiß")]
    _assert_cylinder_filaments(dataclasses.replace(cleared.mesh, deflection=0.005), 0, 1)


@pytest.mark.parametrize("quality", ["coarse", "fine"])
def test_exact_filament_history_survives_project_cache_undo_and_explicit_mesh_export(
    tmp_path: Path, profile: Profile, quality: str
) -> None:
    """Der echte STEP-Import bleibt nach Zuweisung und Wiederöffnen weiterhin STEP-fähig."""
    from app.core.brep import step
    from app.core.brep.kernel import Solid
    from app.core.geom.mesh import MeshCodec
    from app.core.ingest.plan import import_plan
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import ProjectSources, load, new_project, save
    from app.core.types import Source

    original, _ = _exact_filament_cylinder()
    payload = step.write(original.mesh)
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/coloured.step", sha256=""
    )
    history = History(project.document)
    plan = import_plan("src_1", "coloured.step", payload)
    history.apply(plan.title, [plan.draft])
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))

    def evaluated(current=project):
        result = evaluate(
            current.document, profile, quality=quality, sources=ProjectSources(current), cache=cache
        )
        assert result.complete, result.scene.report.findings
        return result

    before = evaluated()
    body = before.scene.objects["obj_1"]
    top = next(
        feature.id
        for feature in body.features.values()
        if feature.kind == "face" and feature.params["normal"][2] > 0.9
    )
    history.apply(
        "Filamente zuweisen",
        [
            OperationDraft(op="assign_slot", inputs=(body.id,), params={"slot": 2, "name": "Blau"}),
            OperationDraft(
                op="paint_slot",
                inputs=(body.id,),
                params={"slot": 3, "name": "Rot", "at_feature": top},
            ),
        ],
    )
    assigned = evaluated()
    assert isinstance(assigned.scene.objects[body.id].mesh, Solid)
    assert not any(finding.converts_exact_body for finding in assigned.scene.report.findings)
    _assert_cylinder_filaments(assigned.scene.objects[body.id].mesh, 3, 2)
    assert history.undo() is not None
    _assert_cylinder_filaments(evaluated().scene.objects[body.id].mesh, 0, 0)
    assert history.redo() is not None
    _assert_cylinder_filaments(evaluated().scene.objects[body.id].mesh, 3, 2)
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(body.id,), params={"dx": 5.0})],
    )
    moved = evaluated().scene.objects[body.id]
    assert isinstance(moved.mesh, Solid)
    _assert_cylinder_filaments(moved.mesh, 3, 2)
    path = save(project, tmp_path / "filaments.solidon")
    reopened = load(path)
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    fresh = evaluated(reopened).scene.objects[body.id]
    assert isinstance(fresh.mesh, Solid)
    _assert_cylinder_filaments(dataclasses.replace(fresh.mesh, deflection=0.005), 3, 2)
    assert [(slot.index, slot.name) for slot in fresh.material_slots] == [(2, "Blau"), (3, "Rot")]
    roundtrip = step.read(step.write(fresh.mesh))
    assert roundtrip.volume == pytest.approx(original.mesh.volume)
    assert roundtrip.bounds.centre == pytest.approx((5.0, 0.0, 10.0))
    fresh_history = History(reopened.document)
    fresh_history.apply(
        "Vernetzen",
        [OperationDraft(op="brep_to_mesh", inputs=(body.id,), params={"deflection": 0.005})],
    )
    meshed = evaluated(reopened).scene.objects[body.id]
    assert isinstance(meshed.mesh, MeshData)
    _assert_cylinder_filaments(meshed.mesh, 3, 2)
    assert fresh_history.undo() is not None
    assert isinstance(evaluated(reopened).scene.objects[body.id].mesh, Solid)
    assert project.sources["src_1"] == reopened.sources["src_1"] == payload
    _assert_cylinder_filaments(body.mesh, 0, 0)


def test_native_filament_cache_keeps_faces_and_only_persists_explicit_meshes(
    tmp_path: Path, profile: Profile
) -> None:
    """Ein warmer Solid behält Flächenattribute.

    Die Platte speichert erst die bewusste Vernetzung.
    """
    from app.core.brep.kernel import Solid
    from app.core.geom.mesh import MeshCodec
    from app.core.scene.cache import CachedResult, DiskCache, ResultCache

    source, top = _exact_filament_cylinder()
    assigned = run("assign_slot", source, profile, slot=2).outputs[0]
    painted = run("paint_slot", assigned, profile, slot=3, at_feature=top).outputs[0]
    native_key, mesh_key = "a" * 64, "b" * 64
    directory = tmp_path / "cache"
    disk = DiskCache(codec=MeshCodec(), directory=directory)
    cache = ResultCache(disk=disk)
    cache.put(native_key, CachedResult(objects=(painted,)), to_disk=True)
    warm = cache.get(native_key)
    assert warm is not None and cache.statistics.hits == 1
    solid = warm.objects[0].mesh
    assert isinstance(solid, Solid)
    assert solid.face_slots == painted.mesh.face_slots
    assert set(solid.face_slots) == {2, 3}
    _assert_cylinder_filaments(dataclasses.replace(solid, deflection=0.005), 3, 2)
    assert disk.get(native_key) is None
    assert not tuple(directory.rglob("objects.json"))

    converted = dataclasses.replace(painted, mesh=solid.to_mesh(deflection=0.005), kind="mesh")
    cache.put(mesh_key, CachedResult(objects=(converted,)), to_disk=True)
    reopened = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    persisted = reopened.get(mesh_key)
    assert persisted is not None and reopened.statistics.disk_hits == 1
    assert isinstance(persisted.objects[0].mesh, MeshData)
    _assert_cylinder_filaments(persisted.objects[0].mesh, 3, 2)


def _filament_cube(slots: tuple[int, ...], definitions: tuple[int, ...]) -> SceneObject:
    """Der geschlossene 20-mm-Korpuswürfel mit bewusst vorgegebenen Filamentflächen."""
    payload = (Path(__file__).parent / "data" / "meshes" / "cube_clean.stl").read_bytes()
    mesh = read_mesh(payload, ".stl")
    mesh.raw.merge_vertices()
    mesh = dataclasses.replace(mesh, slots=slots)
    return SceneObject(
        id="obj_1",
        name="Würfel",
        mesh=mesh,
        material_slots=[
            MaterialSlot(
                index, f"Filament {index}", material=f"Profil {index}", material_type="PLA"
            )
            for index in definitions
        ],
    )


def test_clear_filament_neutralises_whole_body_without_geometry_changes(profile: Profile) -> None:
    entry = _filament_cube((0, 1) * 6, (0, 1, 7))
    before = entry.mesh
    output = run("clear_filament", entry, profile).outputs[0]
    assert output.mesh.raw is before.raw
    assert output.mesh.volume == pytest.approx(8000)
    assert output.mesh.is_watertight
    assert used_slots(output.mesh) == (0,)
    assert output.material_slots == []
    assert entry.material_slots and entry.mesh.slots == (0, 1) * 6


def test_clearing_legacy_body_material_does_not_reintroduce_a_slot_on_export(
    profile: Profile,
) -> None:
    from app.core.export.threemf import slots_for_object

    entry = dataclasses.replace(_filament_cube((), ()), material="abs")
    output = run("clear_filament", entry, profile).outputs[0]
    assert output.material is None
    assert slots_for_object(output) == ()


def test_clearing_legacy_material_on_one_face_keeps_other_faces_assigned(profile: Profile) -> None:
    from app.core.export.threemf import slots_for_object

    entry = dataclasses.replace(_with_top_face(_filament_cube((), ()), (0, 1)), material="abs")
    previous = slots_for_object(entry)[0]
    output = run("clear_filament", entry, profile, at_features=("face_1",)).outputs[0]
    assert output.material is None
    assert counts(output.mesh) == {0: 2, 1: 10}
    assert slots_for_object(output) == (dataclasses.replace(previous, index=1),)


def test_feature_group_preselection_uses_semantic_ids(profile: Profile) -> None:
    from app.core.scene.placement import values_for

    entry = _with_top_face(_filament_cube((), ()), (0, 1))
    assert values_for(REGISTRY.get("clear_filament"), entry.features["face_1"]) == {
        "at_features": ("face_1",)
    }


def test_clear_face_preserves_other_faces_sharing_assigned_slot_zero(profile: Profile) -> None:
    entry = _with_top_face(_filament_cube((), (0,)), (0, 1))
    output = run("clear_filament", entry, profile, at_feature="face_1").outputs[0]
    assert output.mesh.slots[:2] == (0, 0)
    assert output.mesh.slots[2:] == (1,) * 10
    assert output.material_slots == [dataclasses.replace(entry.material_slots[0], index=1)]
    assert output.features == entry.features
    assert output.mesh.raw is entry.mesh.raw
    assert output.mesh.volume == pytest.approx(8000)


def test_clear_face_reuses_a_slot_freed_by_the_same_removal(profile: Profile) -> None:
    slots = (0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 2, 3)
    entry = _with_top_face(_filament_cube(slots, tuple(range(8))), (3, 11))
    output = run("clear_filament", entry, profile, at_feature="face_1").outputs[0]
    assert output.mesh.slots == (3, 1, 2, 0, 4, 5, 6, 7, 3, 1, 2, 0)
    definitions = {slot.index: slot for slot in output.material_slots}
    assert 0 not in definitions
    assert definitions[3] == dataclasses.replace(entry.material_slots[0], index=3)
    for index in (1, 2, 4, 5, 6, 7):
        assert definitions[index] == entry.material_slots[index]


def test_clear_face_at_full_eight_slot_limit_never_changes_other_filaments(
    profile: Profile,
) -> None:
    slots = (0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 2, 3)
    entry = _with_top_face(_filament_cube(slots, tuple(range(8))), (0,))
    with pytest.raises(ValidationError) as raised:
        run("clear_filament", entry, profile, at_feature="face_1")
    assert raised.value.constraint == "slots_full"
    assert raised.value.suggestions
    assert entry.mesh.slots == slots
    assert len(entry.material_slots) == 8


def test_clearing_two_features_together_frees_zero_at_full_eight_slot_limit(
    profile: Profile,
) -> None:
    """Beide Hälften desselben Filaments geben seinen Platz gemeinsam frei."""
    slots = (0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 2, 3)
    entry = _with_top_face(_filament_cube(slots, tuple(range(8))), (0,))
    entry.features["face_2"] = dataclasses.replace(
        entry.features["face_1"], id="face_2", face_indices=(8,)
    )
    output = run("clear_filament", entry, profile, at_features=("face_1", "face_2")).outputs[0]
    assert output.mesh.slots == slots
    assert output.material_slots == entry.material_slots[1:]
    assert output.mesh.raw is entry.mesh.raw
    assert output.mesh.volume == pytest.approx(8000)


def test_clearing_feature_group_preserves_unselected_faces_of_the_same_filament(
    profile: Profile,
) -> None:
    """Merkmale bestimmen die Auswahl, nicht alle Dreiecke ihres bisherigen Filaments."""
    entry = _with_top_face(_filament_cube((), (0,)), (0,))
    entry.features["face_2"] = dataclasses.replace(
        entry.features["face_1"], id="face_2", face_indices=(8,)
    )
    output = run("clear_filament", entry, profile, at_features=("face_1", "face_2")).outputs[0]
    assert {index for index, slot in enumerate(output.mesh.slots) if slot == 0} == {0, 8}
    assert counts(output.mesh) == {0: 2, 1: 10}
    assert output.material_slots == [dataclasses.replace(entry.material_slots[0], index=1)]


def test_clearing_feature_group_rejects_one_missing_feature_without_partial_result(
    profile: Profile,
) -> None:
    entry = _with_top_face(_filament_cube((), (0,)), (0,))
    with pytest.raises(ValidationError) as caught:
        run("clear_filament", entry, profile, at_features=("face_1", "face_missing"))
    assert caught.value.constraint == "unknown_feature"
    assert entry.mesh.slots == ()
    assert entry.material_slots[0].index == 0


def test_clear_face_ignores_orphaned_slot_definitions_when_finding_space(profile: Profile) -> None:
    entry = _with_top_face(_filament_cube((), tuple(range(8))), (0, 1))
    output = run("clear_filament", entry, profile, at_feature="face_1").outputs[0]
    assert counts(output.mesh) == {0: 2, 1: 10}
    assert output.material_slots == [dataclasses.replace(entry.material_slots[0], index=1)]


def test_clear_face_can_reuse_an_identical_filament_when_all_slots_are_occupied(
    profile: Profile,
) -> None:
    entry = _with_top_face(
        _filament_cube((0, 1, 2, 3, 4, 5, 6, 7, 0, 1, 2, 3), tuple(range(8))), (0,)
    )
    entry.material_slots[1] = dataclasses.replace(entry.material_slots[0], index=1)
    output = run("clear_filament", entry, profile, at_feature="face_1").outputs[0]
    assert output.mesh.slots == (0, 1, 2, 3, 4, 5, 6, 7, 1, 1, 2, 3)
    assert output.material_slots == entry.material_slots[1:]


def test_clear_feature_preserves_cavity_and_ignores_stale_face_indices(profile: Profile) -> None:
    entry = _with_top_face(_filament_cube((), (0,)), (0, 1, 999))
    entry.mesh = dataclasses.replace(entry.mesh, cavity=plate())
    output = run("clear_filament", entry, profile, at_feature="face_1").outputs[0]
    assert counts(output.mesh) == {0: 2, 1: 10}
    assert output.mesh.cavity is entry.mesh.cavity


def test_clear_filament_rejects_a_non_face_feature(profile: Profile) -> None:
    entry = _with_top_face(_filament_cube((), (0,)), (0, 1))
    entry.features["face_1"] = dataclasses.replace(entry.features["face_1"], kind="hole")
    with pytest.raises(ValidationError) as raised:
        run("clear_filament", entry, profile, at_feature="face_1")
    assert raised.value.constraint == "feature_kind"


def test_clearing_an_already_neutral_face_does_not_create_a_filament(profile: Profile) -> None:
    entry = _with_top_face(_filament_cube((), ()), (0, 1))
    output = run("clear_filament", entry, profile, at_feature="face_1").outputs[0]
    assert output.material_slots == []
    assert used_slots(output.mesh) == (0,)
    assert output.mesh.raw is entry.mesh.raw


@pytest.mark.parametrize("indices", [(), (999,), (-1,)])
def test_clear_missing_feature_geometry_is_an_actionable_rejection(
    profile: Profile, indices
) -> None:
    entry = _with_top_face(_filament_cube((), (0,)), indices)
    with pytest.raises(ValidationError) as raised:
        run("clear_filament", entry, profile, at_feature="face_1")
    assert raised.value.suggestions
    assert entry.mesh.slots == ()


def test_clear_unknown_feature_is_an_actionable_rejection(profile: Profile) -> None:
    entry = _filament_cube((), (0,))
    with pytest.raises(ValidationError) as raised:
        run("clear_filament", entry, profile, at_feature="missing")
    assert raised.value.constraint == "unknown_feature"
    assert raised.value.suggestions


# --- Die Füllung: was sie färbt -------------------------------------------------


def test_the_colour_field_takes_up_to_four_colours() -> None:
    """``#RRGGBB #RRGGBB``: dieselbe Schreibweise wie die Orca-Familie, damit
    der Wert ohne Umrechnung hinausgeht. Die erste ist die Farbe des Slots,
    die weiteren stehen in ``extra_colours``; leer bleibt leer."""
    from app.core.errors import ValidationError
    from app.core.geom.colour_ops import colour_from, colours_from

    assert colours_from("") == ()
    assert colour_from("") is None
    assert colours_from("#ff0000") == ((1.0, 0.0, 0.0),)
    assert colours_from("#ff0000 #0000ff  #00ff00") == (
        (1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0),
        (0.0, 1.0, 0.0),
    )
    assert colour_from("#ff0000 #0000ff") == (1.0, 0.0, 0.0), "die erste ist die Farbe"
    with pytest.raises(ValidationError) as too_many:
        colours_from("#ff0000 #0000ff #00ff00 #ffff00 #00ffff")
    assert too_many.value.constraint == "range"
    with pytest.raises(ValidationError) as wrong:
        colours_from("#ff0000 rot")
    assert wrong.value.constraint == "format"


def test_assigning_a_filament_with_several_colours_keeps_them_on_the_slot(
    profile: Profile,
) -> None:
    """*Filament zuweisen* und *Filament auf eine Fläche* tragen alle Farben
    in den Slot — sonst käme im Export nur die erste an."""
    body = SceneObject(id="obj_1", name="Teil", mesh=plate())
    result = run("assign_slot", body, profile, slot=1, name="Silk Dual", colour="#ff0000 #0000ff")
    slot = result.outputs[0].material_slots[-1]
    assert slot.colour == (1.0, 0.0, 0.0)
    assert slot.extra_colours == ((0.0, 0.0, 1.0),)

    painted = run(
        "paint_slot",
        _with_top_face(body, (0, 1)),
        profile,
        slot=2,
        at_feature="face_1",
        colour="#00ff00 #ff00ff #000000",
    )
    face_slot = painted.outputs[0].material_slots[-1]
    assert face_slot.index == 2
    assert face_slot.extra_colours == ((1.0, 0.0, 1.0), (0.0, 0.0, 0.0))


def test_filling_paints_the_face_and_nothing_else() -> None:
    """Der Punkt der ganzen Sache: Die Grenze kommt aus der Erkennung.

    Ein Pinsel mit Radius brauchte einen Kantenwinkel, damit die Farbe nicht um
    die Ecke lief; die Fläche weiß selbst, wo sie aufhört (``face_indices``).
    """
    filled = fill_feature(plate(), (0, 1), slot=1)

    assert counts(filled.mesh) == {0: 10, 1: 2}, "the top face, and nothing else"
    assert filled.painted == 2, "der Befund zählt den Strich, nicht den Bestand"


def test_filling_everything_is_a_matter_of_the_indices() -> None:
    """Kein Sonderfall, kein Winkel von 180 Grad: Wer alle Dreiecke nennt,
    färbt alle."""
    body = plate()

    filled = fill_feature(body, tuple(range(body.triangle_count)), slot=1)

    assert used_slots(filled.mesh) == (1,)


def test_filling_does_not_move_a_single_point() -> None:
    """§20: der Slot ist ein Attribut. Farbe ist keine Geometrie."""
    before = plate()

    filled = fill_feature(before, (0, 1), slot=2)

    assert filled.mesh.raw is before.raw
    assert filled.mesh.volume == before.volume


def test_a_second_fill_does_not_undo_the_first() -> None:
    once = fill_feature(plate(), (0, 1), slot=1)

    twice = fill_feature(once.mesh, (2, 3), slot=2)

    assert used_slots(twice.mesh) == (0, 1, 2), "zwei gefärbte Flächen und der Rest"


def test_indices_beyond_the_mesh_are_skipped_not_fatal() -> None:
    """Ein Merkmal einer früheren Auswertung kann mehr Dreiecke kennen, als das
    Netz nach einer Änderung noch hat — der Rest der Fläche ist trotzdem
    gemeint."""
    filled = fill_feature(plate(), (0, 1, 999), slot=1)

    assert filled.painted == 2


# --- Als Operation ---------------------------------------------------------------


def test_painting_runs_as_an_operation(profile: Profile) -> None:
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))

    result = run("paint_slot", entry, profile, slot=1, at_feature="face_1", name="Rot")

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1)
    assert [slot.name for slot in output.material_slots] == ["Rot"]
    assert [finding.code for finding in result.findings] == ["colour.painted"]


def test_painting_one_legacy_abs_face_keeps_abs_on_the_unselected_faces(profile: Profile) -> None:
    from app.core.export.threemf import slots_for_object

    entry = dataclasses.replace(_with_top_face(_filament_cube((), ()), (0, 1)), material="abs")
    legacy = slots_for_object(entry)[0]
    output = run(
        "paint_slot",
        entry,
        profile,
        at_feature="face_1",
        slot=1,
        material_type="PETG",
        replace_filament=True,
    ).outputs[0]
    exported = {slot.index: slot for slot in slots_for_object(output)}
    assert exported[0] == legacy
    assert exported[1].material_type == "PETG"
    assert counts(output.mesh) == {0: 10, 1: 2}


def test_explicit_unknown_spool_does_not_inherit_replaced_material(profile: Profile) -> None:
    """Eine neue unbekannte Spule erbt kein PLA vom belegten Farbplatz."""
    from app.core.types import MaterialSlot

    entry = _with_top_face(
        SceneObject(
            id="obj_1",
            name="Deckel",
            mesh=plate(),
            material_slots=[MaterialSlot(1, "Alt", (1.0, 0.0, 0.0), "PLA Profil", "PLA")],
        ),
        (0, 1),
    )
    params = {"slot": 1, "at_feature": "face_1", "name": "Unbekannte Rolle", "colour": "#123456"}
    old = run("paint_slot", entry, profile, **params).outputs[0]
    assert old.material_slots[0].material_type == "PLA", "bestehende Projekte rechnen unverändert"
    new = run("paint_slot", entry, profile, **params, replace_filament=True).outputs[0]
    assert new.material_slots[0].material_type is None
    assert new.material_slots[0].material is None
    assert counts(new.mesh) == {0: 10, 1: 2}
    assert new.mesh.volume == pytest.approx(entry.mesh.volume)


def test_painting_keeps_the_slicer_identity_with_the_colour(profile: Profile) -> None:
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))

    output = run(
        "paint_slot",
        entry,
        profile,
        slot=1,
        at_feature="face_1",
        name="Werkstattrolle",
        colour="#9AA0A6",
        material_type="PETG",
        slicer_profile="Elegoo PETG PRO @ECC2",
    ).outputs[0]

    slot = output.material_slots[0]
    assert slot.material_type == "PETG"
    assert slot.material == "Elegoo PETG PRO @ECC2"


@pytest.mark.parametrize(
    "profile_path",
    [r"C:\Slicer\PETG.json", "/profiles/PETG.json", "../PETG.json", "profiles/../PETG.json"],
)
def test_painting_rejects_a_slicer_profile_path(profile: Profile, profile_path: str) -> None:
    """Auch die Flächenoperation speichert keinen rechnergebundenen Pfad."""
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))

    with pytest.raises(ValidationError) as raised:
        run(
            "paint_slot",
            entry,
            profile,
            slot=1,
            at_feature="face_1",
            slicer_profile=profile_path,
        )

    assert raised.value.field == "slicer_profile"
    assert raised.value.suggestions


def test_painting_without_a_face_stops_with_advice(profile: Profile) -> None:
    """Der Punkt-Pinsel ist entfallen — ohne Fläche gibt es nichts zu färben,
    und das sagt die Operation, statt still nichts zu tun."""
    entry = SceneObject(id="obj_1", name="Deckel", mesh=plate())

    with pytest.raises(ValidationError) as raised:
        run("paint_slot", entry, profile, slot=1)

    assert raised.value.suggestions, "Regel 17: auch diese Ausnahme trägt Handlungen"


def test_the_slot_keeps_the_name_it_was_given(profile: Profile) -> None:
    """Eine zweite Füllung in denselben Slot darf ihn nicht umbenennen."""
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))
    first = run("paint_slot", entry, profile, slot=1, at_feature="face_1", name="Rot").outputs[0]

    second = run("paint_slot", first, profile, slot=1, at_feature="face_1").outputs[0]

    assert [slot.name for slot in second.material_slots] == ["Rot"]


def test_no_fallback_colour_can_be_mistaken_for_the_selection() -> None:
    """Roberts Befund vom 26.08.2026, als Zusage: Die erste Bemalung, die je
    ein Kunde sah, war ein Orange mit Kontrast 1,09 zur Auswahlfarbe — bemalt
    und ausgewählt waren dasselbe Bild.

    Die Leiter ist seitdem grau (Konzept Filamente); echte Farben kommen vom
    Kunden. Geprüft werden die drei Abstände, an denen die alte Palette
    scheiterte: zur Auswahl, zur Körperfarbe, und der Stufen untereinander —
    zwei farblose Filamente, die gleich aussehen, zeigen ihr Teil erst im
    Slicer zweifarbig.
    """
    from itertools import combinations

    from app.ui.theme import SLOT_COLOURS, contrast_ratio
    from app.ui.viewport import OBJECT_COLOUR

    def spread(colour: str) -> int:
        """Wie bunt eine Farbe ist: der Abstand ihres größten und kleinsten
        Kanals. Null ist reines Grau, die Auswahlfarbe liegt bei 166."""
        channels = [int(colour[index : index + 2], 16) for index in (1, 3, 5)]
        return max(channels) - min(channels)

    for colour in SLOT_COLOURS:
        # Nicht über die Helligkeit gemessen, sondern über die Buntheit: Ein
        # Grau und ein sattes Orange gleicher Helligkeit sind klar zu
        # unterscheiden — der alte Fehler war gleicher Ton UND gleiche
        # Helligkeit. Die Leiter bleibt unbunt, die Auswahl ist es nie.
        assert spread(colour) <= 24, (
            f"{colour} ist keine Graustufe mehr — bunt gehört dem Kunden und der Auswahl"
        )
        assert contrast_ratio(colour, OBJECT_COLOUR) >= 1.25, (
            f"{colour} liegt zu nah an der Körperfarbe — Färben wäre unsichtbar"
        )
    for first, second in combinations(SLOT_COLOURS, 2):
        assert contrast_ratio(first, second) >= 1.1, (
            f"{first} und {second} sind im Bild nicht zu unterscheiden"
        )


# --- die Merkmal-Füllung (Konzept Filamente, 26.08.2026) --------------------------


def test_filling_a_feature_paints_exactly_its_triangles(profile: Profile) -> None:
    """Der Kern des Umbaus: Rechtsklick auf „Oberseite" färbt die Oberseite.

    Kein Radius, kein Klickpunkt — die Dreiecke kommen aus dem Merkmal
    (``face_indices``), und damit wandert die Färbung mit, wenn ein früherer
    Schritt die Maße ändert. Ein gespeicherter Punkt läge dann daneben.
    """
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1, 4))

    result = run("paint_slot", entry, profile, slot=2, at_feature="face_1", name="Weiß")

    slots = result.outputs[0].mesh.slots
    assert slots is not None
    painted = {index for index, slot in enumerate(slots) if slot == 2}
    assert painted == {0, 1, 4}, "genau die Dreiecke des Merkmals, keines mehr, keines weniger"
    assert [finding.code for finding in result.findings] == ["colour.painted"]
    assert [slot.name for slot in result.outputs[0].material_slots] == ["Weiß"]


def test_an_unknown_feature_stops_with_advice(profile: Profile) -> None:
    """Ein Merkmal, das es am Körper nicht gibt, ist ein Halt mit Vorschlag —
    nicht ein stilles Nichtstun und nicht ein Rückfall auf irgendeinen Punkt."""
    from app.core.errors import ValidationError

    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))

    with pytest.raises(ValidationError) as raised:
        run("paint_slot", entry, profile, slot=1, at_feature="face_99")

    assert raised.value.suggestions, "Regel 17: auch diese Ausnahme trägt Handlungen"
    assert raised.value.values.get("feature") == "face_99"


def test_a_feature_without_triangles_says_so(profile: Profile) -> None:
    """Eine offene Kantenschleife hat keine eigenen Dreiecke — gefärbt wird
    nichts, und das steht als Befund da statt als stiller Erfolg."""
    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), ())

    result = run("paint_slot", entry, profile, slot=1, at_feature="face_1")

    assert result.outputs[0] is entry, "nothing changed, so nothing is replaced"
    assert [finding.code for finding in result.findings] == ["colour.nothing_painted"]


# --- die Leiste -----------------------------------------------------------------


def test_two_painted_slots_do_not_look_the_same(profile: Profile) -> None:
    """Bemalen war im Bild folgenlos.

    Der Pinsel legt einen Slot ohne Farbe an (``colour=None``) — dieselbe Lücke
    hat die Schrift und „Slot zuweisen" mit leerem Feld. Die Ansicht nahm für
    einen Slot ohne Farbe die Körperfarbe, und damit standen in der Farbtabelle
    zwei gleiche Einträge: Wer zweifarbig bemalte, sah das Ergebnis zum ersten
    Mal im Slicer. Genau das, was der Docstring von ``_slot_colours`` als
    behoben beschreibt — behoben war es nur für Slots, die schon eine Farbe
    hatten.

    Geprüft wird die Tabelle und nicht das Bild: Offscreen gibt es keinen
    Renderer, und die Aussage steckt in den Farben, nicht im Rendern.
    """
    from app.ui.theme import SLOT_COLOURS, slot_colour

    entry = _with_top_face(SceneObject(id="obj_1", name="Deckel", mesh=plate()), (0, 1))
    first = run("paint_slot", entry, profile, slot=1, at_feature="face_1").outputs[0]
    # Eine **zweite** Fläche in den zweiten Slot: Dieselbe Fläche noch einmal
    # zu färben ließe Slot 1 ohne Dreieck, und der fällt seit dem 22.09.2026
    # aus der Liste (``merged_slots(..., used=...)``).
    second = _with_top_face(first, (2, 3))
    painted = run("paint_slot", second, profile, slot=2, at_feature="face_1").outputs[0]

    assert [slot.colour for slot in painted.material_slots] == [None, None], (
        "der Pinsel setzt keine Farbe — genau darum geht es hier"
    )
    colours = [slot_colour(slot.index) for slot in painted.material_slots]
    assert len(set(colours)) == len(colours), "zwei bemalte Slots bekommen dieselbe Farbe"
    assert all(colour in SLOT_COLOURS for colour in colours)
    assert slot_colour(0) is None, "Slot 0 ist das unbemalte Teil und behält seine Farbe"


def test_a_chosen_colour_wins_over_an_existing_slot() -> None:
    """Wer eine Fläche färbt, hat gerade ein Filament gewählt (§20).

    ``paint_slot`` legte den Slot mit ``setdefault`` an — damit gewann der
    **Bestand**: Färbte man eine zweite Fläche in denselben Slot, blieb dessen
    alter, oft leerer Eintrag stehen, und die eben gewählte Farbe verschwand.
    Am laufenden Fenster sah das so aus: Der Wähler zeigte Rot, und nach dem
    Abwählen war das Teil grau (Robert, 27.08.2026).

    ``assign_slot`` nebenan tat es die ganze Zeit richtig; seine Funktion wird
    jetzt geteilt statt verdoppelt.
    """
    from app.core.geom.colour_ops import merged_slots
    from app.core.types import MaterialSlot

    bestand = [MaterialSlot(index=1, name="", colour=None)]
    gewaehlt = [MaterialSlot(index=1, name="Rot", colour=(0.8, 0.13, 0.13))]

    ergebnis = merged_slots(bestand, gewaehlt)
    assert ergebnis[0].colour == (0.8, 0.13, 0.13), "die Wahl gewinnt, nicht der Bestand"
    assert ergebnis[0].name == "Rot"

    # Und ein Slot, den dieser Schritt nicht anfasst, bleibt unberührt.
    mit_zweitem = merged_slots(
        [MaterialSlot(index=2, name="Weiß", colour=(1.0, 1.0, 1.0)), *bestand], gewaehlt
    )
    weiss = next(s for s in mit_zweitem if s.index == 2)
    assert weiss.colour == (1.0, 1.0, 1.0), "fremde Filamente bleiben, wie sie waren"


def test_the_slot_names_of_lettering_and_texture_follow_the_language(profile: Profile) -> None:
    """Dieselbe Falle wie beim Vorgabenamen, an zwei weiteren Stellen.

    *Text aufbringen* mit eigenem Slot legte „Körper" und „Schrift" als
    ``str(_(…))`` ab, *Textur in Filamente umrechnen* seine Farben als
    ``tr('Farbe')`` — beide in der Sprache, die beim Rechnen eingestellt war,
    und der Ergebnis-Cache hielt sie dort fest. Dazu hieß die Spule der
    Schrift im Englischen „Font": Das Wort ist dasselbe wie der Titel des
    Feldes *Schrift*, gemeint war die Beschriftung.
    """
    import numpy as np

    from app.i18n import SOURCE_LANGUAGE, get_language, set_language
    from app.i18n.catalog import install_language

    install_language("fr")
    vorher = get_language()
    try:
        set_language("fr")
        lettered = run(
            "label_text",
            SceneObject(id="obj_1", name="Platte", mesh=plate()),
            profile,
            text="M4",
            size=8.0,
            depth=0.6,
            z=10.0,
            slot=2,
        ).outputs[0]
        coloured = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
        colours = np.zeros((len(coloured.faces), 4), dtype=np.uint8)
        colours[:, 3] = 255
        colours[: len(colours) // 2, 0] = 255
        colours[len(colours) // 2 :, 2] = 255
        coloured.visual.face_colors = colours
        textured = run(
            "slots_from_texture",
            SceneObject(id="obj_2", name="Würfel", mesh=MeshData.of(coloured)),
            profile,
            filaments=2,
        ).outputs[0]

        set_language(SOURCE_LANGUAGE)
        names = {entry.index: str(entry.name) for entry in lettered.material_slots}
        assert names == {0: "Körper", 2: "Beschriftung"}, names
        assert sorted(str(entry.name) for entry in textured.material_slots) == [
            "Farbe 1",
            "Farbe 2",
        ]
        set_language("fr")
        assert str(lettered.material_slots[1].name) != "Beschriftung", "und wandert mit"
        assert str(textured.material_slots[0].name) == "Couleur 1"
    finally:
        set_language(vorher)


def test_a_default_slot_name_follows_the_language(profile: Profile) -> None:
    """Der Vorgabename eines Filaments wandert mit der Sprache — auch aus dem Cache.

    **Er tat es nicht.** Beide Operationen bauten ihn als
    ``f"{_('Slot').translate()} {slot}"``: Die Übersetzung entstand beim
    Rechnen und wurde damit zu einer festen Zeichenkette in der Sprache, die
    gerade eingestellt war. Der Ergebnis-Cache kennt die Sprache nicht — wer
    ein Projekt auf Deutsch rechnete und danach auf Englisch umstellte, behielt
    „Slot 2"; umgekehrt stand „Emplacement 2" im deutschen Fenster. Ein Fehler,
    den nur ein **warmer** Cache zeigt.

    Geprüft wird die ganze Kette und nicht nur der Text: erst die beiden
    Operationen, dann die Runde durch die Ablage. Der mittlere Schritt ist der,
    an dem es hing — ``_name_to_data`` legte Message-ID und Kontext ab, und die
    Zahl fiel dabei heraus. Aus dem Cache kam dann ein Name mit sichtbarem
    ``{number}`` zurück.
    """
    from app.core.scene.cache import _name_from_data, _name_to_data
    from app.i18n import SOURCE_LANGUAGE, get_language, set_language
    from app.i18n.catalog import install_language

    plain = SceneObject(id="obj_1", name="Platte", mesh=plate())
    assigned = run("assign_slot", plain, profile, slot=2).outputs[0]
    slot = next(entry for entry in assigned.material_slots if entry.index == 2)

    faced = _with_top_face(SceneObject(id="obj_2", name="Platte", mesh=plate()), (0, 1))
    painted = run("paint_slot", faced, profile, slot=3, at_feature="face_1").outputs[0]
    filament = next(entry for entry in painted.material_slots if entry.index == 3)

    vorher = get_language()
    try:
        set_language(SOURCE_LANGUAGE)
        assert str(slot.name) == "Slot 2", "in der Quellsprache steht die Zahl im Text"
        assert str(filament.name) == "Filament 3"

        install_language("fr")
        set_language("fr")
        assert str(slot.name) == "Emplacement 2", "und wandert mit der Sprache"
        assert str(filament.name) == "Filament 3", "französisch gleichlautend, aber übersetzt"

        # Und dieselbe Runde durch die Ablage, in der der Name als Message-ID
        # und Werte liegt — nicht als fertiger Satz.
        abgelegt = _name_to_data(slot.name)
        assert abgelegt == {"msgid": "Slot {number}", "context": None, "values": {"number": 2}}
        zurueck = _name_from_data(abgelegt)
        assert str(zurueck) == "Emplacement 2", "aus dem Cache in der jetzigen Sprache"

        set_language(SOURCE_LANGUAGE)
        assert str(zurueck) == "Slot 2", "und nach dem Umschalten in der neuen"
    finally:
        set_language(vorher)


def test_a_filament_no_triangle_uses_any_more_leaves_the_body(profile: Profile) -> None:
    """Was keine Fläche mehr trägt, steht nicht mehr in der Filamentliste des Körpers.

    Bis zum 22.09.2026 hängten *Filament zuweisen*, *Filament auf eine
    Fläche* und *Textur in Filamente umrechnen* ihre Wahl an die bisherige
    Liste an und behielten alles andere: Wer ein Teil erst rot und dann blau
    zuwies, trug danach Rot und Blau, und die 3MF-Baugruppe schrieb beide
    als Filament — der Slicer fragte nach einer Spule, die kein Dreieck
    braucht. *Filament entfernen* räumte schon auf; jetzt tun es alle vier.
    """
    from app.core.export.threemf import AssemblyPart, merge_slots
    from app.core.geom.mesh import as_mesh_data

    plain = SceneObject(id="obj_1", name="Platte", mesh=plate())
    red = run("assign_slot", plain, profile, slot=1, name="Rot", colour="#ff0000").outputs[0]
    blue = run("assign_slot", red, profile, slot=2, name="Blau", colour="#0000ff").outputs[0]
    assert [slot.index for slot in blue.material_slots] == [2]

    faced = _with_top_face(blue, tuple(range(as_mesh_data(blue.mesh).triangle_count)))
    green = run(
        "paint_slot", faced, profile, slot=3, name="Grün", colour="#00ff00", at_feature="face_1"
    ).outputs[0]
    assert [slot.index for slot in green.material_slots] == [3], "alle Flächen sind grün"

    part = AssemblyPart(
        name="Platte",
        mesh=as_mesh_data(green.mesh),
        slots=tuple(green.material_slots),
    )
    assert [str(slot.name) for slot in merge_slots([part])] == ["Grün"]
