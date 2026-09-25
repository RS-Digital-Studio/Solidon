import sys; sys.path.insert(0, r"F:\3D Druck")
import importlib.util
spec = importlib.util.spec_from_file_location("p4", r"F:\3D Druck\.claude\.state\dreieck-reparatur-claude-2026-09-24\sonden\p4_grosse_luecken.py")
p4 = importlib.util.module_from_spec(spec); spec.loader.exec_module(p4)
import numpy as np
from app.core.geom.repair import repair
from app.core.geom.mesh import face_components
post = p4.load("post_with_fillet.stl")
centres = np.asarray(post.raw.triangles_center)
radial = np.linalg.norm(centres[:, :2], axis=1)
mantle = np.flatnonzero((np.abs(radial - 6.0) < 0.05) & (centres[:, 2] > 6.5))
fixed = repair(p4.without(post, mantle.tolist()))
for c in face_components(fixed.mesh.raw):
    sub = fixed.mesh.raw.submesh([c], append=True, repair=False)
    print("Teil", len(c), "Volumen", round(float(sub.volume), 4), "Fläche", round(float(sub.area), 2), "z", np.round(sub.bounds[:, 2], 3).tolist())
print([ (f.code, f.severity) for f in fixed.findings])
