"""Dichtnut und getrennte Dichtung am realen Träger mit geometrischer Gegenprüfung."""

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.seal_ops import CreateSealParams, create_seal
from app.core.scene.cancel import NeverCancelled
from app.core.sketch import shapes
from app.core.sketch.profile import profile_of
from app.core.sketch.serialize import sketch_to_text
from app.core.sketch.solver import solve_sketch
from app.core.types import Feature, OpContext, Scene, SceneObject


def cube(kind="mesh"):
    if kind == "brep":
        from app.core.brep import edit, profiles

        body = edit.moved(
            profiles.extrude(profile_of(solve_sketch(shapes.rectangle(20, 20))), 20), (0, 0, -10)
        )
    else:
        body = MeshData.of(trimesh.load_mesh(Path(__file__).parent / "data/meshes/cube_clean.stl"))
    return SceneObject("body", "Träger", body, kind=kind)


def run(entry, *, counter=None, profile=None, quality="fine", ask=None, **changes):
    params = CreateSealParams(
        **{
            "path_sketch": sketch_to_text(shapes.circle(10)),
            "groove_width": 2,
            "groove_depth": 2,
            "gasket_width": 1.6,
            "protrusion": 0.4,
            "body_material": "petg",
            "gasket_material": "tpu-95a",
            **changes,
        }
    )
    scene = Scene(objects={entry.id: entry})
    if counter is not None:
        scene.objects[counter.id] = counter
    return create_seal(
        OpContext(
            scene,
            [entry],
            params,
            profile,
            quality,
            None,
            lambda *args: None,
            ask or (lambda question, choices: choices[0]),
            NeverCancelled(),
        )
    )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_one_transaction_produces_real_groove_and_separate_material(kind, profile):
    entry = cube(kind)
    result = run(entry, profile=profile)
    carrier, gasket = result.outputs
    assert len(result.outputs) == 2
    assert carrier.kind == kind
    assert entry.mesh.volume == pytest.approx(8000)
    assert entry.material is None
    assert carrier.material == "petg" and gasket.material == "tpu-95a"
    assert 8000 - carrier.mesh.volume == pytest.approx(math.pi * 10 * 2 * 2, rel=0.003)
    assert gasket.mesh.volume == pytest.approx(math.pi * 10 * 1.6 * 2.4, rel=0.003)
    assert gasket.mesh.bounds.minimum[2] == pytest.approx(8)
    assert gasket.mesh.bounds.maximum[2] == pytest.approx(10.4)
    for output in result.outputs:
        mesh = as_mesh_data(output.mesh)
        assert mesh.is_watertight and mesh.component_count == 1
    assert "groove_floor" in carrier.features
    assert "gasket_contact" in gasket.features
    assert any(f.code == "seal.uncompressed" for f in result.findings)


@pytest.mark.parametrize(
    "changes",
    [
        {"groove_depth": 20},
        {"path_sketch": sketch_to_text(shapes.circle(18))},
        {"body_material": ""},
        {"gasket_material": ""},
    ],
)
def test_missing_material_or_breaking_through_wall_is_rejected(profile, changes):
    with pytest.raises(ValidationError) as caught:
        run(cube(), profile=profile, **changes)
    assert caught.value.suggestions


def counterface(z=10.2):
    raw = trimesh.creation.box((20, 20, 2))
    raw.apply_translation((0, 0, z + 1))
    indices = np.flatnonzero(raw.face_normals[:, 2] < -0.99)
    feature = Feature(
        "bottom",
        "face",
        "generated",
        {"centre": (0, 0, z), "normal": (0, 0, -1)},
        face_indices=tuple(int(i) for i in indices),
    )
    return SceneObject("counter", "Gegenfläche", MeshData.of(raw), features={"bottom": feature})


