"""Gemessene Fertigungszusagen der Bausteine an den Review-Gegenfällen."""

import math

import numpy as np
import pytest
from shapely.geometry import LineString, Polygon

from app.core.geom.mesh import on_surface
from app.core.knowledge import profiles, standards
from app.core.knowledge.parts import PARTS, ops
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project


@pytest.mark.parametrize("countersink,head_room", [(True, 0), (True, 3), (False, 0), (False, 3)])
def test_screw_hole_names_its_real_countersink_and_head_zone(countersink, head_room):
    spec = PARTS.get("screw_hole")
    screw = standards.screw("M4")
    built = spec.fn(spec.params(size="M4", countersink=countersink, head_room=head_room))
    if countersink:
        cone = built.features["countersink_1"]
        assert cone.kind == "cone"
        assert cone.params["recess"] is True
        assert cone.params["angle"] == pytest.approx(90.0)
        depth = (screw.countersink - screw.clearance) / 2.0
        assert cone.params["depth"] == pytest.approx(depth)
        assert cone.params["centre"] == pytest.approx((0, 0, -head_room - depth / 2))
        section = built.mesh.raw.section(plane_origin=cone.params["centre"], plane_normal=(0, 0, 1))
        assert np.ptp(section.vertices[:, 0]) == pytest.approx(
            (screw.countersink + screw.clearance) / 2, abs=0.02
        )
    else:
        assert "countersink_1" not in built.features
    if head_room:
        head = built.features["head_room_1"]
        assert head.kind == "hole"
        assert head.params["depth"] == pytest.approx(head_room)
        assert head.params["centre"] == pytest.approx((0, 0, -head_room / 2))
        section = built.mesh.raw.section(plane_origin=head.params["centre"], plane_normal=(0, 0, 1))
        assert np.ptp(section.vertices[:, 0]) == pytest.approx(head.params["diameter"], abs=0.02)
    else:
        assert "head_room_1" not in built.features


def test_inserted_screw_hole_has_one_named_three_zone_chain(profile):
    from app.core.perceive.relations import cavity_chain_at

    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Bohrung",
        [
            OperationDraft(op="create_box", params={"width": 30, "depth": 30, "height": 12}),
            OperationDraft(
                op="insert_screw_hole",
                inputs=("obj_1",),
                params={"size": "M4", "depth": 12, "head_room": 3, "at_feature": "face_top"},
            ),
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    source = result.scene.objects["obj_1"]
    expected = ("screw_hole_bore_1", "screw_hole_countersink_1", "screw_hole_head_room_1")
    assert [source.features[name].kind for name in expected] == ["hole", "cone", "hole"]
    assert all(source.features[name].face_indices for name in expected)
    for name in expected:
        chain = cavity_chain_at(source.features[name], source.features, source.mesh)
        assert chain is not None
        assert tuple(feature.id for feature in chain) == expected


@pytest.mark.parametrize("size", ["cable-5", "cable-7"])
def test_automatic_cable_clip_retains_the_cable(size: str) -> None:
    spec = PARTS.get("cable_clip")
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    params = spec.params(**ops._part_values(spec, spec.params(size=size), profile))
    mesh = spec.fn(params).mesh
    section = mesh.raw.section(plane_origin=(0, 0, 0), plane_normal=(0, 1, 0))
    diameter = standards.tube(size).outer
    centre = params.wall + (diameter + params.play) / 2
    points = np.asarray(section.vertices)
    opening = 2 * np.min(np.abs(points[points[:, 2] > centre, 0]))
    assert 0 < opening < diameter


def test_insert_uses_the_target_objects_material() -> None:
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Baustein an TPU",
        [
            OperationDraft(op="create_box", params={"width": 60, "depth": 40, "height": 10}),
            OperationDraft(
                op="assign_slot", inputs=("obj_1",), params={"slot": 0, "material_type": "TPU"}
            ),
            OperationDraft(
                op="insert_dowel",
                inputs=("obj_1",),
                params={"kind": "bore", "diameter": 4, "length": 6, "z": 10},
            ),
        ],
    )
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    entry = result.scene.objects["obj_1"]
    assert entry.features["dowel_bore_1"].params["diameter"] == pytest.approx(
        4 + profiles.for_object(profile, entry).material.clearance
    )


