"""Vollständige lokale Merkmale am Originalnetz und ihr gespeicherter Auftrag."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData

DATA = Path(__file__).parent / "data"


def blind_cylinder(*, dense: bool = False) -> MeshData:
    """Analytischer Körper aus der eigenen Korpusdefinition, ohne Booleschen Kern."""
    spec = json.loads((DATA / "local_detection.json").read_text(encoding="utf-8"))
    count = spec["sections"] if dense else 64
    levels = spec["outer_levels"] if dense else 2
    angles = np.arange(count) * (2 * np.pi / count)
    radial = np.column_stack((np.cos(angles), np.sin(angles)))
    outer = np.empty((levels + 1, count, 3))
    outer[:, :, :2] = radial * spec["outer_radius"]
    outer[:, :, 2] = np.linspace(0, spec["height"], levels + 1)[:, None]
    top = np.column_stack((radial * spec["bore_radius"], np.full(count, spec["height"])))
    floor_z = spec["height"] - spec["bore_depth"]
    floor = np.column_stack((radial * spec["bore_radius"], np.full(count, floor_z)))
    vertices = np.vstack((outer.reshape(-1, 3), top, floor, [[0, 0, 0], [0, 0, floor_z]]))
    ti, bi, ci = (levels + 1) * count, (levels + 2) * count, (levels + 3) * count
    k, following = np.arange(count), np.roll(np.arange(count), -1)
    lower = np.arange(levels)[:, None] * count + k
    after = np.arange(levels)[:, None] * count + following
    faces = np.vstack(
        (
            np.stack((lower, after, lower + count), axis=-1).reshape(-1, 3),
            np.stack((after, after + count, lower + count), axis=-1).reshape(-1, 3),
            np.column_stack((levels * count + k, levels * count + following, ti + k)),
            np.column_stack((levels * count + following, ti + following, ti + k)),
            np.column_stack((following, k, np.full(count, ci))),
            np.column_stack((ti + k, ti + following, bi + k)),
            np.column_stack((ti + following, bi + following, bi + k)),
            np.column_stack((bi + k, bi + following, np.full(count, ci + 1))),
        )
    )
    return MeshData.of(trimesh.Trimesh(vertices, faces, process=False))


def bore_seed(mesh: MeshData) -> tuple[int, tuple[float, ...], tuple[float, ...]]:
    """Echte Dreiecksmitte einer nach innen gerichteten Wand, ohne Erkennung."""
    triangles = np.asarray(mesh.raw.triangles)
    radial = np.linalg.norm(triangles[:, :, :2], axis=2)
    face = int(
        np.flatnonzero(
            np.all(np.isclose(radial, 3), axis=1)
            & (triangles[:, :, 2].max(axis=1) > 19)
            & (triangles[:, :, 2].min(axis=1) < 16)
        )[0]
    )
    return (
        face,
        tuple(float(value) for value in mesh.raw.triangles_center[face]),
        tuple(float(value) for value in mesh.raw.face_normals[face]),
    )


@pytest.mark.parametrize(
    ("point", "radius"),
    [((0, 0, 17.5), 8), ((0, 0, 10), 101), ((200, 0, 17.5), 8)],
)
def test_region_filter_preserves_the_original_all_points_boundary(monkeypatch, point, radius):
    """Blockweise Umfangsprüfung liefert dieselbe Menge wie alle Originalpunkte auf einmal."""
    from app.core.perceive import local
    from app.core.perceive.features import detect
    from app.core.units import EPS_GEOM

    mesh = blind_cylinder()
    features = detect(mesh)
    expected = tuple(
        name
        for name, feature in features.items()
        if np.all(
            np.linalg.norm(
                mesh.raw.vertices[mesh.raw.faces[list(feature.face_indices)]] - point,
                axis=2,
            )
            <= radius + EPS_GEOM
        )
    )
    monkeypatch.setattr(local, "SCAN_BLOCK", 3)
    assert local.features_in_region(mesh, features, point, radius=radius) == expected


def test_region_filter_can_cancel_between_original_face_blocks(monkeypatch):
    """Ein einziger großer bekannter Fleck hält den Abbruch nicht bis zum Ende auf."""
    from app.core.errors import OperationCancelled
    from app.core.perceive import local
    from app.core.perceive.features import detect

    mesh = blind_cylinder()
    features = detect(mesh)
    mantle = next(feature for feature in features.values() if feature.kind == "pin")
    assert len(mantle.face_indices) > 200
    monkeypatch.setattr(local, "SCAN_BLOCK", 16)
    checks = []

    def stop():
        checks.append(True)
        if len(checks) == 3:
            raise OperationCancelled

    with pytest.raises(OperationCancelled):
        local.features_in_region(
            mesh, {mantle.id: mantle}, (0, 0, 0), radius=200, check_cancelled=stop
        )
    assert len(checks) == 3


def test_large_blind_bore_is_complete_and_uses_original_indices() -> None:
    """Über einer Million Dreiecken bleibt Ø6/Tiefe5 ein echtes Sackloch."""
    from app.core.perceive.local import detect_local

    mesh = blind_cylinder(dense=True)
    spec = json.loads((DATA / "local_detection.json").read_text(encoding="utf-8"))
    assert mesh.triangle_count == spec["expected_triangles"]
    assert mesh.raw.is_watertight and mesh.raw.is_winding_consistent
    assert mesh.component_count == 1
    assert np.all(mesh.raw.area_faces > 0)
    expected = (
        0.5
        * spec["sections"]
        * np.sin(2 * np.pi / spec["sections"])
        * (
            spec["outer_radius"] ** 2 * spec["height"]
            - spec["bore_radius"] ** 2 * spec["bore_depth"]
        )
    )
    assert mesh.volume == pytest.approx(expected, abs=1e-7)
    before_vertices, before_faces = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    face, point, normal = bore_seed(mesh)
    result = detect_local(mesh, point, normal=normal, radius=8, seed_faces=(face,))
    assert result.complete
    holes = [feature for feature in result.features.values() if feature.kind == "hole"]
    assert len(holes) == 1
    hole = holes[0]
    assert hole.params["diameter"] == pytest.approx(6, abs=1e-4)
    assert hole.params["depth"] == pytest.approx(5, abs=1e-4)
    assert hole.params["through"] is False
    assert len(hole.face_indices) == 2048
    assert face in hole.face_indices
    assert min(hole.face_indices) > 1_000_000
    assert all(feature.kind != "edge_loop" for feature in result.features.values())
    assert np.array_equal(mesh.raw.vertices, before_vertices)
    assert np.array_equal(mesh.raw.faces, before_faces)


@pytest.mark.parametrize("radius", [0.5, 2.0])
def test_search_boundary_never_creates_a_partial_bore(radius: float) -> None:
    """Ein unvollständiger Mantel wird weder Bohrung noch runde Ersatzfläche."""
    from app.core.perceive.local import detect_local

    mesh = blind_cylinder()
    face, point, normal = bore_seed(mesh)
    result = detect_local(mesh, point, normal=normal, radius=radius, seed_faces=(face,))
    assert not result.complete
    assert not result.features
    assert result.reason == "boundary"


def test_cancellation_during_original_scan_publishes_nothing() -> None:
    """Abbruch mitten im blockweisen Originaldurchgang erreicht den Aufrufer."""
    from app.core.errors import OperationCancelled
    from app.core.perceive.local import detect_local

    mesh = blind_cylinder()
    face, point, normal = bore_seed(mesh)
    checks = 0

    def cancel() -> None:
        nonlocal checks
        checks += 1
        if checks == 3:
            raise OperationCancelled

    with pytest.raises(OperationCancelled):
        detect_local(
            mesh, point, normal=normal, radius=8, seed_faces=(face,), check_cancelled=cancel
        )


def test_face_budget_is_not_a_permission_for_partial_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Laufzeitgrenze liefert keinen vermeintlich fertigen Teilbereich."""
    from app.core.perceive import local

    mesh = blind_cylinder()
    face, point, normal = bore_seed(mesh)
    monkeypatch.setattr(local, "LOCAL_FACE_LIMIT", 10)
    result = local.detect_local(mesh, point, normal=normal, radius=8, seed_faces=(face,))
    assert result.reason == "budget"
    assert not result.features