def test_counterface_is_measured_instead_of_trusted_from_saved_values(profile):
    result = run(cube(), counter=counterface(), counterface="counter:bottom", profile=profile)
    coverage = next(f for f in result.findings if f.code == "seal.counterface")
    assert coverage.values["gap_mm"] == pytest.approx(0.2)
    assert coverage.values["overlap_mm"] == pytest.approx(0.2)
    distant = run(cube(), counter=counterface(12), counterface="counter:bottom", profile=profile)
    coverage = next(f for f in distant.findings if f.code == "seal.counterface")
    assert coverage.severity == "warning"
    assert coverage.values["overlap_mm"] == pytest.approx(-1.6)
    missing = counterface()
    cut = missing.mesh.raw.copy()
    cut.vertices[:, 0] *= 0.1
    with pytest.raises(ValidationError):
        run(
            cube(),
            counter=replace(missing, mesh=MeshData.of(cut)),
            counterface="counter:bottom",
            profile=profile,
        )


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("section", ["rectangle", "round"])
def test_round_and_rectangular_sections_obey_the_same_result_in_both_qualities(
    kind, quality, section, profile
):
    result = run(cube(kind), quality=quality, section=section, groove_width=3, profile=profile)
    gasket = as_mesh_data(result.outputs[1].mesh)
    expected = math.pi * 10 * 1.6 * 2.4 if section == "rectangle" else 2 * math.pi**2 * 5 * 1.2**2
    assert gasket.volume == pytest.approx(expected, rel=0.015)
    assert gasket.is_watertight and gasket.component_count == 1