@pytest.mark.parametrize("steps,extrusion", [(6, 0.42), (10, 0.42), (10, 0.8)])
def test_wall_ladder_has_each_separate_measuring_wall(steps: int, extrusion: float) -> None:
    spec = PARTS.get("wall_ladder")
    mesh = spec.fn(spec.params(steps=steps, extrusion=extrusion)).mesh
    section = mesh.raw.section(plane_origin=(0, 0, 3), plane_normal=(0, 0, 1))
    assert len(section.discrete) == steps
    widths = sorted(np.ptp(curve[:, 0]) for curve in section.discrete)
    assert widths == pytest.approx([extrusion * (index + 1) for index in range(steps)])


@pytest.mark.parametrize("first,step", [(20, 10), (5, 2), (60, 5)])
def test_overhang_angles_are_measured_from_vertical(first: float, step: float) -> None:
    spec = PARTS.get("overhang_fan")
    mesh = spec.fn(spec.params(first=first, step=step, steps=2)).mesh.raw
    normals = mesh.face_normals
    angled = normals[(normals[:, 2] < -0.01) & (np.abs(normals[:, 1]) > 0.01)]
    measured = [math.degrees(math.atan2(-n[2], abs(n[1]))) for n in angled]
    for expected in (first, first + step):
        assert any(abs(actual - expected) < 1e-3 for actual in measured)
    assert all(
        min(abs(actual - first), abs(actual - first - step)) < 1e-3 for actual in measured
    ), measured


def test_keyhole_has_a_retaining_lip_above_the_head_channel() -> None:
    spec = PARTS.get("keyhole")
    params = spec.params(size="M4", drop=8, depth=6, head_room=2.5, play=0.25)
    mesh = spec.fn(params).mesh
    section = mesh.raw.section(plane_origin=(0, 0, -0.001), plane_normal=(0, 0, 1))
    outlines = [Polygon(curve[:, :2]) for curve in section.discrete]
    from shapely.ops import unary_union

    shape = unary_union(outlines)
    hold = shape.intersection(LineString([(-20, -8), (20, -8)])).length
    entry = shape.intersection(LineString([(-20, 0), (20, 0)])).length
    assert hold < standards.screw("M4").head < entry
    assert hold >= standards.screw("M4").clearance


@pytest.mark.parametrize("thickness", [0.6, 1.6, 8.0])
def test_snap_arm_anchor_is_on_its_named_surface(thickness: float) -> None:
    spec = PARTS.get("snap_fit")
    result = spec.fn(spec.params(thickness=thickness))
    feature = result.features["arm_1"]
    centre = np.asarray([feature.params["centre"]])
    _points, distances, _faces = on_surface(result.mesh.raw, centre)
    assert distances[0] == pytest.approx(0.0, abs=1e-7)
    assert centre[0, 1] == pytest.approx(-thickness / 2)


@pytest.mark.parametrize("size,length", [("M3", 8.0), ("M6", 8.0), ("M8", 7.3)])
def test_printed_thread_fits_its_actual_internal_tool(size, length):
    from app.core.geom.boolean import boolean
    from app.core.knowledge.parts.fasteners import _printed_thread
    from app.core.knowledge.parts.shapes import moved

    male = _printed_thread(size, length, False, 0.15).mesh
    tool = moved(_printed_thread(size, length, True, 0.15).mesh, (0, 0, length))
    outside = boolean("difference", [male, tool], allow_empty=True)
    assert outside.mesh.volume < 1e-5


def test_component_gap_checks_every_pair_in_any_order():
    import itertools

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge.parts.range_check import printable_gap

    bodies = []
    for x in (0, 20, 21.05):
        body = trimesh.creation.box((1, 1, 1))
        body.apply_translation((x, 0, 0))
        bodies.append(body)
    for ordered in itertools.permutations(bodies):
        result = printable_gap(
            MeshData.of(trimesh.util.concatenate(ordered)), profiles.make_profile()
        )
        assert result == pytest.approx(0.05, abs=1e-8)


def test_collision_clearance_is_symmetric_for_unequal_faces():
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.geom.prepare import _really_overlap

    plate = trimesh.creation.box((100, 100, 2))
    cube = trimesh.creation.box((1, 1, 1))
    cube.apply_translation((0, 0, 1.6))
    a, b = MeshData.of(plate), MeshData.of(cube)
    assert _really_overlap(a, b, 0.2) is True
    assert _really_overlap(b, a, 0.2) is True
    assert _really_overlap(a, b, 0.05) is False


