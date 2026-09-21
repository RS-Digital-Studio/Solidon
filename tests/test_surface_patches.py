"""Analytische Teilträger behalten ihre wirkliche Lösung und Originalhaut."""

from __future__ import annotations

import math
from dataclasses import replace

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData
from app.core.types import Feature, SurfacePatch
from app.core.units import EPS_GEOM


def _patch(kind: str = "cylinder", indices: tuple[int, ...] = (0, 1)) -> SurfacePatch:
    params = {
        "plane": {"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0)},
        "cylinder": {"centre": (0.0, 0.0, 3.0), "axis": (0.0, 0.0, 1.0), "radius": 5.0},
        "cone": {"apex": (0.0, 0.0, -2.0), "axis": (0.0, 0.0, 1.0), "half_angle": math.pi / 6},
        "sphere": {"centre": (0.0, 0.0, 0.0), "radius": 5.0},
        "torus": {
            "centre": (0.0, 0.0, 0.0),
            "axis": (0.0, 0.0, 1.0),
            "ring_radius": 10.0,
            "tube_radius": 2.0,
        },
    }[kind]
    return SurfacePatch(kind, params, indices, "fit")


@pytest.mark.parametrize("kind", ("plane", "cylinder", "cone", "sphere", "torus"))
def test_surface_contract_accepts_only_the_owned_current_indices(kind: str) -> None:
    from app.core.perceive.surfaces import valid_patch

    patch = _patch(kind)
    assert valid_patch(patch, face_count=2, allowed_indices={0, 1, 7})
    assert not valid_patch(patch, face_count=1)
    assert not valid_patch(patch, allowed_indices={1, 7})


@pytest.mark.parametrize("indices", ((), (-1,), (True,), (1.5,), (0, 0)))
def test_surface_contract_rejects_invalid_indices(indices) -> None:
    from app.core.perceive.surfaces import valid_patch

    assert not valid_patch(_patch(indices=indices))


@pytest.mark.parametrize(
    "change",
    (
        {"radius": float("nan")},
        {"radius": float("inf")},
        {"radius": -1.0},
        {"radius": True},
        {"axis": (0.0, 0.0, 0.0)},
        {"axis": (1.0, 0.0)},
        {"centre": (0.0, float("nan"), 0.0)},
        {"extra": 2.0},
    ),
)
def test_surface_contract_never_repairs_bad_parameters(change) -> None:
    from app.core.perceive.surfaces import valid_patch

    patch = _patch()
    assert not valid_patch(replace(patch, params={**patch.params, **change}))


def test_surface_contract_rejects_wrong_nappe_and_nonring_torus() -> None:
    from app.core.perceive.surfaces import valid_patch

    cone, torus = _patch("cone"), _patch("torus")
    for angle in (0.0, -0.2, math.pi / 2):
        assert not valid_patch(replace(cone, params={**cone.params, "half_angle": angle}))
    assert not valid_patch(replace(torus, params={**torus.params, "tube_radius": 10.0}))
    assert not valid_patch(replace(cone, source="parameter"))


def test_planar_proof_checks_corners_instead_of_only_the_centroid() -> None:
    from app.core.perceive.surfaces import planar_patch

    corners = np.array(((0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 3.0, 0.0)))
    mesh = MeshData.of(trimesh.Trimesh(vertices=corners, faces=((0, 1, 2),), process=False))
    patch = planar_patch(mesh, (0,), (1.0, 1.0, 0.0), (0.0, 0.0, 1.0))
    assert patch is not None and patch.source == "facets"
    assert patch.face_indices == (0,)
    bent = corners.copy()
    bent[:, 2] = (-0.1, 0.0, 0.1)
    other = MeshData.of(trimesh.Trimesh(vertices=bent, faces=((0, 1, 2),), process=False))
    assert planar_patch(other, (0,), (1.0, 1.0, 0.0), (0.0, 0.0, 1.0)) is None
    np.testing.assert_array_equal(mesh.raw.vertices, corners)


def test_patch_clipping_and_reindexing_keep_separate_actual_carriers() -> None:
    from app.core.perceive.surfaces import clipped_patches, reindexed_patches

    first = _patch(indices=(0, 1))
    second = replace(_patch(indices=(2, 3)), params={**first.params, "radius": 5.02})
    clipped = clipped_patches((first, second), {1, 2})
    assert [part.face_indices for part in clipped] == [(1,), (2,)]
    mapped = reindexed_patches(clipped, (30, 10, 20, 40))
    assert [part.face_indices for part in mapped] == [(10,), (20,)]
    assert [part.params["radius"] for part in mapped] == [5.0, 5.02]
    assert reindexed_patches((_patch(indices=(-1,)),), (10, 20)) == ()
    assert reindexed_patches((second,), (10, 20)) == ()
    assert first.face_indices == (0, 1)


def test_numpy_triangle_numbers_return_plain_serializable_indices() -> None:
    from app.core.perceive.surfaces import planar_patch, reindexed_patches

    mesh = MeshData.of(trimesh.creation.box())
    indices = np.asarray(mesh.raw.facets[0])
    centre = tuple(float(value) for value in mesh.raw.triangles_center[indices[0]])
    axis = tuple(float(value) for value in mesh.raw.face_normals[indices[0]])
    plane = planar_patch(mesh, indices, centre, axis)
    assert plane is not None
    assert all(type(index) is int for index in plane.face_indices)
    result = reindexed_patches((_patch(),), np.asarray((11, 7)))
    assert result[0].face_indices == (11, 7)
    assert all(type(index) is int for index in result[0].face_indices)


@pytest.mark.parametrize("kind", ("plane", "cylinder", "cone", "sphere", "torus"))
def test_carrier_transform_uses_the_primitive_instead_of_the_feature_label(kind: str) -> None:
    from app.core.perceive.matching import transformed_features

    patch = _patch(kind)
    feature = Feature(
        "fillet_1", "fillet", "detected", {"centre": (90.0, 20.0, 0.0)}, surface_patches=(patch,)
    )
    transform = np.diag((-2.0, 2.0, 2.0, 1.0))
    transform[:3, 3] = (7.0, 11.0, -9.0)
    moved = transformed_features({feature.id: feature}, transform).candidates[feature.id]
    result = moved.surface_patches[0]
    point_key = "apex" if kind == "cone" else "centre"
    expected = transform @ (*patch.params[point_key], 1.0)
    assert result.params[point_key] == pytest.approx(expected[:3], abs=EPS_GEOM)
    for name in ("radius", "ring_radius", "tube_radius"):
        if name in patch.params:
            assert result.params[name] == pytest.approx(2 * patch.params[name], abs=EPS_GEOM)
    assert patch.params[point_key] != result.params[point_key]


def test_axially_symmetric_scaling_preserves_cylinder_cone_and_plane_only() -> None:
    from app.core.perceive.surfaces import transformed_patches

    patches = tuple(_patch(kind) for kind in ("plane", "cylinder", "cone", "sphere", "torus"))
    result = transformed_patches(patches, np.diag((2.0, 2.0, -3.0, 1.0)))
    assert [part.kind for part in result] == ["plane", "cylinder", "cone"]
    cone = result[-1]
    assert cone.params["axis"] == pytest.approx((0.0, 0.0, -1.0))
    assert cone.params["half_angle"] == pytest.approx(math.atan(2 / 3 * math.tan(math.pi / 6)))
    assert [part.kind for part in transformed_patches(patches, np.diag((2.0, 1.0, 1.0, 1.0)))] == [
        "plane"
    ]


def test_affine_plane_uses_its_normal_covector_and_keeps_all_transformed_corners() -> None:
    from app.core.perceive.surfaces import transformed_patches

    centre = (1.0, 2.0, 3.0)
    patch = SurfacePatch("plane", {"centre": centre, "axis": (1.0, 1.0, 1.0)}, (0,), "facets")
    corners = np.asarray((centre, (2.0, 1.0, 3.0), (1.0, 3.0, 2.0)))
    matrix = np.asarray(
        (
            (2.0, 0.5, 1.0, 7.0),
            (0.0, 3.0, -0.2, -11.0),
            (0.0, 0.0, -1.0, 19.0),
            (0.0, 0.0, 0.0, 1.0),
        )
    )
    current = transformed_patches((patch,), matrix)[0]
    moved = corners @ matrix[:3, :3].T + matrix[:3, 3]
    assert (moved - current.params["centre"]) @ current.params["axis"] == pytest.approx(
        np.zeros(3), abs=EPS_GEOM
    )
    assert np.linalg.norm(current.params["axis"]) == pytest.approx(1.0, abs=EPS_GEOM)
    assert current.source == "facets" and current.face_indices == (0,)
    assert patch.params == {"centre": centre, "axis": (1.0, 1.0, 1.0)}


def test_patch_helpers_stop_before_publishing_a_partial_result() -> None:
    from app.core.errors import OperationCancelled
    from app.core.perceive.surfaces import clipped_patches, planar_patch, transformed_patches
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    signal.cancel()
    mesh = MeshData.of(trimesh.creation.box())
    for action in (
        lambda: clipped_patches((_patch(),), {0, 1}, check_cancelled=signal.raise_if_cancelled),
        lambda: transformed_patches(
            (_patch(),), np.eye(4), check_cancelled=signal.raise_if_cancelled
        ),
        lambda: planar_patch(
            mesh, (0,), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), check_cancelled=signal.raise_if_cancelled
        ),
    ):
        with pytest.raises(OperationCancelled):
            action()


