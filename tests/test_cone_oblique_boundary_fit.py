"""Achseinpassung an schief beschnittenen Kegelmänteln."""

from __future__ import annotations

import math

import numpy as np
import pytest

from app.core.deferred import trimesh
from app.core.perceive.features import fit_cone


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
