"""Präzise Platzierung auf Originalflächen, einschließlich Aussparungen und freier Richtung."""

import math

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData
from app.core.geom.transform import apply, rotation
from app.core.registry import REGISTRY
from app.core.scene import placement
from app.core.types import Feature


def _top(mesh):
    return int(np.argmax(np.asarray(mesh.raw.face_normals)[:, 2]))


def test_two_real_edges_replace_the_triangulation_diagonal():
    """Eine Deckfläche hat vier Randkanten; die innere Diagonale taugt nicht als Bezug."""
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    hit = placement.at_point(prepared, (13.123456789, 8.0, 4.0))
    assert hit.planar
    assert len(prepared.edges) == 4
    assert len(hit.edges) == 2
    assert sorted(edge.distance for edge in hit.edges) == pytest.approx([6.876543211, 7.0])
    assert hit.point[0] == 13.123456789
    moved = placement.point_with_distances(prepared, hit, (2.0, 3.0))
    assert [edge.distance for edge in moved.edges] == pytest.approx([2.0, 3.0])
    assert moved.point[2] == pytest.approx(4.0)


def test_rotated_plate_keeps_its_real_plane_and_distances():
    """Abstände bleiben Millimeter in der Flächenebene, ohne Weltachsenrundung."""
    raw = trimesh.creation.box((40.0, 30.0, 8.0))
    face = _top(MeshData.of(raw))
    matrix = np.asarray(rotation("y", 37.0))
    raw.apply_transform(matrix)
    mesh = MeshData.of(raw)
    point = trimesh.transform_points([[13.0, 8.0, 4.0]], matrix)[0]
    prepared = placement.prepare_surface(mesh, face)
    hit = placement.at_point(prepared, tuple(point))
    assert hit.normal == pytest.approx(matrix[:3, 2])
    assert sorted(edge.distance for edge in hit.edges) == pytest.approx([7.0, 7.0])
    load_operations()
    values = placement.surface_values(REGISTRY.get("drill_hole"), hit)
    assert [values[key] for key in ("nx", "ny", "nz")] == pytest.approx(matrix[:3, 2])
    assert "axis" not in values
    assert values["anchor"] == "mouth"


def test_a_small_hole_is_not_filled_by_the_placement_patch():
    """Die Patchfläche bewahrt innere Konturen und bietet echte Bohrungsmittelpunkte."""
    from app.core.perceive.features import detect
    from tests.test_prepare import plate

    mesh = plate()
    face = _top(mesh)
    features = detect(mesh)
    hole = next(item for item in features.values() if item.kind == "hole")
    prepared = placement.prepare_surface(mesh, face, features)
    triangles = np.asarray(mesh.raw.triangles)[list(prepared.face_indices)]
    point = tuple(triangles[0].mean(axis=0))
    hit = placement.at_point(prepared, point)
    assert hole.id in {reference.feature_id for reference in hit.centres}
    # Ein konkreter innerer Ring des Korpus muss bei Punktversatz frei bleiben.
    assert len(prepared.area.interiors) > 0
    opening = np.asarray(prepared.area.interiors[0].coords).mean(axis=0)
    from app.core.sketch.planes import to_world

    with pytest.raises(ValueError):
        placement.at_point(prepared, to_world(prepared.frame, tuple(opening)))


def test_curved_triangles_offer_no_invented_planar_dimensions():
    mesh = MeshData.of(trimesh.creation.icosphere(subdivisions=1, radius=20.0))
    prepared = placement.prepare_surface(mesh, 0)
    hit = placement.at_point(prepared, tuple(mesh.raw.triangles[0].mean(axis=0)))
    assert not hit.planar
    assert not hit.edges


def test_original_ray_hits_the_mesh_and_respects_clipping():
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    hit = placement.original_surface_hit(mesh, (0.0, 0.0, 20.0), (0.0, 0.0, -1.0))
    assert hit is not None and hit[1] == pytest.approx((0.0, 0.0, 4.0))
    assert hit[0] in placement.prepare_surface(mesh, _top(mesh)).face_indices
    clipped = placement.original_surface_hit(
        mesh,
        (0.0, 0.0, 20.0),
        (0.0, 0.0, -1.0),
        clip_origin=(0.0, 0.0, 0.0),
        clip_normal=(0.0, 0.0, -1.0),
    )
    assert clipped is not None and clipped[1] == pytest.approx((0.0, 0.0, -4.0))


def test_all_section_planes_filter_original_hits_without_inventing_caps():
    from app.core.geom.section import SectionPlane

    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    sections = (SectionPlane.along("z", 1.0), SectionPlane.along("z", -1.0).flipped())
    assert (
        placement.original_surface_hit(
            mesh, (0.0, 0.0, 20.0), (0.0, 0.0, -1.0), clip_planes=sections
        )
        is None
    )
    side = placement.original_surface_hit(
        mesh, (50.0, 0.0, 0.0), (-1.0, 0.0, 0.0), clip_planes=sections
    )
    assert side is not None and side[1] == pytest.approx((20.0, 0.0, 0.0))


