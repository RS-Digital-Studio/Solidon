"""Small shapes the parts are built from (Bauplan §24.1).

Everything here is plain ``trimesh`` and ``manifold3d`` — no OpenSCAD, so a part
depends on no external installation and stays testable (§24.1, §36).

The shapes are deliberately few. A part library grows by combining a handful of
well understood bodies, not by every part inventing its own cylinder with its
own segment count and its own idea of where the origin sits.
"""

from __future__ import annotations

import math

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.types import Vec3

#: Segments of a round shape. Fine enough that a printed bore is round, coarse
#: enough that a part stays a few thousand triangles (§31).
SEGMENTS = 48

#: How far the ridge of a thread stands out of its core, as a share of the
#: pitch. Named because three places have to agree on it: the ridge built here,
#: the core the screw carries it on, and the diameter the nut is cut from. Two
#: of the three using a different number is a pair that does not screw
#: together, and it is not visible in either half on its own.
RIDGE_SHARE = 0.55

#: How far a subtracted shape reaches past the surface it cuts through. The
#: rule set asks for it (§39): coincident faces are the classic way to break a
#: boolean operation.
OVERLAP = 0.01


def cylinder(diameter: float, height: float, *, segments: int = SEGMENTS) -> MeshData:
    """Standing on Z = 0, growing upwards — the frame every part uses."""
    body = trimesh.creation.cylinder(radius=diameter / 2.0, height=height, sections=segments)
    body.apply_translation([0.0, 0.0, height / 2.0])
    return MeshData.of(body)


def box(width: float, depth: float, height: float) -> MeshData:
    """Centred in X and Y, standing on Z = 0."""
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation([0.0, 0.0, height / 2.0])
    return MeshData.of(body)


def hexagon(width: float, height: float) -> MeshData:
    """A hexagonal prism, ``width`` across the flats — a nut, in other words."""
    radius = width / math.sqrt(3.0)
    angles = np.linspace(0.0, 2.0 * math.pi, 7)[:-1] + math.pi / 6.0
    points = np.column_stack([radius * np.cos(angles), radius * np.sin(angles)])
    body = trimesh.creation.extrude_polygon(_polygon(points), height=height)
    return MeshData.of(body)


def cone(bottom: float, top: float, height: float, *, segments: int = SEGMENTS) -> MeshData:
    """A truncated cone standing on Z = 0 — a countersink, or a chamfer."""
    profile = np.array(
        [[0.0, 0.0], [bottom / 2.0, 0.0], [top / 2.0, height], [0.0, height]], dtype=float
    )
    body = trimesh.creation.revolve(profile, sections=segments)
    return MeshData.of(body)


def slot(width: float, length: float, height: float, *, segments: int = SEGMENTS) -> MeshData:
    """A rounded slot: two half circles with a rectangle between them."""
    if length <= width:
        return cylinder(width, height, segments=segments)
    body = trimesh.creation.extrude_polygon(
        _polygon(_slot_outline(width, length, segments)), height=height
    )
    return MeshData.of(body)


def _slot_outline(width: float, length: float, segments: int) -> np.ndarray:
    radius = width / 2.0
    offset = (length - width) / 2.0
    half = max(segments // 2, 3)
    right = np.linspace(-math.pi / 2.0, math.pi / 2.0, half)
    left = np.linspace(math.pi / 2.0, 3.0 * math.pi / 2.0, half)
    return np.vstack(
        [
            np.column_stack([offset + radius * np.cos(right), radius * np.sin(right)]),
            np.column_stack([-offset + radius * np.cos(left), radius * np.sin(left)]),
        ]
    )


def wedge(width: float, depth: float, height: float, tip: float = 0.0) -> MeshData:
    """A ramp: full ``depth`` at the bottom, ``tip`` at the top.

    The shape a latch and a snap hook are made of — it prints without support
    because it grows outwards on the way down, not upwards.

    Built as an extruded outline rather than from eight corners by hand: with
    ``tip`` at zero two of those corners would fall together, and a body with a
    degenerate face is not watertight (§24.3).
    """
    outline = [(0.0, 0.0), (depth, 0.0), (tip, height), (0.0, height)]
    if tip <= 0.0:
        outline = [(0.0, 0.0), (depth, 0.0), (0.0, height)]

    body = trimesh.creation.extrude_polygon(_polygon(np.array(outline)), height=width)
    # The outline lies in XY and grew along Z; turn it so depth runs along Y,
    # height along Z and the extrusion across X, centred.
    body.apply_transform(
        np.array(
            [
                [0.0, 0.0, 1.0, -width / 2.0],
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 0.0, 1.0],
            ]
        )
    )
    return MeshData.of(body)


