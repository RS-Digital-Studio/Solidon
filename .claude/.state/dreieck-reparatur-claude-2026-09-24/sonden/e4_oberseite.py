"""Ganze Deckfläche mit Bohrungsmündungen fehlt: Ring mit Innenringen."""
import sys; sys.path.insert(0, r"F:\3D Druck")
import importlib.util
spec = importlib.util.spec_from_file_location("p4", r"F:\3D Druck\.claude\.state\dreieck-reparatur-claude-2026-09-24\sonden\p4_grosse_luecken.py")
p4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p4)
import numpy as np
from collections import Counter
from app.core.geom.repair import repair, open_edge_count, self_intersection_check, boundary_loops
from app.core.geom.mesh import face_components
from app.core.perceive.features import detect, forget_cache
plate = p4.load("plate_holes.stl")
c = np.asarray(plate.raw.triangles_center); n = np.asarray(plate.raw.face_normals)
top = np.flatnonzero((c[:, 2] > 3.99) & (n[:, 2] > 0.999))
damaged = p4.without(plate, top.tolist())
print("entfernt", len(top), "Randringe", [len(l) for l in boundary_loops(damaged)])
fixed = repair(damaged)
s, ok = self_intersection_check(fixed.mesh)
print("Reparatur:", [(f.code, f.severity) for f in fixed.findings], "open", open_edge_count(fixed.mesh), "wt", fixed.mesh.is_watertight, "Teile", fixed.mesh.component_count, "Vol", round(fixed.mesh.volume, 2), "vorher", round(plate.volume, 2), "Durchdringungen", len(s))
forget_cache(); f0 = detect(plate); forget_cache(); f1 = detect(fixed.mesh)
print("vorher", dict(Counter(v.kind for v in f0.values())), sorted((v.kind, v.params.get("through")) for v in f0.values() if v.kind=="hole"))
print("nachher", dict(Counter(v.kind for v in f1.values())), sorted((v.kind, v.params.get("through")) for v in f1.values() if v.kind=="hole"))
for comp in face_components(fixed.mesh.raw):
    sub = fixed.mesh.raw.submesh([comp], append=True, repair=False)
    print("  Teil", len(comp), "Volumen", round(float(sub.volume), 3))
