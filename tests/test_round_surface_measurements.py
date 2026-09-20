"""Analytische Endmaße und unveränderte Geometrie bei Facettenunterteilung."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect, fit_cone, fit_sphere, fit_torus
from app.core.units import EPS_GEOM


def _round_surface(kind: str) -> trimesh.Trimesh:
    """Drei unabhängig parametrisierte Träger mit bekannten Maßen erzeugen."""
    if kind == "sphere":
        return trimesh.creation.icosphere(subdivisions=2, radius=7.234567)
    if kind == "torus":
        return trimesh.creation.torus(
            major_radius=17.125, minor_radius=3.234567, major_sections=48, minor_sections=24
        )
    angles = np.linspace(0.0, math.tau, 48, endpoint=False)
    heights = (4.0, 12.0)
    vertices = np.asarray(
        [
            (z * math.tan(math.pi / 6) * math.cos(a), z * math.tan(math.pi / 6) * math.sin(a), z)
            for z in heights
            for a in angles
        ]
    )
    faces = []
    for lower in range(len(angles)):
        following = (lower + 1) % len(angles)
        faces.extend(
            (
                (lower, following, following + len(angles)),
                (lower, following + len(angles), lower + len(angles)),
            )
        )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _subdivided(body: trimesh.Trimesh, manner: str) -> trimesh.Trimesh:
    """Nur gerade Dreiecke unterteilen; kein neuer Punkt liegt auf dem glatten Träger."""
    if manner == "none":
        return body.copy()
    if manner == "separate_vertices":
        copied = body.copy()
        copied.unmerge_vertices()
        return copied
    if manner == "reordered":
        return trimesh.Trimesh(
            vertices=body.vertices.copy(), faces=body.faces[::-1].copy(), process=False
        )
    if manner == "one_sided_edges":
        points, faces = trimesh.remesh.subdivide(
            body.vertices, body.faces, face_index=np.arange(0, len(body.faces), 2)
        )
        return trimesh.Trimesh(vertices=points, faces=faces, process=False)
    if manner == "uniform":
        vertices, faces = trimesh.remesh.subdivide(body.vertices, body.faces)
        return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    vertices = body.vertices.tolist()
    faces = []
    for triangle, middle in zip(body.faces, body.triangles_center, strict=True):
        if middle[0] <= 0.0:
            faces.append(tuple(triangle))
            continue
        centre = len(vertices)
        vertices.append(middle.tolist())
        for first, second in zip(triangle, np.roll(triangle, -1), strict=True):
            faces.append((int(first), int(second), centre))
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _assert_measures(kind: str, fit: Any) -> None:
    """Sollwerte direkt aus den Konstruktorparametern, unabhängig vom Fit vergleichen."""
    assert fit is not None
    assert fit.good
    assert fit.fit_error is not None and fit.fit_error <= EPS_GEOM
    if kind == "sphere":
        assert fit.radius == pytest.approx(7.234567, abs=EPS_GEOM, rel=0)
        assert fit.centre == pytest.approx((0.0, 0.0, 0.0), abs=EPS_GEOM, rel=0)
    elif kind == "torus":
        assert fit.ring_radius == pytest.approx(17.125, abs=EPS_GEOM, rel=0)
        assert fit.tube_radius == pytest.approx(3.234567, abs=EPS_GEOM, rel=0)
        assert fit.centre == pytest.approx((0.0, 0.0, 0.0), abs=EPS_GEOM, rel=0)
        assert abs(fit.axis[2]) == pytest.approx(1.0, abs=EPS_GEOM, rel=0)
    else:
        assert fit.half_angle == pytest.approx(30.0, abs=EPS_GEOM, rel=0)
        assert fit.radius == pytest.approx(12.0 * math.tan(math.pi / 6), abs=EPS_GEOM, rel=0)
        assert fit.apex == pytest.approx((0.0, 0.0, 0.0), abs=EPS_GEOM, rel=0)
        assert fit.centre == pytest.approx((0.0, 0.0, 12.0), abs=EPS_GEOM, rel=0)
        assert fit.axis == pytest.approx((0.0, 0.0, 1.0), abs=EPS_GEOM, rel=0)
    assert fit.recess is False


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
@pytest.mark.parametrize(
    "manner", ("none", "uniform", "one_side", "one_sided_edges", "separate_vertices", "reordered")
)
def test_round_surface_measures_use_original_points(kind: str, manner: str) -> None:
    """Reine Unterteilung verändert kein analytisches Maß und kein Eingabearray."""
    source = _round_surface(kind)
    body = _subdivided(source, manner)
    points, triangles = body.vertices.copy(), body.faces.copy()
    fitter = {"sphere": fit_sphere, "cone": fit_cone, "torus": fit_torus}[kind]

    fitted = fitter(body, list(range(len(body.faces))))

    np.testing.assert_array_equal(body.vertices, points)
    np.testing.assert_array_equal(body.faces, triangles)
    _assert_measures(kind, fitted)


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
def test_true_detection_publishes_unrounded_round_surface_measures(kind: str) -> None:
    """Der wirkliche Erkennungsweg veröffentlicht dieselben ungerundeten Endmaße."""
    body = _round_surface(kind)
    before_points, before_faces = body.vertices.copy(), body.faces.copy()

    found = [feature for feature in detect(MeshData.of(body)).values() if feature.kind == kind]

    assert len(found) == 1
    params = found[0].params
    assert params["recess"] is False
    if kind == "sphere":
        assert params["diameter"] == pytest.approx(2 * 7.234567, abs=EPS_GEOM, rel=0)
    elif kind == "torus":
        assert params["diameter"] == pytest.approx(2 * 17.125, abs=EPS_GEOM, rel=0)
        assert params["tube_diameter"] == pytest.approx(2 * 3.234567, abs=EPS_GEOM, rel=0)
    else:
        assert params["diameter"] == pytest.approx(24 * math.tan(math.pi / 6), abs=EPS_GEOM, rel=0)
        assert params["angle"] == pytest.approx(60.0, abs=EPS_GEOM, rel=0)
    measured = {"diameter", "centre"}
    if kind != "sphere":
        measured.add("axis")
    measured.update(
        {"tube_diameter"} if kind == "torus" else {"angle"} if kind == "cone" else set()
    )
    assert {name: found[0].measure_sources.get(name) for name in measured} == dict.fromkeys(
        measured, "fit"
    )
    np.testing.assert_array_equal(body.vertices, before_points)
    np.testing.assert_array_equal(body.faces, before_faces)


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
@pytest.mark.parametrize("pose", ("rotation", "translation", "reflection", "scale"))
def test_end_measures_follow_the_known_rigid_frame(kind: str, pose: str) -> None:
    """Große Lage, Spiegelung und Maßstab verändern die unabhängigen Sollmaße korrekt."""
    body = _subdivided(_round_surface(kind), "one_side")
    matrix = trimesh.transformations.rotation_matrix(0.73, (1.0, 2.0, -0.5))
    scale = 3.7 if pose == "scale" else 1.0
    matrix[:3, :3] *= scale
    if pose == "translation":
        matrix[:3, 3] = (1_000_003.25, -2_000_007.5, 3_000_011.75)
    if pose == "reflection":
        matrix[:3, 0] *= -1.0
    body.apply_transform(matrix)
    before = body.vertices.copy(), body.faces.copy()
    fitter = {"sphere": fit_sphere, "cone": fit_cone, "torus": fit_torus}[kind]

    fitted = fitter(body, list(range(len(body.faces))))

    assert fitted is not None and fitted.good
    assert fitted.recess is False
    centre = (0.0, 0.0, 12.0) if kind == "cone" else (0.0, 0.0, 0.0)
    expected_centre = trimesh.transform_points([centre], matrix)[0]
    assert fitted.centre == pytest.approx(expected_centre, abs=EPS_GEOM, rel=0)
    if kind == "sphere":
        assert fitted.radius == pytest.approx(7.234567 * scale, abs=EPS_GEOM, rel=0)
    elif kind == "cone":
        assert fitted.apex == pytest.approx(matrix[:3, 3], abs=EPS_GEOM, rel=0)
        assert fitted.half_angle == pytest.approx(30.0, abs=EPS_GEOM, rel=0)
        assert fitted.radius == pytest.approx(
            12 * math.tan(math.pi / 6) * scale, abs=EPS_GEOM, rel=0
        )
        assert fitted.axis == pytest.approx(matrix[:3, 2] / scale, abs=EPS_GEOM, rel=0)
    else:
        assert fitted.ring_radius == pytest.approx(17.125 * scale, abs=EPS_GEOM, rel=0)
        assert fitted.tube_radius == pytest.approx(3.234567 * scale, abs=EPS_GEOM, rel=0)
        assert abs(np.dot(fitted.axis, matrix[:3, 2] / scale)) == pytest.approx(
            1, abs=EPS_GEOM, rel=0
        )
    found = [feature for feature in detect(MeshData.of(body)).values() if feature.kind == kind]
    assert len(found) == 1
    assert found[0].params["centre"] == pytest.approx(expected_centre, abs=EPS_GEOM, rel=0)
    assert set(found[0].face_indices) == set(range(len(body.faces)))
    np.testing.assert_array_equal(body.vertices, before[0])
    np.testing.assert_array_equal(body.faces, before[1])


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
def test_a_trimmed_round_patch_passes_the_real_classification(kind: str) -> None:
    """Der nicht vorhandene Vollkörper darf die belegte Teilfläche nicht aussperren."""
    from tests.test_cone_fit_quality import _partial_cone
    from tests.test_torus_fit_quality import _partial_torus

    if kind == "sphere":
        source = _round_surface(kind)
        body = trimesh.intersections.slice_mesh_plane(source, (0.0, 0.0, 1.0), (0.0, 0.0, 3.0))
    elif kind == "cone":
        body = _partial_cone(12, 4, reverse=True)
    else:
        source, patch = _partial_torus(96, 48)
        body = source.submesh([patch], append=True, repair=False)
    points, faces = body.vertices.copy(), body.faces.copy()

    found = [feature for feature in detect(MeshData.of(body)).values() if feature.kind == kind]

    assert len(found) == 1
    assert set(found[0].face_indices) == set(range(len(body.faces)))
    params = found[0].params
    if kind == "sphere":
        assert params["diameter"] == pytest.approx(2 * 7.234567, abs=EPS_GEOM, rel=0)
        assert params["centre"] == pytest.approx((0, 0, 0), abs=EPS_GEOM, rel=0)
    elif kind == "cone":
        assert params["angle"] == pytest.approx(60.0, abs=EPS_GEOM, rel=0)
        assert params["diameter"] == pytest.approx(30 * math.tan(math.pi / 6), abs=EPS_GEOM, rel=0)
    else:
        assert params["diameter"] == pytest.approx(40, abs=EPS_GEOM, rel=0)
        assert params["tube_diameter"] == pytest.approx(10, abs=EPS_GEOM, rel=0)
    np.testing.assert_array_equal(body.vertices, points)
    np.testing.assert_array_equal(body.faces, faces)


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
@pytest.mark.parametrize("stop_at", (1, 5))
def test_the_round_fit_can_stop_before_and_during_preparation(kind: str, stop_at: int) -> None:
    """Ein Abbruch liefert keine halben Maße und lässt dieselbe Quelle erneut berechnen."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    body = _subdivided(_round_surface(kind), "uniform")
    before = body.vertices.copy(), body.faces.copy()
    fitter = {"sphere": fit_sphere, "cone": fit_cone, "torus": fit_torus}[kind]
    signal = CancelSignal()
    reached = []

    def stop() -> None:
        reached.append(True)
        if len(reached) == stop_at:
            signal.cancel()
        signal.raise_if_cancelled()

    with pytest.raises(OperationCancelled):
        fitter(body, list(range(len(body.faces))), check_cancelled=stop)

    assert len(reached) == stop_at
    np.testing.assert_array_equal(body.vertices, before[0])
    np.testing.assert_array_equal(body.faces, before[1])
    _assert_measures(kind, fitter(body, list(range(len(body.faces)))))


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
def test_true_detection_stops_inside_the_first_solver_evaluation(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Operationsabbruch erreicht den echten Löser vor dessen nächstem Schritt."""
    from app.core.errors import OperationCancelled
    from app.core.perceive import features
    from app.core.scene.cancel import CancelSignal

    mesh = MeshData.of(_round_surface(kind))
    before = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    signal = CancelSignal()
    features.forget_cache()
    original = features.least_squares
    evaluated: list[bool] = []

    def cancel_inside(residual: Any, initial: Any, **options: Any) -> Any:
        """Eine echte Residualauswertung bricht denselben weitergereichten Auftrag ab."""

        def stopped(values: Any) -> Any:
            evaluated.append(True)
            signal.cancel()
            return residual(values)

        return original(stopped, initial, **options)

    with monkeypatch.context() as patch:
        patch.setattr(features, "least_squares", cancel_inside)
        with pytest.raises(OperationCancelled):
            detect(mesh, check_cancelled=signal.raise_if_cancelled)

    assert len(evaluated) == 1
    assert not features._FEATURE_CACHE
    assert not features._CACHE_INDICES
    np.testing.assert_array_equal(mesh.raw.vertices, before[0])
    np.testing.assert_array_equal(mesh.raw.faces, before[1])
    assert any(feature.kind == kind for feature in detect(mesh).values())


@pytest.mark.parametrize("diameter,travel,source", ((6.0, 10.0, "facets"), (12.0, 0.5, "fit")))
def test_a_slot_names_the_actual_source_of_its_width(
    diameter: float, travel: float, source: str
) -> None:
    """Flankenabstand und Stadionfit bleiben trotz gleicher Merkmalsart unterscheidbar."""
    from tests.test_slot_features import a_foreign_slot

    found = [
        feature
        for feature in detect(a_foreign_slot(diameter, travel)).values()
        if feature.kind == "slot"
    ]

    assert len(found) == 1
    assert found[0].measure_sources["diameter"] == source
    assert found[0].measure_sources["depth"] == "facets"
    assert found[0].measure_sources["travel"] == "fit"


def test_cylinder_and_planar_measure_sources_follow_their_calculation() -> None:
    """Der gefittete Durchmesser und die wirkliche axiale Netzausdehnung reisen getrennt."""
    mesh = MeshData.of(trimesh.creation.cylinder(radius=4.125, height=7.375, sections=48))

    found = detect(mesh)
    pin = next(feature for feature in found.values() if feature.kind == "pin")
    face = next(feature for feature in found.values() if feature.kind == "face")

    assert pin.measure_sources["diameter"] == "fit"
    assert pin.measure_sources["axis"] == "fit"
    assert pin.measure_sources["depth"] == "facets"
    assert face.measure_sources == {"area": "facets", "normal": "facets", "centre": "facets"}


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
def test_opposite_coincident_faces_do_not_promote_chord_points_to_round_corners(kind: str) -> None:
    """Zwei entgegengesetzte Häute erzeugen keine zusätzliche Stützung ihrer Sehnenpunkte."""
    source = _subdivided(_round_surface(kind), "uniform")
    body = trimesh.Trimesh(
        vertices=source.vertices.copy(),
        faces=np.r_[source.faces, source.faces[:, ::-1]],
        process=False,
    )
    fitter = {"sphere": fit_sphere, "cone": fit_cone, "torus": fit_torus}[kind]

    assert fitter(body, list(range(len(body.faces)))) is None


def test_disconnected_facet_fans_at_one_point_do_not_share_their_support() -> None:
    """Drei getrennte Fächer am Berührpunkt sind keine ursprüngliche Rundflächenecke."""
    from app.core.perceive.features import _surface_support

    vertices = [(0.0, 0.0, 0.0)]
    faces = []
    for first, second in (
        ((2.0, 0.0, 0.0), (2.0, 1.0, 0.0)),
        ((0.0, 2.0, 1.0), (-1.0, 2.0, 1.0)),
        ((-1.0, -2.0, 1.0), (1.0, -2.0, 1.0)),
    ):
        offset = len(vertices)
        vertices.extend((first, tuple((np.asarray(first) + second) / 2.0), second))
        faces.extend(((0, offset, offset + 1), (0, offset + 1, offset + 2)))
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)

    support = _surface_support(body, list(range(len(body.faces))))

    assert support is not None
    shared = np.flatnonzero(np.linalg.norm(support.points, axis=1) <= EPS_GEOM)[0]
    assert not support.round_corners[shared]
    assert not support.ridges[shared]


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
@pytest.mark.parametrize("sections", (24, 48, 72))
def test_new_surface_points_recover_the_same_independent_measures(kind: str, sections: int) -> None:
    """Eine neue Vernetzung erzeugt echte Mantelpunkte statt weiterer Sehnenpunkte."""
    if kind == "sphere":
        body = trimesh.creation.uv_sphere(radius=7.234567, count=(sections // 2, sections))
    elif kind == "torus":
        body = trimesh.creation.torus(
            major_radius=17.125, minor_radius=3.234567, major_sections=sections, minor_sections=12
        )
    else:
        angles = np.linspace(0, math.tau, sections, endpoint=False)
        radius = 12 * math.tan(math.pi / 6)
        vertices = [
            (0.0, 0.0, 0.0),
            *((radius * math.cos(a), radius * math.sin(a), 12.0) for a in angles),
        ]
        faces = [(0, (index + 1) % sections + 1, index + 1) for index in range(sections)]
        body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    fitter = {"sphere": fit_sphere, "cone": fit_cone, "torus": fit_torus}[kind]

    fit = fitter(body, list(range(len(body.faces))))

    _assert_measures(kind, fit)
    found = [feature for feature in detect(MeshData.of(body)).values() if feature.kind == kind]
    assert len(found) == 1
    assert found[0].params["fit_error"] <= EPS_GEOM


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
def test_float32_source_resolution_is_not_claimed_as_float64_input_accuracy(kind: str) -> None:
    """Die Eingabeschranke folgt der ursprünglichen Float32-Koordinatenauflösung."""
    source = _round_surface(kind)
    quantised = np.asarray(source.vertices, dtype=np.float32)
    body = trimesh.Trimesh(vertices=quantised, faces=source.faces, process=False)
    tolerance = math.sqrt(3) * float(np.spacing(np.float32(np.abs(quantised).max())))
    fitter = {"sphere": fit_sphere, "cone": fit_cone, "torus": fit_torus}[kind]

    fitted = fitter(body, list(range(len(body.faces))))

    assert fitted is not None and fitted.good
    assert fitted.fit_error is not None and fitted.fit_error <= tolerance
    if kind == "sphere":
        assert fitted.radius == pytest.approx(7.234567, abs=tolerance, rel=0)
    elif kind == "torus":
        assert fitted.ring_radius == pytest.approx(17.125, abs=tolerance, rel=0)
        assert fitted.tube_radius == pytest.approx(3.234567, abs=tolerance, rel=0)
    else:
        assert fitted.apex == pytest.approx((0, 0, 0), abs=tolerance, rel=0)
        assert fitted.radius == pytest.approx(12 * math.tan(math.pi / 6), abs=tolerance, rel=0)


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
def test_a_used_up_solver_budget_publishes_no_unfinished_fit(
    kind: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein begrenzter Löserlauf darf keinen bloßen Zwischenwert als Endmaß liefern."""
    from app.core.perceive import features

    body = _round_surface(kind)
    if kind == "sphere":
        body.vertices[0] *= 1.0002
    fitter = {"sphere": fit_sphere, "cone": fit_cone, "torus": fit_torus}[kind]
    points, faces = body.vertices.copy(), body.faces.copy()
    with monkeypatch.context() as patch:
        patch.setattr(features, "ROUND_FIT_EVALUATIONS", 1)
        assert fitter(body, list(range(len(body.faces)))) is None
    after = fitter(body, list(range(len(body.faces))))
    assert after is not None and after.good
    np.testing.assert_array_equal(body.vertices, points)
    np.testing.assert_array_equal(body.faces, faces)


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
@pytest.mark.parametrize("deformation", ("ellipse", "single_bump"))
def test_all_original_faces_must_support_a_published_round_form(
    kind: str, deformation: str
) -> None:
    """Einzelne Beulen und elliptische Gegenträger verschwinden nicht im mittleren Rückstand."""
    from app.core.perceive.features import detect_cones, detect_spheres, detect_tori

    body = _round_surface(kind)
    if deformation == "ellipse":
        body.vertices[:, 2 if kind == "torus" else 0] *= 1.2
    else:
        body.vertices[0, 0] += 2.0
    indices = list(range(len(body.faces)))
    fitter = {"sphere": fit_sphere, "cone": fit_cone, "torus": fit_torus}[kind]
    publisher = {"sphere": detect_spheres, "cone": detect_cones, "torus": detect_tori}[kind]
    fitted = fitter(body, indices)

    assert fitted is None or not publisher(MeshData.of(body), [(fitted, indices)])


def test_a_normal_constrained_chamfer_does_not_claim_an_original_cone_angle() -> None:
    """Ein Kreis und Facettennormalen liefern einen geschätzten Winkel, keinen Ursprungsnachweis."""
    from app.core.perceive import features
    from tests.test_features import _plate_with_a_chamfered_slot

    mesh = _plate_with_a_chamfered_slot()
    fitted = features._fitted(mesh)
    candidates = [(fit, faces) for fit, faces in fitted.cones if fit.normal_constrained]
    assert len(candidates) == 2
    for fit, faces in candidates:
        assert fit.fit_error is not None and fit.fit_error <= EPS_GEOM
        assert abs(fit.half_angle - 45.0) > EPS_GEOM
        found = features.detect_cones(mesh, [(fit, faces)])
        assert len(found) == 1
        assert found[0].measure_sources["angle"] == "fit"
    actual = features.detect(mesh)
    slot = next(feature for feature in actual.values() if feature.kind == "slot")
    assert all(set(faces).issubset(slot.face_indices) for _fit, faces in candidates)


@pytest.mark.parametrize("name", ("shallow_sphere_cap_icosphere.stl", "shallow_sphere_cap_uv.stl"))
def test_true_detection_measures_the_independently_constructed_five_degree_cap(name: str) -> None:
    """Die echte Erkennung erhält R80 bei zwei Float32-Kalotten aus dem Korpus."""
    from tests.test_sphere_fit_quality import _surface

    body = _surface(name)
    points, faces = body.vertices.copy(), body.faces.copy()
    # Eine Höhenänderung wird bei der 5°-Kalotte um den Kehrwert der relativen
    # Stichhöhe verstärkt. Die Schranke folgt aus der Float32-Quelldatei und
    # diesem unabhängig konstruierten Winkel, nicht aus einem alten Fitwert.
    coordinate_step = float(np.spacing(np.float32(np.abs(points).max())))
    tolerance = math.sqrt(3) * coordinate_step / (1 - math.cos(math.radians(5)))

    found = [feature for feature in detect(MeshData.of(body)).values() if feature.kind == "sphere"]

    assert len(found) == 1
    assert found[0].params["diameter"] == pytest.approx(160.0, abs=2 * tolerance, rel=0)
    assert found[0].params["centre"] == pytest.approx((0, 0, 0), abs=tolerance, rel=0)
    assert found[0].measure_sources == {"diameter": "fit", "centre": "fit"}
    assert set(found[0].face_indices) == set(range(len(body.faces)))
    np.testing.assert_array_equal(body.vertices, points)
    np.testing.assert_array_equal(body.faces, faces)


def test_local_detection_keeps_the_actual_measure_sources() -> None:
    """Die lokale Veröffentlichung erhält Fitmaß und gemessene Netzgrenzen getrennt."""
    from app.core.perceive.local import detect_local
    from tests.test_local_detection import blind_cylinder, bore_seed

    mesh = blind_cylinder()
    face, point, normal = bore_seed(mesh)
    source = next(feature for feature in detect(mesh).values() if feature.kind == "hole")

    local = detect_local(mesh, point, normal=normal, radius=9, seed_faces=(face,))
    result = next(feature for feature in local.features.values() if feature.kind == "hole")

    assert result.measure_sources == source.measure_sources
    assert result.measure_sources["diameter"] == "fit"
    assert result.measure_sources["depth"] == "facets"
    assert result.params["diameter"] == pytest.approx(6.0, abs=EPS_GEOM, rel=0)


@pytest.mark.parametrize("kind", ("sphere", "cone", "torus"))
def test_round_mesh_measures_survive_real_history_quality_and_project_roundtrips(
    kind: str,
    profile: Any,
    tmp_path: Any,
) -> None:
    """Import und Verschieben führen beide Qualitäten durch Cache, Datei und Undo/Redo."""
    import hashlib
    from copy import deepcopy

    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshCodec
    from app.core.perceive.features import forget_cache
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import DiskCache, ResultCache
    from app.core.scene.project import ProjectSources, load, new_project, save
    from app.core.types import Source

    load_operations()
    source = _round_surface(kind)
    source_points, source_faces = source.vertices.copy(), source.faces.copy()
    # OBJ erhält die Float64-Sollpunkte; dieser Test prüft den Verlauf und
    # nicht die getrennt nachgewiesene Quantisierung binärer STL-Koordinaten.
    payload = source.export(
        file_type="obj",
        digits=17,
        include_normals=False,
        include_color=False,
        include_texture=False,
    ).encode("utf-8")
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1",
        kind="import",
        path=f"sources/{kind}.obj",
        sha256=hashlib.sha256(payload).hexdigest(),
    )
    history = History(project.document)
    history.apply(
        "Sollfläche importieren",
        [
            OperationDraft(
                op="load",
                params={
                    "source": "src_1",
                    "unit": "mm",
                    "weld": False,
                    "remove_degenerate": False,
                    "unify_normals": False,
                    "place_on_bed": False,
                    "centre": False,
                },
            )
        ],
    )
    directory = tmp_path / "cache"
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    offset = np.asarray((37.0, -19.0, 53.0))
    original_entries = []
    snapshots = []
    identifier = None

    def measured(current: Any, active_cache: Any, quality: str, moved: bool) -> Any:
        """Jede echte Auswertung mit unabhängigen Maßen und Originaldreiecken abnehmen."""
        result = evaluate(
            current.document,
            profile,
            sources=ProjectSources(current),
            quality=quality,
            cache=active_cache,
        )
        assert result.complete, result.error
        entry = result.scene.objects["obj_1"]
        assert isinstance(entry.mesh, MeshData)
        found = [feature for feature in entry.features.values() if feature.kind == kind]
        assert len(found) == 1
        feature = found[0]
        expected = {"sphere": 2 * 7.234567, "cone": 24 * math.tan(math.pi / 6), "torus": 2 * 17.125}
        centre = np.asarray((0.0, 0.0, 12.0) if kind == "cone" else (0.0, 0.0, 0.0))
        assert feature.params["diameter"] == pytest.approx(expected[kind], abs=EPS_GEOM, rel=0)
        assert feature.params["centre"] == pytest.approx(
            centre + (offset if moved else 0), abs=EPS_GEOM, rel=0
        )
        assert feature.params["fit_error"] <= EPS_GEOM
        assert feature.params["recess"] is False
        expected_sources = {"diameter": "fit", "centre": "fit"}
        if kind != "sphere":
            expected_sources["axis"] = "fit"
            assert abs(feature.params["axis"][2]) == pytest.approx(1, abs=EPS_GEOM, rel=0)
        if kind == "cone":
            expected_sources["angle"] = "fit"
            assert feature.params["angle"] == pytest.approx(60, abs=EPS_GEOM, rel=0)
        if kind == "torus":
            expected_sources["tube_diameter"] = "fit"
            assert feature.params["tube_diameter"] == pytest.approx(
                2 * 3.234567, abs=EPS_GEOM, rel=0
            )
        assert feature.measure_sources == expected_sources
        assert set(feature.face_indices) == set(range(entry.mesh.triangle_count))
        np.testing.assert_allclose(
            entry.mesh.raw.triangles,
            source.triangles + (offset if moved else 0),
            atol=EPS_GEOM,
            rtol=0,
        )
        if identifier is not None:
            assert feature.id == identifier
        return entry

    for quality in ("draft", "fine"):
        entry = measured(project, cache, quality, False)
        original_entries.append(entry)
        snapshots.append(
            (entry.mesh.raw.vertices.copy(), entry.mesh.raw.faces.copy(), deepcopy(entry.features))
        )
        identifier = next(feature.id for feature in entry.features.values() if feature.kind == kind)
    history.apply(
        "Sollfläche verschieben",
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={
                    "dx": float(offset[0]),
                    "dy": float(offset[1]),
                    "dz": float(offset[2]),
                    "keep_on_bed": False,
                },
            )
        ],
    )
    for quality in ("draft", "fine"):
        measured(project, cache, quality, True)
        hits = cache.statistics.hits
        measured(project, cache, quality, True)
        assert cache.statistics.hits > hits
        forget_cache()
        cold = ResultCache()
        measured(project, cold, quality, True)
        assert cold.statistics.hits == cold.statistics.disk_hits == 0
    reopened = load(save(project, tmp_path / f"{kind}.solidon"))
    disk_cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    for quality in ("draft", "fine"):
        measured(reopened, disk_cache, quality, True)
    assert disk_cache.statistics.disk_hits >= 4
    reopened_history = History(reopened.document)
    reopened_history.undo()
    for quality in ("draft", "fine"):
        forget_cache()
        measured(reopened, ResultCache(), quality, False)
    reopened_history.redo()
    for quality in ("draft", "fine"):
        forget_cache()
        measured(reopened, ResultCache(), quality, True)
    assert project.sources["src_1"] == reopened.sources["src_1"] == payload
    np.testing.assert_array_equal(source.vertices, source_points)
    np.testing.assert_array_equal(source.faces, source_faces)
    for entry, (points, faces, features) in zip(original_entries, snapshots, strict=True):
        np.testing.assert_array_equal(entry.mesh.raw.vertices, points)
        np.testing.assert_array_equal(entry.mesh.raw.faces, faces)
        assert entry.features == features