def test_editing_distances_cannot_put_the_point_into_a_cutout():
    from shapely.geometry import Polygon

    outline = Polygon(
        [(-20, -15), (20, -15), (20, 15), (-20, 15)], holes=[[(-2, -2), (2, -2), (2, 2), (-2, 2)]]
    )
    mesh = MeshData.of(trimesh.creation.extrude_polygon(outline, 8.0))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    hit = placement.at_point(prepared, (18.0, 13.0, 8.0))
    # Ziel: genau die Mitte der Aussparung, aus denselben beiden Außenkanten.
    distances = tuple(
        float(np.dot(np.asarray((0.0, 0.0, 8.0)) - edge.start, edge.inward)) for edge in hit.edges
    )
    with pytest.raises(ValueError, match="außerhalb"):
        placement.point_with_distances(prepared, hit, distances)
    assert hit.point == (18.0, 13.0, 8.0)


def test_repeated_point_moves_reuse_the_prepared_geometry(monkeypatch):
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    monkeypatch.setattr(placement, "_patch_faces", lambda *_: pytest.fail("topology recomputed"))
    for x in (-7.123456789, 0.0, 13.123456789):
        hit = placement.at_point(prepared, (x, 5.0, 4.0))
        assert hit.point == (x, 5.0, 4.0)


@pytest.mark.parametrize("normal", [(0.0, 0.0, -1.0), (0.3, -0.7, 0.6), (0.0, 0.0, 0.0)])
def test_text_preview_and_real_body_share_geometry_and_orientation(normal, profile):
    from app.core.sketch.planes import frame_of
    from tests.test_missing_ops import run

    load_operations()
    spec = REGISTRY.get("create_label")
    values = {"text": "L7", "size": 8.0, "depth": 0.7, "angle": 37.0}
    tool = placement.placement_tool(spec, values, profile)
    point = (3.123456789, -2.1, 8.0)
    frame = frame_of(normal if np.linalg.norm(normal) else (0.0, 0.0, 1.0), point)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    matrix[:3, 3] = point
    expected = apply(tool, matrix)
    actual = (
        run(
            "create_label",
            None,
            profile,
            **values,
            x=point[0],
            y=point[1],
            z=point[2],
            nx=normal[0],
            ny=normal[1],
            nz=normal[2],
        )
        .outputs[0]
        .mesh
    )
    assert actual.volume == pytest.approx(expected.volume)
    assert np.asarray(actual.raw.vertices) == pytest.approx(expected.raw.vertices, abs=1e-12)


def test_drill_preview_and_actual_cut_share_the_same_local_tool(profile, monkeypatch):
    import app.core.geom.prepare as module

    load_operations()
    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    values = {"diameter": 4.0, "depth": 3.0, "compensate": False}
    preview = placement.placement_tool(REGISTRY.get("drill_hole"), values, profile)
    captured = []
    original = module.boolean

    def record(kind, meshes, **kwargs):
        captured.append(meshes[1])
        return original(kind, meshes, **kwargs)

    monkeypatch.setattr(module, "boolean", record)
    module.drill(
        mesh, position=(0.0, 0.0, 4.0), axis="z", normal=(0.3, 0.4, 0.5), profile=profile, **values
    )
    assert captured[0].raw.vertices == pytest.approx(preview.raw.vertices, abs=1e-12)


def test_only_real_placement_operations_accept_surface_values():
    load_operations()
    assert placement.supports_surface_placement(REGISTRY.get("drill_hole"))
    assert placement.supports_surface_placement(REGISTRY.get("insert_screw_hole"))
    assert not placement.supports_surface_placement(REGISTRY.get("translate_object"))


def test_circle_facets_never_become_two_linear_measurement_references():
    from app.core.geom.boolean import boolean

    plate = MeshData.of(trimesh.creation.box((20.0, 20.0, 4.0)))
    cutter = MeshData.of(trimesh.creation.cylinder(radius=0.25, height=10.0, sections=48))
    mesh = boolean("difference", [plate, cutter]).mesh
    feature = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "depth": 4.0, "diameter": 0.5},
    )
    prepared = placement.prepare_surface(mesh, _top(mesh), {feature.id: feature})
    assert len(prepared.edges) == 4
    hit = placement.at_point(prepared, (0.3, 0.3, 2.0))
    assert len(hit.edges) == 2
    assert all(abs(edge.distance) > 9.0 for edge in hit.edges)
    assert hit.centres[0].point == pytest.approx((0.0, 0.0, 2.0))


def test_small_straight_cutout_edges_are_preserved():
    from shapely.geometry import Polygon

    outline = Polygon(
        [(-10, -10), (10, -10), (10, 10), (-10, 10)],
        holes=[[(-0.1, -0.1), (0.1, -0.1), (0.1, 0.1), (-0.1, 0.1)]],
    )
    mesh = MeshData.of(trimesh.creation.extrude_polygon(outline, 2.0))
    prepared = placement.prepare_surface(mesh, _top(mesh))
    assert len(prepared.edges) == 8
    assert min(
        np.linalg.norm(np.asarray(edge.start) - edge.end) for edge in prepared.edges
    ) == pytest.approx(0.2)