def thread_body(
    diameter: float,
    pitch: float,
    height: float,
    *,
    depth: float | None = None,
    segments: int = SEGMENTS,
    internal: bool = False,
) -> MeshData:
    """A printable thread as a helical ridge — or, inverted, a threaded hole.

    Not an ISO profile: a printer cannot resolve one, and pretending otherwise
    would be the kind of accuracy that costs trust (§39). What this builds is
    the shape printers actually use — a triangular ridge with a flattened crest,
    rounded by the nozzle anyway.

    The mesh is stitched by hand rather than swept, because a sweep leaves the
    ends open and a part that is not watertight is not a part (§24.3).
    """
    steps = max(round(height / pitch), 1) * segments
    if depth is None:
        depth = pitch * RIDGE_SHARE
    radius = diameter / 2.0
    inner = radius + depth if internal else radius - depth

    angles = np.linspace(0.0, 2.0 * math.pi * height / pitch, steps + 1)
    heights = np.linspace(0.0, height, steps + 1)

    rings = []
    for angle, level in zip(angles, heights, strict=True):
        direction = np.array([math.cos(angle), math.sin(angle), 0.0])
        up = np.array([0.0, 0.0, 1.0])
        crest = direction * radius
        root = direction * inner
        rings.append(
            [
                root + up * level,
                crest + up * (level + pitch * 0.25),
                crest + up * (level + pitch * RIDGE_SHARE),
                root + up * (level + pitch * 0.8),
            ]
        )

    vertices = np.array([point for ring in rings for point in ring], dtype=float)
    faces: list[list[int]] = []
    per_ring = 4
    for index in range(len(rings) - 1):
        base = index * per_ring
        following = base + per_ring
        for corner in range(per_ring):
            first = base + corner
            second = base + (corner + 1) % per_ring
            third = following + (corner + 1) % per_ring
            fourth = following + corner
            faces.append([first, second, third])
            faces.append([first, third, fourth])

    faces.extend(_cap(list(range(per_ring)), flip=True))
    last = (len(rings) - 1) * per_ring
    faces.extend(_cap([last + corner for corner in range(per_ring)], flip=False))

    body = trimesh.Trimesh(vertices=vertices, faces=np.array(faces, dtype=np.int64), process=True)
    trimesh.repair.fix_normals(body)
    return MeshData.of(body)


def _cap(indices: list[int], flip: bool) -> list[list[int]]:
    """Close a four-point ring with two triangles."""
    first, second, third, fourth = indices
    faces = [[first, second, third], [first, third, fourth]]
    return [list(reversed(face)) for face in faces] if flip else faces


def _polygon(points: np.ndarray):  # type: ignore[no-untyped-def]
    from shapely.geometry import Polygon as ShapelyPolygon

    return ShapelyPolygon([(float(x), float(y)) for x, y in points])


def moved(mesh: MeshData, offset: Vec3) -> MeshData:
    body = mesh.raw.copy()
    body.apply_translation(np.asarray(offset, dtype=float))
    return mesh.replacing(body)


def turned(mesh: MeshData, degrees: float, axis: Vec3 = (0.0, 0.0, 1.0)) -> MeshData:
    body = mesh.raw.copy()
    body.apply_transform(
        trimesh.transformations.rotation_matrix(math.radians(degrees), np.asarray(axis))
    )
    return mesh.replacing(body)