@pytest.mark.parametrize(
    "name,values,field",
    [
        ("cable_clip", {"diameter": 4, "grip": 5}, "grip"),
        ("keyhole", {"size": "M8", "drop": 2, "play": 2}, "drop"),
        ("keyhole", {"depth": 2, "head_room": 2.5}, "head_room"),
        ("overhang_fan", {"first": 80, "step": 10, "steps": 2}, "steps"),
    ],
)
def test_impossible_mechanical_combinations_explain_which_value_to_change(name, values, field):
    from app.core.errors import ValidationError

    spec = PARTS.get(name)
    with pytest.raises(ValidationError) as caught:
        spec.fn(spec.params(**values))
    assert caught.value.field == field
    assert caught.value.suggestions


@pytest.mark.parametrize("diameter,play,grip", [(0.1, 0, 0), (4, 2, 1.9), (100, 2, 5)])
def test_cable_clip_parameter_boundaries_keep_a_real_opening(diameter, play, grip):
    spec = PARTS.get("cable_clip")
    result = spec.fn(spec.params(diameter=diameter, play=play, grip=grip))
    assert result.mesh.is_watertight and result.mesh.component_count == 1
    section = result.mesh.raw.section(plane_origin=(0, 0, 0), plane_normal=(0, 1, 0))
    centre = 2 + (diameter + play) / 2
    points = np.asarray(section.vertices)
    opening = 2 * np.min(np.abs(points[points[:, 2] > centre, 0]))
    assert 0 < opening < diameter


def test_gap_includes_edge_interiors_not_only_vertices():
    import trimesh

    from app.core.geom.measure import surface_gap
    from app.core.geom.mesh import MeshData

    a = trimesh.creation.box((10, 1, 1))
    b = trimesh.creation.box((1, 10, 1))
    b.apply_translation((0, 0, 1.1))
    assert surface_gap(MeshData.of(a), MeshData.of(b), 2) == pytest.approx(0.1)


def test_the_range_report_warns_about_a_later_component_pair():
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.knowledge.parts.range_check import check
    from app.core.knowledge.parts.registry import WallRequirement
    from app.core.types import BaseParams, PartResult

    bodies = []
    for x in (0, 20, 21.05):
        body = trimesh.creation.box((1, 1, 1))
        body.apply_translation((x, 0, 0))
        bodies.append(body)
    mesh = MeshData.of(trimesh.util.concatenate(bodies))
    result = check(
        BaseParams,
        lambda _: PartResult(mesh=mesh),
        profiles.make_profile(),
        bodies=3,
        wall=WallRequirement.not_applicable("Die Probe misst nur den Spalt."),
    )
    assert not result.passed
    assert any("Spalt 0.05" in failure.reason for failure in result.failures)


@pytest.mark.parametrize("normal", [(0, 0, -1), (1, 0, 1)])
@pytest.mark.parametrize(
    "part,values,subtractive",
    [
        ("dowel", {"kind": "bore", "diameter": 4, "length": 6}, True),
        ("dowel", {"kind": "pin", "diameter": 4, "length": 6}, False),
        ("nut_trap", {"size": "M4", "screw_hole": False}, True),
    ],
)
def test_surface_normal_places_the_real_tool_on_the_correct_side(normal, part, values, subtractive):
    import trimesh

    from app.core.geom.align import rotation_between
    from app.core.geom.transform import apply
    from app.core.types import SceneObject
    from tests.test_subdivision import run

    normal = np.asarray(normal, dtype=np.float64)
    normal /= np.linalg.norm(normal)
    # Der Träger endet bei z=0 und wird samt Außenrichtung gedreht.
    body = trimesh.creation.box((40, 40, 20))
    body.apply_translation((0, 0, -10))
    from app.core.geom.mesh import MeshData

    body = apply(MeshData.of(body), rotation_between((0, 0, 1), tuple(normal)))
    source = SceneObject(id="obj_1", name="Träger", mesh=body)
    profile = profiles.make_profile()
    result = run(
        ops.op_name(part), source, profile, **values, nx=normal[0], ny=normal[1], nz=normal[2]
    )
    volume = result.outputs[0].mesh.volume
    assert (volume < body.volume) if subtractive else (volume > body.volume)
    assert result.outputs[0].mesh.component_count == 1
    assert not any(f.code == "boolean.without_effect" for f in result.findings)
    local = ops.placement_tool(PARTS.get(part), values, profile)
    extent = local.bounds.maximum[2] if subtractive else local.bounds.minimum[2]
    assert abs(extent) <= 0.011