@pytest.mark.parametrize("hint", [-1, 0])
def test_missing_or_stale_face_hint_is_checked_geometrically(hint: int) -> None:
    """Eine alte Dreiecksnummer kann niemals eine andere Stelle auswählen."""
    from app.core.perceive.local import detect_local

    mesh = blind_cylinder()
    face, point, normal = bore_seed(mesh)
    found = detect_local(mesh, point, normal=normal, radius=8, seed_faces=(hint,))
    assert found.complete
    assert any(face in feature.face_indices for feature in found.features.values())


def test_shared_diagonal_on_one_plane_is_one_surface() -> None:
    """Ein Treffer genau auf der Dreiecksdiagonale löst keine Rückfrage aus."""
    from app.core.perceive.local import detect_local

    mesh = MeshData.of(trimesh.creation.box((4, 4, 4)))
    result = detect_local(mesh, (0, 0, 2), normal=(0, 0, 1), radius=8)
    assert result.complete
    assert not result.seed_choices
    assert len(result.selected) == 1
    hints = tuple(int(index) for index in np.flatnonzero(mesh.raw.face_normals[:, 2] > 0.9))
    grouped = detect_local(mesh, (0, 0, 2), normal=(0, 0, 1), radius=8, seed_faces=hints)
    assert grouped.complete and not grouped.seed_choices