def test_a_pin_on_the_underside_uses_its_material_base(profile):
    from app.core.geom.boolean import boolean
    from app.core.geom.prepare_ops import feature_placement_geometry
    from app.core.types import SceneObject

    load_operations()
    plate = trimesh.creation.box((20.0, 20.0, 4.0))
    pin = trimesh.creation.cylinder(radius=2.0, height=6.0, sections=48)
    pin.apply_translation((0.0, 0.0, -4.0))
    mesh = boolean("union", [MeshData.of(plate), MeshData.of(pin)]).mesh
    feature = Feature(
        id="pin_1",
        kind="pin",
        provenance="generated",
        params={"centre": (0.0, 0.0, -4.5), "axis": (0.0, 0.0, 1.0), "diameter": 4.0, "depth": 5.0},
    )
    source = SceneObject(id="obj_1", name="Zapfenplatte", mesh=mesh, features={feature.id: feature})
    geometry = feature_placement_geometry(source, feature, "move_feature")
    assert geometry.frame.normal == pytest.approx((0.0, 0.0, -1.0))
    assert geometry.frame.origin == pytest.approx((0.0, 0.0, -2.0))
    assert geometry.mesh.bounds.maximum[2] == pytest.approx(5.02)


@pytest.mark.parametrize("operation", ["move_feature", "duplicate_feature"])
def test_existing_feature_tool_matches_free_placement_and_preserves_ids(
    operation, profile, monkeypatch
):
    import app.core.geom.prepare_ops as module
    from app.core.geom.boolean import boolean
    from app.core.types import SceneObject
    from tests.test_missing_ops import run

    load_operations()
    mesh = boolean(
        "difference",
        [
            MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0))),
            MeshData.of(trimesh.creation.cylinder(radius=1.5, height=12.0, sections=48)),
        ],
    ).mesh
    feature = Feature(
        id="hole_9",
        kind="hole",
        provenance="generated",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 3.0,
            "depth": 8.0,
            "through": True,
        },
    )
    source = SceneObject(id="obj_1", name="Platte", mesh=mesh, features={feature.id: feature})
    spec = REGISTRY.get(operation)
    target = MeshData.of(trimesh.creation.box((20.0, 20.0, 8.0)))
    prepared = placement.prepare_surface(target, _top(target))
    hit = placement.at_point(prepared, (7.0, 6.0, 4.0))
    values = placement.surface_values(spec, hit, feature=feature, source=source)
    tool = placement.placement_tool(spec, values, profile, source=source, feature=feature)
    captured = []
    original = module.boolean

    def record(kind, meshes, **kwargs):
        if kind == "difference":
            captured.append(meshes[1])
        return original(kind, meshes, **kwargs)

    monkeypatch.setattr(module, "boolean", record)
    result = run(operation, source, profile, **values).outputs[0]
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((hit.frame.x_axis, hit.frame.y_axis, hit.normal))
    matrix[:3, 3] = hit.point
    expected = apply(tool, matrix)
    assert captured[0].raw.vertices == pytest.approx(expected.raw.vertices, abs=1e-12)
    assert "hole_9" in result.features
    if operation == "duplicate_feature":
        assert "hole_10" in result.features
        assert result.features["hole_9"].params["centre"] == feature.params["centre"]
    else:
        assert result.features["hole_9"].params["centre"] == pytest.approx((7.0, 6.0, 0.0))


@pytest.mark.parametrize("operation", ["move_feature", "duplicate_feature"])
@pytest.mark.parametrize("chosen", [0, 1, 2])
def test_surface_placement_carries_the_complete_bore_chain(operation, chosen, profile):
    from app.core.geom.prepare_ops import feature_placement_geometry
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chains
    from app.core.types import SceneObject
    from tests.test_missing_ops import run

    load_operations()
    outline = [
        [30.0, 0.0],
        [30.0, 10.0],
        [5.5, 10.0],
        [5.5, 8.5],
        [3.0, 6.0],
        [3.0, 0.0],
        [30.0, 0.0],
    ]
    mesh = MeshData.of(trimesh.creation.revolve(outline, sections=64))
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    assert len(chain) == 3
    feature = chain[chosen]
    source = SceneObject(id="obj_1", name="Senkbohrung", mesh=mesh, features=features)
    spec = REGISTRY.get(operation)
    geometry = feature_placement_geometry(source, feature, operation)
    assert geometry.frame.normal == pytest.approx((0.0, 0.0, 1.0))
    assert geometry.frame.origin[2] == pytest.approx(10.0)
    prepared = placement.prepare_surface(mesh, _top(mesh), features)
    hit = placement.at_point(prepared, (15.0, 0.0, 10.0))
    values = placement.surface_values(spec, hit, feature=feature, source=source)
    result = run(operation, source, profile, **values).outputs[0]
    assert result.mesh.raw.is_watertight
    assert all(identifier in result.features for identifier in features)
    if operation == "move_feature":
        assert result.mesh.volume == pytest.approx(mesh.volume, abs=0.02)
        assert [result.features[item.id].params["centre"][0] for item in chain] == pytest.approx(
            [15.0] * 3
        )
    else:
        assert len(result.features) == len(features) + 3
        assert mesh.volume - result.mesh.volume == pytest.approx(
            math.pi * (54.0 + 56.0 * 2.5 / 3.0 + 45.375), rel=0.01
        )
        assert all(
            result.features[item.id].params["centre"] == item.params["centre"] for item in chain
        )


