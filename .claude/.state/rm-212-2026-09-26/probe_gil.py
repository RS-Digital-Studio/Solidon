"""Sonde RM-212: Welche manifold3d-Aufrufe halten den GIL?

Ein Taktfaden schläft 5 ms und misst seine längste Verspätung, während im
Hauptfaden je ein Aufruf läuft — Konstruktion aus Mesh64, simplify,
refine_to_length, Differenz, to_mesh64. Hält der Aufruf den GIL, ist die
längste Verspätung so lang wie der Aufruf.

Aufruf: python probe_gil.py <stl>
"""

from __future__ import annotations

import sys
import threading
import time

import manifold3d
import numpy as np
import trimesh

print("manifold3d", getattr(manifold3d, "__version__", "?"), flush=True)
body = trimesh.load(sys.argv[1], force="mesh")
print(f"{len(body.faces)} Dreiecke, dicht {body.is_watertight}", flush=True)


def measured(label, work):
    late = [0.0]
    done = threading.Event()

    def tick():
        while not done.is_set():
            started = time.perf_counter()
            time.sleep(0.005)
            late[0] = max(late[0], time.perf_counter() - started - 0.005)

    ticker = threading.Thread(target=tick, daemon=True)
    ticker.start()
    time.sleep(0.05)
    started = time.perf_counter()
    result = work()
    spent = time.perf_counter() - started
    done.set()
    ticker.join()
    print(f"  {label:<28} {spent * 1000:8.0f} ms, längster Stillstand {late[0] * 1000:6.0f} ms", flush=True)
    return result


vertices = np.asarray(body.vertices, dtype=np.float64)
faces = np.asarray(body.faces, dtype=np.uint64)
solid = measured("Manifold(Mesh64)", lambda: manifold3d.Manifold(manifold3d.Mesh64(vertices, faces)))
print("  leer" if solid.is_empty() else f"  {solid.num_tri()} Dreiecke im Kern")
if not solid.is_empty():
    measured("simplify(0.05)", lambda: solid.simplify(0.05))
    measured("simplify(0.8)", lambda: solid.simplify(0.8))
    box = solid.bounding_box()
    centre = [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2]
    tool = manifold3d.Manifold.cylinder(200.0, 3.0, 3.0, 64).translate((centre[0], centre[1], centre[2] - 100.0))
    measured("Differenz mit Zylinder", lambda: (solid - tool).num_tri())
    measured("refine_to_length(2.0)", lambda: solid.refine_to_length(2.0).num_tri())
    measured("to_mesh64", lambda: solid.to_mesh64())
