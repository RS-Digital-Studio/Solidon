"""Belastbarkeit veröffentlichter Torusmerkmale."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect_tori, fit_torus


def _freeform_patch() -> trimesh.Trimesh:
    """Ein doppelt gekrümmter Fleck mit gutem, aber falschem Torus-Punktfit."""
    x_values = np.linspace(-2.881082538, 2.881082538, 9)
    y_values = np.linspace(-0.690018666, 0.690018666, 4)
    x_grid, y_grid = np.meshgrid(x_values, y_values, indexing="ij")
    coefficients = (
        -0.07396211,
        0.11951744,
        -0.03682532,
        -0.00363970,
        0.00475529,
        -0.00054038,
        0.00428175,
    )
    a, b, xy, x3, y3, x2y, xy2 = coefficients
    z_grid = (
        a * x_grid**2
        + b * y_grid**2
        + xy * x_grid * y_grid
        + x3 * x_grid**3
        + y3 * y_grid**3
        + x2y * x_grid**2 * y_grid
        + xy2 * x_grid * y_grid**2
    )
    vertices = np.column_stack([x_grid.ravel(), y_grid.ravel(), z_grid.ravel()])
    faces: list[tuple[int, int, int]] = []
    rows = len(y_values)
    for x_index in range(len(x_values) - 1):
        for y_index in range(rows - 1):
            lower = x_index * rows + y_index
            if (x_index + y_index) % 2:
                faces.extend(
                    [
                        (lower, lower + rows, lower + 1),
                        (lower + 1, lower + rows, lower + rows + 1),
                    ]
                )
            else:
                faces.extend(
                    [
                        (lower, lower + rows, lower + rows + 1),
                        (lower, lower + rows + 1, lower + 1),
                    ]
                )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def _partial_torus(major_sections: int, minor_sections: int) -> tuple[trimesh.Trimesh, list[int]]:
    """Ein echter Torus mit je einem begrenzten Bogen in beiden Richtungen."""
    ring = trimesh.creation.torus(
        major_radius=20.0,
        minor_radius=5.0,
        major_sections=major_sections,
        minor_sections=minor_sections,
    )
    centres = np.asarray(ring.triangles_center, dtype=float)
    major_angle = np.arctan2(centres[:, 1], centres[:, 0])
    radial = np.linalg.norm(centres[:, :2], axis=1)
    minor_angle = np.arctan2(centres[:, 2], radial - 20.0)
    patch = np.flatnonzero(
        (np.abs(major_angle) <= math.radians(45.0)) & (np.abs(minor_angle) <= math.radians(60.0))
    )
    return ring, [int(index) for index in patch]


def _placed(body: trimesh.Trimesh, scale: float, angle: float) -> trimesh.Trimesh:
    """Eine starre Lage und ein einheitlicher Maßstab für dieselbe Fläche."""
    placed = body.copy()
    placed.apply_scale(scale)
    placed.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(angle),
            direction=(0.3, -0.8, 0.5),
            point=(0.0, 0.0, 0.0),
        )
    )
    placed.apply_translation((37.0, -19.0, 83.0))
    return placed


@pytest.mark.parametrize(("scale", "angle"), [(1.0, 0.0), (3.7, 53.0), (0.25, -31.0)])
def test_a_freeform_patch_with_a_good_point_fit_is_not_published_as_a_torus(
    scale: float, angle: float
) -> None:
    """Punktnähe allein belegt keine zur Torusfläche gehörenden Normalen."""
    body = _placed(_freeform_patch(), scale, angle)
    patch = list(range(len(body.faces)))
    fit = fit_torus(body, patch)

    assert fit is not None and fit.good, "der isolierte Fehlerfall erreicht die Veröffentlichung"
    assert detect_tori(MeshData.of(body), [(fit, patch)]) == []


@pytest.mark.parametrize(
    ("scale", "angle", "sections"),
    [
        (1.0, 0.0, (96, 48)),
        (3.7, 53.0, (144, 72)),
        (0.25, -31.0, (96, 48)),
    ],
)
def test_a_true_partial_torus_survives_pose_scale_and_triangulation(
    scale: float, angle: float, sections: tuple[int, int]
) -> None:
    """Ein begrenzter echter Ring bleibt ein sicher bearbeitbares Merkmal."""
    body, patch = _partial_torus(*sections)
    body = _placed(body, scale, angle)
    fit = fit_torus(body, patch)

    assert fit is not None and fit.good
    assert len(detect_tori(MeshData.of(body), [(fit, patch)])) == 1