def test_distinct_overlaid_planes_ask_once_and_replay_the_saved_seed(profile) -> None:
    """Eine wirkliche Mehrdeutigkeit wird gefragt und als Operationsparameter gespeichert."""
    from app.core.perceive.ops import DetectRegionParams, detect_region
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    first, second = (trimesh.creation.box((4, 4, 4)) for _index in range(2))
    first.apply_translation((-0.3, -0.1, 0))
    second.apply_translation((0.4, 0.2, 0))
    source = SceneObject(
        "own", "Zwei Körper", MeshData.of(trimesh.util.concatenate([first, second]))
    )
    asked = []

    def ask(question, choices):
        asked.append((question, choices))
        return choices[-1]

    params = DetectRegionParams(radius=8, z=2)
    ctx = OpContext(
        Scene(objects={source.id: source}),
        [source],
        params,
        profile,
        "fine",
        None,
        lambda *_args: None,
        ask,
        NeverCancelled(),
    )
    chosen = detect_region(ctx)
    assert len(asked) == 1 and len(asked[0][1]) == 2
    assert chosen.answered["seed_face"] >= len(first.faces)
    repeated = detect_region(
        replace(
            ctx,
            params=replace(params, **chosen.answered),
            ask=lambda *_args: pytest.fail("unexpected repeated question"),
        )
    )
    assert repeated.outputs[0].features == chosen.outputs[0].features


def test_detect_region_preserves_geometry_and_repeated_ids(profile) -> None:
    """Derselbe Auftrag findet denselben Namen, ohne das Netz neu zu speichern."""
    from app.core.perceive.ops import DetectRegionParams, detect_region
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    mesh = blind_cylinder()
    face, point, normal = bore_seed(mesh)
    source = SceneObject("own", "Eigener Körper", mesh)
    params = DetectRegionParams(
        radius=8,
        x=point[0],
        y=point[1],
        z=point[2],
        nx=normal[0],
        ny=normal[1],
        nz=normal[2],
        seed_face=face,
    )
    ctx = OpContext(
        Scene(objects={source.id: source}),
        [source],
        params,
        profile,
        "exact",
        None,
        lambda _amount, _message: None,
        lambda *_args: pytest.fail("unexpected question"),
        NeverCancelled(),
    )
    first = detect_region(ctx).outputs[0]
    assert first.mesh is mesh
    assert not source.features
    again = detect_region(replace(ctx, inputs=[first])).outputs[0]
    assert again.features == first.features
    assert all(
        feature.provenance == "detected" and feature.created_by is None
        for feature in first.features.values()
    )


