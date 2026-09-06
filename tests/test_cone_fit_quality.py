"""Belastbarkeit veröffentlichter Kegelmerkmale."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect_cones, fit_cone


def _freeform_patch() -> trimesh.Trimesh:
    """Ein Freiformfleck mit gutem Punktfit, aber widersprechenden Normalen."""
    x_values = np.linspace(-3.149173285, 3.149173285, 7)
    y_values = np.linspace(-0.549986636, 0.549986636, 10)
    x_grid, y_grid = np.meshgrid(x_values, y_values, indexing="ij")
    coefficients = (
        -0.07410578,
        -0.00965022,
        0.00710678,
        0.00816076,
        -0.00453320,
        -0.00786774,
        -0.00095932,
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


def _partial_cone(angular_sections: int, height_sections: int, *, reverse: bool) -> trimesh.Trimesh:
    """Ein 45°-Teilbogen eines exakten 60°-Kegels ohne Deckflächen."""
    angles = np.linspace(-math.radians(22.5), math.radians(22.5), angular_sections + 1)
    heights = np.linspace(5.0, 15.0, height_sections + 1)
    vertices = []
    for height in heights:
        radius = height * math.tan(math.radians(30.0))
        vertices.extend(
            (radius * math.cos(angle), radius * math.sin(angle), height) for angle in angles
        )

    faces: list[tuple[int, int, int]] = []
    row = len(angles)
    for height_index in range(height_sections):
        for angle_index in range(angular_sections):
            lower = height_index * row + angle_index
            if (height_index + angle_index) % 2:
                faces.extend(
                    [
                        (lower, lower + row, lower + 1),
                        (lower + 1, lower + row, lower + row + 1),
                    ]
                )
            else:
                faces.extend(
                    [
                        (lower, lower + row, lower + row + 1),
                        (lower, lower + row + 1, lower + 1),
                    ]
                )
    if reverse:
        faces = [(first, third, second) for first, second, third in faces]
    return trimesh.Trimesh(vertices=np.asarray(vertices), faces=faces, process=False)


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


@pytest.mark.parametrize(("scale", "angle"), [(1.0, 0.0), (3.7, 53.0), (0.5, -31.0)])
def test_a_freeform_patch_with_a_good_point_fit_is_not_published_as_a_cone(
    scale: float, angle: float
) -> None:
    """Ein passender Durchmesser belegt noch keine Kegelfläche."""
    body = _placed(_freeform_patch(), scale, angle)
    patch = list(range(len(body.faces)))
    fit = fit_cone(body, patch)

    assert fit is not None and fit.good, "der isolierte Fehlerfall erreicht die Veröffentlichung"
    assert detect_cones(MeshData.of(body), [(fit, patch)]) == []


@pytest.mark.parametrize(
    ("angular_sections", "height_sections", "reverse", "scale", "angle"),
    [
        (4, 2, False, 1.0, 0.0),
        (12, 4, True, 3.7, 53.0),
        (24, 8, False, 0.25, -31.0),
    ],
)
def test_a_true_partial_cone_survives_role_pose_scale_and_triangulation(
    angular_sections: int,
    height_sections: int,
    reverse: bool,
    scale: float,
    angle: float,
) -> None:
    """Ein enger Teilbogen bleibt in beiden Flächenrichtungen ein Kegel."""
    body = _placed(_partial_cone(angular_sections, height_sections, reverse=reverse), scale, angle)
    patch = list(range(len(body.faces)))
    fit = fit_cone(body, patch)

    assert fit is not None and fit.good
    features = detect_cones(MeshData.of(body), [(fit, patch)])
    assert len(features) == 1
    assert features[0].params["recess"] is (not reverse)
