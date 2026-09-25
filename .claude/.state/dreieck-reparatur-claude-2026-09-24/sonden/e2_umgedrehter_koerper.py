import sys; sys.path.insert(0, r"F:\3D Druck")
import importlib.util
spec = importlib.util.spec_from_file_location("p1", r"F:\3D Druck\.claude\.state\dreieck-reparatur-claude-2026-09-24\sonden\p1_schaden_reparatur.py")
p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
import numpy as np, trimesh
from app.core.geom import repair as R
from app.core.geom.mesh import MeshData, enclosed_volume, face_components
name, pristine = p1.load(p1.KUNDEN / "broomholdervcd_d35mm.stl")[0]
comps = face_components(pristine.raw)
print("Komponenten:", [len(c) for c in comps])
for c in comps:
    sub = pristine.raw.submesh([c], append=True, repair=False)
    print("  Teil", len(c), "Volumen", round(float(sub.volume),2), "wt", sub.is_watertight, "bounds", np.round(sub.bounds,1).tolist())
rng = np.random.default_rng(20260924)
count = max(3, pristine.triangle_count // 400)
scattered = sorted(set(rng.choice(pristine.triangle_count, size=count, replace=False).tolist()))
table = p1.neighbours(pristine)
apart = []
for face in scattered:
    if not table.get(face, set()) & set(apart):
        apart.append(face)
# gleiche Zufallsfolge wie in p1 bis zu den 5 %-Normalen: p1 zieht danach noch Flips aus demselben rng
flips = rng.choice(pristine.triangle_count, size=max(1, pristine.triangle_count // 20), replace=False).tolist()
damaged = p1.flipped(pristine, flips)
fixed = R.repair(damaged)
same = np.array_equal(np.asarray(fixed.mesh.raw.faces), np.asarray(pristine.raw.faces))
print("5%-Fall: Flächen gleich wie unbeschädigt:", same)
f_now = np.asarray(fixed.mesh.raw.faces); f_old = np.asarray(pristine.raw.faces)
diff = np.flatnonzero(~np.all(f_now == f_old, axis=1))
print("  abweichende Dreiecke:", len(diff))
for c in face_components(fixed.mesh.raw):
    sub = fixed.mesh.raw.submesh([c], append=True, repair=False)
    inter = len(set(c.tolist()) & set(diff.tolist()))
    print("  Teil", len(c), "Volumen", round(float(sub.volume),2), "davon abweichend", inter)
print("  Gesamtvolumen P", round(float(pristine.volume),2), "R", round(float(fixed.mesh.volume),2))
print("---- Importweg: ein Körper vollständig umgedreht in der Datei")
from app.core.ingest.loader import normalise, read_model
from app.core.perceive.features import detect, forget_cache
second = face_components(pristine.raw)[1]
inverted = p1.flipped(pristine, second.tolist())
stl = inverted.raw.export(file_type="stl")
imported = normalise(read_model(stl, ".stl"), "mm")
print("  Befunde:", [f.code for f in imported.findings])
for c in face_components(imported.mesh.raw):
    sub = imported.mesh.raw.submesh([c], append=True, repair=False)
    print("  Teil", len(c), "Volumen", round(float(sub.volume),2))
forget_cache(); fp = detect(pristine)
forget_cache(); fi = detect(imported.mesh)
def holes(f): return sorted((round(v.params["diameter"],2), tuple(round(x,1) for x in v.params["centre"])) for v in f.values() if v.kind=="hole")
print("  Bohrungen unbeschädigt:", holes(fp))
print("  Bohrungen importiert  :", holes(fi))
from collections import Counter
print("  Arten unbeschädigt:", dict(Counter(v.kind for v in fp.values())))
print("  Arten importiert  :", dict(Counter(v.kind for v in fi.values())))
res = R.repair(imported.mesh)
print("  Reparatur danach:", res.changed, [f.code for f in res.findings])
