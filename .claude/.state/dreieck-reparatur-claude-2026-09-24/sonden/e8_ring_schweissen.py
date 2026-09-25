import sys; sys.path.insert(0, r"F:\3D Druck")
import importlib.util
spec = importlib.util.spec_from_file_location("p1", r"F:\3D Druck\.claude\.state\dreieck-reparatur-claude-2026-09-24\sonden\p1_schaden_reparatur.py")
p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
import numpy as np
from app.core.geom import repair as R
from app.core.units import weld_tolerance
parts = p1.load(p1.KUNDEN / "Siebhalter+X1C.3mf")
name, ring = parts[1]
print(name, ring.triangle_count, "wt", ring.is_watertight, "Diagonale", round(ring.bounds.diagonal, 2), "Schweißtoleranz", weld_tolerance(ring.bounds.diagonal))
cand, removed = R.merge_vertices(ring)
print("Schweißen am unbeschädigten Netz: entfernt", removed, "offen/verzweigt vorher", R.open_edge_count(ring), R.branching_edge_count(ring), "nachher", R.open_edge_count(cand), R.branching_edge_count(cand))
res0 = R.repair(ring)
print("repair unbeschädigt:", res0.changed, [f.code for f in res0.findings])
torn = p1.seam(ring)
res = R.repair(torn)
print("repair nach Riss:", res.changed, [f.code for f in res.findings], res.mesh.triangle_count, "Volumen", round(float(res.mesh.volume), 4), "vorher", round(float(ring.volume), 4))
# Abstand der eng beieinander liegenden Ecken
v = np.asarray(ring.raw.vertices)
from scipy.spatial import cKDTree
pairs = cKDTree(v).query_pairs(r=1e-4)
d = sorted(float(np.linalg.norm(v[a]-v[b])) for a, b in pairs)
print("Eckpaare unter 0,1 µm:", len(d), d[:6])
