import sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import numpy as np
import trimesh
from app.core.geom.mesh import unique_edges
from app.core.perceive.features import _vertex_rank
from app.core.scene.placement import _welded_adjacency
raw = trimesh.load(sys.argv[1], process=True)
v = np.asarray(raw.vertices, dtype=np.float64)
print(len(raw.faces), len(v))
for _ in range(2):
    t = time.perf_counter(); _, inv = np.unique(v, axis=0, return_inverse=True); a = time.perf_counter() - t
    raw._cache.cache.pop("solidon_vertex_rank", None)
    t = time.perf_counter(); rank = _vertex_rank(raw); b = time.perf_counter() - t
    print(f"unique axis=0 {a*1000:.1f} ms, _vertex_rank {b*1000:.1f} ms, gleich {np.array_equal(inv.reshape(-1), rank)}")
faces = inv.reshape(-1)[np.asarray(raw.faces, dtype=np.int64)]
t = time.perf_counter()
_, edge_ids = unique_edges(faces[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), return_inverse=True)
edge_ids = np.asarray(edge_ids, dtype=np.int64).reshape(-1)
c = time.perf_counter() - t
t = time.perf_counter(); order = np.argsort(edge_ids, kind="stable"); d = time.perf_counter() - t
print(f"unique_edges {c*1000:.1f} ms, argsort {d*1000:.1f} ms")
from app.core.geom.mesh import edge_table
t = time.perf_counter(); table = edge_table(raw); e = time.perf_counter() - t
t = time.perf_counter(); pairs = table.face_pairs(); f = time.perf_counter() - t
shared = np.bincount(edge_ids)[edge_ids[order]] == 2
old = (order[shared] // 3).reshape(-1, 2)
old = old[old[:, 0] != old[:, 1]]
same = {tuple(p) for p in old.tolist()} == {tuple(p) for p in pairs.tolist()}
print(f"edge_table {e*1000:.1f} ms, face_pairs {f*1000:.1f} ms, gleiche Paare {same}, {len(pairs)} Paare")