@pytest.mark.parametrize("kind", ("cone", "sphere", "torus"))
def test_real_recognition_keeps_the_accepted_carrier_without_a_second_fit(kind: str) -> None:
    from app.core.perceive.features import detect
    from tests.test_round_surface_measurements import _round_surface

    body = _round_surface(kind)
    vertices, faces = body.vertices.copy(), body.faces.copy()
    feature = next(value for value in detect(MeshData.of(body)).values() if value.kind == kind)
    assert len(feature.surface_patches) == 1
    patch = feature.surface_patches[0]
    assert patch.kind == kind and patch.source == "fit"
    assert patch.face_indices == feature.face_indices
    if kind == "cone":
        assert patch.params["apex"] == pytest.approx((0.0, 0.0, 0.0), abs=EPS_GEOM)
        assert patch.params["half_angle"] == pytest.approx(math.pi / 6, abs=EPS_GEOM)
        assert patch.params["axis"] == pytest.approx((0.0, 0.0, 1.0), abs=EPS_GEOM)
    elif kind == "sphere":
        assert patch.params["radius"] == pytest.approx(7.234567, abs=EPS_GEOM)
    else:
        assert patch.params["ring_radius"] == pytest.approx(17.125, abs=EPS_GEOM)
        assert patch.params["tube_radius"] == pytest.approx(3.234567, abs=EPS_GEOM)
    np.testing.assert_array_equal(body.vertices, vertices)
    np.testing.assert_array_equal(body.faces, faces)


