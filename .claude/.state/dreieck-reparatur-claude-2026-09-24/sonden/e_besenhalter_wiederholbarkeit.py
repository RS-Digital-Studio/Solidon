import sys; sys.path.insert(0, r"F:\3D Druck")
import importlib.util
spec = importlib.util.spec_from_file_location("p1", r"F:\3D Druck\.claude\.state\dreieck-reparatur-claude-2026-09-24\sonden\p1_schaden_reparatur.py")
p1 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p1)
import numpy as np, hashlib
from collections import Counter
from app.core.geom import repair as R
from app.core.perceive.features import detect, forget_cache
name, pristine = p1.load(p1.KUNDEN / "broomholdervcd_d35mm.stl")[0]
rng = np.random.default_rng(20260924)
count = max(3, pristine.triangle_count // 400)
scattered = sorted(set(rng.choice(pristine.triangle_count, size=count, replace=False).tolist()))
table = p1.neighbours(pristine)
apart = []
for face in scattered:
    if not table.get(face, set()) & set(apart):
        apart.append(face)
damaged = p1.without(pristine, apart)
for attempt in range(3):
    fixed = R.repair(damaged)
    key = hashlib.md5(np.asarray(fixed.mesh.raw.vertices).tobytes() + np.asarray(fixed.mesh.raw.faces).tobytes()).hexdigest()
    forget_cache()
    fr = detect(fixed.mesh)
    print(attempt, key[:10], fixed.mesh.triangle_count, dict(Counter(v.kind for v in fr.values())))
forget_cache(); fp = detect(pristine)
forget_cache(); fr = detect(fixed.mesh)
missing, extra = p1.compare(fp, fr, pristine.bounds.diagonal)
print("fehlt:", [p1.label(f) for f in missing if f.kind!='edge_loop'])
print("neu:", [p1.label(f) for f in extra])
