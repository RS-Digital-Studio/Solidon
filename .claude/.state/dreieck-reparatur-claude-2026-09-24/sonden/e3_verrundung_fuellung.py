import sys; sys.path.insert(0, r"F:\3D Druck")
import importlib.util
spec = importlib.util.spec_from_file_location("p1", r"F:\3D Druck\.claude\.state\dreieck-reparatur-claude-2026-09-24\sonden\p1_schaden_reparatur.py")
p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
import numpy as np
from app.core.geom import repair as R
from app.core.perceive.features import detect, forget_cache
name, pristine = p1.load(p1.KUNDEN / "the-over-engineered-backpack-wall-mount-v2.stl")[0]
forget_cache(); ref = detect(pristine)
fillet = next(f for f in ref.values() if f.kind == "fillet" and abs(f.params["radius"] - 3.0) < 0.01 and len(f.face_indices) == 17)
print("Verrundung", fillet.id, fillet.params["radius"], fillet.params["length"], sorted(fillet.face_indices))
patch = p1.interior_patch(pristine, fillet.face_indices, 2, 7)
print("entfernt", patch, [np.asarray(pristine.raw.faces)[f].tolist() for f in patch])
tri = np.asarray(pristine.raw.triangles)
for f in patch:
    print("  Dreieck", f, np.round(tri[f], 3).tolist(), "Normale", np.round(pristine.raw.face_normals[f], 4).tolist())
damaged = p1.without(pristine, patch)
fixed = R.repair(damaged)
new = np.asarray(fixed.mesh.raw.faces)[damaged.triangle_count:]
print("neu", new.tolist())
for row in range(len(new)):
    face = damaged.triangle_count + row
    print("  neu", face, np.round(np.asarray(fixed.mesh.raw.triangles)[face], 3).tolist(), "Normale", np.round(fixed.mesh.raw.face_normals[face], 4).tolist())
# Diederwinkel alt/neu an den Füllkanten
forget_cache(); healed = detect(fixed.mesh)
for f in healed.values():
    if f.kind == "fillet" and abs(f.params["centre"][0] - 20.5) < 1.0 and abs(f.params["centre"][2] - 40.3) < 1.0:
        print("R", f.id, round(f.params["radius"], 3), round(f.params["length"], 3), len(f.face_indices))