@pytest.mark.parametrize(
    "direction", [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
)
@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_groove_on_each_real_side_keeps_world_location_and_depth(direction, kind, profile):
    entry = cube(kind)
    mesh = as_mesh_data(entry.mesh)
    indices = np.flatnonzero(mesh.raw.face_normals @ direction > 0.99)
    entry.features = {
        "support": Feature(
            "support",
            "face",
            "generated",
            {"normal": direction, "centre": tuple(10 * np.array(direction))},
            face_indices=tuple(int(i) for i in indices),
        )
    }
    sketch = replace(shapes.circle(10), plane="feature:body:support")
    result = run(entry, path_sketch=sketch_to_text(sketch), profile=profile)
    gasket = as_mesh_data(result.outputs[1].mesh)
    projected = gasket.raw.vertices @ direction
    assert projected.min() == pytest.approx(8)
    assert projected.max() == pytest.approx(10.4)
    assert 8000 - result.outputs[0].mesh.volume == pytest.approx(math.pi * 40, rel=0.003)


# Um (1, 2, 3) riss der Lauf am 16.09.2026 auf Ubuntu, um (1, 0, 0) auf
# Windows: Die Dichtung steht auf dem Nutboden, und nach der Drehung
# durchdringen sich die beiden Flächen um Nanometer — 5,6e-3 mm³ über
# 402 mm², das ist die Fließkommarechnung und keine Überschneidung.
@pytest.mark.parametrize("axis", [(1, 2, 3), (1, 0, 0)])
def test_selected_opening_is_saved_and_rotated_without_new_guess(profile, axis):
    from test_seal_openings import plate

    from app.core.geom.seal import opening_choices
    from app.core.perceive.matching import moved_features
    from app.core.types import FeatureRef

    entry = plate()
    choices = opening_choices(entry, FeatureRef(entry.id, "top"))
    asked = []

    def choose(question, labels):
        asked.append(question)
        return labels[1]

    result = run(
        entry, path_sketch="", support_feature="plate:top", offset=3, profile=profile, ask=choose
    )
    assert len(asked) == 1
    signature = result.answered["opening_signature"]
    assert signature == choices[1].signature
    assert "Kontur" not in signature
    matrix = trimesh.transformations.rotation_matrix(0.57, axis)
    matrix[:3, 3] = (7, 12, -4)
    raw = entry.mesh.raw.copy()
    raw.apply_transform(matrix)
    moved = replace(
        entry,
        mesh=MeshData.of(raw),
        features=moved_features(entry.features, tuple(tuple(row) for row in matrix)),
    )
    second = run(
        moved,
        path_sketch="",
        support_feature="plate:top",
        opening_signature=signature,
        offset=3,
        profile=profile,
        ask=choose,
    )
    assert len(asked) == 1
    assert not second.answered
    before = as_mesh_data(result.outputs[1].mesh).raw.copy()
    before.apply_transform(matrix)
    assert second.outputs[1].mesh.volume == pytest.approx(result.outputs[1].mesh.volume, rel=1e-8)
    assert as_mesh_data(second.outputs[1].mesh).raw.bounds == pytest.approx(before.bounds, abs=1e-6)


def test_history_parameter_save_load_and_disk_cache_preserve_the_two_outputs(profile, tmp_path):
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import load, new_project, save
    from app.core.types import Parameter

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    project.document.parameters["seal_width"] = Parameter("seal_width", 1.6)
    history = History(project.document)
    history.apply(
        "Träger", [OperationDraft("create_box", params={"width": 20, "depth": 20, "height": 20})]
    )
    before = evaluate(project.document, profile)
    assert before.complete
    carrier_id = next(iter(before.scene.objects))
    history.apply(
        "Dichtung",
        [
            OperationDraft(
                "create_seal",
                inputs=(carrier_id,),
                params={
                    "path_sketch": sketch_to_text(shapes.circle(10)),
                    "groove_width": 2,
                    "groove_depth": 2,
                    "gasket_width": "=@seal_width",
                    "protrusion": 0.4,
                    "body_material": "petg",
                    "gasket_material": "tpu-95a",
                },
            )
        ],
    )
    cache = ResultCache(disk=DiskCache(MeshCodec(), tmp_path / "cache"))
    preview = evaluate(project.document, profile, quality="draft", cache=cache)
    applied = evaluate(project.document, profile, quality="fine", cache=cache)
    assert applied.complete and preview.complete, applied.scene.report.findings
    assert len(applied.scene.objects) == 2
    assert carrier_id in applied.scene.objects
    for key in applied.scene.objects:
        shown = as_mesh_data(preview.scene.objects[key].mesh).raw
        final = as_mesh_data(applied.scene.objects[key].mesh).raw
        assert shown.vertices.tobytes() == final.vertices.tobytes()
        assert shown.faces.tobytes() == final.faces.tobytes()
    assert history.undo() is not None
    assert evaluate(project.document, profile).object_hashes == before.object_hashes
    assert history.redo() is not None
    assert evaluate(project.document, profile, cache=cache).object_hashes == applied.object_hashes
    path = save(project, tmp_path / "dichtung.p3d")
    reopened = load(path)
    cold = ResultCache(disk=DiskCache(MeshCodec(), tmp_path / "cache"))
    restored = evaluate(reopened.document, profile, cache=cold)
    assert restored.complete and cold.statistics.disk_hits == 2
    assert restored.object_hashes == applied.object_hashes
    assert reopened.document.ops[-1].params["gasket_width"] == "=@seal_width"
    reopened.document.parameters["seal_width"] = Parameter("seal_width", 1.8)
    changed = evaluate(reopened.document, profile, cache=cold)
    assert changed.complete, changed.scene.report.findings
    old_gasket = next(o for o in applied.scene.objects.values() if o.material == "tpu-95a")
    new_gasket = next(o for o in changed.scene.objects.values() if o.material == "tpu-95a")
    # Echte Normalversätze haben unabhängig facettierte Rundungen; das
    # analytische Verhältnis gilt innerhalb derselben Sehnengenauigkeit.
    assert new_gasket.mesh.volume / old_gasket.mesh.volume == pytest.approx(1.8 / 1.6, rel=0.003)


def test_sketch_expression_is_reused_by_the_parameter_collector(document, profile):
    from app.core.bootstrap import load_operations
    from app.core.scene import ResultCache, evaluate
    from app.core.scene.parameter_usage import ParameterUse
    from app.core.types import Operation, Parameter
    from tests.test_sketch import rectangle

    load_operations()
    drawing = sketch_to_text(rectangle("=@path_width", "@path_height"))
    document.parameters = {
        "path_width": Parameter("path_width", 8),
        "path_height": Parameter("path_height", 7),
    }
    document.ops = [
        Operation(
            1, "create_box", outputs=("body",), params={"width": 60, "depth": 40, "height": 20}
        ),
        Operation(
            2,
            "create_seal",
            inputs=("body",),
            outputs=("cut", "gasket"),
            params={
                "path_sketch": drawing,
                "groove_width": 2,
                "groove_depth": 2,
                "gasket_width": 1.6,
                "protrusion": 0.4,
                "body_material": "petg",
                "gasket_material": "tpu-95a",
            },
        ),
    ]
    cache = ResultCache()
    first = evaluate(document, profile, cache=cache)
    assert first.complete, first.scene.report.findings
    assert first.parameter_usage == {
        key: (ParameterUse(2, "path_sketch"),) for key in document.parameters
    }
    document.parameters["path_width"] = Parameter("path_width", 10)
    changed = evaluate(document, profile, cache=cache)
    assert changed.complete, changed.scene.report.findings
    assert changed.scene.objects["gasket"].mesh.volume > first.scene.objects["gasket"].mesh.volume
    assert document.ops[-1].params["path_sketch"] == drawing


def test_recalibrated_material_rechecks_restwall_before_using_cached_geometry(
    document, profile, monkeypatch
):
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles
    from app.core.scene import ResultCache, evaluate
    from app.core.types import Operation

    load_operations()
    material = profiles.material
    selected = material("petg")
    monkeypatch.setattr(
        profiles, "material", lambda key: selected if key == "petg" else material(key)
    )
    document.ops = [
        Operation(
            1, "create_box", outputs=("body",), params={"width": 20, "depth": 20, "height": 20}
        ),
        Operation(
            2,
            "create_seal",
            inputs=("body",),
            outputs=("cut", "gasket"),
            params={
                "path_sketch": sketch_to_text(shapes.circle(14)),
                "groove_width": 2,
                "groove_depth": 2,
                "gasket_width": 1.6,
                "protrusion": 0.4,
                "body_material": "petg",
                "gasket_material": "tpu-95a",
            },
        ),
    ]
    cache = ResultCache()
    first = evaluate(document, profile, cache=cache)
    assert first.complete, first.scene.report.findings
    assert evaluate(document, profile, cache=cache).complete
    selected = replace(
        selected,
        minimum_wall=3,
        calibration_printer=profile.printer.id,
        calibration_nozzle_diameter=profile.printer.nozzle_diameter,
        calibration_layer_height=profile.printer.layer_height,
        calibration_extrusion_width=profile.printer.extrusion_width,
    )
    changed = evaluate(document, profile, cache=cache)
    assert not changed.complete and changed.stopped_at == 2
    assert any("zu wenig Material" in str(f.message) for f in changed.scene.report.findings)


@pytest.mark.parametrize("material", ["pla", "petg"])
def test_material_change_preserves_colour_faces_but_releases_incompatible_filament(
    profile, material
):
    from app.core.geom.attributes import with_slot
    from app.core.types import MaterialSlot

    source = cube()
    source = replace(
        source,
        material="pla",
        mesh=with_slot(source.mesh, 3),
        material_slots=[
            MaterialSlot(3, "Meine blaue Spule", (0.1, 0.3, 0.7), "Hersteller PLA", "PLA"),
        ],
    )
    result = run(source, profile=profile, body_material=material)
    changed = result.outputs[0]
    # Neue Schnittflächen nutzen wie bei der gemeinsamen Taschen-Op Slot 0;
    # die unveränderte Unterseite behält ihre wirklich bemalten Dreiecke.
    bottom = changed.mesh.raw.face_normals[:, 2] < -0.99
    assert set(np.asarray(changed.mesh.slots)[bottom]) == {3}
    assert changed.material_slots[0].colour == source.material_slots[0].colour
    assert changed.material_slots[0].index == 3
    assert changed.material_slots[0].name == source.material_slots[0].name
    if material == "pla":
        assert changed.material_slots == source.material_slots
    else:
        assert changed.material_slots[0].material is None
        assert changed.material_slots[0].material_type is None
    assert source.material_slots[0].material == "Hersteller PLA"
    assert any(f.code == "seal.filament_reassign" for f in result.findings) is (material == "petg")


def test_material_binding_change_survives_cache_and_undo_restores_original_spool(document, profile):
    from app.core.bootstrap import load_operations
    from app.core.filament_usage import spool_for, with_spool
    from app.core.scene import History, OperationDraft, ResultCache, evaluate
    from app.core.types import PrintSettings

    load_operations()
    history = History(document)
    history.apply(
        "Träger", [OperationDraft("create_box", params={"width": 20, "depth": 20, "height": 20})]
    )
    first = evaluate(document, profile)
    key = next(iter(first.scene.objects))
    history.apply(
        "Filament",
        [
            OperationDraft(
                "assign_slot",
                inputs=(key,),
                params={
                    "slot": 0,
                    "name": "Blaue Spule",
                    "colour": "#123456",
                    "material_type": "PLA",
                    "slicer_profile": "Hersteller PLA",
                },
            )
        ],
    )
    painted = evaluate(document, profile)
    key = next(iter(painted.scene.objects))
    original = painted.scene.objects[key]
    document.print_settings = with_spool(PrintSettings(), original.material_slots[0], "my_spool")
    history.apply(
        "Dichtung",
        [
            OperationDraft(
                "create_seal",
                inputs=(key,),
                params={
                    "path_sketch": sketch_to_text(shapes.circle(10)),
                    "groove_width": 2,
                    "groove_depth": 2,
                    "gasket_width": 1.6,
                    "body_material": "petg",
                    "gasket_material": "tpu-95a",
                },
            )
        ],
    )
    cache = ResultCache()
    changed = evaluate(document, profile, cache=cache)
    assert changed.complete, changed.scene.report.findings
    remembered = evaluate(document, profile, cache=cache)
    assert remembered.complete
    slot = remembered.scene.objects[key].material_slots[0]
    assert slot.colour == original.material_slots[0].colour
    assert slot.material is None and slot.material_type is None
    assert not spool_for(document.print_settings, slot)
    assert history.undo()
    restored = evaluate(document, profile, cache=cache)
    assert restored.scene.objects[key].material_slots == original.material_slots
    assert (
        spool_for(document.print_settings, restored.scene.objects[key].material_slots[0])
        == "my_spool"
    )
    assert history.redo()
    redone = evaluate(document, profile, cache=cache)
    assert redone.scene.objects[key].material_slots == changed.scene.objects[key].material_slots


def test_counterface_change_invalidates_the_operation_cache(document, profile):
    from app.core.bootstrap import load_operations
    from app.core.scene import ResultCache, evaluate
    from app.core.types import Operation

    load_operations()
    document.ops = [
        Operation(
            1, "create_box", outputs=("body",), params={"width": 20, "depth": 20, "height": 20}
        ),
        Operation(
            2, "create_box", outputs=("lid",), params={"width": 20, "depth": 20, "height": 2}
        ),
        Operation(
            3,
            "translate_object",
            inputs=("lid",),
            outputs=("counter",),
            params={"dz": 20.2, "keep_on_bed": False},
        ),
    ]
    first = evaluate(document, profile)
    assert first.complete, first.scene.report.findings
    counter = first.scene.objects["counter"]
    bottom = next(
        f for f in counter.features.values() if f.kind == "face" and f.params["normal"][2] < -0.9
    )
    document.ops.append(
        Operation(
            4,
            "create_seal",
            inputs=("body",),
            outputs=("cut", "gasket"),
            params={
                "path_sketch": sketch_to_text(shapes.circle(10)),
                "groove_width": 2,
                "groove_depth": 2,
                "gasket_width": 1.6,
                "protrusion": 0.4,
                "body_material": "petg",
                "gasket_material": "tpu-95a",
                "counterface": f"counter:{bottom.id}",
            },
        )
    )
    cache = ResultCache()
    old = evaluate(document, profile, cache=cache)
    assert old.complete, old.scene.report.findings
    assert evaluate(document, profile, cache=cache).complete
    document.ops[2] = replace(document.ops[2], params={"dz": 22, "keep_on_bed": False})
    moved = evaluate(document, profile, cache=cache)
    assert moved.complete, moved.scene.report.findings
    finding = next(f for f in moved.scene.report.findings if f.code == "seal.counterface")
    assert finding.severity == "warning"
    assert finding.values["gap_mm"] == pytest.approx(2)
    assert finding.values["overlap_mm"] == pytest.approx(-1.6)
