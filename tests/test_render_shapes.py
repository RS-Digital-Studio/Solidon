"""Die Formen der Ansicht, ohne Renderer nachgemessen (§18).

Jede Form muss geschlossen und nach außen orientiert sein — sonst sähe man
im Bild durch sie hindurch oder ihre Rückseite —, und ihre Maße müssen
stimmen: Ein Zylinder mit Radius 5 und Höhe 10 hat das Volumen, das die
Formel nennt, nicht ungefähr.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
import trimesh

from app.ui.render import shapes
from app.ui.render.edges import feature_edges


def as_trimesh(mesh: shapes.Mesh) -> trimesh.Trimesh:
    vertices, faces = mesh
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


@pytest.mark.parametrize(
    ("name", "mesh", "volume"),
    [
        ("cube", shapes.cube((1.0, 2.0, 3.0), 4.0), 64.0),
        (
            "cylinder",
            shapes.cylinder((0.0, 0.0, 0.0), (0.0, 0.0, 1.0), 5.0, 10.0, 96),
            math.pi * 25 * 10,
        ),
        ("cone", shapes.cone((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 3.0, 6.0, 96), math.pi * 9 * 6 / 3),
        (
            "arrow",
            shapes.arrow(
                (0.0, 0.0, 0.0),
                (0.0, 1.0, 0.0),
                10.0,
                shaft_radius=0.2,
                tip_radius=0.5,
                segments=96,
            ),
            None,
        ),
    ],
)
def test_solid_shapes_are_closed_and_point_outwards(
    name: str, mesh: shapes.Mesh, volume: float | None
) -> None:
    body = as_trimesh(mesh)
    assert body.is_watertight, f"{name} ist nicht geschlossen"
    assert body.is_winding_consistent, f"{name} hat wechselnde Orientierung"
    assert body.volume > 0.0, f"{name} zeigt nach innen"
    if volume is not None:
        assert body.volume == pytest.approx(volume, rel=0.01)


def test_an_arrow_points_along_its_direction_with_the_given_length() -> None:
    vertices, _faces = shapes.arrow(
        (1.0, 1.0, 1.0), (0.0, 0.0, 2.0), 8.0, shaft_radius=0.1, tip_radius=0.3
    )
    assert vertices[:, 2].max() == pytest.approx(9.0)
    assert vertices[:, 2].min() == pytest.approx(1.0)
    assert np.hypot(vertices[:, 0] - 1.0, vertices[:, 1] - 1.0).max() == pytest.approx(0.3)


def test_a_disc_lies_flat_in_its_plane_and_a_ring_has_a_hole() -> None:
    vertices, faces = shapes.disc((0.0, 0.0, 5.0), (0.0, 0.0, 1.0), 4.0, 32)
    assert np.allclose(vertices[:, 2], 5.0)
    flat = as_trimesh((vertices, faces))
    assert flat.area == pytest.approx(math.pi * 16.0, rel=0.02)
    ring_vertices, ring_faces = shapes.disc((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 4.0, 32, inner=2.0)
    assert np.allclose(ring_vertices[:, 0], 0.0)
    ring = as_trimesh((ring_vertices, ring_faces))
    assert ring.area == pytest.approx(math.pi * (16.0 - 4.0), rel=0.02)


def test_a_polygon_fans_out_from_its_first_point() -> None:
    corners = np.array([[0, 0, 0], [4, 0, 0], [4, 3, 0], [0, 3, 0]], dtype=float)
    vertices, faces = shapes.polygon(corners)
    assert faces.tolist() == [[0, 1, 2], [0, 2, 3]]
    assert as_trimesh((vertices, faces)).area == pytest.approx(12.0)
    _empty, none = shapes.polygon(corners[:2])
    assert len(none) == 0


def test_a_grid_covers_the_plate_in_steps() -> None:
    points, spans = shapes.grid_lines((10.0, 5.0, 0.0), 40.0, 20.0, 10.0)
    assert spans == [2] * ((4 + 1) + (2 + 1))
    assert points[:, 0].min() == pytest.approx(-10.0) and points[:, 0].max() == pytest.approx(30.0)
    assert points[:, 1].min() == pytest.approx(-5.0) and points[:, 1].max() == pytest.approx(15.0)


def test_a_circle_lies_in_the_plane_of_its_normal_and_closes() -> None:
    circle = shapes.circle_points((1.0, 2.0, 3.0), (0.0, 1.0, 0.0), 2.5, 12)
    assert np.allclose(circle[:, 1], 2.0)
    assert np.allclose(np.linalg.norm(circle - np.array([1.0, 2.0, 3.0]), axis=1), 2.5)
    ring = shapes.closed_ring(circle)
    assert len(ring) == 13 and np.allclose(ring[0], ring[-1])


def test_merge_shifts_indices_and_plane_faces_up() -> None:
    first = shapes.cube((0.0, 0.0, 0.0), 1.0)
    second = shapes.cube((5.0, 0.0, 0.0), 1.0)
    vertices, faces = shapes.merge(first, second)
    assert len(vertices) == 16 and faces.max() == 15
    both = as_trimesh((vertices, faces))
    assert both.volume == pytest.approx(2.0)
    plane_vertices, plane_faces = shapes.plane((0.0, 0.0, 2.0), 10.0, 4.0)
    normal = np.cross(
        plane_vertices[plane_faces[0][1]] - plane_vertices[plane_faces[0][0]],
        plane_vertices[plane_faces[0][2]] - plane_vertices[plane_faces[0][0]],
    )
    assert normal[2] > 0.0
    assert shapes.triangle_soup(2).tolist() == [[0, 1, 2], [3, 4, 5]]


def test_feature_edges_are_the_creases_and_the_open_rims() -> None:
    """Ein Würfel hat zwölf Kanten — seine sechs Flächendiagonalen sind
    keine, denn dort knickt nichts. Eine Platte aus zwei Dreiecken hat vier
    Ränder und keine Diagonale; Boden und Wand aus je zwei Dreiecken im
    rechten Winkel haben sechs Ränder und dazu die eine scharfe Kante, die
    bei einem größeren Knick als Grenze wieder wegfällt."""
    vertices, faces = shapes.cube((0.0, 0.0, 0.0), 2.0)
    assert len(feature_edges(vertices, faces, 30.0)) == 12 * 2
    plate_vertices, plate_faces = shapes.plane((0.0, 0.0, 0.0), 4.0, 2.0)
    assert len(feature_edges(plate_vertices, plate_faces, 30.0)) == 4 * 2
    roof = np.array([[0, 0, 0], [2, 0, 0], [2, 2, 0], [0, 2, 0], [2, 0, 2], [2, 2, 2]], dtype=float)
    roof_faces = np.array([[0, 1, 2], [0, 2, 3], [1, 4, 5], [1, 5, 2]])
    assert len(feature_edges(roof, roof_faces, 30.0)) == 7 * 2
    assert len(feature_edges(roof, roof_faces, 100.0)) == 6 * 2
    assert feature_edges(roof, np.zeros((0, 3), dtype=int), 30.0).shape == (0, 3)