def test_real_cylinder_and_planes_publish_their_distinct_sources() -> None:
    from app.core.perceive.features import detect

    source = MeshData.of(trimesh.creation.cylinder(radius=5.75, height=12.0, sections=48))
    found = detect(source)
    pin = next(feature for feature in found.values() if feature.kind == "pin")
    assert pin.surface_patches[0].params["radius"] == pytest.approx(5.75, abs=EPS_GEOM)
    assert pin.surface_patches[0].source == "fit"
    planes = [feature for feature in found.values() if feature.kind == "face"]
    assert len(planes) == 2
    assert all(feature.surface_patches[0].source == "facets" for feature in planes)
    assert all(
        feature.surface_patches[0].face_indices == feature.face_indices for feature in planes
    )


def test_closed_slots_keep_two_end_carriers_and_actual_flanks() -> None:
    from app.core.perceive.features import _fitted, _one_body, detect
    from tests.test_slot_features import a_foreign_slot

    travel = 20.0
    source = a_foreign_slot(12.0, travel)
    slot = next(feature for feature in detect(source).values() if feature.kind == "slot")
    arcs = [patch for patch in slot.surface_patches if patch.kind == "cylinder"]
    planes = [patch for patch in slot.surface_patches if patch.kind == "plane"]
    assert len(arcs) == len(planes) == 2
    assert [patch.params["radius"] for patch in arcs] == pytest.approx((6.0, 6.0), abs=EPS_GEOM)
    centres = sorted(tuple(patch.params["centre"]) for patch in arcs)
    assert np.linalg.norm(np.asarray(centres[1]) - centres[0]) == pytest.approx(
        travel, abs=EPS_GEOM
    )
    covered = [index for patch in slot.surface_patches for index in patch.face_indices]
    # Einzelne Übergangsdreiecke waren an keinem der beiden Fits beteiligt.
    # Sie werden weder zum nächsten Bogen noch zu einer Ebene geraten.
    fitted = _fitted(_one_body(source))
    assert {frozenset(part.face_indices) for part in arcs} == {
        frozenset(indices) for _fit, indices in fitted.fillets
    }
    assert set(covered) < set(slot.face_indices)
    assert len(covered) == len(set(covered))