def test_a_free_direction_drills_the_rotated_plate_to_the_given_depth():
    from app.core.geom.prepare import drill
    from tests.test_prepare import profiles

    mesh = MeshData.of(trimesh.creation.box((40.0, 30.0, 8.0)))
    matrix = np.asarray(rotation("y", 37.0))
    moved = apply(mesh, rotation("y", 37.0))
    mouth = tuple(trimesh.transform_points([[0.0, 0.0, 4.0]], matrix)[0])
    result = drill(
        moved,
        position=mouth,
        axis="z",
        normal=tuple(matrix[:3, 2]),
        diameter=4.0,
        depth=3.0,
        compensate=False,
        profile=profiles.make_profile("centauri-carbon-2", "petg"),
    )
    removed = moved.volume - result.mesh.volume
    assert removed == pytest.approx(math.pi * 4.0 * 3.0, rel=0.03)


@pytest.mark.parametrize("route", ["x", "y", "z", "normal"])
@pytest.mark.parametrize("side", [-1.0, 1.0])
@pytest.mark.parametrize("anchor", ["mouth", "centre"])
@pytest.mark.parametrize("widened", [False, True])
def test_blind_drill_keeps_the_exact_bottom_and_anchor(route, side, anchor, widened, profile):
    """Die eingegebene Tiefe begrenzt das echte Loch, einschließlich seiner Blindböden."""
    from app.core.geom.mesh import ray_hit_distances
    from app.core.geom.prepare import BORE_SECTIONS, drill
    from app.core.sketch.planes import frame_of
    from tests.test_prepare import cube

    outward = (
        np.asarray((0.3, 0.4, math.sqrt(0.75)))
        if route == "normal"
        else np.eye(3)[{"x": 0, "y": 1, "z": 2}[route]]
    )
    outward *= side
    frame = frame_of(tuple(outward), (0.0, 0.0, 0.0))
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    original = cube().raw.copy()
    original.apply_transform(matrix)
    mesh = MeshData.of(original)
    depth = 2.0
    mouth = 10.0 if anchor == "mouth" else depth / 2.0
    position = tuple(outward * (10.0 if anchor == "mouth" else 0.0))
    result = drill(
        mesh,
        position=position,
        axis="z" if route == "normal" else route,
        normal=tuple(outward) if route == "normal" else (0.0, 0.0, 0.0),
        diameter=2.0,
        depth=depth,
        anchor=anchor,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    local = result.mesh.raw.copy()
    local.apply_transform(np.linalg.inv(matrix))
    vertices = np.asarray(local.vertices)
    internal = vertices[np.linalg.norm(vertices[:, :2], axis=1) < 2.1]
    assert len(internal)
    assert float(internal[:, 2].min()) == pytest.approx(mouth - depth, abs=1e-8)
    assert float(internal[:, 2].max()) == pytest.approx(mouth, abs=1e-8)
    # Die 48-seitige Netzfläche ist analytisch bekannt; ihre Kreisabweichung
    # darf keine zusätzliche Bohrtiefe in einer großzügigen Volumentoleranz verstecken.
    area_factor = BORE_SECTIONS * math.sin(math.tau / BORE_SECTIONS) / 2.0
    volume_factor = (0.75 + 4.0 * 0.25 + (1.0 + 2.0 + 4.0) / 3.0) if widened else depth
    # Die native Rundflächenübergabe weicht im Volumen um wenige 1e-7 mm³ ab;
    # das unabhängig geprüfte Bodenmaß behält seine engere Längenschranke.
    assert mesh.volume - result.mesh.volume == pytest.approx(area_factor * volume_factor, abs=1e-6)
    assert result.mesh.is_watertight
    assert result.solver.strategy == "direct"
    if anchor == "mouth":
        hits = ray_hit_distances(
            local.triangles, np.asarray((0.0, 0.0, 11.0)), np.asarray((0.0, 0.0, -1.0))
        )
        assert float(hits.min()) == pytest.approx(11.0 - (mouth - depth), abs=1e-8)


@pytest.mark.parametrize("widened", [False, True])
def test_the_shared_drill_tool_has_no_hidden_end_allowance(widened, profile):
    """Auch nicht gerundete Eingabetiefen bleiben im Werkzeugkörper exakt erhalten."""
    from app.core.geom.prepare import drill_tool

    depth = 2.123456789
    tool = drill_tool(
        diameter=2.0,
        depth=depth,
        profile=profile,
        compensate=False,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
    )
    assert tool.bounds.minimum[2] == pytest.approx(-depth, abs=1e-12)
    assert tool.bounds.maximum[2] == pytest.approx(0.0, abs=1e-12)
    assert tool.is_watertight


@pytest.mark.parametrize("widened", [False, True])
def test_an_entered_mouth_inside_material_keeps_its_exact_start(widened, profile):
    """Eine manuell im Material gesetzte Mündung ist kein belegter Außenanschluss."""
    from app.core.geom.prepare import drill
    from tests.test_prepare import cube

    result = drill(
        cube(),
        position=(0.0, 0.0, 5.0),
        axis="z",
        normal=(0.0, 0.0, 1.0),
        diameter=2.0,
        depth=2.0,
        anchor="mouth",
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    vertices = np.asarray(result.mesh.raw.vertices)
    internal = vertices[np.linalg.norm(vertices[:, :2], axis=1) < 2.1]
    assert float(internal[:, 2].min()) == pytest.approx(3.0, abs=1e-8)
    assert float(internal[:, 2].max()) == pytest.approx(5.0, abs=1e-8)


@pytest.mark.parametrize("normal", [(0.0, 0.0, 0.0), (0.0, 0.0, -1.0)])
@pytest.mark.parametrize("anchor", ["mouth", "centre"])
@pytest.mark.parametrize("widened", [False, True])
def test_through_drilling_stays_open_after_removing_blind_allowances(
    normal, anchor, widened, profile
):
    """Die ausdrücklich überlange Durchgangsgeometrie lässt auf keiner Seite einen Boden."""
    from app.core.geom.mesh import ray_hit_distances
    from app.core.geom.prepare import drill
    from tests.test_prepare import cube

    mesh = cube()
    result = drill(
        mesh,
        position=(0.0, 0.0, -10.0),
        axis="z",
        normal=normal,
        anchor=anchor,
        diameter=2.0,
        depth=0.0,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    for side in (-1.0, 1.0):
        hits = ray_hit_distances(
            result.mesh.raw.triangles,
            np.asarray((0.0, 0.0, side * 11.0)),
            np.asarray((0.0, 0.0, -side)),
        )
        assert not len(hits)
    assert result.mesh.is_watertight
    assert result.solver.strategy == "direct"


@pytest.mark.parametrize("gap", [-1e-9, 1e-9])
@pytest.mark.parametrize("widened", [False, True])
def test_a_real_offset_from_the_drill_mouth_survives_roundoff_cleanup(gap, widened, profile):
    """Ein Abstand oberhalb des Float64-Rechenfehlers bleibt ein echter Abstand."""
    from app.core.geom.mesh import ray_hit_distances
    from app.core.geom.prepare import drill
    from app.core.sketch.planes import frame_of
    from tests.test_prepare import cube

    outward = np.asarray((0.3, 0.4, math.sqrt(0.75)))
    frame = frame_of(tuple(outward), (0.0, 0.0, 0.0))
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    raw = cube().raw.copy()
    # apply_translation überspringt solche kleinen Verschiebungen als Identität;
    # hier muss der analytisch vorgegebene Abstand wirklich im Eingang stehen.
    raw.vertices = np.asarray(raw.vertices) + np.asarray((0.0, 0.0, gap))
    raw.apply_transform(matrix)
    result = drill(
        MeshData.of(raw),
        position=tuple(outward * 10.0),
        axis="z",
        normal=tuple(outward),
        diameter=2.0,
        depth=2.0,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    local = result.mesh.raw.copy()
    local.apply_transform(np.linalg.inv(matrix))
    assert local.bounds[1, 2] == pytest.approx(10.0 + gap, abs=5e-14)
    hits = ray_hit_distances(
        local.triangles, np.asarray((0.0, 0.0, 11.0)), np.asarray((0.0, 0.0, -1.0))
    )
    expected = 1.0 - gap if gap > 0.0 else 3.0
    assert float(hits.min()) == pytest.approx(expected, abs=5e-14)
    assert result.mesh.is_watertight


@pytest.mark.parametrize("widened", [False, True])
def test_a_coplanar_drill_mouth_keeps_its_bottom_after_welding(widened, profile, monkeypatch):
    """Die echte zweite Stufe darf die maßhaltige koplanare Mündung ebenfalls schneiden."""
    from importlib import import_module

    from app.core.geom.mesh import ray_hit_distances
    from app.core.geom.prepare import drill
    from tests.test_prepare import cube

    module = import_module("app.core.geom.boolean")
    original = module._run_stage

    def skip_direct(kind, meshes, stage, seed):
        return None if stage == "direct" else original(kind, meshes, stage, seed)

    monkeypatch.setattr(module, "_run_stage", skip_direct)
    result = drill(
        cube(),
        position=(0.0, 0.0, 10.0),
        axis="z",
        normal=(0.0, 0.0, 1.0),
        diameter=2.0,
        depth=2.0,
        widening_diameter=4.0 if widened else 0.0,
        widening_depth=0.25 if widened else 0.0,
        compensate=False,
        profile=profile,
    )
    hits = ray_hit_distances(
        result.mesh.raw.triangles,
        np.asarray((0.0, 0.0, 11.0)),
        np.asarray((0.0, 0.0, -1.0)),
    )
    assert result.solver.strategy == "welded"
    assert result.solver.attempted == ("direct", "welded")
    assert result.mesh.is_watertight
    assert float(hits.min()) == pytest.approx(3.0, abs=1e-8)


@pytest.mark.parametrize("depth", [0.0, 10.0])
def test_a_surface_drill_builds_one_connected_three_stage_cavity(depth, profile):
    """Bohrung, Übergang und Aufweitung bilden dieselbe erkennbare zusammenhängende Form."""
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chains
    from app.core.types import SceneObject
    from tests.test_missing_ops import run

    load_operations()
    raw = trimesh.creation.box((40.0, 30.0, 10.0))
    raw.apply_translation((0.0, 0.0, 5.0))
    source = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(raw))
    result = run(
        "drill_hole",
        source,
        profile,
        diameter=6.0,
        depth=depth,
        widening_diameter=11.0,
        widening_depth=1.5,
        transition_angle=90.0,
        z=10.0,
        nz=1.0,
        compensate=False,
    ).outputs[0]
    chain = next(iter(cavity_chains(detect(result.mesh), result.mesh)))
    assert sorted(item.kind for item in chain) == ["cone", "hole", "hole"]
    assert result.mesh.raw.is_watertight
    assert source.mesh.volume - result.mesh.volume == pytest.approx(
        math.pi * (54.0 + 55.75 * 2.5 / 3.0 + 45.375), rel=0.005
    )


@pytest.mark.parametrize("sides", [8, 12, 16])
def test_regular_polygon_edges_need_round_provenance_before_being_hidden(sides):
    """Ein echtes regelmäßiges Vieleck verliert seine Bezugskanten nicht an einen Kreisfit."""
    mesh = MeshData.of(trimesh.creation.cylinder(radius=10.0, height=8.0, sections=sides))
    face = _top(mesh)
    plane = Feature(
        id="face_top",
        kind="face",
        provenance="generated",
        face_indices=[face],
        params={"normal": (0.0, 0.0, 1.0)},
    )
    prepared = placement.prepare_surface(mesh, face, {plane.id: plane})
    assert len(prepared.edges) == sides


def test_drill_preview_and_actual_operation_use_the_objects_material(profile, monkeypatch):
    """Die Körperwahl gilt für den sichtbaren Werkzeugkörper und den tatsächlichen Abtrag."""
    import app.core.geom.prepare as module
    from app.core.types import SceneObject
    from tests.test_missing_ops import run

    load_operations()
    source = SceneObject(
        id="obj_1",
        name="PLA-Platte",
        material="pla",
        mesh=MeshData.of(trimesh.creation.box((30.0, 20.0, 10.0))),
    )
    values = {
        "diameter": 4.0,
        "depth": 8.0,
        "widening_diameter": 8.0,
        "widening_depth": 1.0,
        "transition_angle": 90.0,
    }
    preview = placement.placement_tool(REGISTRY.get("drill_hole"), values, profile, source=source)
    captured = []
    original = module.boolean

    def record(kind, meshes, **kwargs):
        captured.append(meshes[1])
        return original(kind, meshes, **kwargs)

    monkeypatch.setattr(module, "boolean", record)
    run("drill_hole", source, profile, **values, z=5.0, nx=0.3, ny=0.4, nz=0.5)
    assert captured[0].raw.vertices == pytest.approx(preview.raw.vertices, abs=1e-12)
    from app.core.knowledge.profiles import for_object

    assert np.ptp(preview.raw.vertices[:, 0]) == pytest.approx(
        module.bore_diameter(8.0, for_object(profile, source), True)
    )


@pytest.mark.parametrize(
    "values",
    [
        {"widening_diameter": 3.0},
        {"widening_diameter": float("nan")},
        {"widening_diameter": 8.0, "widening_depth": 3.0},
        {"widening_diameter": 8.0, "transition_angle": 0.0},
    ],
)
def test_invalid_widening_has_an_actionable_error(values, profile):
    from app.core.errors import ValidationError
    from app.core.geom.prepare import drill_tool

    with pytest.raises(ValidationError) as caught:
        drill_tool(diameter=4.0, depth=4.0, profile=profile, compensate=False, **values)
    assert caught.value.suggestions


def test_widening_starts_at_the_clicked_step_not_the_highest_face(profile):
    """Ein höherer Nachbar verschiebt die Aufweitung nicht aus der gewählten Fläche."""
    from app.core.geom.boolean import boolean
    from app.core.geom.prepare import drill

    low = trimesh.creation.box((40.0, 30.0, 8.0))
    low.apply_translation((0.0, 0.0, 4.0))
    high = trimesh.creation.box((10.0, 30.0, 20.0))
    high.apply_translation((-15.0, 0.0, 10.0))
    mesh = boolean("union", [MeshData.of(low), MeshData.of(high)]).mesh
    actual = drill(
        mesh,
        position=(8.0, 0.0, 8.0),
        axis="z",
        normal=(0.0, 0.0, 1.0),
        diameter=4.0,
        depth=0.0,
        widening_diameter=8.0,
        widening_depth=1.0,
        transition_angle=180.0,
        profile=profile,
        compensate=False,
    ).mesh
    assert mesh.volume - actual.volume == pytest.approx(math.pi * (4.0 * 7.0 + 16.0), rel=0.005)


def test_centre_offsets_are_editable_in_the_actual_rotated_plane():
    """Mittelpunktmaße gehören zur Flächenebene und dürfen nicht in die Öffnung führen."""
    from app.core.geom.boolean import boolean

    raw = boolean(
        "difference",
        [
            MeshData.of(trimesh.creation.box((20.0, 20.0, 4.0))),
            MeshData.of(trimesh.creation.cylinder(radius=2.0, height=10.0, sections=48)),
        ],
    ).mesh
    matrix = np.asarray(rotation("y", 37.0))
    mesh = apply(raw, matrix)
    centre = Feature(
        id="hole_1",
        kind="hole",
        provenance="generated",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": tuple(matrix[:3, 2]),
            "depth": 4.0,
            "diameter": 4.0,
        },
    )
    prepared = placement.prepare_surface(mesh, _top(raw), {centre.id: centre})
    point = tuple(trimesh.transform_points([[6.0, 5.0, 2.0]], matrix)[0])
    surface = placement.at_point(prepared, point)
    result = placement.point_with_centre(prepared, surface, centre.id, (3.123456789, 4.0))
    reference = next(item for item in result.centres if item.feature_id == centre.id)
    assert reference.offset == pytest.approx((3.123456789, 4.0), abs=1e-12)
    assert reference.distance == pytest.approx(math.hypot(3.123456789, 4.0))
    with pytest.raises(ValueError, match="außerhalb"):
        placement.point_with_centre(prepared, result, centre.id, (0.0, 0.0))
    with pytest.raises(ValueError, match="außerhalb"):
        placement.point_with_centre(prepared, result, centre.id, (100.0, 100.0))


def test_through_drill_preview_uses_the_target_size(profile):
    from app.core.types import SceneObject

    load_operations()
    source = SceneObject(
        id="obj_1", name="Würfel", mesh=MeshData.of(trimesh.creation.box((20.0, 20.0, 20.0)))
    )
    tool = placement.placement_tool(
        REGISTRY.get("drill_hole"), {"diameter": 4.0}, profile, source=source
    )
    assert 20.0 <= float(np.ptp(tool.raw.vertices[:, 2])) < 35.0


def test_a_nonuniform_bore_rim_does_not_shift_its_placement_anchor():
    """Zusätzliche Teilungen an einer Kreisstelle verschieben weder Mündung noch Bohrungsachse."""
    from shapely.geometry import Polygon

    from app.core.geom.prepare_ops import feature_placement_geometry
    from app.core.types import SceneObject

    angles = np.concatenate(
        (
            np.linspace(0.0, math.pi / 2.0, 33, endpoint=False),
            np.linspace(math.pi / 2.0, 2.0 * math.pi, 16, endpoint=False),
        )
    )
    points = np.column_stack((2.0 * np.cos(angles), 2.0 * np.sin(angles)))
    polygon = Polygon([(-20, -15), (20, -15), (20, 15), (-20, 15)], holes=[points])
    raw = trimesh.creation.extrude_polygon(polygon, 8.0)
    faces = np.flatnonzero(
        (np.linalg.norm(raw.triangles_center[:, :2], axis=1) < 3.0)
        & (np.abs(raw.face_normals[:, 2]) < 0.5)
    )
    feature = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 4.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 4.0,
            "depth": 8.0,
            "through": True,
        },
        face_indices=tuple(int(index) for index in faces),
    )
    source = SceneObject(
        id="obj_1", name="Platte", mesh=MeshData.of(raw), features={feature.id: feature}
    )
    load_operations()
    geometry = feature_placement_geometry(source, feature, "move_feature")
    assert geometry.frame.origin == pytest.approx((0.0, 0.0, 8.0), abs=1e-12)
    assert geometry.selected_offset == pytest.approx((0.0, 0.0, -4.0), abs=1e-12)


