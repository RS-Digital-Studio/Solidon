"""Kleine Netze für die Ansicht, ohne Renderer (§18).

Was PyVista als ``pv.Disc``, ``pv.Cylinder``, ``pv.Arrow``, ``pv.Cube`` und
``pv.Plane`` lieferte, entsteht hier als NumPy-Felder — Ecken ``(n, 3)`` und
Dreiecke ``(m, 3)`` —, damit beide Renderer dasselbe zeichnen und ein Test
die Geometrie ohne Fenster nachmessen kann. Alles in Millimetern, alle
Normalen nach außen.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.core.units import EPS_GEOM

Mesh = tuple[np.ndarray, np.ndarray]
Vec = Sequence[float] | np.ndarray


def _frame(normal: Vec) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Zwei Richtungen quer zur Normale — eine Basis für Kreise und Scheiben."""
    axis = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(axis))
    axis = axis / length if length > EPS_GEOM else np.array([0.0, 0.0, 1.0])
    # Irgendein Vektor, der nicht parallel zur Normale liegt: die Achse, in der
    # sie am schwächsten ist. Ein fester Startvektor wäre genau dort entartet,
    # wo er parallel zu ihr steht.
    other = np.zeros(3)
    other[int(np.argmin(np.abs(axis)))] = 1.0
    first = np.cross(axis, other)
    first /= np.linalg.norm(first)
    second = np.cross(axis, first)
    return axis, first, second


def circle_points(centre: Vec, normal: Vec, radius: float, segments: int = 48) -> np.ndarray:
    """Die Punkte eines Kreises, flach in der Ebene mit dieser Normale."""
    _axis, first, second = _frame(normal)
    angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    return np.asarray(centre, dtype=float) + radius * (
        np.outer(np.cos(angles), first) + np.outer(np.sin(angles), second)
    )


def closed_ring(points: np.ndarray) -> np.ndarray:
    """Die Punkte eines Rings, mit dem ersten noch einmal am Ende — für eine
    Kette, die sich schließt."""
    return np.vstack([points, points[:1]])


def polygon(points: Sequence[Sequence[float]]) -> Mesh:
    """Ein konvexes Vieleck als Fächer von Dreiecken um seinen ersten Punkt."""
    corners = np.asarray(points, dtype=float).reshape(-1, 3)
    count = len(corners)
    if count < 3:
        return corners, np.zeros((0, 3), dtype=np.int64)
    faces = np.column_stack(
        [np.zeros(count - 2, dtype=np.int64), np.arange(1, count - 1), np.arange(2, count)]
    )
    return corners, faces


def disc(
    centre: Vec,
    normal: Vec,
    radius: float,
    segments: int = 24,
    inner: float = 0.0,
) -> Mesh:
    """Eine flache Scheibe — oder ein Ring, wenn ``inner`` größer als null ist."""
    outer = circle_points(centre, normal, radius, segments)
    if inner <= EPS_GEOM:
        vertices = np.vstack([np.asarray(centre, dtype=float)[None, :], outer])
        rim = np.arange(1, segments + 1)
        faces = np.column_stack([np.zeros(segments, dtype=np.int64), rim, np.roll(rim, -1)])
        return vertices, faces
    hole = circle_points(centre, normal, inner, segments)
    vertices = np.vstack([outer, hole])
    out = np.arange(segments)
    out_next = np.roll(out, -1)
    inner_index = out + segments
    inner_next = np.roll(inner_index, -1)
    faces = np.vstack(
        [
            np.column_stack([out, out_next, inner_next]),
            np.column_stack([out, inner_next, inner_index]),
        ]
    )
    return vertices, faces


def cylinder(
    centre: Vec,
    direction: Vec,
    radius: float,
    height: float,
    segments: int = 24,
    *,
    capped: bool = True,
) -> Mesh:
    """Ein Zylinder um ``centre``, seine Achse entlang ``direction``."""
    axis, first, second = _frame(direction)
    middle = np.asarray(centre, dtype=float)
    bottom = middle - axis * (height / 2.0)
    top = middle + axis * (height / 2.0)
    angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    around = radius * (np.outer(np.cos(angles), first) + np.outer(np.sin(angles), second))
    lower = bottom + around
    upper = top + around
    vertices = [lower, upper]
    index = np.arange(segments)
    next_index = np.roll(index, -1)
    faces = [
        np.column_stack([index, next_index, next_index + segments]),
        np.column_stack([index, next_index + segments, index + segments]),
    ]
    if capped:
        base = 2 * segments
        vertices.append(bottom[None, :])
        vertices.append(top[None, :])
        faces.append(np.column_stack([np.full(segments, base), next_index, index]))
        faces.append(
            np.column_stack([np.full(segments, base + 1), index + segments, next_index + segments])
        )
    return np.vstack(vertices), np.vstack(faces).astype(np.int64)


