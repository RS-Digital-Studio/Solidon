import sys, time; sys.path.insert(0, r"F:\3D Druck")
from pathlib import Path
import numpy as np
from app.core.ingest import threemf
from app.core.ingest.loader import normalise
from app.core.perceive.local import detect_local, _region, LOCAL_FACE_LIMIT
from app.core.perceive.features import _one_body
parts = threemf.read_objects(Path(r"F:\3D Dateien\Mausoleum Dragon.3mf").read_bytes(), [])
mesh = normalise(parts[0].mesh, "mm").mesh
print("Ausdehnung", np.round(mesh.raw.extents, 1).tolist(), "Fläche", round(float(mesh.raw.area), 0))
centres = np.asarray(mesh.raw.triangles_center); normals = np.asarray(mesh.raw.face_normals)
low = centres[:, 2].min()
bottom = np.flatnonzero((centres[:, 2] < low + 0.01) & (normals[:, 2] < -0.999))
area = float(np.asarray(mesh.raw.area_faces)[bottom].sum())
print("Unterseite: Dreiecke", len(bottom), "Fläche", round(area, 1), "Ausdehnung", np.round(centres[bottom].max(0) - centres[bottom].min(0), 1).tolist())
face = int(bottom[len(bottom)//2]); point = centres[face]; normal = normals[face]
for radius in (5.0, 6.0, 7.0, 8.0, 10.0, 12.0, 15.0):
    idx = _region(mesh, point, radius, None)
    t = time.perf_counter()
    r = detect_local(mesh, tuple(point), normal=tuple(normal), radius=radius, seed_faces=(face,))
    print(f"r={radius:g}: Bereich={'>'+str(LOCAL_FACE_LIMIT) if idx is None else len(idx)} reason={r.reason} Merkmale={[(f.kind, round(f.params.get('area',0),1)) for f in r.features.values()]} ({time.perf_counter()-t:.1f}s)")
