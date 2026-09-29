"""Sonde RM-212 (Hilfsprozess): Welche manifold3d-Aufrufe halten an großen
Netzen den GIL, und wie lange?

Ein Taktfaden schläft 2 ms und misst seine längste Verspätung, während im
Hauptfaden je ein Aufruf läuft. Hält der Aufruf den GIL, ist die längste
Verspätung so lang wie der Aufruf; gibt er ihn her, bleibt sie klein.

Gemessen je Modell: Aufbau aus Mesh64, simplify (0 / 0,05 / 0,2 mm),
refine_to_length (ein Durchgang), to_mesh64, Differenz mit einem Zylinder
(batch_boolean + status), decompose — dazu die Kosten des Kopierens
(Pickle, Kopie in einen gemeinsamen Speicher) an denselben Feldern.

Aufruf (gebunden, aus dem Arbeitsbaum): python ../sonden/hilfsprozess/gil_kern.py [kurz]
"""

from __future__ import annotations

import os
import pickle
import sys
import threading
import time
from multiprocessing import shared_memory

import manifold3d
import numpy as np
import trimesh

MODELS = [
    (r"F:\3D Dateien\dice_w6_16mm_v00.stl", 0.05),
    (r"F:\3D Dateien\spiderman+voronoi+bambu+10cm_stls\obj_1_spiderman.stl", 0.2),
    (r"F:\3D Dateien\pirate+ship+with+sails_stls\obj_15_Assembly.stl", 0.5),
    (r"F:\3D Dateien\meshy_ai_wooden-marble-game-board_1789261431_generate-1.stl", 1.53),
]
if len(sys.argv) > 1 and sys.argv[1] == "kurz":
    MODELS = MODELS[:1]


class Ticker:
    def __init__(self) -> None:
        self.late = 0.0
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.done.is_set():
            started = time.perf_counter()
            time.sleep(0.002)
            self.late = max(self.late, time.perf_counter() - started - 0.002)

    def __enter__(self) -> Ticker:
        self.thread.start()
        time.sleep(0.03)
        self.late = 0.0
        self.started = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        self.spent = time.perf_counter() - self.started
        self.done.set()
        self.thread.join()


def measured(label: str, work):
    with Ticker() as ticker:
        result = work()
    print(
        f"  {label:<34} {ticker.spent * 1000:9.0f} ms, längster Stillstand "
        f"{ticker.late * 1000:8.0f} ms",
        flush=True,
    )
    return result


print("manifold3d 3.5.3 erwartet; numpy", np.__version__, "Prozess", os.getpid(), flush=True)
for path, edge in MODELS:
    name = os.path.basename(path)
    body = trimesh.load(path, force="mesh")
    vertices = np.ascontiguousarray(body.vertices, dtype=np.float64)
    faces = np.ascontiguousarray(body.faces, dtype=np.uint64)
    print(f"{name}: {len(faces)} Dreiecke, dicht {body.is_watertight}", flush=True)
    solid = measured("Manifold(Mesh64)", lambda: manifold3d.Manifold(manifold3d.Mesh64(vertices, faces)))
    if solid.is_empty():
        print("  leer — Kern nimmt es nicht", flush=True)
        continue
    measured("simplify(0)", lambda: solid.simplify(0.0).num_tri())
    measured("simplify(0.05)", lambda: solid.simplify(0.05).num_tri())
    measured("simplify(0.2)", lambda: solid.simplify(0.2).num_tri())
    measured("decompose", lambda: len(solid.decompose()))
    box = solid.bounding_box()
    centre = [(box[0] + box[3]) / 2, (box[1] + box[4]) / 2, (box[2] + box[5]) / 2]
    height = box[5] - box[2] + 2.0
    tool = manifold3d.Manifold.cylinder(height, 3.0, 3.0, 64).translate(
        (centre[0], centre[1], box[2] - 1.0)
    )
    cut = measured(
        "Differenz batch_boolean+status",
        lambda: (
            lambda result: (result.status(), result)[1]
        )(manifold3d.Manifold.batch_boolean([solid, tool], manifold3d.OpType.Subtract)),
    )
    measured("Differenz to_mesh64", lambda: cut.to_mesh64())
    fine = measured(f"refine_to_length({edge})", lambda: solid.refine_to_length(edge))
    print(f"    → {fine.num_tri()} Dreiecke", flush=True)
    built = measured("to_mesh64 (fein)", lambda: fine.to_mesh64())
    points = np.array(built.vert_properties[:, :3], dtype=np.float64, order="C", copy=True)
    corners = np.array(built.tri_verts, dtype=np.int64, order="C", copy=True)
    big = points.nbytes + corners.nbytes
    print(f"    Felder fein: {big / 1e6:.0f} MB", flush=True)
    measured(
        "Manifold(Mesh64) fein",
        lambda: manifold3d.Manifold(manifold3d.Mesh64(points, corners.astype(np.uint64))),
    )
    measured("pickle.dumps fein", lambda: pickle.dumps((points, corners), protocol=5))
    blob = pickle.dumps((points, corners), protocol=5)
    measured("pickle.loads fein", lambda: pickle.loads(blob))
    del blob
    segment = shared_memory.SharedMemory(create=True, size=big)
    try:
        target = np.ndarray(points.shape, dtype=points.dtype, buffer=segment.buf)
        measured("np.copyto in gemeinsamen Speicher", lambda: np.copyto(target, points))
        measured("np.array(copy) aus gemeinsamem Speicher", lambda: np.array(target, copy=True))
        del target
    finally:
        segment.close()
        segment.unlink()
    measured("np.array(copy) Ecken", lambda: np.array(corners, copy=True))
    measured("astype(uint64) Ecken", lambda: corners.astype(np.uint64))
print("Ende", flush=True)
