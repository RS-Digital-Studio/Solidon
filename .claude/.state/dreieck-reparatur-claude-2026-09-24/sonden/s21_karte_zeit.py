"""Sonde 21: Zeit der Netzfehlerkarte am aktuellen Budget (max(2 Mio., 512 × Dreiecke))."""
import hashlib, time
from pathlib import Path
import numpy as np
from common import KUNDE, R
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive import maps

print("repair.py", hashlib.sha1(Path(R.__file__).read_bytes()).hexdigest()[:8])
for rel in ("broomholdervcd_d35mm.stl", "spiderman+voronoi+bambu+10cm_stls/obj_1_spiderman.stl"):
    mesh = normalise(read_mesh((KUNDE / rel).read_bytes(), ".stl"), "mm", weld_is_reading=True).mesh
    t0 = time.perf_counter(); dm = maps.defect_map(mesh); spent = time.perf_counter() - t0
    vals = np.asarray(dm.values)
    print(f"{rel}: {mesh.triangle_count} Dreiecke, Karte {spent:.2f}s, Durchdringung={int((vals == 3).sum())}, unbekannt={dm.unknown_count}, Budget={R.intersection_budget(mesh.triangle_count):,}", flush=True)
