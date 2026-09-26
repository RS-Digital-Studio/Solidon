"""Übernommen aus review-050/sonden/vorschau für RM-212 (Baum aus SONDE_TREE, Ziel aus ZIEL).

Anzeigeweg an großen Netzen: Dauer je Stufe und längster GIL-Stillstand.

Ein Taktgeber-Faden schläft 5 ms und misst, wie spät er aufwacht, während
``decimate_for_display`` in einem zweiten Faden rechnet — so wie der
Vorschau-Arbeiter neben dem Qt-Hauptfaden.
"""
import os, sys, tempfile, threading, time
TREE = os.environ["SONDE_TREE"]
TARGET = int(os.environ.get("ZIEL", "50000"))
sys.path.insert(0, TREE)
_ISOLATED = tempfile.mkdtemp(prefix="sonde-vorschau-")
for v in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[v] = _ISOLATED
import app
from pathlib import Path
assert str(Path(app.__file__).resolve()).startswith(str(Path(TREE).resolve())), app.__file__
print('app aus', app.__file__, 'Ziel', TARGET, flush=True)
from app.core.geom import mesh_ops
from app.core.geom.mesh import read_mesh, MeshData
from app.core.ingest.loader import normalise
import trimesh

stages = []
def wrap(name):
    orig = getattr(mesh_ops, name)
    def timed(*a, **k):
        t = time.perf_counter()
        try:
            return orig(*a, **k)
        finally:
            stages.append((name, time.perf_counter() - t))
    setattr(mesh_ops, name, timed)
for name in ("_as_solid", "_display_manifold_decimation", "_clustered_for_display", "_as_mesh"):
    wrap(name)

for path in sys.argv[1:]:
    raw = trimesh.load(path, force="mesh")
    mesh = MeshData.of(raw)
    stages.clear()
    late = []
    done = threading.Event()
    def tick():
        while not done.is_set():
            t = time.perf_counter()
            time.sleep(0.005)
            late.append(time.perf_counter() - t - 0.005)
    ticker = threading.Thread(target=tick); ticker.start()
    t = time.perf_counter()
    out = []
    if os.environ.get("ALTER_WEG"):
        worker = threading.Thread(target=lambda: out.append(mesh_ops._decimate_with_solver(mesh, TARGET)[0]))
    else:
        worker = threading.Thread(target=lambda: out.append(mesh_ops.decimate_for_display(mesh, TARGET)))
    worker.start(); worker.join()
    total = time.perf_counter() - t
    done.set(); ticker.join()
    print(f"{os.path.basename(path)}: {mesh.triangle_count} → {out[0].triangle_count} in {total:.2f} s, "
          f"geschlossen={mesh.is_watertight}, längster Stillstand {max(late)*1000:.0f} ms", flush=True)
    for name, seconds in stages:
        print(f"    {name:<32} {seconds:.2f} s")
