"""Sonde 6c: Naht-zusammengesetzt.stl — Rohzustand, Import ohne/mit Füllen, Defektkarte."""
import numpy as np
from common import KUNDE, R, MeshData, facts, codes
from app.core.geom.mesh import read_mesh, face_components
from app.core.ingest.loader import normalise
from app.core.perceive import maps

path = KUNDE / "3D Drucker" / "16_CC2-Auffangrinne" / "Naht-zusammengesetzt.stl"
mesh = read_mesh(path.read_bytes(), ".stl")
w, _ = R.merge_vertices(mesh)
print("roh verschweißt:", facts(w))
plain = normalise(mesh, "mm", weld_is_reading=True, mend=False)
print("Import ohne Füllen:", codes(plain.findings), facts(plain.mesh))
full = normalise(mesh, "mm", weld_is_reading=True)
print("Import mit Füllen:", codes(full.findings), facts(full.mesh))
for label, m in (("ohne Füllen", plain.mesh), ("mit Füllen", full.mesh)):
    dm = maps.defect_map(m)
    vals = np.asarray(dm.values)
    cats = {name: int(np.count_nonzero(vals == i)) for i, name in enumerate(dm.categories)}
    print(f"Defektkarte {label}:", cats, "unbekannt", dm.unknown_count)