@pytest.mark.parametrize("actual_fit", (False, True))
def test_stadium_parts_keep_the_accepted_frame_and_leave_crossing_triangles_unknown(
    actual_fit: bool,
) -> None:
    from app.core.perceive.features import StadiumFit, _fitted, _one_body
    from app.core.perceive.slots import slots_from_stadiums
    from tests.test_slot_features import a_foreign_slot

    source = _one_body(a_foreign_slot(12.0, 0.5))
    measured, indices = _fitted(source).stadiums[0]
    known = StadiumFit(
        axis=(0.0, 0.0, 1.0),
        centre=(0.0, 0.0, 0.0),
        direction=(1.0, 0.0, 0.0),
        radius=6.0,
        travel=0.5,
        depth=12.0,
        residual=0.0,
        inward=True,
    )
    fit = measured if actual_fit else known
    slot = slots_from_stadiums(source, [(fit, indices)])[0]
    arcs = [patch for patch in slot.surface_patches if patch.kind == "cylinder"]
    assert len(arcs) == 2
    assert [patch.params["radius"] for patch in arcs] == [fit.radius, fit.radius]
    for arc in arcs:
        offset = np.asarray(arc.params["centre"]) - fit.centre
        assert np.linalg.norm(offset) == pytest.approx(fit.travel / 2, abs=EPS_GEOM)
        assert abs(np.dot(offset, fit.direction)) == pytest.approx(fit.travel / 2, abs=EPS_GEOM)
    covered = [index for patch in slot.surface_patches for index in patch.face_indices]
    assert len(covered) == len(set(covered))
    if actual_fit:
        assert set(covered) < set(indices)
        assert abs(fit.radius - 6.0) > EPS_GEOM
    else:
        assert len([patch for patch in slot.surface_patches if patch.kind == "plane"]) == 2
        assert set(covered) == set(indices)


@pytest.mark.parametrize("local", (False, True))
def test_enclosed_air_keeps_its_original_cylinder_and_material_island(local: bool) -> None:
    from app.core.perceive.features import detect
    from app.core.perceive.local import detect_local

    stock = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    air = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=48)
    air.invert()
    island = trimesh.creation.icosphere(radius=1.0, subdivisions=2)
    source = MeshData.of(trimesh.util.concatenate((stock, air, island)))
    if local:
        seed = 13
        found = detect_local(
            source,
            tuple(source.raw.triangles_center[seed]),
            normal=tuple(source.raw.face_normals[seed]),
            radius=20.0,
            seed_faces=(seed,),
        ).features
    else:
        found = detect(source)
    cavity = next(feature for feature in found.values() if feature.kind == "void")
    assert not any(feature.kind == "hole" for feature in found.values())
    kinds = {patch.kind for patch in cavity.surface_patches}
    covered = {index for patch in cavity.surface_patches for index in patch.face_indices}
    if local:
        # Die Zusammenhangssuche hat die getrennte Insel nicht eingepasst;
        # ihre vollständige Luftzuordnung ist kein analytischer Formbeleg.
        assert kinds == {"plane", "cylinder"}
        assert covered == set(range(len(stock.faces), len(stock.faces) + len(air.faces)))
        assert set(cavity.face_indices) - covered == set(
            range(len(stock.faces) + len(air.faces), source.triangle_count)
        )
    else:
        assert kinds == {"plane", "cylinder", "sphere"}
        assert covered == set(cavity.face_indices)
    assert min(index for patch in cavity.surface_patches for index in patch.face_indices) >= len(
        stock.faces
    )