def test_zero_normal_preserves_legacy_axis_and_feature_has_priority():
    from types import SimpleNamespace

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import Feature, SceneObject

    spec = PARTS.get("dowel")
    plain = ops.build_params(spec)(axis="y", x=2)
    zero = ops.build_params(spec)(axis="y", x=2, nx=0, ny=0, nz=0)
    assert np.array_equal(ops._matrix(plain), ops._matrix(zero))
    mesh = MeshData.of(trimesh.creation.box((10, 10, 10)))
    feature = Feature(
        id="chosen",
        kind="face",
        params={"normal": (1, 0, 0), "centre": (5, 0, 0)},
        provenance="generated",
    )
    source = SceneObject(id="obj_1", name="Träger", mesh=mesh, features={"chosen": feature})
    params = SimpleNamespace(at_feature="chosen", nx=0, ny=0, nz=-1)
    assert ops._anchor(source, params)[1] == pytest.approx((1, 0, 0))


@pytest.mark.parametrize(
    "name,values",
    [
        ("dowel", {"kind": "pin", "shape": "hex"}),
        ("nut_trap", {"size": "M4", "screw_hole": False}),
        ("keyhole", {"size": "M4", "depth": 6}),
    ],
)
def test_nonround_surface_preview_matches_the_actual_boolean_tool(name, values, monkeypatch):
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.geom.transform import apply
    from app.core.sketch.planes import frame_of
    from app.core.types import SceneObject
    from tests.test_subdivision import run

    point = (0.123456789012, 0.246891234567, 0.987654321098)
    frame = frame_of((1, 2, -3), point)
    matrix = np.eye(4, dtype=np.float64)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    matrix[:3, 3] = point
    body = trimesh.creation.box((100, 100, 30))
    body.apply_translation((0, 0, -15))
    source = SceneObject(id="obj_1", name="Träger", mesh=apply(MeshData.of(body), matrix))
    captured = []
    original = ops.boolean

    def capture(kind, meshes, **kwargs):
        captured.append(meshes[1])
        return original(kind, meshes, **kwargs)

    monkeypatch.setattr(ops, "boolean", capture)
    profile = profiles.make_profile()
    entered = {**values, "angle": 37.0}
    preview = apply(ops.placement_tool(PARTS.get(name), entered, profile), matrix)
    run(
        ops.op_name(name),
        source,
        profile,
        **entered,
        x=point[0],
        y=point[1],
        z=point[2],
        nx=frame.normal[0],
        ny=frame.normal[1],
        nz=frame.normal[2],
    )
    assert len(captured) == 1
    assert captured[0].raw.vertices == pytest.approx(preview.raw.vertices, abs=1e-12)
    assert np.array_equal(captured[0].raw.faces, preview.raw.faces)


def test_free_part_placement_survives_project_roundtrip(tmp_path):
    from app.core.scene.project import load, save

    project = new_project("centauri-carbon-2", "petg")
    location = 0.123456789012
    History(project.document).apply(
        "Baustein",
        [
            OperationDraft(op="create_box", params={"width": 30, "depth": 30, "height": 20}),
            OperationDraft(
                op="insert_dowel",
                inputs=("obj_1",),
                params={"kind": "bore", "x": location, "nx": 0, "ny": 0, "nz": -1},
            ),
        ],
    )
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    before = evaluate(project.document, profile, sources=ProjectSources(project))
    assert before.complete
    after_project = load(save(project, tmp_path / "surface.solidon"))
    after = evaluate(after_project.document, profile, sources=ProjectSources(after_project))
    assert after.complete
    assert after_project.document.ops[-1].params["x"] == location
    assert after_project.document.ops[-1].params["nz"] == -1
    assert after.scene.objects["obj_1"].mesh.volume == pytest.approx(
        before.scene.objects["obj_1"].mesh.volume
    )


def test_a_following_part_uses_the_snap_arm_surface():
    from app.core.types import SceneObject
    from tests.test_subdivision import run

    spec = PARTS.get("snap_fit")
    built = spec.fn(spec.params(thickness=1.6))
    source = SceneObject(id="obj_1", name="Rastarm", mesh=built.mesh, features=dict(built.features))
    result = run(
        "insert_dowel",
        source,
        profiles.make_profile(),
        at_feature="arm_1",
        kind="pin",
        diameter=1,
        length=2,
    )
    assert result.outputs[0].mesh.component_count == 1
    assert result.outputs[0].mesh.volume > source.mesh.volume
    assert not any(f.code == "parts.hanging_loose" for f in result.findings)