def test_large_path_revalidates_known_features_after_translation(monkeypatch) -> None:
    """Die bisher frühe Rückgabe bei großen Netzen darf alte Merkmale nicht liegen lassen."""
    import importlib

    evaluation = importlib.import_module("app.core.scene.evaluate")
    from app.core.perceive.local import detect_local
    from app.core.types import Operation, SceneObject

    mesh = blind_cylinder()
    face, point, normal = bore_seed(mesh)
    known = detect_local(mesh, point, normal=normal, radius=8, seed_faces=(face,)).features
    hole = next(feature for feature in known.values() if feature.kind == "hole")
    old = replace(hole, id="hole_31")
    shifted = mesh.raw.copy()
    shifted.apply_translation((12, -8, 2))
    monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", 1)
    output = evaluation._with_features(
        SceneObject("own", "Eigener Körper", MeshData.of(shifted)),
        {old.id: old},
        Operation(2, "translate"),
        lambda *_args: pytest.fail("unexpected question"),
        [],
        transform=((1, 0, 0, 12), (0, 1, 0, -8), (0, 0, 1, 2), (0, 0, 0, 1)),
        previous_bounds=mesh.bounds,
    )
    assert "hole_31" in output.features
    assert output.features["hole_31"].params["centre"] == pytest.approx((12, -8, 19.5))
    assert output.features["hole_31"].params["through"] is False


@pytest.mark.parametrize("factors", [(2, 2, 2), (1, 1, 3), (2, 2, 1), (2, 1, 1)])
@pytest.mark.parametrize("provenance", ["detected", "generated"])
def test_affine_large_path_measures_current_shape_and_search_extent(
    monkeypatch, factors, provenance
) -> None:
    """Skalierung ändert Suchraum und Maße; eine Ellipse bleibt keine runde Altbohrung."""
    import importlib

    from app.core.perceive.local import detect_local
    from app.core.types import Operation, SceneObject

    evaluation = importlib.import_module("app.core.scene.evaluate")
    mesh = blind_cylinder()
    face, point, normal = bore_seed(mesh)
    known = detect_local(mesh, point, normal=normal, radius=8, seed_faces=(face,)).features
    old = next(
        replace(
            feature,
            id="hole_31",
            provenance=provenance,
            created_by=11 if provenance == "generated" else None,
        )
        for feature in known.values()
        if feature.kind == "hole"
    )
    matrix = np.diag([*factors, 1.0])
    turned = mesh.raw.copy()
    turned.apply_transform(matrix)
    monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", 1)
    output = evaluation._with_features(
        SceneObject("own", "Eigener Körper", MeshData.of(turned), features={old.id: old}),
        {old.id: old},
        Operation(2, "scale_object"),
        lambda *_args: pytest.fail("unexpected question"),
        [],
        transform=matrix,
        previous_bounds=mesh.bounds,
    )
    if factors[0] != factors[1]:
        assert not any(feature.kind == "hole" for feature in output.features.values())
        return
    hole = output.features[old.id]
    assert hole.params["diameter"] == pytest.approx(6 * factors[0], rel=0.003)
    assert hole.params["depth"] == pytest.approx(5 * factors[2], abs=1e-4)
    assert hole.params["through"] is False
    assert hole.params["local_search_radius"] >= old.params["local_search_radius"] * max(factors)
    assert hole.provenance == old.provenance and hole.created_by == old.created_by


def test_search_extent_remains_stable_on_repeated_known_scans() -> None:
    """Wiederholtes Auswerten vergrößert den Suchradius nicht ohne Geometrieänderung."""
    from app.core.perceive.local import detect_known, detect_local

    mesh = blind_cylinder()
    face, point, normal = bore_seed(mesh)
    first = detect_local(mesh, point, normal=normal, radius=8, seed_faces=(face,)).features
    again = detect_known(mesh, first)
    repeated = detect_known(mesh, again)
    assert repeated == again
    assert all("local_search_radius" in feature.params for feature in first.values())