@pytest.mark.parametrize("round_cut", (False, True))
def test_open_slot_retains_its_actual_arc_and_newly_joined_faces(round_cut: bool) -> None:
    pytest.importorskip("OCP")
    from app.core.brep import edit
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect

    stock = edit.box(40.0, 30.0, 10.0)
    settings = {
        "position": (19.0 if round_cut else 17.0, 0.0, 5.0),
        "direction": (0.0, 0.0, 1.0),
        "diameter": 6.0,
        "depth": 10.0,
    }
    body = (
        edit.cut_bore(stock, **settings)
        if round_cut
        else edit.slot_bore(
            stock,
            **settings,
            length=18.0,
            angle_deg=0.0,
            overlap=0.0,
        )
    )
    mesh = as_mesh_data(body)
    slot = next(feature for feature in detect(mesh).values() if feature.kind == "slot")
    assert slot.params["open"]
    arcs = [patch for patch in slot.surface_patches if patch.kind == "cylinder"]
    assert len(arcs) == 1
    assert arcs[0].params["radius"] == pytest.approx(3.0, abs=EPS_GEOM)
    assert arcs[0].params["centre"] == pytest.approx(slot.params["arc_centre"], abs=EPS_GEOM)
    assert all(
        patch.source == "fit" if patch.kind == "cylinder" else patch.source == "facets"
        for patch in slot.surface_patches
    )
    covered = [index for patch in slot.surface_patches for index in patch.face_indices]
    assert set(covered) == set(slot.face_indices)
    assert len(covered) == len(set(covered))


def test_merged_slot_chamfer_retains_its_true_apices_and_radian_half_angles() -> None:
    from app.core.perceive import features
    from tests.test_features import _plate_with_a_chamfered_slot

    mesh = _plate_with_a_chamfered_slot()
    fitted = features._fitted(mesh)
    expected = features.detect_cones(mesh, fitted.cones)
    assert len(expected) == 2
    slot = next(feature for feature in features.detect(mesh).values() if feature.kind == "slot")
    cones = [patch for patch in slot.surface_patches if patch.kind == "cone"]
    assert len(cones) == 2
    assert {frozenset(part.face_indices) for part in cones} == {
        frozenset(feature.face_indices) for feature in expected
    }
    for feature in expected:
        assert feature.surface_patches[0] in cones
    assert slot.params["diameter"] == pytest.approx(6.0, abs=EPS_GEOM)
    assert slot.params["length"] == pytest.approx(26.0, abs=EPS_GEOM)


def test_a_slot_does_not_average_its_two_accepted_reference_radii() -> None:
    from app.core.perceive.features import _fitted, _one_body
    from app.core.perceive.slots import find_slots
    from tests.test_slot_features import a_foreign_slot

    mesh = _one_body(a_foreign_slot(12.0, 20.0))
    fits = _fitted(mesh).fillets
    assert len(fits) == 2
    first, second = fits
    changed = (first, (replace(second[0], radius=6.024), second[1]))
    slot = find_slots(mesh, changed)[0]
    arcs = [part for part in slot.surface_patches if part.kind == "cylinder"]
    assert sorted(part.params["radius"] for part in arcs) == pytest.approx(
        (6.0, 6.024), abs=EPS_GEOM
    )
    assert slot.diameter == pytest.approx(12.0, abs=EPS_GEOM)


def test_local_detection_reindexes_carriers_after_vertex_and_face_selection() -> None:
    from app.core.perceive.local import detect_local
    from tests.test_local_detection import blind_cylinder, bore_seed

    mesh = blind_cylinder()
    seed, point, normal = bore_seed(mesh)
    feature = next(
        feature
        for feature in detect_local(
            mesh,
            point,
            normal=normal,
            radius=20.0,
            seed_faces=(seed,),
        ).features.values()
        if feature.kind == "hole"
    )
    patch = feature.surface_patches[0]
    assert set(patch.face_indices) == set(feature.face_indices)
    assert min(patch.face_indices) > 0
    triangles = mesh.raw.triangles[list(patch.face_indices)]
    axis = np.asarray(patch.params["axis"])
    relative = triangles - patch.params["centre"]
    radial = relative - np.einsum("ijk,k->ij", relative, axis)[..., None] * axis
    assert np.max(np.linalg.norm(radial, axis=2)) == pytest.approx(
        patch.params["radius"], abs=EPS_GEOM
    )


