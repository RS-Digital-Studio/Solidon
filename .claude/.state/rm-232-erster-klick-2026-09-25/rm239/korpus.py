"""RM-239: Das neue Verschweißen gegen das heutige, über den ganzen Korpus.

Aufruf: python korpus.py <ordner> [...]
Je Körper: offene und verzweigte Kanten, Teile, flache Dreiecke — heute
(``Trimesh.merge_vertices``) gegen Rand- und Blattregel. Ausgegeben werden nur
Körper, an denen sich etwas unterscheidet, dazu die Summe.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom.mesh import weld_digits, weld_tolerance  # noqa: E402
from schweissen import weld_by_sheet  # noqa: E402
from schweissen2 import weld_sheets  # noqa: E402

SUFFIXES = {".stl", ".3mf", ".obj", ".ply", ".glb"}


def figures(vertices, faces) -> tuple[int, int, int, int]:
    faces = np.asarray(faces, dtype=np.int64)
    if not len(faces):
        return 0, 0, 0, 0
    edges = np.sort(faces[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
    n = int(faces.max()) + 1
    code = edges[:, 0] * n + edges[:, 1]
    _u, counts = np.unique(code, return_counts=True)
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    parts = len(trimesh.graph.connected_components(body.face_adjacency, nodes=np.arange(len(faces)), engine="scipy"))
    flat = int(np.count_nonzero(np.asarray(body.area_faces) <= 1e-18))
    return int((counts == 1).sum()), int((counts > 2).sum()), parts, flat


def main() -> None:
    files = []
    for root in sys.argv[1:]:
        base = Path(root)
        files += sorted(p for p in base.rglob("*") if p.suffix.lower() in SUFFIXES)
    bodies = differing = better = worse = 0
    time_old = time_new = 0.0
    for path in files:
        try:
            loaded = trimesh.load(str(path), process=False)
        except Exception as problem:  # noqa: BLE001
            print(f"übersprungen {path.name}: {problem}")
            continue
        geometries = list(loaded.geometry.values()) if isinstance(loaded, trimesh.Scene) else [loaded]
        for index, geometry in enumerate(geometries):
            if not isinstance(geometry, trimesh.Trimesh) or not len(geometry.faces):
                continue
            vertices = np.asarray(geometry.vertices, dtype=float)
            faces = np.asarray(geometry.faces, dtype=np.int64)
            diagonal = float(np.linalg.norm(vertices.max(axis=0) - vertices.min(axis=0)))
            digits = weld_digits(weld_tolerance(diagonal))
            t = time.perf_counter()
            old = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
            old.merge_vertices(digits_vertex=digits)
            time_old += time.perf_counter() - t
            t = time.perf_counter()
            new_vertices, new_faces = weld_sheets(vertices, faces, digits)
            time_new += time.perf_counter() - t
            slow_vertices, slow_faces = weld_by_sheet(vertices, faces, digits, rims_only=True)
            if len(slow_faces) != len(new_faces) or figures(slow_vertices, slow_faces) != figures(new_vertices, new_faces) or len(slow_vertices) != len(new_vertices):
                print(f"ABWEICHUNG schnell/langsam {path.name} #{index}: {figures(slow_vertices, slow_faces)} {len(slow_vertices)} gegen {figures(new_vertices, new_faces)} {len(new_vertices)}")
            bodies += 1
            a = figures(old.vertices, old.faces)
            b = figures(new_vertices, new_faces)
            if a != b:
                differing += 1
                score_a, score_b = a[0] + a[1], b[0] + b[1]
                verdict = "besser" if score_b < score_a or (score_b == score_a and b[3] < a[3]) else "schlechter" if score_b > score_a else "anders"
                better += verdict == "besser"
                worse += verdict == "schlechter"
                print(
                    f"{verdict:10s} {path.name[:40]:40s} #{index} {len(faces):8d} Dr.  heute offen/verzw/Teile/flach {a}  neu {b}"
                )
    print(f"{bodies} Körper, {differing} verschieden: {better} besser, {worse} schlechter")
    print(f"Zeit heute {time_old:.2f} s, neu {time_new:.2f} s")


main()
