"""Sackboden-Kennungen bei bewusst geänderter Bohrungsweite erhalten."""

from __future__ import annotations

import importlib
import math
from dataclasses import replace

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.perceive.features import detect
from app.core.perceive.local import detect_local
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, Finding, OpContext, Operation, Profile, Scene, SceneObject
from tests.test_local_detection import blind_cylinder, bore_seed


def _resize(source: SceneObject, hole: Feature, diameter: float, profile: Profile, **params):
    """Den Kundenvertrag einschließlich der anschließenden Zuordnung ausführen."""
    load_operations()
    operation = Operation(9, "resize_hole")
    spec = REGISTRY.get("resize_hole")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=hole.id, diameter=diameter, compensate=False, **params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda *_args: None,
            ask=lambda *_args: pytest.fail("unexpected question"),
            cancelled=NeverCancelled(),
        )
    )
    findings: list[Finding] = list(result.findings)
    evaluation = importlib.import_module("app.core.scene.evaluate")
    changed = evaluation._with_features(
        result.outputs[0],
        source.features,
        operation,
        lambda *_args: pytest.fail("unexpected matching question"),
        findings,
        previous_bounds=source.mesh.bounds,
    )
    return changed, findings, result


def _floor_at(features: dict[str, Feature], height: float) -> Feature:
    """Die unabhängig bekannte Bodenhöhe bestimmt den Eingang der Gegenprobe."""
    found = [
        feature
        for feature in features.values()
        if feature.kind == "face"
        and np.allclose(feature.params["centre"], (0, 0, height), atol=1e-4)
        and np.allclose(np.abs(feature.params["normal"]), (0, 0, 1), atol=1e-4)
    ]
    assert len(found) == 1
    return found[0]


def _assert_floor(changed: SceneObject, identifier: str, diameter: float, height: float) -> None:
    """Neue reale Bodenfläche, geschlossener Körper und derselbe alte Verweis."""
    body = as_mesh_data(changed.mesh)
    assert body.is_watertight and body.component_count == 1
    assert body.raw.nondegenerate_faces().all()
    floor = changed.features[identifier]
    assert floor.recognised and floor.kind == "face" and floor.face_indices
    indices = np.asarray(floor.face_indices)
    points = np.asarray(body.raw.triangles)[indices]
    assert np.allclose(points[:, :, 2], height, atol=1e-5)
    actual_area = float(np.asarray(body.raw.area_faces)[indices].sum())
    ideal_area = math.pi * diameter**2 / 4
    assert actual_area == pytest.approx(ideal_area, rel=0.005)
    if changed.kind == "brep":
        assert floor.params["area"] == pytest.approx(ideal_area, abs=1e-4)
    else:
        assert floor.params["area"] == pytest.approx(actual_area, abs=1e-4)


@pytest.mark.parametrize("diameter", [4.0, 8.0])
def test_resizing_changes_the_floor_measure_without_orphaning_its_reference(
    profile: Profile, diameter: float
) -> None:
    """Eigener Korpus: Ø6, 5 mm tief; nur Radius und Bodenfläche ändern sich."""
    mesh = blind_cylinder()
    features = detect(mesh)
    old = _floor_at(features, 15.0)
    floor = replace(old, id="known_floor")
    features = {name: item for name, item in features.items() if name != old.id}
    features[floor.id] = floor
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    source = SceneObject("own", "Eigener Zylinder", mesh, features=features)
    before = mesh.raw.vertices.copy()
    assert mesh.is_watertight and mesh.component_count == 1
    assert float(floor.params["area"]) == pytest.approx(
        64 * 9 / 2 * math.sin(math.tau / 64), abs=1e-4
    )
    changed, findings, result = _resize(source, hole, diameter, profile)
    assert result.solver is not None and result.solver.strategy == "direct"
    _assert_floor(changed, floor.id, diameter, 15.0)
    assert not [finding for finding in findings if finding.code == "perceive.orphaned"]
    assert np.array_equal(mesh.raw.vertices, before) and source.features[floor.id] == floor


