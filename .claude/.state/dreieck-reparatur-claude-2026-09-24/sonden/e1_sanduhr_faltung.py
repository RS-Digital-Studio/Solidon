import sys; sys.path.insert(0, r"F:\3D Druck")
import importlib.util
from pathlib import Path
spec = importlib.util.spec_from_file_location("p1", r"F:\3D Druck\.claude\.state\dreieck-reparatur-claude-2026-09-24\sonden\p1_schaden_reparatur.py")
p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
import numpy as np
from app.core.geom import repair as R
from app.core.perceive.features import detect, forget_cache
name, pristine = p1.load(p1.REPO / "tests/data/meshes/plate_holes.stl")[0]
rng = np.random.default_rng(20260924)
count = max(3, pristine.triangle_count // 400)
scattered = sorted(set(rng.choice(pristine.triangle_count, size=count, replace=False).tolist()))
table = p1.neighbours(pristine)
apart = []
for face in scattered:
    if not table.get(face, set()) & set(apart):
        apart.append(face)
print("removed", apart, [np.asarray(pristine.raw.faces)[f].tolist() for f in apart])
print("normals", [np.round(pristine.raw.face_normals[f],3).tolist() for f in apart])
damaged = p1.without(pristine, apart)
loops = R.boundary_loops(damaged)
print("loops", loops)
filled, n, wide = R.fill_boundary_loops(damaged)
print("filled", n, wide, filled.triangle_count)
new = np.asarray(filled.raw.faces)[damaged.triangle_count:]
print("new faces", new.tolist())
print("new normals", np.round(np.asarray(filled.raw.face_normals)[damaged.triangle_count:],3).tolist())
print("vertices added", len(filled.raw.vertices) - len(damaged.raw.vertices))
res = R.repair(damaged)
print("repair", res.changed, [f.code for f in res.findings], res.mesh.triangle_count, res.mesh.is_watertight, res.mesh.raw.is_winding_consistent)
new2 = np.asarray(res.mesh.raw.faces)[damaged.triangle_count:]
print("R new normals", np.round(np.asarray(res.mesh.raw.face_normals)[damaged.triangle_count:],3).tolist())
forget_cache()
f = detect(res.mesh)
for k,v in f.items():
    if v.kind=="face": print(k, round(v.params["area"],3), v.params["normal"], np.round(v.params["centre"],3).tolist(), len(v.face_indices))
print("---- Selbstdurchdringung und Importweg")
found, complete = R.self_intersection_check(res.mesh)
print("self-intersections repaired:", len(found), complete)
found0, c0 = R.self_intersection_check(pristine)
print("self-intersections pristine:", len(found0), c0)
from app.core.ingest.loader import normalise, read_model
stl = damaged.raw.export(file_type="stl")
imported = normalise(read_model(stl, ".stl"), "mm")
print("import:", imported.mesh.triangle_count, imported.mesh.is_watertight, [f.code for f in imported.findings])
forget_cache()
fi = detect(imported.mesh)
print("import faces:", sorted((v.kind, round(v.params.get("area",0),1)) for v in fi.values() if v.kind=="face"))
print("import kinds:", {k: sum(1 for v in fi.values() if v.kind==k) for k in set(v.kind for v in fi.values())})
fs, cs = R.self_intersection_check(imported.mesh)
print("self-intersections import:", len(fs), cs)
# Zweiter Fall: zwei Einzeldreiecke mit gemeinsamer Ecke auf der Unterseite
