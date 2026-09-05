"""Körperkanten aus einem Netz, ohne Renderer (§18.1).

PyVistas ``extract_feature_edges`` lieferte die Kanten, an denen sich ein
Körper knickt, dazu seine offenen Ränder — die Linien, die ``solid`` über die
Flächen zeichnet. Dasselbe rechnet :func:`feature_edges` über NumPy: Jede
Kante gehört zu einem oder zwei Dreiecken. Eine mit einem ist ein Rand; eine
mit zweien ist scharf, wenn die Normalen der beiden mehr als ``angle`` Grad
auseinanderstehen. Kanten mit drei und mehr Dreiecken (nicht mannigfaltig)
bleiben weg, wie vorher (``non_manifold_edges=False``).
"""

from __future__ import annotations

import numpy as np

from app.core.units import EPS_GEOM


def feature_edges(vertices: np.ndarray, faces: np.ndarray, angle: float) -> np.ndarray:
    """Die Endpunkte der Körperkanten, paarweise — ``(2m, 3)`` für ``add_lines``.

    ``angle`` ist der Knick in Grad, ab dem eine Kante zwischen zwei Dreiecken
    als Kante des Körpers gilt; Ränder zählen immer.
    """
    triangles = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    points = np.asarray(vertices, dtype=float).reshape(-1, 3)
    if len(triangles) == 0:
        return np.zeros((0, 3), dtype=float)
    edges = np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    edges.sort(axis=1)
    owners = np.tile(np.arange(len(triangles)), 3)
    unique, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
    inverse = np.asarray(inverse).ravel()
    chosen = counts == 1
    shared = np.flatnonzero(counts == 2)
    if len(shared):
        order = np.argsort(inverse, kind="stable")
        starts = np.searchsorted(inverse[order], shared)
        first = owners[order[starts]]
        second = owners[order[starts + 1]]
        normals = _face_normals(points, triangles)
        cosine = np.clip(np.einsum("ij,ij->i", normals[first], normals[second]), -1.0, 1.0)
        sharp = np.degrees(np.arccos(cosine)) >= float(angle)
        chosen[shared[sharp]] = True
    return np.asarray(points[unique[chosen].ravel()], dtype=float)


def _face_normals(points: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Die Normalen aller Dreiecke, normiert — entartete zeigen nach +Z."""
    corners = points[triangles]
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    flat = lengths <= EPS_GEOM
    normals[flat] = (0.0, 0.0, 1.0)
    lengths[flat] = 1.0
    return normals / lengths[:, None]