def test_resizing_a_locally_recognised_large_bore_keeps_the_floor_reference(profile: Profile):
    """Der echte Körper über einer Million Dreiecken bleibt beim lokalen Suchweg."""
    mesh = blind_cylinder(dense=True)
    seed, point, normal = bore_seed(mesh)
    features = detect_local(mesh, point, normal=normal, radius=10.0, seed_faces=(seed,)).features
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    floor = _floor_at(features, 15.0)
    source = SceneObject("own", "Eigener großer Zylinder", mesh, features=features)
    assert mesh.triangle_count > 1_000_000
    changed, findings, result = _resize(source, hole, 8.0, profile)
    assert changed.mesh.triangle_count > 1_000_000
    _assert_floor(changed, floor.id, 8.0, 15.0)
    assert not [finding for finding in findings if finding.code == "perceive.orphaned"]
    assert result.solver is not None and result.solver.strategy == "direct"


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("mode", ["keep", "follow"])
@pytest.mark.parametrize("diameter", [4.0, 8.0])
def test_sunken_bore_preserves_the_floor_reference_on_both_kernels(
    profile: Profile, kind: str, mode: str, diameter: float
) -> None:
    """Eigene Senkbohrung: Boden z=2; der Einlauf ändert seine Zugehörigkeit nicht."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.sketch.planes import frame_of

    solid = edit.bore_profile(
        edit.box(30, 24, 12),
        [(0, 2), (3, 2), (3, 10), (5, 12), (0, 12), (0, 2)],
        frame_of((0, 0, 1), (0, 0, 0)),
    )
    mesh = solid if kind == "brep" else as_mesh_data(solid)
    features = features_of(solid) if kind == "brep" else detect(mesh)
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    floor = _floor_at(features, 2.0)
    source = SceneObject("own", "Eigene Senkbohrung", mesh, kind=kind, features=features)
    changed, findings, _result = _resize(source, hole, diameter, profile, entrance_mode=mode)
    _assert_floor(changed, floor.id, diameter, 2.0)
    assert not [finding for finding in findings if finding.code == "perceive.orphaned"]


@pytest.mark.parametrize("mode", ["keep", "follow"])
@pytest.mark.parametrize("diameter", [6.0, 10.0])
@pytest.mark.parametrize("turned", [False, True])
def test_sloping_floor_keeps_its_entire_surface_and_identifier(
    profile: Profile, mode: str, diameter: float, turned: bool
) -> None:
    """Schräger Boden und freie Lage werden an der realen Ebene wiedererkannt."""
    from tests.test_bore_mouth_resize import _sloping_bore

    mesh, _features, _hole = _sloping_bore()
    transform = np.eye(4)
    if turned:
        transform = trimesh.transformations.rotation_matrix(0.73, (1, 2, 3))
        transform[:3, 3] = (17, -31, 9)
        raw = mesh.raw.copy()
        raw.apply_transform(transform)
        mesh = MeshData.of(raw)
    features = detect(mesh)
    inverse = np.linalg.inv(transform)
    floor = next(
        feature
        for feature in features.values()
        if feature.kind == "face"
        and np.allclose(
            trimesh.transform_points([feature.params["centre"]], inverse)[0],
            (0, 0, 3),
            atol=1e-3,
        )
    )
    hole = min(
        (feature for feature in features.values() if feature.kind == "hole"),
        key=lambda feature: abs(
            trimesh.transform_points([feature.params["centre"]], inverse)[0, 0]
        ),
    )
    source = SceneObject("own", "Eigene schräge Senkbohrung", mesh, features=features)
    changed, findings, _result = _resize(source, hole, diameter, profile, entrance_mode=mode)
    kept = changed.features[floor.id]
    body = as_mesh_data(changed.mesh)
    assert kept.recognised and body.is_watertight and body.component_count == 1
    points = trimesh.transform_points(np.asarray(body.raw.vertices), inverse)
    triangles = points[np.asarray(body.raw.faces)]
    on_floor = np.all(np.abs(triangles[:, :, 2] - 3 - 0.04 * triangles[:, :, 0]) < 1e-5, axis=1)
    assert set(kept.face_indices) == set(np.flatnonzero(on_floor))
    assert kept.params["area"] == pytest.approx(
        math.pi * diameter**2 / 4 * math.sqrt(1 + 0.04**2), rel=0.005
    )
    assert not [finding for finding in findings if finding.code == "perceive.orphaned"]


def test_outer_annuli_and_an_unrelated_coplanar_floor_are_not_bore_floors(profile: Profile):
    """Gleiche Höhe und Achsrichtung ersetzen keine echte gemeinsame Randlinie."""
    from app.core.geom.prepare_ops import _bore_floor

    first = blind_cylinder()
    other = first.raw.copy()
    other.apply_translation((240, 0, 0))
    mesh = MeshData.of(trimesh.util.concatenate((first.raw, other)))
    features = detect(mesh)
    hole = min(
        (feature for feature in features.values() if feature.kind == "hole"),
        key=lambda feature: feature.params["centre"][0],
    )
    floor = _floor_at(features, 15.0)
    incomplete = {name: feature for name, feature in features.items() if name != floor.id}
    assert _bore_floor(mesh, hole, incomplete, None, combine=True) is None
    source = SceneObject("own", "Zwei eigene Sackbohrungen", mesh, features=features)
    changed, _findings, _result = _resize(source, hole, 8.0, profile)
    other_floor = next(
        feature
        for feature in features.values()
        if feature.kind == "face" and np.allclose(feature.params["centre"], (240, 0, 15))
    )
    assert changed.features[other_floor.id].params["area"] == pytest.approx(
        other_floor.params["area"]
    )
    assert changed.features[other_floor.id].params["centre"] == pytest.approx(
        other_floor.params["centre"]
    )
    assert changed.features[floor.id].params["area"] > other_floor.params["area"]


@pytest.mark.parametrize("invalid", ["ambiguous", "partial", "shifted"])
def test_floor_mapping_requires_unique_full_topology_on_the_same_plane(invalid: str):
    """Doppelte Eigentümer, halbe Böden und eine neue Tiefe erhalten keine Zusage."""
    from app.core.geom.prepare_ops import _resized_bore_floor

    mesh = blind_cylinder()
    features = detect(mesh)
    floor = _floor_at(features, 15.0)
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    changed = mesh
    found = dict(features)
    if invalid == "ambiguous":
        found["duplicate_floor"] = replace(floor, id="duplicate_floor")
    elif invalid == "partial":
        found[floor.id] = replace(floor, face_indices=floor.face_indices[:10])
    else:
        raw = mesh.raw.copy()
        points = np.asarray(raw.vertices).copy()
        points[np.isclose(points[:, 2], 15), 2] = 14
        raw.vertices = points
        changed = MeshData.of(raw)
        found = detect(changed)
    after = next(feature for feature in found.values() if feature.kind == "hole")
    assert _resized_bore_floor(mesh, hole, features, changed, after, found) == {}


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_repeated_resize_updates_a_previously_preserved_floor(profile: Profile, kind: str):
    """Auch ein schon zusammengesetzter Boden behält beim nächsten Maß seine Kennung."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.sketch.planes import feature_plane, frame_for, frame_of

    solid = edit.bore_profile(
        edit.box(30, 24, 12),
        [(0, 2), (3, 2), (3, 10), (5, 12), (0, 12), (0, 2)],
        frame_of((0, 0, 1), (0, 0, 0)),
    )
    mesh = solid if kind == "brep" else as_mesh_data(solid)
    features = features_of(solid) if kind == "brep" else detect(mesh)
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    floor = _floor_at(features, 2.0)
    current = SceneObject("own", "Wiederholte Bodenänderung", mesh, kind=kind, features=features)
    for diameter in (8.0, 4.0, 10.0):
        current, _findings, _result = _resize(current, current.features[hole.id], diameter, profile)
        _assert_floor(current, floor.id, diameter, 2.0)
        frame = frame_for(feature_plane(current.id, floor.id), [current])
        assert frame.origin == pytest.approx((0, 0, 2), abs=1e-4)