@pytest.mark.parametrize("deviation", (0.15, 0.03))
def test_native_retriangulation_maps_patch_faces_and_discards_only_unproved_subsets(
    deviation: float,
) -> None:
    pytest.importorskip("OCP")
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.transform import moved_object
    from app.core.types import SceneObject

    solid = replace(edit.cylinder(6.0, 8.0), deflection=deviation)
    found = features_of(solid)
    pin = next(feature for feature in found.values() if feature.kind == "pin")
    native = pin.surface_patches[0]
    partial = replace(native, face_indices=native.face_indices[:1])
    pin = replace(pin, surface_patches=(native, partial))
    source = SceneObject(
        id="obj_1", name="Zylinder", mesh=solid, kind="brep", features={pin.id: pin}
    )
    old_triangles = as_mesh_data(solid).raw.triangles.copy()
    matrix = np.diag((10.0, 10.0, 10.0, 1.0))
    matrix[:3, 3] = (7.0, -11.0, 19.0)
    result = moved_object(source, matrix)
    current = result.features[pin.id]
    assert len(current.surface_patches) == 1
    patch = current.surface_patches[0]
    assert patch.face_indices == current.face_indices
    assert len(patch.face_indices) != len(native.face_indices)
    assert patch.params["radius"] == pytest.approx(30.0, abs=EPS_GEOM)
    assert patch.params["centre"] == pytest.approx(
        np.asarray(native.params["centre"]) * 10 + matrix[:3, 3], abs=EPS_GEOM
    )
    assert patch.source == "native"
    np.testing.assert_array_equal(as_mesh_data(solid).raw.triangles, old_triangles)


def test_recognition_cache_counts_carrier_indices_and_reuses_its_published_values(
    monkeypatch,
) -> None:
    """Der Cache wiegt seine Träger mit — und ein einzelner Eintrag über der Grenze bleibt.

    Bis zum 21.09.2026 warf die Verdrängung den einzigen Eintrag weg und
    brach erst danach ab; der Kommentar daneben versprach das Gegenteil. Ein
    Modell, das allein über der Grenze liegt, wäre so bei jedem Schritt neu
    erkannt worden — der Cache nicht begrenzt, sondern aus.
    """
    from collections import OrderedDict

    from app.core.perceive import features

    monkeypatch.setattr(features, "_FEATURE_CACHE", OrderedDict())
    monkeypatch.setattr(features, "_CACHE_INDICES", {})
    monkeypatch.setattr(features, "_FREEFORM_DROPPED", {})
    monkeypatch.setattr(features, "_UNREADABLE_VOIDS", {})
    mesh = MeshData.of(trimesh.creation.box(extents=(20.0, 30.0, 40.0)))
    result = features.detect(mesh)
    assert len(result) == 6
    assert sum(features._CACHE_INDICES.values()) == 24
    with monkeypatch.context() as read:
        read.setattr(
            features, "_fitted", lambda *_a, **_kw: pytest.fail("warm cache must not refit")
        )
        assert features.detect(mesh) == result
    features.forget_cache()
    monkeypatch.setattr(features, "CACHE_INDEX_LIMIT", 23)
    assert features.detect(mesh) == result
    assert len(features._FEATURE_CACHE) == 1, "der einzige Eintrag bleibt, auch über der Grenze"
    assert sum(features._CACHE_INDICES.values()) == 24
    with monkeypatch.context() as read:
        read.setattr(
            features, "_fitted", lambda *_a, **_kw: pytest.fail("warm cache must not refit")
        )
        assert features.detect(mesh) == result
    # Ein zweiter Eintrag verdrängt den ersten: Über der Grenze bleibt genau einer.
    other = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    assert len(features.detect(other)) == 6
    assert list(features._FEATURE_CACHE) == [features._mesh_key(other)]


def test_a_cancelled_planar_publication_leaves_no_partial_detection_cache(monkeypatch) -> None:
    from collections import OrderedDict

    from app.core.errors import OperationCancelled
    from app.core.perceive import features
    from app.core.scene.cancel import CancelSignal

    mesh = MeshData.of(trimesh.creation.box(extents=(20.0, 30.0, 40.0)))
    vertices, faces = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    monkeypatch.setattr(features, "_FEATURE_CACHE", OrderedDict())
    monkeypatch.setattr(features, "_CACHE_INDICES", {})
    monkeypatch.setattr(features, "_FREEFORM_DROPPED", {})
    signal = CancelSignal()
    calls = []
    original = features.planar_patch

    def stopped(*args, **kwargs):
        assert kwargs["check_cancelled"] == signal.raise_if_cancelled
        result = original(*args, **kwargs)
        calls.append(result)
        signal.cancel()
        return result

    with monkeypatch.context() as active:
        active.setattr(features, "planar_patch", stopped)
        with pytest.raises(OperationCancelled):
            features.detect(mesh, check_cancelled=signal.raise_if_cancelled)
    assert len(calls) == 1
    assert not features._FEATURE_CACHE and not features._CACHE_INDICES
    signal.reset()
    assert len(features.detect(mesh, check_cancelled=signal.raise_if_cancelled)) == 6
    np.testing.assert_array_equal(mesh.raw.vertices, vertices)
    np.testing.assert_array_equal(mesh.raw.faces, faces)