def test_open_blind_floor_is_not_a_complete_cavity() -> None:
    """Ein fehlendes Originalbodendreieck kann im Ausschnitt keine Öffnung beweisen."""
    from app.core.perceive.local import detect_local

    source = blind_cylinder()
    raw = source.raw.copy()
    raw.update_faces(np.arange(len(raw.faces) - 1))
    mesh = MeshData.of(raw)
    assert not mesh.raw.is_watertight
    face, point, normal = bore_seed(mesh)
    result = detect_local(mesh, point, normal=normal, radius=8, seed_faces=(face,))
    assert not any(feature.kind == "hole" for feature in result.features.values())


@pytest.mark.parametrize("radius", [12.0, 25.0])
def test_counterbore_shoulder_never_hides_a_truncated_deeper_bore(radius) -> None:
    """Die ganze Ringschulter verbindet Ø10 mit der 14 mm tiefen Ø6-Bohrung."""
    from app.core.perceive.local import detect_local
    from app.core.perceive.relations import cavity_chains

    profile = [(0, 0), (100, 0), (100, 20), (5, 20), (5, 16), (3, 16), (3, 2), (0, 2)]
    mesh = MeshData.of(trimesh.creation.revolve(profile, sections=64))
    assert mesh.raw.is_watertight and mesh.raw.is_winding_consistent
    triangles = mesh.raw.triangles
    radial = np.linalg.norm(triangles[:, :, :2], axis=2)
    face = int(
        np.flatnonzero(
            np.all(np.isclose(radial, 5), axis=1) & (triangles[:, :, 2].max(axis=1) > 19)
        )[0]
    )
    result = detect_local(
        mesh,
        tuple(mesh.raw.triangles_center[face]),
        normal=tuple(mesh.raw.face_normals[face]),
        radius=radius,
    )
    holes = [feature for feature in result.features.values() if feature.kind == "hole"]
    if radius < 20:
        assert not holes
    else:
        assert len(holes) == 2
        smaller = min(holes, key=lambda feature: feature.params["diameter"])
        assert smaller.params["diameter"] == pytest.approx(6, rel=0.003)
        assert smaller.params["depth"] == pytest.approx(14)
        assert smaller.params["through"] is False
        assert len(cavity_chains(result.features, mesh)) == 1


def test_closed_hole_disappears_without_a_false_boundary_error() -> None:
    """Ein verschlossenes Loch ist entfernt; seine ehemalige weite Deckfläche ist kein Lochrest."""
    from app.core.perceive.local import detect_known, detect_local

    source = blind_cylinder()
    face, point, normal = bore_seed(source)
    known = detect_local(source, point, normal=normal, radius=8, seed_faces=(face,)).features
    closed = trimesh.creation.cylinder(radius=100, height=20, sections=64)
    closed.apply_translation((0, 0, 10))
    result = detect_known(MeshData.of(closed), known)
    assert not any(feature.kind == "hole" for feature in result.values())


def test_a_face_without_a_length_measure_keeps_its_own_search_extent() -> None:
    """Eine Fläche trägt ihren Umfang in ihrer Größe, nicht in einem Längenmaß.

    Nach einer Änderung kommt ein Merkmal frisch gemessen an und **ohne**
    ``local_search_radius`` — es stammt ja nicht mehr aus einer lokalen Suche.
    Für eine Bohrung trägt dann ``diameter`` den Suchumfang; eine Fläche hat
    keines dieser Maße, und ihr Umfang fiel damit auf null. Null gilt als
    abgeschnitten, und die Auswertung stand mit „Das Merkmal setzt sich über
    den Suchbereich hinaus fort" — für den Sackboden einer auf Ø8 geänderten
    Bohrung, der vollständig im Netz lag.
    """
    from app.core.perceive.local import detect_known, detect_local

    source = blind_cylinder()
    face, point, normal = bore_seed(source)
    known = detect_local(source, point, normal=normal, radius=8, seed_faces=(face,)).features
    floor = next(feature for feature in known.values() if feature.kind == "face")
    # So kommt sie aus der Zuordnung nach einer Operation: gemessen, benannt,
    # ohne Suchradius.
    measured = replace(
        floor,
        params={
            name: value for name, value in floor.params.items() if name != "local_search_radius"
        },
    )
    assert not {"diameter", "depth", "length"} & set(measured.params), "sonst trägt ein Längenmaß"

    result = detect_known(source, {measured.id: measured})

    assert result, "die Fläche wurde gemessen, nicht als abgeschnitten abgewiesen"
    assert any(feature.kind == "face" for feature in result.values())


