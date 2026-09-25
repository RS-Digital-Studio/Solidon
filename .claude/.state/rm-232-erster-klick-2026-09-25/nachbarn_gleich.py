"""RM-232: Die neue Platzierungsnachbarschaft gegen die alte Rechnung."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import numpy as np
import trimesh
from app.core.geom.mesh import unique_edges
from app.core.scene import placement


def old(raw):
    vertices = np.asarray(raw.vertices, dtype=np.float64)
    _, inverse = np.unique(vertices, axis=0, return_inverse=True)
    faces = inverse.reshape(-1)[np.asarray(raw.faces, dtype=np.int64)]
    _, edge_ids = unique_edges(faces[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), return_inverse=True)
    edge_ids = np.asarray(edge_ids, dtype=np.int64).reshape(-1)
    order = np.argsort(edge_ids, kind="stable")
    shared = np.bincount(edge_ids)[edge_ids[order]] == 2
    pairs = (order[shared] // 3).reshape(-1, 2)
    return pairs[pairs[:, 0] != pairs[:, 1]]


for name in sys.argv[1:]:
    for process in (True, False):
        raw = trimesh.load(name, process=process, force="mesh")
        a = old(raw)
        t = time.perf_counter()
        b = placement._welded_adjacency(raw)
        took = (time.perf_counter() - t) * 1000
        same = {tuple(p) for p in a.tolist()} == {tuple(p) for p in b.tolist()} and len(a) == len(b)
        print(f"{Path(name).name:40s} process={process!s:5s} {len(raw.faces):7d} Dreiecke  gleich {same}  {took:6.1f} ms")
