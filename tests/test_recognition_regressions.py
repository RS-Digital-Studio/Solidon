"""Konstruktionsmerkmale aus dem Dateiaudit, mit unabhängigen Formbelegen."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive import features
from app.core.perceive.features import _fit_circle, detect, detect_faces, forget_cache
from app.core.perceive.helix import find_helices
from app.core.units import EPS_GEOM


def _corpus(name: str, *, internal: bool = False) -> MeshData:
    """Eigene analytische Netze ohne Neubau oder STL-Rundung lesen."""
    path = Path(__file__).parent / "data" / "meshes" / f"recognition_{name}.npz"
    with np.load(path, allow_pickle=False) as data:
        prefix = "inner_" if internal else ""
        return MeshData(
            raw=trimesh.Trimesh(data[f"{prefix}vertices"], data[f"{prefix}faces"], process=False)
        )


def test_circular_guide_fit_uses_local_coordinates() -> None:
    """Die Kreiswand Ø32,8 behält ihr Maß auch fern vom Weltursprung."""
    vertices = np.asarray(_corpus("spice_base").raw.vertices)
    circle = vertices[abs(np.linalg.norm(vertices[:, :2], axis=1) - 16.4) < 1e-4, :2]
    assert len(circle) > 100
    for offset in [(0.0, 0.0), (1e8, -2e8)]:
        centre, radius = _fit_circle(circle + offset)
        np.testing.assert_allclose(centre, offset, atol=1e-5)
        assert radius == pytest.approx(16.4, abs=1e-5)


def test_translated_instances_keep_their_detected_surfaces() -> None:
    """Zwölf gleiche Kragen unterscheiden sich nur um 47-mm-Rasterversatz."""
    mesh = _corpus("spice_base")
    forget_cache()
    original = detect(mesh)
    signature = {(feature.kind, frozenset(feature.face_indices)) for feature in original.values()}
    for translation in [(47.0 * x, 47.0 * y, 0.0) for x in range(4) for y in range(3)]:
        moved = MeshData(raw=mesh.raw.copy())
        moved.raw.apply_translation(translation)
        found = detect(moved)
        assert {
            (feature.kind, frozenset(feature.face_indices)) for feature in found.values()
        } == signature


def test_round_guide_with_three_detents_is_not_a_stadium() -> None:
    """Der Kragen ist kreisrund mit drei Mulden, ohne zwei gerade Langlochflanken."""
    found = detect(_corpus("spice_base"))
    assert not [feature for feature in found.values() if feature.kind == "slot"]


def test_waterfall_front_wall_is_outside_despite_the_lower_lip() -> None:
    """Die vordere Wand liegt über der Lippe und hat nach außen freien Raum."""
    found = detect_faces(_corpus("waterfall"))
    wall = [
        feature
        for feature in found
        if np.allclose(feature.params["normal"], (0.0, -1.0, 0.0), atol=1e-6)
        and abs(float(feature.params["centre"][1]) + 6.0) < 1e-4
        and float(feature.params["area"]) > 1000.0
    ]
    assert len(wall) == 1
    assert wall[0].params["inner"] is False


@pytest.mark.parametrize(
    ("name", "height", "expected_count", "expected_area"),
    [
        ("bayonet_lid", 3.5, 3, 22.8),
        ("bayonet_cage", 8.0, 3, 20.0),
        ("bayonet_cage", 12.0, 3, 20.0),
    ],
)
def test_bayonet_contact_planes_survive_a_large_unrelated_floor(
    name: str, height: float, expected_count: int, expected_area: float
) -> None:
    """Drei Nocken und drei Drehwege haben jeweils eigene horizontale Kontaktflächen."""
    found = detect_faces(_corpus(name))
    contacts = [
        feature
        for feature in found
        if abs(abs(float(feature.params["normal"][2])) - 1.0) < 1e-5
        and abs(float(feature.params["centre"][2]) - height) < 1e-4
        and abs(float(feature.params["area"]) - expected_area) < 0.01
    ]
    assert len(contacts) == expected_count


@pytest.mark.parametrize("internal", [False, True])
@pytest.mark.parametrize("angle", [0.0, 0.73, 2.2])
def test_short_wide_trapezoid_thread_names_its_independent_pitch(internal, angle) -> None:
    """Der konstruierte Radialverlauf hat 3,5 mm Steigung und 1,4 mm Gangtiefe."""
    mesh = _corpus("short_thread", internal=internal)
    assert mesh.raw.is_watertight
    assert mesh.raw.extents[2] == pytest.approx(10.5 if internal else 14.0)
    transform = trimesh.transformations.rotation_matrix(angle, (1.0, 2.0, 3.0))
    mesh.raw.apply_transform(transform)
    mesh.raw.apply_translation((17.0, -23.0, 44.0))
    found = find_helices(mesh)
    assert len(found) == 1
    assert found[0].pitch == pytest.approx(3.5, abs=0.02)
    assert found[0].diameter == pytest.approx(34.9 if internal else 34.0, abs=0.05)
    assert found[0].depth == pytest.approx(1.4, abs=0.05)
    assert found[0].internal is internal
    assert abs(float(np.asarray(found[0].axis) @ transform[:3, 2])) == pytest.approx(1.0, abs=0.002)


def _through_corpus(blind: bool = False):
    """Bekannte 5,2-mm-Bohrung samt Mantelflächen aus dem bestehenden Korpus."""
    name = "plate_countersunk_blind.stl" if blind else "plate_holes.stl"
    payload = (Path(__file__).parent / "data" / "meshes" / name).read_bytes()
    body = normalise(read_mesh(payload, ".stl"), "mm").mesh.raw
    centre = (0.0, 0.0, 0.0) if blind else (-25.0, -15.0, 0.0)
    corners = np.asarray(body.triangles)
    radial = np.linalg.norm(corners[:, :, :2] - centre[:2], axis=2)
    on_wall = np.max(np.abs(radial - 2.6), axis=1) < 1e-4
    on_wall &= np.abs(body.face_normals[:, 2]) < 1e-8
    patch = np.flatnonzero(on_wall).tolist()
    assert len(patch) >= 48
    fit = features.CylinderFit((0.0, 0.0, 1.0), centre, 2.6, 0.0, True)
    return MeshData(raw=body), fit, patch


def _through(mesh, fit, patch, bounded):
    """Unveränderten Einzelweg oder die gemeinsame Vorarbeit ausdrücklich wählen."""
    if not bounded:
        return features._is_through(mesh, fit, patch=patch)
    return features._is_through(mesh, fit, patch=patch, bounds=features._ThroughBounds(mesh.raw))


@pytest.mark.parametrize("bounded", [False, True], ids=["baseline", "bounded"])
@pytest.mark.parametrize("blind", [False, True], ids=["through", "blind"])
@pytest.mark.parametrize("axis_index", [0, 1, 2], ids=["x", "y", "z"])
@pytest.mark.parametrize("sign", [-1.0, 1.0], ids=["negative", "positive"])
@pytest.mark.parametrize("angle", [0.0, 1e-10, 0.61], ids=["exact", "nearly", "oblique"])
@pytest.mark.parametrize("offset", [(0.0, 0.0, 0.0), (1e9, -2e9, 3e9)], ids=["local", "far"])
def test_through_bounds_preserve_signed_axes_and_distant_coordinates(
    bounded, blind, axis_index, sign, angle, offset
) -> None:
    """Die Platte geht durch; das gesenkte Sackloch behält seinen 2-mm-Boden."""
    mesh, fit, patch = _through_corpus(blind)
    assert mesh.raw.is_watertight
    assert mesh.volume > 0.0
    matrix = np.roll(np.eye(3), axis_index + 1, axis=0)
    if angle:
        matrix = matrix @ trimesh.transformations.rotation_matrix(angle, (1.0, 2.0, 3.0))[:3, :3]
    mesh.raw.vertices = np.asarray(mesh.raw.vertices) @ matrix.T + offset
    fit = replace(
        fit,
        axis=tuple(sign * matrix[:, 2]),
        centre=tuple(matrix @ np.asarray(fit.centre) + offset),
    )
    before = np.asarray(mesh.raw.vertices).copy(), np.asarray(mesh.raw.faces).copy()
    assert _through(mesh, fit, patch, bounded) is not blind
    np.testing.assert_array_equal(mesh.raw.vertices, before[0])
    np.testing.assert_array_equal(mesh.raw.faces, before[1])


def _add_through_triangles(mesh, triangles):
    """Gezielte Bodenflächen anhängen; die vorherigen Mantelindizes bleiben erhalten."""
    vertices = np.asarray(triangles, dtype=float).reshape(-1, 3)
    faces = np.arange(len(vertices)).reshape(-1, 3) + len(mesh.raw.vertices)
    return MeshData(
        raw=trimesh.Trimesh(
            vertices=np.vstack((mesh.raw.vertices, vertices)),
            faces=np.vstack((mesh.raw.faces, faces)),
            process=False,
        )
    )


@pytest.mark.parametrize("bounded", [False, True], ids=["baseline", "bounded"])
@pytest.mark.parametrize("floor", ["sloped", "stepped", "separate"])
@pytest.mark.parametrize("with_patch", [False, True], ids=["whole_axis", "wall_span"])
def test_through_bounds_keep_sloped_stepped_and_separate_floors(bounded, floor, with_patch) -> None:
    """Schräge und gestufte Böden schließen; eine Wand dahinter schließt den Abschnitt nicht."""
    mesh, fit, patch = _through_corpus()
    if floor == "stepped":
        triangles = [
            [(-3, -3, -1), (0, -3, -1), (0, 3, -1)],
            [(-3, -3, -1), (0, 3, -1), (-3, 3, -1)],
            [(0, -3, 1), (3, -3, 1), (3, 3, 1)],
            [(0, -3, 1), (3, 3, 1), (0, 3, 1)],
        ]
    else:
        low, high = (-1.0, 1.0) if floor == "sloped" else (10.0, 10.0)
        triangles = [
            [(-3, -3, low), (3, -3, high), (3, 3, high)],
            [(-3, -3, low), (3, 3, high), (-3, 3, low)],
        ]
    mesh = _add_through_triangles(mesh, np.asarray(triangles) + fit.centre)
    expected = floor == "separate" and with_patch
    assert _through(mesh, fit, patch if with_patch else None, bounded) is expected


@pytest.mark.parametrize("bounded", [False, True], ids=["baseline", "bounded"])
@pytest.mark.parametrize(
    ("position", "expected"),
    [
        ((0.0, 0.0, 0.0), False),
        ((2.6, 0.0, 0.0), False),
        ((np.nextafter(2.6, np.inf), 0.0, 0.0), True),
        ((0.0, 0.0, 4.0 + EPS_GEOM), False),
        ((0.0, 0.0, np.nextafter(4.0 + EPS_GEOM, np.inf)), True),
        ((10.0, 10.0, 0.0), True),
    ],
)
def test_through_bounds_preserve_degenerate_candidates_and_exact_boundaries(
    bounded, position, expected
) -> None:
    """Der Vorfilter behält auch die bisherige Behandlung entarteter Punktdreiecke."""
    mesh, fit, patch = _through_corpus()
    # Mittelpunkt null hält die beiden benachbarten Floatwerte beim Verschieben auseinander.
    mesh.raw.apply_translation(-np.asarray(fit.centre))
    fit = replace(fit, centre=(0.0, 0.0, 0.0))
    mesh = _add_through_triangles(mesh, [[position, position, position]])
    assert _through(mesh, fit, patch, bounded) is expected


def test_through_bounds_are_shared_by_all_bores_and_preserve_complete_features(monkeypatch) -> None:
    """Vier Bohrungen teilen eine Vorarbeit; ihr vollständiges Ergebnis bleibt gleich."""
    mesh, _fit, _patch = _through_corpus()
    factory = features._ThroughBounds
    prepared = []

    def record(body):
        bounds = factory(body)
        prepared.append(bounds)
        return bounds

    forget_cache()
    with monkeypatch.context() as local:
        local.setattr(features, "_ThroughBounds", record)
        bounded = features.detect(mesh)
    assert len(prepared) == 1
    holes = [feature for feature in bounded.values() if feature.kind == "hole"]
    assert len(holes) == 4
    assert all(hole.params["through"] is True for hole in holes)
    forget_cache()
    with monkeypatch.context() as local:
        local.setattr(features, "_ThroughBounds", lambda body: None)
        baseline = features.detect(mesh)
    assert bounded == baseline


def test_through_bounds_leave_oblique_axes_on_the_complete_path() -> None:
    """Selbst ein nur 1e-10 geneigter Richtungsvektor wird niemals gerade gerundet."""
    mesh, fit, patch = _through_corpus()
    bounds = features._ThroughBounds(mesh.raw)
    for angle in (1e-10, 0.61):
        axis = trimesh.transformations.rotation_matrix(angle, (1.0, 2.0, 3.0))[:3, 2]
        first, second = features._plane_basis(axis)
        assert bounds.candidates(axis, first, second, fit, patch) is None


def test_through_bounds_reuse_geometry_but_not_the_previous_query() -> None:
    """Eine andere Mitte, Breite oder Richtung bekommt ihre eigene Kandidatenauswahl."""
    mesh, fit, patch = _through_corpus()
    bounds = features._ThroughBounds(mesh.raw)
    for query, expected in (
        (fit, True),
        (replace(fit, centre=(0.0, 0.0, 0.0)), False),
        (replace(fit, radius=10.0), False),
        (replace(fit, axis=(1.0, 0.0, 0.0)), False),
        (replace(fit, centre=(1000.0, 1000.0, 1000.0)), True),
        (fit, True),
    ):
        assert features._is_through(mesh, query, bounds=bounds) is expected
        assert features._is_through(mesh, query) is expected
    axis = np.asarray(fit.axis)
    first, second = features._plane_basis(axis)
    selected = bounds.candidates(axis, first, second, fit, patch)
    assert selected is not None
    assert np.count_nonzero(selected) < len(mesh.raw.faces) / 2
    assert np.all(selected[patch]), "the complete cylindrical wall remains a candidate"