def test_local_floor_role_uses_the_far_original_rim() -> None:
    """Der Innenboden bleibt innen, auch wenn der belegende Rand 85 mm höher liegt."""
    from app.core.perceive.features import detect_faces
    from app.core.perceive.local import detect_local

    raw = blind_cylinder().raw.copy()
    vertices = np.asarray(raw.vertices).copy()
    vertices[np.isclose(vertices[:, 2], 20), 2] = 100
    raw.vertices = vertices
    mesh = MeshData.of(raw)
    assert mesh.raw.is_watertight and mesh.raw.is_winding_consistent
    original = next(
        feature
        for feature in detect_faces(mesh)
        if feature.params["centre"][2] == pytest.approx(15)
    )
    assert original.params["inner"] is True
    found = detect_local(mesh, (0, 0, 15), normal=(0, 0, 1), radius=8)
    floor = next(feature for feature in found.features.values() if feature.kind == "face")
    assert floor.params["inner"] is True
    assert set(floor.face_indices) == set(original.face_indices)


def test_original_plane_witness_fits_only_its_relevant_complete_patch() -> None:
    """Eine ebene Kappe braucht keinen Mantelfit; dessen Budget gilt vor dem ersten Fit."""
    from app.core.errors import ValidationError
    from app.core.perceive.features import _large_facet_faces
    from app.core.perceive.local import local_error

    raw = trimesh.creation.cylinder(radius=10, height=20, sections=64)
    raw = raw.subdivide().subdivide()
    triangles = np.asarray(raw.triangles)
    cap = set(np.flatnonzero(np.all(np.isclose(triangles[:, :, 2], 10), axis=1)))
    wall = set(np.flatnonzero(np.ptp(triangles[:, :, 2], axis=1) > 0))
    assert len(wall) == 2048
    attempted = []

    def bounded(count: int) -> None:
        """Der ganze Mantel ist bewusst größer als das Budget dieser Gegenprobe."""
        attempted.append(count)
        if count > 2000:
            raise local_error("budget")

    assert cap <= _large_facet_faces(raw, requested=cap, check_patch_size=bounded)
    assert not attempted
    with pytest.raises(ValidationError):
        _large_facet_faces(raw, requested=wall, check_patch_size=bounded)
    assert attempted == [2048]


def test_long_thin_plane_keeps_its_measured_scope_after_rotation(monkeypatch) -> None:
    """Eine 80×0,2-Fläche braucht ihre echten Randpunkte, nicht die Wurzel ihrer Fläche."""
    import importlib

    from app.core.perceive.local import detect_local
    from app.core.types import Operation, SceneObject

    evaluation = importlib.import_module("app.core.scene.evaluate")
    mesh = MeshData.of(trimesh.creation.box((80, 0.2, 2)))
    known = detect_local(mesh, (0, 0, 1), normal=(0, 0, 1), radius=45).features
    old = next(
        replace(feature, id="face_41")
        for feature in known.values()
        if feature.kind == "face" and feature.params["normal"][2] > 0.9
    )
    rotation = trimesh.transformations.rotation_matrix(np.radians(33), (1, 2, 3))
    rotation[:3, 3] = (120, -40, 30)
    raw = mesh.raw.copy()
    raw.apply_transform(rotation)
    monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", 1)
    output = evaluation._with_features(
        SceneObject("own", "Eigener Körper", MeshData.of(raw)),
        {old.id: old},
        Operation(2, "rotate_object"),
        lambda *_args: pytest.fail("unexpected question"),
        [],
        transform=rotation,
        previous_bounds=mesh.bounds,
    )
    face = output.features[old.id]
    assert face.params["area"] == pytest.approx(16)
    assert face.params["normal"] == pytest.approx(rotation[:3, :3] @ np.array([0, 0, 1]))
    assert face.params["centre"] == pytest.approx((rotation @ np.array([0, 0, 1, 1]))[:3])
    assert face.face_indices == old.face_indices