def test_unwelded_original_uses_geometric_shared_floor_edges(profile: Profile):
    """STL-Einzeldreiecke bleiben im Eingang unverändert, die Randzuordnung trägt."""
    raw = blind_cylinder().raw
    triangles = np.asarray(raw.triangles)
    separated = trimesh.Trimesh(
        triangles.reshape(-1, 3), np.arange(triangles.size // 3).reshape(-1, 3), process=False
    )
    mesh = MeshData.of(separated)
    features = detect(mesh)
    floor = _floor_at(features, 15)
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    source = SceneObject("own", "Eigene STL-Dreiecke", mesh, features=features)
    changed, _findings, _result = _resize(source, hole, 8, profile)
    _assert_floor(changed, floor.id, 8, 15)
    assert mesh.vertex_count == mesh.triangle_count * 3


def test_floor_mapping_obeys_cancellation_before_reading_topology():
    """Ein abgebrochener Suchauftrag übernimmt auch keinen scheinbar passenden Boden."""
    from app.core.errors import OperationCancelled
    from app.core.geom.prepare_ops import _resized_bore_floor
    from app.core.scene.cancel import CancelSignal

    mesh = blind_cylinder()
    features = detect(mesh)
    hole = next(feature for feature in features.values() if feature.kind == "hole")
    cancelled = CancelSignal()
    cancelled.cancel()
    with pytest.raises(OperationCancelled):
        _resized_bore_floor(
            mesh, hole, features, mesh, hole, features, check_cancelled=cancelled.raise_if_cancelled
        )
