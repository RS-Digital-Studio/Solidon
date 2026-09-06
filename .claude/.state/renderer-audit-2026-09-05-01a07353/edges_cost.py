"""Misst die CPU-Kosten der Kantenpaarsuche des GFX-Renderers an großen Netzen."""
import sys, time
import numpy as np
sys.path.insert(0, r"F:/3D Druck")
import trimesh
from app.ui.render.gfx_renderer import _unique_edges
mesh = trimesh.load(r"C:\Users\rober\Downloads\tree_with_tray_stl.stl", force="mesh")
print("Dreiecke", len(mesh.faces))
for stage in range(3):
    faces = np.asarray(mesh.faces)
    t = time.perf_counter()
    pairs = _unique_edges(faces)
    dt = time.perf_counter() - t
    positions = np.asarray(mesh.vertices, dtype=np.float32)
    t = time.perf_counter()
    lines = positions[pairs].reshape(-1, 3)
    dt2 = time.perf_counter() - t
    print(f"Stufe {stage}: {len(faces)} Dreiecke -> {len(pairs)} Kanten in {dt*1000:.0f} ms, Linienpuffer {dt2*1000:.0f} ms, {lines.nbytes/1e6:.0f} MB")
    if stage < 2:
        mesh = mesh.subdivide()
