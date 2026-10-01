"""Belastbarkeit veröffentlichter Kegelmerkmale."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect_cones, fit_cone
from tests.helpers import partial_cone
from tests.helpers import placed as _placed


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
    body = _placed(partial_cone(angular_sections, height_sections, reverse=reverse), scale, angle)
    patch = list(range(len(body.faces)))
    fit = fit_cone(body, patch)

    assert fit is not None and fit.good
    features = detect_cones(MeshData.of(body), [(fit, patch)])
    assert len(features) == 1
    assert features[0].params["recess"] is (not reverse)


# --- Achseinpassung an schief beschnittenen Kegelmänteln ------------------------------


def _obliquely_clipped_cone(
    lower_sections: int,
    upper_sections: int,
) -> trimesh.Trimesh:
    """Ein wahrer 90°-Kegel mit unterschiedlich abgetasteten, schiefen Rändern.

    Die beiden Schnittebenen entsprechen dem belegten Drill-Holder-Fall:
    ungefähr 5,7° beziehungsweise 4,6° gegen die wahre Kegelachse. Die
    Mantelpunkte liegen trotzdem exakt auf dem Kegel um die Z-Achse. Der
    Dreiecksring hat ohne innere Punkte genau so viele Facetten wie Randpunkte.
    """
    half_angle = math.radians(45.0)
    radius_per_height = math.tan(half_angle)

    def ring(sections: int, height: float, slope: float) -> list[tuple[float, float, float]]:
        points: list[tuple[float, float, float]] = []
        for index in range(sections):
            angle = math.tau * index / sections
            # z = height + slope*x und x = tan(alpha)*z*cos(angle).
            z = height / (1.0 - slope * radius_per_height * math.cos(angle))
            radius = radius_per_height * z
            points.append((radius * math.cos(angle), radius * math.sin(angle), z))
        return points

    lower = ring(lower_sections, 4.0, 0.10)
    upper = ring(upper_sections, 5.0, 0.08)
    vertices = np.asarray([*lower, *upper], dtype=float)
    upper_offset = len(lower)

    # Zwei verschieden dichte, zyklische Ränder ohne Umvernetzung verbinden.
    # Bei jedem Schritt rückt der Rand mit dem nächsten Polarwinkel vor.
    faces: list[tuple[int, int, int]] = []
    lower_index = 0
    upper_index = 0
    while lower_index < lower_sections or upper_index < upper_sections:
        next_lower = math.tau * (lower_index + 1) / lower_sections
        next_upper = math.tau * (upper_index + 1) / upper_sections
        current_lower = lower_index % lower_sections
        current_upper = upper_index % upper_sections
        if lower_index < lower_sections and (
            upper_index >= upper_sections or next_lower <= next_upper
        ):
            following_lower = (lower_index + 1) % lower_sections
            faces.append((current_lower, following_lower, upper_offset + current_upper))
            lower_index += 1
        else:
            following_upper = (upper_index + 1) % upper_sections
            faces.append(
                (
                    current_lower,
                    upper_offset + following_upper,
                    upper_offset + current_upper,
                )
            )
            upper_index += 1

    return trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)


def _axis_error_deg(axis: tuple[float, float, float]) -> float:
    """Vorzeichenunabhängiger Winkel zur bekannten Z-Achse."""
    direction = np.asarray(axis, dtype=float)
    cosine = abs(float(direction[2])) / float(np.linalg.norm(direction))
    return math.degrees(math.acos(float(np.clip(cosine, -1.0, 1.0))))


def test_oblique_unequal_boundary_sampling_does_not_tilt_the_cone_axis() -> None:
    """Randdichte und Schnittebene dürfen die wahre Mantelachse nicht drehen."""
    body = _obliquely_clipped_cone(120, 64)
    patch = list(range(len(body.faces)))

    fit = fit_cone(body, patch)

    assert len(body.vertices) == 184
    assert len(body.faces) == 184
    assert fit is not None
    assert _axis_error_deg(fit.axis) < 0.25
    assert fit.half_angle == pytest.approx(45.0, abs=0.25)
    assert fit.good