def test_prepared_feature_tool_keeps_geometry_out_of_point_updates(profile, monkeypatch):
    """Der Worker baut den Merkmalskörper; Punktänderungen verwenden nur den Versatz."""
    import app.core.geom.prepare_ops as module
    from app.core.geom.boolean import boolean
    from app.core.types import SceneObject

    load_operations()
    mesh = boolean(
        "difference",
        [
            MeshData.of(trimesh.creation.box((20.0, 20.0, 8.0))),
            MeshData.of(trimesh.creation.cylinder(radius=1.5, height=10.0, sections=48)),
        ],
    ).mesh
    feature = Feature(
        id="hole_1",
        kind="hole",
        provenance="generated",
        params={
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 3.0,
            "depth": 8.0,
            "through": True,
        },
    )
    source = SceneObject(id="obj_1", name="Platte", mesh=mesh, features={feature.id: feature})
    spec = REGISTRY.get("move_feature")
    tool = placement.prepare_tool(spec, {}, profile, source=source, feature=feature)
    monkeypatch.setattr(
        module,
        "feature_placement_geometry",
        lambda *_: pytest.fail("geometry rebuilt in point update"),
    )
    prepared = placement.prepare_surface(mesh, _top(mesh))
    for point in ((6.0, 4.0, 4.0), (7.123456789, 3.0, 4.0)):
        surface = placement.at_point(prepared, point)
        values = placement.surface_values(
            spec, surface, feature=feature, source=source, prepared_tool=tool
        )
        assert (values["x"], values["y"], values["z"]) == pytest.approx((*point[:2], 0.0))


