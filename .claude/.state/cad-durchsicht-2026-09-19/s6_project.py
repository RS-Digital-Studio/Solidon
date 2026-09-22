"""S6: Projizieren auf der Fläche, auf der man zeichnet — Ebenenschnitt oder Kontur?"""

import inspect
import _iso  # noqa: F401

import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect_faces
from app.core.sketch import edit
from app.core.sketch.planes import frame_of

print(inspect.getsource(edit.project)[:200])

Sketch = None
for modname in ("app.core.sketch.types", "app.core.sketch.model", "app.core.sketch", "app.core.types"):
    try:
        mod = __import__(modname, fromlist=["Sketch"])
        Sketch = getattr(mod, "Sketch", None)
        if Sketch:
            print("Sketch aus", modname, inspect.signature(Sketch))
            break
    except Exception as e:  # noqa: BLE001
        print(modname, repr(e))

body = trimesh.load(r"F:\3D Druck\tests\data\meshes\plate_holes.stl", force="mesh")
mesh = MeshData.of(body)
faces = detect_faces(mesh)
print("Flächen:", len(faces), "erste:", faces[0])
f0 = faces[0]
normal = getattr(f0, "normal", None) or (getattr(f0, "params", {}) or {}).get("normal")
centre = getattr(f0, "centre", None) or getattr(f0, "center", None) or (getattr(f0, "params", {}) or {}).get("centre")
print("normal/centre der ersten Fläche:", normal, centre)

if Sketch:
    ok = fail = 0
    for f in faces:
        n = getattr(f, "normal", None) or (getattr(f, "params", {}) or {}).get("normal")
        c = getattr(f, "centre", None) or getattr(f, "center", None) or (getattr(f, "params", {}) or {}).get("centre")
        frame = frame_of(tuple(n), tuple(c))
        sk = Sketch(plane="plane:xy", elements=())
        try:
            out = edit.project(sk, mesh, frame)
            kinds = {}
            for el in getattr(out, "elements", []):
                k = getattr(el, "kind", type(el).__name__)
                kinds[k] = kinds.get(k, 0) + 1
            ok += 1
            print(f"  Fläche {f.id}: {len(getattr(out, 'elements', []))} Elemente {kinds}")
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"  Fläche {f.id}: {type(e).__name__}: {str(e)[:120]}")
    print("Ergebnis: ok", ok, "fehlgeschlagen", fail)
    # Rand um EPS nach innen
    n = tuple(normal)
    c = tuple(centre)
    inner = tuple(c[i] - 1e-3 * n[i] for i in range(3))
    sk = Sketch(plane="plane:xy", elements=())
    try:
        out = edit.project(sk, mesh, frame_of(n, inner))
        kinds = {}
        for el in getattr(out, "elements", []):
            k = getattr(el, "kind", type(el).__name__)
            kinds[k] = kinds.get(k, 0) + 1
        print("Ebene 1e-3 ins Material geschoben:", len(getattr(out, "elements", [])), kinds)
    except Exception as e:  # noqa: BLE001
        print("verschobene Ebene:", repr(e)[:200])