def cone(
    base_centre: Vec,
    direction: Vec,
    radius: float,
    height: float,
    segments: int = 24,
) -> Mesh:
    """Ein Kegel, der von ``base_centre`` aus ``height`` weit in ``direction`` zeigt."""
    axis, first, second = _frame(direction)
    base = np.asarray(base_centre, dtype=float)
    tip = base + axis * height
    angles = np.linspace(0.0, 2.0 * np.pi, segments, endpoint=False)
    rim = base + radius * (np.outer(np.cos(angles), first) + np.outer(np.sin(angles), second))
    vertices = np.vstack([rim, tip[None, :], base[None, :]])
    index = np.arange(segments)
    next_index = np.roll(index, -1)
    faces = np.vstack(
        [
            np.column_stack([index, next_index, np.full(segments, segments)]),
            np.column_stack([np.full(segments, segments + 1), next_index, index]),
        ]
    )
    return vertices, faces.astype(np.int64)


def arrow(
    start: Vec,
    direction: Vec,
    length: float,
    *,
    shaft_radius: float,
    tip_radius: float,
    tip_share: float = 0.35,
    segments: int = 20,
) -> Mesh:
    """Ein Pfeil: Schaft als Zylinder, Spitze als Kegel — das Maß von
    PyVistas ``pv.Arrow`` (Spitze 35 Prozent der Länge)."""
    axis, _first, _second = _frame(direction)
    origin = np.asarray(start, dtype=float)
    tip_length = length * tip_share
    shaft_length = length - tip_length
    shaft_vertices, shaft_faces = cylinder(
        origin + axis * (shaft_length / 2.0), axis, shaft_radius, shaft_length, segments
    )
    tip_vertices, tip_faces = cone(
        origin + axis * shaft_length, axis, tip_radius, tip_length, segments
    )
    return merge((shaft_vertices, shaft_faces), (tip_vertices, tip_faces))


def cube(centre: Vec, size: float) -> Mesh:
    """Ein Würfel mit Kantenlänge ``size`` um ``centre``."""
    half = size / 2.0
    corners = np.array(
        [
            [-1, -1, -1],
            [1, -1, -1],
            [1, 1, -1],
            [-1, 1, -1],
            [-1, -1, 1],
            [1, -1, 1],
            [1, 1, 1],
            [-1, 1, 1],
        ],
        dtype=float,
    )
    vertices = np.asarray(centre, dtype=float) + corners * half
    faces = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],
            [4, 5, 6],
            [4, 6, 7],
            [0, 1, 5],
            [0, 5, 4],
            [1, 2, 6],
            [1, 6, 5],
            [2, 3, 7],
            [2, 7, 6],
            [3, 0, 4],
            [3, 4, 7],
        ],
        dtype=np.int64,
    )
    return vertices, faces


def plane(centre: Vec, width: float, depth: float) -> Mesh:
    """Eine waagerechte Fläche (Normale +Z) aus zwei Dreiecken um ``centre``."""
    x, y, z = (float(value) for value in centre)
    half_w, half_d = width / 2.0, depth / 2.0
    vertices = np.array(
        [
            [x - half_w, y - half_d, z],
            [x + half_w, y - half_d, z],
            [x + half_w, y + half_d, z],
            [x - half_w, y + half_d, z],
        ]
    )
    return vertices, np.array([[0, 1, 2], [0, 2, 3]], dtype=np.int64)


def grid_lines(
    centre: Vec, width: float, depth: float, step: float
) -> tuple[np.ndarray, list[int]]:
    """Die Linien eines Rasters über einer Fläche — als Punktpaare, dazu die
    Kettenlängen (immer zwei), für ``add_lines(polylines=...)``."""
    x, y, z = (float(value) for value in centre)
    columns = max(1, round(width / step))
    rows = max(1, round(depth / step))
    xs = np.linspace(x - width / 2.0, x + width / 2.0, columns + 1)
    ys = np.linspace(y - depth / 2.0, y + depth / 2.0, rows + 1)
    points: list[list[float]] = []
    for value in xs:
        points.append([float(value), float(ys[0]), z])
        points.append([float(value), float(ys[-1]), z])
    for value in ys:
        points.append([float(xs[0]), float(value), z])
        points.append([float(xs[-1]), float(value), z])
    return np.asarray(points, dtype=float), [2] * (len(points) // 2)


def merge(*meshes: Mesh) -> Mesh:
    """Mehrere Netze zu einem — die Indizes verschieben sich mit."""
    vertices: list[np.ndarray] = []
    faces: list[np.ndarray] = []
    offset = 0
    for mesh_vertices, mesh_faces in meshes:
        vertices.append(np.asarray(mesh_vertices, dtype=float).reshape(-1, 3))
        faces.append(np.asarray(mesh_faces, dtype=np.int64).reshape(-1, 3) + offset)
        offset += len(vertices[-1])
    if not vertices:
        return np.zeros((0, 3)), np.zeros((0, 3), dtype=np.int64)
    return np.vstack(vertices), np.vstack(faces)


def triangle_soup(count: int) -> np.ndarray:
    """Die Dreiecksliste für ``count`` Dreiecke mit je eigenen Eckpunkten —
    die Indizes zählen einfach durch (siehe ``Viewport._lifted_corners``)."""
    return np.arange(count * 3, dtype=np.int64).reshape(count, 3)
