"""Längs unterteilte Zylindermäntel bleiben als ein Merkmal erkennbar."""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect_holes
from app.core.units import EPS_GEOM


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


@pytest.mark.parametrize("levels", (2, 6, 17))
def test_a_longitudinally_subdivided_bore_wall_stays_one_hole(levels: int) -> None:
    """Axiale Unterteilung verändert weder Kreismaß noch wirkliche Facettenradien."""
    radius, height = 5.75, 8.5
    sections = 48
    mesh = _subdivided_inner_wall(radius=radius, height=height, sections=sections, levels=levels)
    radial_minimum = radius * np.cos(np.pi / sections)
    # Die Originalecken tragen den Umkreis, die Mitte einer Facettensehne
    # den Inkreis. Beide Sollwerte kommen aus der konstruierten Kontur.
    vertices = np.asarray(mesh.raw.vertices)
    assert np.linalg.norm(vertices[:, :2], axis=1) == pytest.approx(radius, abs=EPS_GEOM, rel=0)
    chord_middle = (vertices[0, :2] + vertices[1, :2]) / 2.0
    assert np.linalg.norm(chord_middle) == pytest.approx(radial_minimum, abs=EPS_GEOM, rel=0)

    holes = detect_holes(mesh)

    assert len(holes) == 1
    hole = holes[0]
    assert set(hole.face_indices) == set(range(len(mesh.raw.faces)))
    assert hole.params["diameter"] == pytest.approx(2.0 * radius, abs=EPS_GEOM, rel=0)
    assert hole.params["depth"] == pytest.approx(height, abs=EPS_GEOM, rel=0)
    assert hole.params["fit_error"] == pytest.approx(0.0, abs=EPS_GEOM, rel=0)
    assert hole.params["radial_min"] == pytest.approx(radial_minimum, abs=EPS_GEOM, rel=0)
    assert hole.params["radial_max"] == pytest.approx(radius, abs=EPS_GEOM, rel=0)
