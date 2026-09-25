"""Sonde 8: Laufzeit der Lochfüllung an einem großen Randring (offener Zylinder,
oben offen) und an einem gewellten Ring. Misst fill_boundary_loops und
repair(holes=True) und ob ein Abbruch dazwischen greift."""

from __future__ import annotations

import math
import threading
import time

import numpy as np
import trimesh

from common import R, MeshData

from app.core.errors import OperationCancelled
from app.core.scene.cancel import CancelSignal


def open_cylinder(segments: int, wavy: bool = False) -> MeshData:
    angles = np.linspace(0, 2 * math.pi, segments, endpoint=False)
    radius = 20.0 + (3.0 * np.sin(angles * 7) if wavy else 0.0)
    ring = np.column_stack([radius * np.cos(angles), radius * np.sin(angles)])
    bottom = np.column_stack([ring, np.zeros(segments)])
    top = np.column_stack([ring, np.full(segments, 10.0)])
    centre = np.array([[0.0, 0.0, 0.0]])
    vertices = np.vstack([bottom, top, centre])
    faces = []
    c = 2 * segments
    for i in range(segments):
        j = (i + 1) % segments
        faces += [[i, j, segments + j], [i, segments + j, segments + i], [c, j, i]]
    body = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)
    if body.volume < 0:
        body.invert()
    return MeshData.of(body)


for wavy in (False, True):
    for n in (500, 1000, 2000, 4000, 8000):
        mesh = open_cylinder(n, wavy)
        t0 = time.perf_counter()
        closed, filled, wide = R.fill_boundary_loops(mesh)
        spent = time.perf_counter() - t0
        print(f"{'gewellt' if wavy else 'rund   '} Ring {n:>6} Kanten: fill {spent:7.2f}s  "
              f"gefüllt={filled} groß={wide} dicht={closed.is_watertight} "
              f"neue Dreiecke={closed.triangle_count - mesh.triangle_count}", flush=True)
        if spent > 60:
            break

# Abbruch: greift er während der Lochfüllung?
mesh = open_cylinder(8000, wavy=True)
signal = CancelSignal()
timer = threading.Timer(0.5, signal.cancel)
timer.start()
t0 = time.perf_counter()
try:
    R.repair(mesh, cancelled=signal)
    print(f"Abbruch nach 0,5 s angefordert: repair lief bis zum Ende, {time.perf_counter()-t0:.2f}s")
except OperationCancelled:
    print(f"Abbruch griff nach {time.perf_counter()-t0:.2f}s")
