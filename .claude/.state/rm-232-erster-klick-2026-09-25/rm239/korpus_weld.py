"""RM-239: ``repair.weld`` gegen das bisherige Verschweißen, über ganze Ordner.

Aufruf: python korpus_weld.py <ordner> [...]
Je Körper offene und verzweigte Kanten, Teile nach Eckennummern und Ecken —
bisher (trimeshs ``merge_vertices``, übernommen nur, wenn die Summe offener
und verzweigter Kanten nicht wächst, wie ``repair`` es tat) gegen ``weld``.
Ausgegeben wird jeder Körper, an dem sich etwas unterscheidet, dazu die Summe
und die Zeit beider Wege.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from scipy.sparse import coo_matrix  # noqa: E402
from scipy.sparse.csgraph import connected_components  # noqa: E402

from app.core.geom.mesh import unique_edges  # noqa: E402
from app.core.geom.repair import weld  # noqa: E402
from app.core.units import weld_digits, weld_tolerance  # noqa: E402

SUFFIXES = {".stl", ".3mf", ".obj", ".ply", ".glb"}


def figures(body: trimesh.Trimesh) -> tuple[int, int, int, int]:
    faces = np.asarray(body.faces, dtype=np.int64)
    # Gezählt wie der Schritt danach es sieht: ohne Dreiecke, die das
    # Verschweißen flach gedrückt hat — die fallen dort.
    faces = faces[(faces[:, 0] != faces[:, 1]) & (faces[:, 1] != faces[:, 2]) & (faces[:, 2] != faces[:, 0])]
    if not len(faces):
        return 0, 0, 0, 0
    _unique, inverse, counts = unique_edges(
        faces[:, [0, 1, 1, 2, 2, 0]], return_inverse=True, return_counts=True
    )
    rows = np.flatnonzero(counts[inverse] == 2)
    paired = rows[np.argsort(inverse[rows], kind="stable")] // 3
    pairs = paired.reshape(-1, 2)
    graph = coo_matrix(
        (np.ones(len(pairs)), (pairs[:, 0], pairs[:, 1])), shape=(len(faces), len(faces))
    )
    parts, _labels = connected_components(graph, directed=False)
    used = len(np.unique(faces))
    return int((counts == 1).sum()), int((counts > 2).sum()), int(parts), used


def main() -> None:
    files: list[Path] = []
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
            diagonal = float(np.linalg.norm(vertices.max(axis=0) - vertices.min(axis=0)))
            digits = weld_digits(weld_tolerance(diagonal))
            before = figures(geometry)
            t = time.perf_counter()
            old = geometry.copy()
            old.merge_vertices(digits_vertex=digits)
            after_old = figures(old)
            # Das Bessere aus „wie trimesh verschweißt" und „gar nicht verschweißt":
            # Import und Reparatur nahmen je eines davon.
            if after_old[0] + after_old[1] > before[0] + before[1]:
                after_old = before
            time_old += time.perf_counter() - t
            t = time.perf_counter()
            new = geometry.copy()
            weld(new, digits)
            after_new = figures(new)
            time_new += time.perf_counter() - t
            bodies += 1
            if after_old != after_new:
                differing += 1
                score_old = after_old[0] + after_old[1]
                score_new = after_new[0] + after_new[1]
                verdict = (
                    "besser" if score_new < score_old else "schlechter" if score_new > score_old else "anders"
                )
                better += verdict == "besser"
                worse += verdict == "schlechter"
                print(
                    f"{verdict:10s} {path.name[:44]:44s} #{index} {len(geometry.faces):8d} Dr."
                    f"  vorher {before}  bisher {after_old}  neu {after_new}",
                    flush=True,
                )
    print(f"{bodies} Körper, {differing} verschieden: {better} besser, {worse} schlechter")
    print(f"Zeit bisher {time_old:.2f} s, neu {time_new:.2f} s")


main()