@pytest.mark.parametrize(
    ("operation", "values"),
    [
        ("create_box", {"width": 12.0, "depth": 8.0, "height": 5.0}),
        ("create_box", {"width": 12.0, "depth": 8.0, "height": 5.0, "anchor": "corner"}),
        ("create_cylinder", {"diameter": 10.0, "height": 7.0, "segments": 32}),
        ("create_cone", {"bottom_diameter": 12.0, "top_diameter": 6.0, "height": 9.0}),
        ("create_sphere", {"diameter": 10.0, "segments": 24}),
        ("create_torus", {"outer_diameter": 20.0, "tube_diameter": 4.0, "segments": 32}),
    ],
)
def test_primitive_surface_route_places_the_actual_tool_without_rounding(
    operation, values, profile
):
    """Jeder Grundkörper nutzt vom Originaltreffer bis zur echten Op denselben Rahmen."""
    from tests.test_primitive_placement import _run

    load_operations()
    raw = trimesh.creation.box((40.0, 30.0, 8.0))
    original_face = _top(MeshData.of(raw))
    turn = np.asarray(rotation("y", 127.0))
    raw.apply_transform(turn)
    point = trimesh.transform_points([[4.123456789, 3.0, 4.0]], turn)[0]
    prepared = placement.prepare_surface(MeshData.of(raw), original_face)
    hit = placement.at_point(prepared, tuple(point))
    spec = REGISTRY.get(operation)
    assert placement.supports_surface_placement(spec)
    tool = placement.prepare_tool(spec, values, profile)
    placed_values = placement.surface_values(spec, hit, prepared_tool=tool)
    assert [placed_values[key] for key in ("x", "y", "z")] == pytest.approx(point, abs=1e-12)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((hit.frame.x_axis, hit.frame.y_axis, hit.normal))
    matrix[:3, 3] = point
    shown = apply(tool.mesh, matrix)
    actual = _run(operation, {**values, **placed_values}, profile).outputs[0].mesh
    assert actual.raw.vertices == pytest.approx(shown.raw.vertices, abs=1e-12)
    assert np.array_equal(actual.raw.faces, shown.raw.faces)


