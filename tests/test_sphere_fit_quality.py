"""Bestimmtheit und örtliche Güte erkannter Kugelflächen."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.perceive.features import detect, detect_spheres, fit_sphere, forget_cache

MESHES = Path(__file__).parent / "data" / "meshes"


def _surface(name: str) -> trimesh.Trimesh:
    """Eine selbst erzeugte Prüffläche mit gemeinsam benutzten Ecken laden."""
    body = read_mesh((MESHES / name).read_bytes(), ".stl").raw
    body.merge_vertices()
    return body


def _recognised(body: trimesh.Trimesh) -> bool:
    """Den Rohfit durch die tatsächliche Veröffentlichungsgrenze schicken."""
    patch = list(range(len(body.faces)))
    fitted = fit_sphere(body, patch)
    assert fitted is not None
    return bool(detect_spheres(MeshData.of(body), [(fitted, patch)]))


@pytest.mark.parametrize(
    "name",
    ["shallow_sphere_cap_icosphere.stl", "shallow_sphere_cap_uv.stl"],
)
def test_a_shallow_spherical_cap_survives_different_triangulations(name: str) -> None:
    """Eine echte 5°-Kalotte bleibt trotz ihres großen Radius eine Kugel."""
    body = _surface(name)

    fitted = fit_sphere(body, list(range(len(body.faces))))

    assert fitted is not None
    assert fitted.good
    assert fitted.radius == pytest.approx(80.0, rel=0.003)
    assert _recognised(body)


@pytest.mark.parametrize("scale", [0.1, 1.0, 10.0])
def test_sphere_evidence_is_invariant_under_pose_and_scale(scale: float) -> None:
    """Einheitenlage, Drehung und Verschiebung ändern das Güteurteil nicht."""
    original = _surface("shallow_sphere_cap_icosphere.stl")
    before = fit_sphere(original, list(range(len(original.faces))))
    assert before is not None

    transform = trimesh.transformations.rotation_matrix(0.73, (1.0, 2.0, -0.5))
    transform[:3, :3] *= scale
    transform[:3, 3] = (37.0, -19.0, 211.0)
    changed = original.copy()
    changed.apply_transform(transform)

    after = fit_sphere(changed, list(range(len(changed.faces))))

    assert after is not None
    assert after.good == before.good
    assert after.radius == pytest.approx(before.radius * scale, rel=1e-9)
    expected = trimesh.transform_points(np.asarray([before.centre]), transform)[0]
    assert np.asarray(after.centre) == pytest.approx(expected, abs=1e-8)
    assert _recognised(original)
    assert _recognised(changed)


def test_a_narrow_spherical_ribbon_does_not_claim_an_editable_sphere() -> None:
    """Ein fast eindimensionaler Ausschnitt bestimmt keine sichere Kugel."""
    body = _surface("ambiguous_sphere_ribbon.stl")

    fitted = fit_sphere(body, list(range(len(body.faces))))

    assert fitted is not None
    assert fitted.good
    assert not _recognised(body)


def test_an_almost_flat_cap_does_not_claim_a_distant_sphere_centre() -> None:
    """Ein nur schlecht bestimmter Mittelpunkt wird nicht als Messwert ausgegeben."""
    body = _surface("indeterminate_sphere_cap.stl")

    fitted = fit_sphere(body, list(range(len(body.faces))))

    assert fitted is not None
    assert fitted.good
    assert not _recognised(body)


def test_an_ellipsoid_does_not_pass_by_normalising_error_to_a_large_radius() -> None:
    """Der Rückstand wird an der sichtbaren Fläche statt am Fitradius gemessen."""
    body = _surface("near_sphere_ellipsoid.stl")

    fitted = fit_sphere(body, list(range(len(body.faces))))

    assert fitted is not None
    assert fitted.good
    assert not _recognised(body)


def test_an_unsafe_sphere_does_not_fall_through_to_another_round_feature() -> None:
    """Die Formauswahl behält den Rohfit, veröffentlicht ihn aber nicht."""
    body = _surface("near_sphere_ellipsoid.stl")
    forget_cache()

    found = detect(MeshData.of(body))

    assert not {feature.kind for feature in found.values()} & {"sphere", "cone", "torus"}