def test_carrier_reindexing_can_stop_inside_its_original_index_block(monkeypatch) -> None:
    from app.core.errors import OperationCancelled
    from app.core.perceive import surfaces
    from app.core.scene.cancel import CancelSignal

    monkeypatch.setattr(surfaces, "PATCH_BLOCK", 2)
    signal = CancelSignal()
    mapped = []

    class IndexMap:
        def __len__(self):
            return 6

        def __getitem__(self, index):
            mapped.append(index)
            if len(mapped) == 2:
                signal.cancel()
            return index + 10

    original = _patch(indices=tuple(range(6)))
    with pytest.raises(OperationCancelled):
        surfaces.reindexed_patches(
            (original,), IndexMap(), check_cancelled=signal.raise_if_cancelled
        )
    assert mapped == [0, 1]
    assert original.face_indices == tuple(range(6))
    assert surfaces.reindexed_patches((original,), tuple(range(10, 16)))[0].face_indices == tuple(
        range(10, 16)
    )


def test_two_voids_clip_the_original_carrier_before_semantic_deletion() -> None:
    from app.core.perceive.features import voids_instead_of_phantom_bores

    carrier = _patch(indices=(0, 1, 2, 3))
    old = Feature(
        "hole_1",
        "hole",
        "detected",
        {},
        face_indices=carrier.face_indices,
        surface_patches=(carrier,),
    )
    first = Feature("void_1", "void", "detected", {}, face_indices=(0, 1, 2))
    second = Feature("void_2", "void", "detected", {}, face_indices=(3,))
    result = voids_instead_of_phantom_bores({old.id: old}, (first, second))
    assert old.id not in result
    assert result[first.id].surface_patches[0].face_indices == (0, 1, 2)
    assert result[second.id].surface_patches[0].face_indices == (3,)
    assert old.surface_patches == (carrier,)


def test_two_real_air_chambers_keep_their_own_round_surfaces() -> None:
    from app.core.perceive.features import detect

    stock = trimesh.creation.box(extents=(50.0, 30.0, 20.0))
    chambers = []
    for x, radius in ((-10.0, 3.0), (10.0, 4.0)):
        air = trimesh.creation.cylinder(radius=radius, height=8.0, sections=48)
        air.apply_translation((x, 0.0, 0.0))
        air.invert()
        chambers.append(air)
    source = MeshData.of(trimesh.util.concatenate((stock, *chambers)))
    voids = sorted(
        (feature for feature in detect(source).values() if feature.kind == "void"),
        key=lambda feature: feature.params["centre"][0],
    )
    assert len(voids) == 2
    for index, (void, radius, x) in enumerate(zip(voids, (3.0, 4.0), (-10.0, 10.0), strict=True)):
        arcs = [patch for patch in void.surface_patches if patch.kind == "cylinder"]
        assert len(arcs) == 1
        assert arcs[0].params["radius"] == pytest.approx(radius, abs=EPS_GEOM)
        assert arcs[0].params["centre"][0] == pytest.approx(x, abs=EPS_GEOM)
        covered = {face for patch in void.surface_patches for face in patch.face_indices}
        first = len(stock.faces) + index * len(chambers[0].faces)
        assert covered == set(range(first, first + len(chambers[index].faces)))


def test_recognised_reflected_cone_keeps_the_nappe_containing_its_actual_skin() -> None:
    from app.core.perceive.features import detect
    from tests.test_round_surface_measurements import _round_surface

    body = _round_surface("cone")
    pose = np.diag((1.0, 1.0, -1.0, 1.0))
    pose[:3, 3] = (7.0, -11.0, 19.0)
    body.apply_transform(pose)
    feature = next(
        feature for feature in detect(MeshData.of(body)).values() if feature.kind == "cone"
    )
    patch = feature.surface_patches[0]
    assert patch.params["apex"] == pytest.approx((7.0, -11.0, 19.0), abs=EPS_GEOM)
    assert patch.params["axis"] == pytest.approx((0.0, 0.0, -1.0), abs=EPS_GEOM)
    assert patch.params["half_angle"] == pytest.approx(math.pi / 6, abs=EPS_GEOM)
    relative = body.triangles[list(patch.face_indices)] - patch.params["apex"]
    assert np.all(relative @ patch.params["axis"] > 0.0)
