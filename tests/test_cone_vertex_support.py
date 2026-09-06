"""Vertexbeleg für als Kegel veröffentlichte Facettenbänder."""

from __future__ import annotations

import math

import numpy as np

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect_cones, fit_cone


def _partial_cone(sections: int, *, reverse: bool) -> trimesh.Trimesh:
    """Eine grobe echte 90°-Fase über einem begrenzten Kreisbogen."""
    angles = np.linspace(-math.radians(50.0), math.radians(50.0), sections + 1)
    vertices = []
    for height in (4.0, 4.5):
        vertices.extend(
            (height * math.cos(angle), height * math.sin(angle), height) for angle in angles
        )
    row = len(angles)
    faces: list[tuple[int, int, int]] = []
    for index in range(sections):
        faces.extend(
            [
                (index, index + 1, row + index + 1),
                (index, row + index + 1, row + index),
            ]
        )
    if reverse:
        faces = [(first, third, second) for first, second, third in faces]
    return trimesh.Trimesh(vertices=np.asarray(vertices), faces=faces, process=False)


def test_tangent_face_centres_do_not_replace_vertex_support_for_a_cone() -> None:
    """Ein guter Schwerpunktfit darf weit entfernte Facettenecken nicht übersehen."""
    source = _partial_cone(24, reverse=False)
    vertices = np.asarray(source.vertices, dtype=float).copy()
    faces = np.asarray(source.faces, dtype=np.intp).copy()
    original = np.asarray(source.triangles[0], dtype=float)
    centre = original.mean(axis=0)
    exaggerated = centre + 8.0 * (original - centre)
    first = len(vertices)
    vertices = np.vstack([vertices, exaggerated])
    faces[0] = np.arange(first, first + 3, dtype=np.intp)
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    patch = list(range(len(body.faces)))
    fit = fit_cone(body, patch)

    assert fit is not None and fit.good, "die Regression erreicht den bisherigen Publikationsweg"
    assert detect_cones(MeshData.of(body), [(fit, patch)]) == []


def test_a_coarse_true_ninety_degree_chamfer_keeps_both_surface_roles() -> None:
    """Die zusätzliche Punktprobe verlangt weder feine Facetten noch Vollumfang."""
    for reverse in (False, True):
        body = _partial_cone(6, reverse=reverse)
        patch = list(range(len(body.faces)))
        fit = fit_cone(body, patch)

        assert fit is not None and fit.good
        found = detect_cones(MeshData.of(body), [(fit, patch)])
        assert len(found) == 1
        assert found[0].params["recess"] is reverse
