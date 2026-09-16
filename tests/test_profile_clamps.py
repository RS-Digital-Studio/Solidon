"""Getrennte Klemmteile mit tatsächlichem Sitz, Wand und freiem Montageweg."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_to_text
from app.core.units import EPS_GEOM


@pytest.fixture
def clamp_reference():
    return json.loads(
        (Path(__file__).parent / "data/profile_clamp_reference.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("half", ["lower", "upper"])
def test_separate_shell_and_liner_have_a_real_free_axial_mount(clamp_reference, half):
    """Der Bund schlägt vorne an; ein vollständiger Körperabstand null ist hier richtig.

    Die Schale allein sitzt wie jeder Baustein bei null. Ins Paar hebt das
    Klemmenset sie um die Bundhöhe der Einlage — hier tut der Test dasselbe,
    bevor er die Montage prüft.
    """
    from app.core.knowledge.parts import shapes as part_shapes
    from app.core.knowledge.parts.profile_clamps import (
        ProfileClampLinerParams,
        ProfileClampShellParams,
        profile_clamp_liner,
        profile_clamp_shell,
    )

    case = clamp_reference
    outside = case["diameter"] + case["counter_press_total"] + 2 * case["liner_thickness"]
    shell = profile_clamp_shell(
        ProfileClampShellParams(
            seat_sketch=sketch_to_text(shapes.circle(outside + case["seat_clearance_total"])),
            depth=case["depth"],
            wall=case["wall"],
            half=half,
            joint_gap=case["joint_gap"],
            play=case["hardware_clearance_total"],
        )
    )
    assert shell.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=EPS_GEOM)
    paired = part_shapes.moved(shell.mesh, (0.0, 0.0, case["flange_height"]))
    liner = profile_clamp_liner(
        ProfileClampLinerParams(
            counter_sketch=sketch_to_text(shapes.circle(case["diameter"])),
            depth=case["depth"],
            liner_thickness=case["liner_thickness"],
            half=half,
            grip=-case["counter_press_total"],
            play=case["seat_clearance_total"],
            flange_width=case["flange_width"],
            flange_height=case["flange_height"],
            rear_relief=case["rear_relief"],
        )
    )
    for part in (shell, liner):
        assert part.mesh.is_watertight and part.mesh.component_count == 1
        assert part.mesh.raw.is_winding_consistent and part.mesh.raw.nondegenerate_faces().all()
        assert part.features
        assert all(feature.face_indices for feature in part.features.values())
        assert all(
            max(feature.face_indices) < part.mesh.triangle_count
            for feature in part.features.values()
        )
    assert (
        boolean("intersection", [paired, liner.mesh], quality="fine", allow_empty=True).mesh.volume
        <= EPS_GEOM
    )
    for distance in np.linspace(case["depth"] + case["flange_height"], 0.0, 9):
        moving = liner.mesh.raw.copy()
        moving.apply_translation((0, 0, -distance))
        overlap = boolean(
            "intersection", [paired, MeshData.of(moving)], quality="fine", allow_empty=True
        )
        assert overlap.mesh.volume <= EPS_GEOM
    blocked = liner.mesh.raw.copy()
    blocked.apply_translation((0, 0, case["flange_height"]))
    assert boolean("intersection", [paired, MeshData.of(blocked)], quality="fine").mesh.volume > 1.0


def _context(params, profile, inputs=(), parameters=None, quality="fine"):
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    return OpContext(
        scene=Scene(objects={one.id: one for one in inputs}, parameters=parameters or {}),
        inputs=list(inputs),
        params=params,
        profile=profile,
        quality=quality,
        seed=None,
        progress=lambda *_: None,
        ask=lambda *_: pytest.fail("unexpected ambiguity"),
        cancelled=NeverCancelled(),
    )


@pytest.mark.parametrize("shape", ["round", "ellipse", "drawn"])
def test_set_builds_four_separate_roles_with_the_declared_materials(
    clamp_reference, profile, shape
):
    from app.core.geom.profile_clamp_ops import ProfileClampSetParams, create_profile_clamp_set
    from app.core.sketch.serialize import sketch_to_text
    from app.core.types import Sketch, SketchElement

    case = clamp_reference
    points = [tuple(point) for point in case["drawn_points"]]
    drawing = (
        sketch_to_text(
            Sketch(
                plane="plane:xy",
                elements=tuple(
                    SketchElement("line", (point, points[(i + 1) % len(points)]))
                    for i, point in enumerate(points)
                ),
            )
        )
        if shape == "drawn"
        else ""
    )
    params = ProfileClampSetParams(
        profile_shape=shape,
        diameter=case["diameter"],
        width=case["ellipse_width"],
        height=case["ellipse_height"],
        counter_sketch=drawing,
        clamp_material="petg",
        liner_material="tpu-95a",
        depth=case["depth"],
    )
    result = create_profile_clamp_set(_context(params, profile))
    assert len(result.outputs) == 4 and result.solver.strategy == "direct"
    assert [entry.material for entry in result.outputs] == ["petg", "petg", "tpu-95a", "tpu-95a"]
    roles = [entry.features["front"].params["profile_clamp"]["role"] for entry in result.outputs]
    assert roles == ["shell_lower", "shell_upper", "liner_lower", "liner_upper"]
    for entry in result.outputs:
        assert entry.mesh.is_watertight and entry.mesh.component_count == 1
        assert entry.mesh.raw.nondegenerate_faces().all()
    for index, first in enumerate(result.outputs):
        for second in result.outputs[index + 1 :]:
            intersection = boolean("intersection", [first.mesh, second.mesh], allow_empty=True)
            assert intersection.mesh.volume <= EPS_GEOM


def test_replacement_keeps_the_actual_shells_and_outer_liner_seat(clamp_reference, profile):
    from dataclasses import replace

    from app.core.geom.profile_clamp_ops import (
        ProfileClampSetParams,
        ReplaceProfileLinersParams,
        create_profile_clamp_set,
        replace_profile_liners,
    )

    built = create_profile_clamp_set(
        _context(
            ProfileClampSetParams(
                clamp_material="petg",
                liner_material="tpu-95a",
            ),
            profile,
        )
    )
    entries = [replace(entry, id=f"part_{i}") for i, entry in enumerate(built.outputs)]
    replacement = replace_profile_liners(
        _context(
            ReplaceProfileLinersParams(
                diameter=14.0,
                clamp_material="petg",
                liner_material="tpu-95a",
            ),
            profile,
            entries,
        )
    )
    for index in range(2):
        assert replacement.outputs[index].mesh is entries[index].mesh
        assert replacement.outputs[index].features == entries[index].features
    for before, after in zip(entries[2:], replacement.outputs[2:], strict=True):
        old = before.features["front"].params["profile_clamp"]
        new = after.features["front"].params["profile_clamp"]
        assert old["outside"] == new["outside"]
        assert after.mesh.volume > before.mesh.volume


@pytest.fixture
def clamp_set(profile):
    from dataclasses import replace

    from app.core.geom.profile_clamp_ops import ProfileClampSetParams, create_profile_clamp_set

    built = create_profile_clamp_set(
        _context(
            ProfileClampSetParams(
                clamp_material="petg",
                liner_material="tpu-95a",
            ),
            profile,
        )
    )
    return [replace(entry, id=f"part_{i}") for i, entry in enumerate(built.outputs)]


def _carried(entries, matrix):
    from dataclasses import replace

    from app.core.geom.transform import apply
    from app.core.perceive.matching import moved_features

    return [
        replace(
            entry, mesh=apply(entry.mesh, matrix), features=moved_features(entry.features, matrix)
        )
        for entry in entries
    ]


@pytest.mark.parametrize("mirror", [False, True])
def test_replacement_follows_a_rigid_or_mirrored_complete_frame(clamp_set, profile, mirror):
    from app.core.geom.profile_clamp_ops import ReplaceProfileLinersParams, replace_profile_liners
    from app.core.geom.transform import apply, rotation, scaling, translation

    matrix = translation((13.0, -21.0, 37.0)) @ rotation("y", 31.0)
    if mirror:
        matrix = matrix @ scaling((-1.0, 1.0, 1.0))
    params = ReplaceProfileLinersParams(
        diameter=14.0, clamp_material="petg", liner_material="tpu-95a"
    )
    original = replace_profile_liners(_context(params, profile, clamp_set))
    moved = replace_profile_liners(_context(params, profile, _carried(clamp_set, matrix)))
    for one, other in zip(original.outputs[2:], moved.outputs[2:], strict=True):
        restored = apply(other.mesh, np.linalg.inv(matrix))
        assert np.allclose(one.mesh.raw.vertices, restored.raw.vertices, rtol=0, atol=EPS_GEOM)


@pytest.mark.parametrize("factors", [(1.1, 1.0, 1.0), (1.0, 1.0, 1.1), (1.0, 1.0, 0.9)])
def test_scaled_shells_cannot_claim_the_old_seat(clamp_set, profile, factors):
    from app.core.errors import ValidationError
    from app.core.geom.profile_clamp_ops import ReplaceProfileLinersParams, replace_profile_liners
    from app.core.geom.transform import scaling

    params = ReplaceProfileLinersParams(
        diameter=14.0, clamp_material="petg", liner_material="tpu-95a"
    )
    with pytest.raises(ValidationError, match="Klemmensitz"):
        replace_profile_liners(_context(params, profile, _carried(clamp_set, scaling(factors))))


@pytest.mark.parametrize("shape,axes", [("round", (8.0, 8.0)), ("ellipse", (23.5, 16.0))])
def test_actual_cross_sections_have_normal_wall_and_seat_gaps(profile, shape, axes):
    """Analytische Ellipsennormalen prüfen die Netze unabhängig vom Erzeuger-Offset."""
    from shapely.geometry import LineString

    from app.core.geom.profile_clamp_ops import ProfileClampSetParams, create_profile_clamp_set
    from app.core.slice.analysis import cross_section
    from app.core.units import MAX_FACET_SAG

    result = create_profile_clamp_set(
        _context(
            ProfileClampSetParams(
                profile_shape=shape,
                clamp_material="petg",
                liner_material="tpu-95a",
            ),
            profile,
        )
    )
    shapes_at_height = [cross_section(entry.mesh, 10.0) for entry in result.outputs]
    a, b = axes
    for angle in np.linspace(np.pi / 4, 3 * np.pi / 4, 9):
        point = np.array([a * np.cos(angle), b * np.sin(angle)])
        normal = np.array([np.cos(angle) / a, np.sin(angle) / b])
        normal /= np.linalg.norm(normal)

        def offset_at(boundary, expected, point=point, normal=normal):
            line = LineString(
                [point + (expected - 0.1) * normal, point + (expected + 0.1) * normal]
            )
            hit = boundary.intersection(line)
            assert hit.geom_type == "Point"
            return float((np.array(hit.coords[0]) - point) @ normal)

        inner = offset_at(shapes_at_height[3].boundary, -0.05)
        outside = offset_at(shapes_at_height[3].boundary, 1.95)
        seat = offset_at(shapes_at_height[1].boundary, 2.125)
        assert inner == pytest.approx(-0.05, abs=MAX_FACET_SAG / 4)
        assert outside - inner == pytest.approx(2.0, abs=MAX_FACET_SAG / 4)
        assert seat - outside == pytest.approx(0.175, abs=MAX_FACET_SAG / 4)


def test_a_changed_seat_wall_is_rejected_even_with_the_old_binding(clamp_set, profile):
    from dataclasses import replace

    from app.core.deferred import trimesh
    from app.core.errors import ValidationError
    from app.core.geom.profile_clamp_ops import ReplaceProfileLinersParams, replace_profile_liners

    cutter = trimesh.creation.box(extents=(2.0, 8.0, 2.0))
    cutter.apply_translation((0.0, 12.0, 20.0))
    mesh = boolean("difference", [clamp_set[1].mesh, MeshData.of(cutter)]).mesh
    features = dict(clamp_set[1].features)
    for name, height, sign in (("front", 1.5, -1.0), ("back", 41.5, 1.0)):
        indices = np.flatnonzero(
            (np.abs(mesh.raw.face_normals[:, 2] - sign) < EPS_GEOM)
            & (np.abs(mesh.raw.triangles_center[:, 2] - height) < EPS_GEOM)
        )
        features[name] = replace(features[name], face_indices=tuple(int(i) for i in indices))
    damaged = [*clamp_set]
    damaged[1] = replace(damaged[1], mesh=mesh, features=features)
    with pytest.raises(ValidationError, match="Klemmensitz"):
        replace_profile_liners(
            _context(
                ReplaceProfileLinersParams(
                    diameter=14.0,
                    clamp_material="petg",
                    liner_material="tpu-95a",
                ),
                profile,
                damaged,
            )
        )


def test_replacement_refuses_a_counter_profile_that_consumes_the_liner_wall(clamp_set, profile):
    from app.core.errors import ValidationError
    from app.core.geom.profile_clamp_ops import ReplaceProfileLinersParams, replace_profile_liners

    with pytest.raises(ValidationError, match="Einlagenwand"):
        replace_profile_liners(
            _context(
                ReplaceProfileLinersParams(
                    diameter=19.0,
                    clamp_material="petg",
                    liner_material="tpu-95a",
                ),
                profile,
                clamp_set,
            )
        )


def test_all_parts_roundtrip_through_stl_with_their_geometric_dimensions(clamp_set):
    import io

    from app.core.deferred import trimesh

    for entry in clamp_set:
        data = entry.mesh.raw.export(file_type="stl")
        restored = MeshData.of(trimesh.load(io.BytesIO(data), file_type="stl", force="mesh"))
        assert restored.is_watertight and restored.component_count == 1
        assert restored.volume == pytest.approx(entry.mesh.volume, rel=1e-6)
        assert np.allclose(restored.raw.bounds, entry.mesh.raw.bounds, rtol=0, atol=2e-6)


def test_required_choices_and_drawing_follow_the_active_profile_shape():
    from app.core.errors import ValidationError
    from app.core.geom.profile_clamp_ops import ProfileClampSetParams
    from app.core.registry import validate

    specs = {field.name: field for field in ProfileClampSetParams.spec()}
    assert all(
        specs[name].required
        for name in (
            "clamp_material",
            "liner_material",
            "counter_sketch",
        )
    )
    assert specs["counter_sketch"].placement == "front"
    common = {"clamp_material": "petg", "liner_material": "tpu-95a"}
    for shape in ("round", "ellipse"):
        assert validate(ProfileClampSetParams, {**common, "profile_shape": shape})
    with pytest.raises(ValidationError):
        validate(ProfileClampSetParams, {**common, "profile_shape": "drawn"})
    for name in common:
        with pytest.raises(ValidationError):
            validate(
                ProfileClampSetParams, {key: value for key, value in common.items() if key != name}
            )


def _bound_feature(entry):
    return next(feature for feature in entry.features.values() if "profile_clamp" in feature.params)


def _mesh_fingerprint(mesh):
    import hashlib

    return hashlib.sha256(mesh.raw.vertices.tobytes() + mesh.raw.faces.tobytes()).hexdigest()


@pytest.mark.parametrize("arranged", [False, True])
def test_create_replace_preview_undo_redo_and_project_cache_are_the_same(
    profile,
    tmp_path,
    arranged,
):
    from app.core.geom import profile_clamp_ops  # noqa: F401
    from app.core.geom.mesh import MeshCodec
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import load, new_project, save

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    material = {"clamp_material": "petg", "liner_material": "tpu-95a"}
    history.apply("Klemme", [OperationDraft(op="create_profile_clamp_set", params=material)])
    initial = evaluate(project.document, profile)
    assert initial.complete, initial.scene.report.findings
    if arranged:
        from app.core.geom import ops  # noqa: F401

        for index, key in enumerate(initial.scene.objects):
            history.apply(
                "Drehen",
                [
                    OperationDraft(
                        op="rotate_object",
                        inputs=(key,),
                        params={
                            "axis": "x",
                            "angle": 31.0 * (index + 1),
                            "keep_on_bed": False,
                        },
                    )
                ],
            )
            moved = history.operations[-1].outputs[0]
            history.apply(
                "Verschieben",
                [
                    OperationDraft(
                        op="translate_object",
                        inputs=(moved,),
                        params={"dx": 40.0 * index, "dy": -30.0 * index, "dz": 7.0 * index},
                    )
                ],
            )
        initial = evaluate(project.document, profile)
        assert initial.complete, initial.scene.report.findings
    transactions_before = len(history.transactions)
    objects = tuple(initial.scene.objects)
    history.apply(
        "Einlagen wechseln",
        [
            OperationDraft(
                op="replace_profile_liners",
                inputs=objects,
                params={**material, "diameter": 14.0},
            )
        ],
    )
    cache = ResultCache(disk=DiskCache(MeshCodec(), tmp_path / "cache"))
    preview = evaluate(project.document, profile, quality="draft", cache=cache)
    applied = evaluate(project.document, profile, quality="fine", cache=cache)
    assert preview.complete, preview.scene.report.findings
    assert applied.complete, applied.scene.report.findings
    assert tuple(applied.scene.objects) == objects
    assert len(history.transactions) == transactions_before + 1
    for key in objects:
        before = preview.scene.objects[key]
        after = applied.scene.objects[key]
        assert _mesh_fingerprint(before.mesh) == _mesh_fingerprint(after.mesh)
        assert _bound_feature(before).params == _bound_feature(after).params
    for key in objects[:2]:
        assert _mesh_fingerprint(applied.scene.objects[key].mesh) == _mesh_fingerprint(
            initial.scene.objects[key].mesh
        )
    assert history.undo() is not None
    undone = evaluate(project.document, profile)
    assert undone.object_hashes == initial.object_hashes
    assert history.redo() is not None
    assert evaluate(project.document, profile, cache=cache).object_hashes == applied.object_hashes
    path = save(project, tmp_path / "klemme.p3d")
    reopened = load(path)
    cold = ResultCache(disk=DiskCache(MeshCodec(), tmp_path / "cache"))
    restored = evaluate(reopened.document, profile, cache=cold)
    assert restored.complete, restored.scene.report.findings
    assert restored.object_hashes == applied.object_hashes
    completed_operations = len(project.document.ops)
    assert cold.statistics.disk_hits == completed_operations
    for key in objects:
        assert _mesh_fingerprint(restored.scene.objects[key].mesh) == _mesh_fingerprint(
            applied.scene.objects[key].mesh
        )
        assert json.dumps(_bound_feature(restored.scene.objects[key]).params, sort_keys=True) == (
            json.dumps(_bound_feature(applied.scene.objects[key]).params, sort_keys=True)
        )
    history.apply(
        "Zweiter Wechsel",
        [
            OperationDraft(
                op="replace_profile_liners",
                inputs=objects,
                params={**material, "diameter": 13.0},
            )
        ],
    )
    again = evaluate(project.document, profile, cache=cold)
    assert again.complete, again.scene.report.findings
    assert cold.statistics.hits == completed_operations


def test_drawn_profile_expressions_change_all_roles_and_keep_their_usage(document, profile):
    from app.core.geom import profile_clamp_ops  # noqa: F401
    from app.core.scene.cache import ResultCache
    from app.core.scene.evaluate import evaluate
    from app.core.scene.parameter_usage import ParameterUse
    from app.core.types import Operation, Parameter
    from tests.test_sketch import rectangle

    drawing = sketch_to_text(rectangle("=@base*2", "@height"))
    document.parameters = {"base": Parameter("base", 12.0), "height": Parameter("height", 14.0)}
    document.ops = [
        Operation(
            1,
            "create_profile_clamp_set",
            outputs=("a", "b", "c", "d"),
            params={
                "profile_shape": "drawn",
                "counter_sketch": drawing,
                "split_offset": 10.0,
                "clamp_material": "petg",
                "liner_material": "tpu-95a",
            },
        )
    ]
    cache = ResultCache()
    original = evaluate(document, profile, cache=cache)
    assert original.complete, original.scene.report.findings
    assert original.parameter_usage == {
        key: (ParameterUse(1, "counter_sketch"),) for key in ("base", "height")
    }
    assert evaluate(document, profile, cache=cache).complete
    assert cache.statistics.hits == 1
    document.parameters["base"] = Parameter("base", 15.0)
    changed = evaluate(document, profile, cache=cache)
    assert changed.complete, changed.scene.report.findings
    for key in original.scene.objects:
        assert changed.object_hashes[key] != original.object_hashes[key]
        points = _bound_feature(changed.scene.objects[key]).params["profile_clamp"]["counter"]
        assert np.ptp(np.asarray(points)[:, 0]) == pytest.approx(30.0)
    assert document.ops[0].params["counter_sketch"] == drawing


def test_liner_calibration_invalidates_the_real_set_cache(document, profile, monkeypatch):
    from dataclasses import replace

    from app.core.geom import profile_clamp_ops  # noqa: F401
    from app.core.knowledge import profiles
    from app.core.scene.cache import ResultCache
    from app.core.scene.evaluate import evaluate
    from app.core.types import Operation

    original = profiles.material
    soft = original("tpu-95a")
    monkeypatch.setattr(
        profiles, "material", lambda name: soft if name == soft.id else original(name)
    )
    document.ops = [
        Operation(
            1,
            "create_profile_clamp_set",
            outputs=("a", "b", "c", "d"),
            params={
                "clamp_material": "petg",
                "liner_material": soft.id,
            },
        )
    ]
    cache = ResultCache()
    first = evaluate(document, profile, cache=cache)
    assert first.complete, first.scene.report.findings
    assert evaluate(document, profile, cache=cache).complete
    soft = replace(soft, clearance=0.6)
    changed = evaluate(document, profile, cache=cache)
    assert changed.complete, changed.scene.report.findings
    assert changed.object_hashes != first.object_hashes
    for key in changed.scene.objects:
        binding = _bound_feature(changed.scene.objects[key]).params["profile_clamp"]
        assert binding["seat_clearance"] == pytest.approx(0.6)
        assert _mesh_fingerprint(changed.scene.objects[key].mesh) != _mesh_fingerprint(
            first.scene.objects[key].mesh
        )


def test_an_undercut_needs_an_explicit_mountable_split(clamp_reference, profile):
    from app.core.errors import ValidationError
    from app.core.geom.profile_clamp_ops import ProfileClampSetParams, create_profile_clamp_set
    from app.core.types import Sketch, SketchElement

    points = [tuple(point) for point in clamp_reference["undercut_points"]]
    drawing = sketch_to_text(
        Sketch(
            plane="plane:xy",
            elements=tuple(
                SketchElement("line", (point, points[(i + 1) % len(points)]))
                for i, point in enumerate(points)
            ),
        )
    )
    with pytest.raises(ValidationError, match="Hinterschnitt"):
        create_profile_clamp_set(
            _context(
                ProfileClampSetParams(
                    profile_shape="drawn",
                    counter_sketch=drawing,
                    clamp_material="petg",
                    liner_material="tpu-95a",
                ),
                profile,
            )
        )


@pytest.mark.parametrize("change_material", [False, True])
def test_replacement_preserves_only_compatible_filament_assignments(
    clamp_set,
    profile,
    monkeypatch,
    change_material,
):
    from dataclasses import replace

    from app.core.geom.attributes import with_slot
    from app.core.geom.profile_clamp_ops import ReplaceProfileLinersParams, replace_profile_liners
    from app.core.knowledge import profiles
    from app.core.types import MaterialSlot

    for index, entry in enumerate(clamp_set):
        clamp_set[index] = replace(
            entry,
            mesh=with_slot(entry.mesh, 3),
            material_slots=[
                MaterialSlot(3, "Eigene Spule", (0.2, 0.3, 0.4), "Hersteller TPU", "TPU"),
            ],
        )
    original = profiles.material
    alternate = replace(original("tpu-95a"), id="alternative_soft", clearance=0.6)
    monkeypatch.setattr(
        profiles, "material", lambda name: alternate if name == alternate.id else original(name)
    )
    material = alternate.id if change_material else "tpu-95a"
    result = replace_profile_liners(
        _context(
            ReplaceProfileLinersParams(
                diameter=14.0,
                clamp_material="petg",
                liner_material=material,
            ),
            profile,
            clamp_set,
        )
    )
    for index, entry in enumerate(result.outputs):
        if index < 2:
            assert entry is clamp_set[index]
        elif change_material:
            assert not entry.material_slots
            assert not entry.mesh.slots
            assert entry.material == material
        else:
            assert entry.material_slots == clamp_set[index].material_slots
            assert set(entry.mesh.slots) == {3}
    assert (
        any(f.code == "profile_clamp.filament_reassign" for f in result.findings) is change_material
    )


def test_standalone_liner_and_preview_read_their_own_material_profile():
    from app.core.knowledge.parts import ops, profile_clamps  # noqa: F401
    from app.core.knowledge.parts.registry import PARTS
    from app.core.knowledge.profiles import make_profile
    from app.core.registry import validate

    soft = make_profile("centauri-carbon-2", "tpu-95a")
    spec = PARTS.get("profile_clamp_liner")
    schema = ops.build_params(spec, standalone=True)
    values = {"counter_sketch": sketch_to_text(shapes.circle(16.0))}
    params = validate(schema, values)
    chosen, part = ops._built_part(spec, params, soft, "fine")
    preview, extra = ops.placement_tools(spec, values, soft, standalone=True)
    assert chosen.play == pytest.approx(soft.material.clearance)
    assert chosen.grip == pytest.approx(-soft.material.press)
    assert part.mesh.volume == pytest.approx(preview.volume)
    assert extra is None


def test_material_change_does_not_rebind_a_global_spool_and_undo_restores_it(profile, document):
    from app.core.export.threemf import slots_for_object
    from app.core.filament_usage import spool_for, with_spool
    from app.core.geom import colour_ops, profile_clamp_ops  # noqa: F401
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.types import PrintSettings

    history = History(document)
    history.apply(
        "Klemme",
        [
            OperationDraft(
                op="create_profile_clamp_set",
                params={
                    "clamp_material": "petg",
                    "liner_material": "tpu-95a",
                },
            )
        ],
    )
    first = evaluate(document, profile)
    assert first.complete
    entries = list(first.scene.objects)
    history.apply(
        "Filamente",
        [
            OperationDraft(
                op="assign_slot",
                inputs=(key,),
                params={
                    "slot": 0,
                    "name": "Meine TPU-Spule",
                    "material_type": "TPU",
                    "slicer_profile": "Hersteller TPU",
                },
            )
            for key in entries[2:]
        ],
    )
    painted = evaluate(document, profile)
    assert painted.complete
    by_role = {
        _bound_feature(entry).params["profile_clamp"]["role"]: entry
        for entry in painted.scene.objects.values()
    }
    roles = profile_clamp_ops.ROLES
    objects = tuple(by_role[role].id for role in roles)
    slot = by_role["liner_lower"].material_slots[0]
    document.print_settings = with_spool(PrintSettings(), slot, "my_physical_spool")
    assert spool_for(document.print_settings, slot) == "my_physical_spool"
    history.apply(
        "Anderes Einlagenmaterial",
        [
            OperationDraft(
                op="replace_profile_liners",
                inputs=objects,
                params={"diameter": 14.0, "clamp_material": "petg", "liner_material": "petg"},
            )
        ],
    )
    changed = evaluate(document, profile)
    assert changed.complete, changed.scene.report.findings
    for key in objects[2:]:
        entry = changed.scene.objects[key]
        assert not entry.material_slots and not entry.mesh.slots
        assert all(not spool_for(document.print_settings, one) for one in slots_for_object(entry))
    assert history.undo()
    undone = evaluate(document, profile)
    for key in objects[2:]:
        entry = undone.scene.objects[key]
        assert entry.material_slots == painted.scene.objects[key].material_slots
        assert entry.mesh.slots == painted.scene.objects[key].mesh.slots
        assert spool_for(document.print_settings, entry.material_slots[0]) == "my_physical_spool"


@pytest.mark.parametrize("name", ["profile_clamp_shell", "profile_clamp_liner"])
def test_each_pure_part_has_its_declared_faces_render_and_source_export(name):
    from app.core.knowledge.parts import profile_clamps  # noqa: F401
    from app.core.knowledge.parts.preview import render
    from app.core.knowledge.parts.registry import PARTS
    from app.core.knowledge.parts.scad import to_scad

    spec = PARTS.get(name)
    result = spec.fn(spec.params())
    assert set(result.features) == set(spec.features) == {"front", "back"}
    assert "<svg" in render(spec, size=100).svg
    assert "polyhedron" in to_scad(spec)


def test_liners_from_a_different_seat_depth_are_not_silently_grouped(clamp_set, profile):
    from app.core.errors import ValidationError
    from app.core.geom.profile_clamp_ops import (
        ProfileClampSetParams,
        ReplaceProfileLinersParams,
        create_profile_clamp_set,
        replace_profile_liners,
    )

    other = create_profile_clamp_set(
        _context(
            ProfileClampSetParams(
                depth=50.0,
                clamp_material="petg",
                liner_material="tpu-95a",
            ),
            profile,
        )
    )
    with pytest.raises(ValidationError, match="Klemmensitz"):
        replace_profile_liners(
            _context(
                ReplaceProfileLinersParams(
                    diameter=14.0,
                    clamp_material="petg",
                    liner_material="tpu-95a",
                ),
                profile,
                [*clamp_set[:2], *other.outputs[2:]],
            )
        )


@pytest.mark.parametrize("angle,offset", [(33.0, 2.0), (-27.0, -1.5)])
def test_the_explicit_split_frame_controls_both_halves_and_their_mount(profile, angle, offset):
    from app.core.geom.profile_clamp_ops import ProfileClampSetParams, create_profile_clamp_set
    from app.core.geom.transform import apply, rotation, translation

    result = create_profile_clamp_set(
        _context(
            ProfileClampSetParams(
                profile_shape="ellipse",
                split_angle=angle,
                split_offset=offset,
                clamp_material="petg",
                liner_material="tpu-95a",
            ),
            profile,
        )
    )
    for index, entry in enumerate(result.outputs):
        local = apply(entry.mesh, rotation("z", -angle))
        gap = 1.0 if index < 2 else 0.35
        if index % 2:
            assert local.bounds.minimum[1] == pytest.approx(offset + gap / 2.0, abs=EPS_GEOM)
        else:
            assert local.bounds.maximum[1] == pytest.approx(offset - gap / 2.0, abs=EPS_GEOM)
    for first, second in ((0, 2), (1, 3)):
        for distance in (0.0, 10.0, 42.0):
            liner = apply(result.outputs[second].mesh, translation((0.0, 0.0, -distance)))
            overlap = boolean("intersection", [result.outputs[first].mesh, liner], allow_empty=True)
            assert overlap.mesh.volume <= EPS_GEOM


def test_independently_arranged_parts_keep_all_four_individual_frames(clamp_set, profile):
    from app.core.geom.profile_clamp_ops import ReplaceProfileLinersParams, replace_profile_liners
    from app.core.geom.transform import apply, rotation, translation

    frames = [
        translation((40.0 * i, -30.0 * i, 7.0 * i))
        @ rotation("x", 31.0 * i)
        @ rotation("z", 17.0 * i)
        for i in range(4)
    ]
    arranged = [
        _carried([entry], matrix)[0] for entry, matrix in zip(clamp_set, frames, strict=True)
    ]
    params = ReplaceProfileLinersParams(
        diameter=14.0, clamp_material="petg", liner_material="tpu-95a"
    )
    baseline = replace_profile_liners(_context(params, profile, clamp_set))
    renewed = replace_profile_liners(_context(params, profile, arranged))
    for index in range(4):
        if index < 2:
            assert renewed.outputs[index] is arranged[index]
        else:
            restored = apply(renewed.outputs[index].mesh, np.linalg.inv(frames[index]))
            assert np.allclose(
                restored.raw.vertices,
                baseline.outputs[index].mesh.raw.vertices,
                atol=EPS_GEOM,
                rtol=0,
            )


@pytest.mark.parametrize("index", [2, 3])
def test_scaled_liners_do_not_claim_an_unmodified_rigid_frame(clamp_set, profile, index):
    from app.core.errors import ValidationError
    from app.core.geom.profile_clamp_ops import ReplaceProfileLinersParams, replace_profile_liners
    from app.core.geom.transform import scaling

    changed = list(clamp_set)
    changed[index] = _carried([changed[index]], scaling((1.1, 1.0, 1.0)))[0]
    with pytest.raises(ValidationError, match="Klemmensitz"):
        replace_profile_liners(
            _context(
                ReplaceProfileLinersParams(
                    diameter=14.0,
                    clamp_material="petg",
                    liner_material="tpu-95a",
                ),
                profile,
                changed,
            )
        )
