"""Sonde: Zwei fehlende Dreiecke über einer scharfen Kante — kommt die Kante zurück oder eine Fase?"""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path.cwd()))
warnings.simplefilter("ignore")
import app.core.geom.repair as R  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402


def corners(mesh: MeshData, rows: np.ndarray) -> list:
    points = np.asarray(mesh.raw.vertices)
    return sorted(tuple(sorted(tuple(np.round(points[v], 6).tolist()) for v in row)) for row in rows)


def case(label: str, body: trimesh.Trimesh, pick) -> None:
    whole = MeshData.of(body)
    faces = np.asarray(body.faces)
    gone = pick(body)
    keep = np.setdiff1d(np.arange(len(faces)), gone)
    broken = MeshData.of(body.submesh([keep], append=True, repair=False))
    for limit in (16, 0):
        R.SMOOTH_FILL_CORNERS = limit
        result = R.repair(broken)
        added = np.asarray(result.mesh.raw.faces)[broken.triangle_count :]
        same = corners(result.mesh, added) == corners(whole, faces[gone])
        print(
            f"{label} Grenze {limit}: dicht {result.mesh.is_watertight}, Volumen "
            f"{whole.volume:.4f} -> {result.mesh.volume:.4f}, wie vorher {same}"
        )
    R.SMOOTH_FILL_CORNERS = 16


def edge_pair(body: trimesh.Trimesh) -> list[int]:
    """Zwei Dreiecke, die sich eine Würfelkante teilen (Knick 90°)."""
    pairs = np.asarray(body.face_adjacency)
    angles = np.asarray(body.face_adjacency_angles)
    row = int(np.flatnonzero(angles > 1.5)[0])
    return pairs[row].tolist()


def corner_three(body: trimesh.Trimesh) -> list[int]:
    """Die drei Dreiecke an einer Würfelecke, je eines je Seite."""
    target = np.asarray(body.vertices)[np.argmax(np.asarray(body.vertices).sum(axis=1))]
    at = np.flatnonzero(np.any(np.all(np.isclose(body.vertices[body.faces], target), axis=2), axis=1))
    return at.tolist()


cube = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide().subdivide()
case("Würfelkante", cube, edge_pair)
case("Würfelecke", cube, corner_three)
plate = R.merge_vertices(
    MeshData.of(trimesh.load("tests/data/meshes/plate_holes.stl", force="mesh"))
)[0].raw
case("Plattenkante", plate, edge_pair)
