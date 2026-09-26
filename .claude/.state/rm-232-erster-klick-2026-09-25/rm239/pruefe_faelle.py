"""RM-239: Die Sonde gegen das heutige Verschweißen an den Abnahmefällen."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom.mesh import weld_digits, weld_tolerance  # noqa: E402
from schweissen import weld_by_sheet, weld_the_rims  # noqa: E402
from schweissen2 import weld_sheets  # noqa: E402


def state(vertices, faces) -> str:
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    edges = np.sort(np.asarray(body.faces)[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
    _u, counts = np.unique(edges, axis=0, return_counts=True)
    used = len(np.unique(np.asarray(body.faces)))
    degenerate = int(np.count_nonzero(np.asarray(body.area_faces) <= 0.0))
    parts = len(trimesh.graph.connected_components(body.face_adjacency, nodes=np.arange(len(body.faces)), engine="scipy"))
    return (
        f"Ecken {used:6d}  Dreiecke {len(body.faces):6d}  offen {int((counts == 1).sum()):4d}"
        f"  verzweigt {int((counts > 2).sum()):4d}  Teile {parts:3d}  flach {degenerate}"
    )


def compare(name: str, vertices: np.ndarray, faces: np.ndarray) -> None:
    diagonal = float(np.linalg.norm(vertices.max(axis=0) - vertices.min(axis=0)))
    digits = weld_digits(weld_tolerance(diagonal))
    old = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    old.merge_vertices(digits_vertex=digits)
    new_vertices, new_faces = weld_by_sheet(vertices, faces, digits)
    print(name)
    print("  vorher ", state(vertices, faces))
    print("  heute  ", state(old.vertices, old.faces))
    print("  je Blatt", state(new_vertices, new_faces))
    rim_vertices, rim_faces = weld_the_rims(vertices, faces, digits)
    print("  Ränder ", state(rim_vertices, rim_faces))
    both_vertices, both_faces = weld_by_sheet(vertices, faces, digits, rims_only=True)
    print("  beides ", state(both_vertices, both_faces))
    fast_vertices, fast_faces = weld_sheets(vertices, faces, digits)
    print("  schnell", state(fast_vertices, fast_faces))


def cubes_with_a_tear() -> tuple[np.ndarray, np.ndarray]:
    first = trimesh.creation.box((10.0, 10.0, 10.0))
    second = trimesh.creation.box((10.0, 10.0, 10.0))
    second.apply_translation((10.0 + 1e-8, 10.0, 10.0))
    vertices = np.asarray(first.vertices, dtype=float)
    faces = np.asarray(first.faces, dtype=np.int64).copy()
    # Riss: die zwei Dreiecke der Oberseite bekommen eigene Ecken (gleiche Lage).
    top = np.flatnonzero(np.asarray(first.face_normals)[:, 2] > 0.9)
    extra = []
    for row in top:
        for k in range(3):
            extra.append(vertices[faces[row, k]])
            faces[row, k] = len(vertices) + len(extra) - 1
    vertices = np.vstack([vertices, np.asarray(extra)])
    offset = len(vertices)
    vertices = np.vstack([vertices, np.asarray(second.vertices, dtype=float)])
    faces = np.vstack([faces, np.asarray(second.faces, dtype=np.int64) + offset])
    return vertices, faces


def as_soup(vertices: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return vertices[faces].reshape(-1, 3), np.arange(3 * len(faces), dtype=np.int64).reshape(-1, 3)


vertices, faces = cubes_with_a_tear()
compare("Würfel, Ecken 1e-8 auf zwei Blättern, mit Riss", vertices, faces)
compare("dasselbe als Suppe", *as_soup(vertices, faces))
for name in sys.argv[1:]:
    loaded = trimesh.load(name, process=False)
    geometries = list(loaded.geometry.values()) if isinstance(loaded, trimesh.Scene) else [loaded]
    for index, geometry in enumerate(geometries):
        v = np.asarray(geometry.vertices, dtype=float)
        f = np.asarray(geometry.faces, dtype=np.int64)
        compare(f"{Path(name).name} #{index} ({len(f)} Dreiecke)", v, f)
