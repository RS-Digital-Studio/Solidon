"""Sonde 14: Was kostet der Kantenteil der Netzfehlerkarte (group_rows + Python-Schleife je Kante)
gegenüber der Kantentabelle der Reparatur? Durchdringungssuche dafür abgeschaltet."""
import time
import numpy as np
from common import KUNDE, R
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive import maps

orig = R.self_intersection_check
R.self_intersection_check = lambda mesh, cancelled=None: ((), True)
for rel in ("spiderman+voronoi+bambu+10cm_stls/obj_1_spiderman.stl", "pirate+ship+with+sails_stls/obj_15_Assembly.stl"):
    path = KUNDE / rel
    mesh = normalise(read_mesh(path.read_bytes(), ".stl"), "mm", weld_is_reading=True).mesh
    fresh = type(mesh)(raw=mesh.raw.copy())
    t0 = time.perf_counter(); dm = maps.defect_map(fresh); t_map = time.perf_counter() - t0
    fresh2 = type(mesh)(raw=mesh.raw.copy())
    t0 = time.perf_counter(); o = R.open_edge_count(fresh2); b = R.branching_edge_count(fresh2); t_tab = time.perf_counter() - t0
    vals = np.asarray(dm.values)
    print(f"{rel}: {mesh.triangle_count} Dreiecke; Karte ohne Durchdringung {t_map:.2f}s "
          f"(offen={int((vals==1).sum())}, verzweigt={int((vals==2).sum())}); Kantentabelle {t_tab:.2f}s (offen={o}, verzweigt={b})", flush=True)
R.self_intersection_check = orig
