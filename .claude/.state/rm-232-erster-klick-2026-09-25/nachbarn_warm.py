import sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import trimesh
from app.core.geom.mesh import edge_table
from app.core.perceive.features import vertex_rank
from app.core.scene import placement
raw = trimesh.load(sys.argv[1], process=True, force="mesh")
vertex_rank(raw); edge_table(raw)
for _ in range(3):
    raw._cache.cache.pop(placement._ADJACENCY_KEY, None)
    t = time.perf_counter(); placement._welded_adjacency(raw); print(f"{(time.perf_counter()-t)*1000:.1f} ms")
