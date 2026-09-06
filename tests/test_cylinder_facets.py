"""Längs unterteilte Zylindermäntel bleiben als ein Merkmal erkennbar."""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect_holes


def _subdivided_inner_wall(
    *, radius: float = 5.75, height: float = 8.5, sections: int = 48, levels: int = 6
) -> MeshData:
    """Einen innen gerichteten Mantel mit vielen Dreiecken je Facette bauen."""
    angles = np.linspace(0.0, 2.0 * np.pi, sections, endpoint=False)
    z_values = np.linspace(-height / 2.0, height / 2.0, levels)
    vertices = np.asarray(
        [(radius * np.cos(angle), radius * np.sin(angle), z) for z in z_values for angle in angles],
        dtype=float,
    )
    faces: list[tuple[int, int, int]] = []
    for level in range(levels - 1):
        lower = level * sections
        upper = (level + 1) * sections
        for section in range(sections):
            following = (section + 1) % sections
            # Umgekehrte Windung: Die Normalen zeigen in die Bohrung.
            faces.extend(
                [
                    (lower + section, upper + following, lower + following),
                    (lower + section, upper + section, upper + following),
                ]
            )
    return MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))


def test_a_longitudinally_subdivided_bore_wall_stays_one_hole() -> None:
    """Viele koplanare Dreiecke dürfen einen vollständigen Mantel nicht verstecken."""
    holes = detect_holes(_subdivided_inner_wall())

    assert len(holes) == 1
    assert holes[0].params["diameter"] == pytest.approx(11.48, abs=0.02)
    assert holes[0].params["depth"] == pytest.approx(8.5, abs=0.01)