def test_large_local_transaction_replays_through_project_disk_cache_and_undo(
    profile, tmp_path
) -> None:
    """Der gespeicherte Erkennungsschritt trägt >1M-Flächen über Änderung und alle Rückwege."""
    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.perceive.ops import detect_region
    from app.core.registry import REGISTRY, Registry, op_params, register_op
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import load, new_project, save
    from app.core.types import BaseParams, OpResult, SceneObject
    from app.i18n import _

    load_operations()
    assert REGISTRY.get("detect_region").fn is detect_region
    registry = Registry()
    for name in ("detect_region", "scale_object"):
        registry.register(REGISTRY.get(name))

    @op_params
    class OwnParams(BaseParams):
        pass

    @register_op(
        name="own_local_body",
        title=_("Eigener Prüfkörper"),
        category="primitive",
        params=OwnParams,
        consumes=0,
        produces=1,
        registry=registry,
    )
    def own_body(_ctx):
        return OpResult(outputs=[SceneObject("", "Eigener Körper", blind_cylinder(dense=True))])

    seed_mesh = blind_cylinder(dense=True)
    face, point, normal = bore_seed(seed_mesh)
    expected_volume = seed_mesh.volume
    del seed_mesh
    project = new_project()
    history = History(project.document, registry=registry)
    history.apply("Prüfkörper", [OperationDraft(op="own_local_body")])
    history.apply(
        "Hier erkennen und ändern",
        [
            OperationDraft(
                op="detect_region",
                inputs=("obj_1",),
                params={
                    "radius": 8.0,
                    "x": point[0],
                    "y": point[1],
                    "z": point[2],
                    "nx": normal[0],
                    "ny": normal[1],
                    "nz": normal[2],
                    "seed_face": face,
                },
            ),
            OperationDraft(
                op="scale_object",
                inputs=("obj_1",),
                params={"factor": 2.0, "about": "origin", "keep_on_bed": False},
            ),
        ],
    )
    directory = tmp_path / "results"
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    first = evaluate(project.document, profile, registry=registry, cache=cache)
    assert first.complete, first.error
    changed = first.scene.objects["obj_1"]
    assert changed.mesh.triangle_count == 1_054_720
    assert changed.mesh.volume == pytest.approx(expected_volume * 8, abs=1e-6)
    hole = next(feature for feature in changed.features.values() if feature.kind == "hole")
    assert hole.params["diameter"] == pytest.approx(12, abs=1e-4)
    assert hole.params["depth"] == pytest.approx(10)
    assert hole.params["through"] is False
    assert len(hole.face_indices) == 2048 and min(hole.face_indices) > 1_000_000
    assert hole.provenance == "detected" and hole.created_by is None
    warm = evaluate(project.document, profile, registry=registry, cache=cache)
    assert warm.complete and cache.statistics.hits >= 3
    assert warm.scene.objects["obj_1"].features == changed.features
    path = save(project, tmp_path / "local.p3d")
    reopened = load(path)
    stored = reopened.document.ops[1]
    assert stored.op == "detect_region" and stored.params["seed_face"] == face
    assert len(reopened.document.transactions[-1].ops) == 2
    disk_cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    from_disk = evaluate(reopened.document, profile, registry=registry, cache=disk_cache)
    assert from_disk.complete and disk_cache.statistics.disk_hits >= 3
    assert from_disk.scene.objects["obj_1"].features == changed.features
    cold = evaluate(reopened.document, profile, registry=registry)
    assert cold.complete and cold.scene.objects["obj_1"].features == changed.features
    assert cold.object_hashes == first.object_hashes
    history.undo()
    undone = evaluate(project.document, profile, registry=registry, cache=cache)
    assert undone.complete and not undone.scene.objects["obj_1"].features
    assert undone.scene.objects["obj_1"].mesh.volume == pytest.approx(expected_volume)
    history.redo()
    redone = evaluate(project.document, profile, registry=registry, cache=cache)
    assert redone.complete and redone.scene.objects["obj_1"].features == changed.features