def test_primitive_preview_validates_dimensions_before_building(profile, monkeypatch):
    """Ungültige Maße erreichen auch über den Vorschauweg keine Geometriefunktion."""
    import app.core.geom.primitive_ops as module
    from app.core.errors import ValidationError

    load_operations()
    monkeypatch.setattr(module, "primitive_local_tool", lambda *_: pytest.fail("unvalidated build"))
    with pytest.raises(ValidationError):
        placement.prepare_tool(REGISTRY.get("create_cone"), {"height": -1.0}, profile)


def test_internal_shoulders_never_replace_the_outer_cavity_mouth():
    """Eine breitere Innenstufe ist keine Ansatzfläche der vollständigen Bohrkette."""
    from app.core.geom.prepare_ops import feature_placement_geometry
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chains
    from app.core.types import SceneObject

    outline = [
        [12.0, 0.0],
        [12.0, 12.0],
        [3.0, 12.0],
        [3.0, 9.0],
        [5.0, 9.0],
        [5.0, 6.0],
        [7.0, 6.0],
        [7.0, 3.0],
        [2.0, 3.0],
        [2.0, 0.0],
        [12.0, 0.0],
    ]
    mesh = MeshData.of(trimesh.creation.revolve(outline, sections=48))
    features = detect(mesh)
    chain = next(iter(cavity_chains(features, mesh)))
    assert len(chain) == 4
    source = SceneObject(id="obj_1", name="Innenstufen", mesh=mesh, features=features)
    geometry = feature_placement_geometry(source, chain[0], "move_feature")
    assert geometry.frame.origin == pytest.approx((0.0, 0.0, 12.0), abs=1e-10)
    assert geometry.frame.normal == pytest.approx((0.0, 0.0, 1.0))
    assert geometry.mesh.is_watertight
    assert geometry.mesh.bounds.maximum[2] == pytest.approx(0.0, abs=1e-10)
