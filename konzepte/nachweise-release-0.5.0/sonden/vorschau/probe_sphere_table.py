"""Tabelle „Die Merkmale bleiben erkennbar" für den Anzeigeweg (RM-208).

Kugel r = 20 mm, 327 680 Dreiecke; ``decimate_mesh(method="fast")`` auf das
Ziel, danach *Bohrung* Ø 5 durch die Mitte. Abweichung beidseitig
(``mesh_ops.deviation``), Geschlecht aus der Euler-Zahl, erkannter
Bohrungsdurchmesser, Abtrag — jeweils gegen denselben Schritt am genauen Körper.
"""
import os, sys, tempfile, time
TREE = r"F:\3D Druck.review-050\wt-vorschau"
sys.path.insert(0, TREE)
_ISOLATED = tempfile.mkdtemp(prefix="sonde-vorschau-")
for v in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[v] = _ISOLATED
import app
assert app.__file__.startswith(TREE)
import trimesh
from app.core import bootstrap
bootstrap.load_operations()
from app.core.geom import mesh_ops
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Scene, SceneObject

profile = profiles.make_profile("centauri-carbon-2", "petg")

def run(op, mesh, **params):
    entry = SceneObject(id="obj_1", name="K", mesh=mesh)
    spec = REGISTRY.get(op)
    return spec.fn(OpContext(scene=Scene(objects={"obj_1": entry}), inputs=[entry], params=spec.params(**params),
        profile=profile, quality="draft", seed=None, progress=lambda f, t: None, ask=lambda q, c: c[0], cancelled=NeverCancelled()))

def drill(mesh):
    return run("drill_hole", mesh, diameter=5.0, x=0.0, y=0.0, z=20.0, depth=0.0).outputs[0].mesh

def hole(mesh):
    found = [f.params["diameter"] for f in detect(mesh).values() if f.kind == "hole"]
    return found

sub = int(sys.argv[1]) if len(sys.argv) > 1 else 7
sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=sub, radius=20.0))
exact = drill(sphere)
print(f"Kugel {sphere.triangle_count} Dreiecke; genau: Geschlecht {1 - exact.raw.euler_number // 2}, "
      f"Loch {hole(exact)}, Abtrag {sphere.volume - exact.volume:.1f} mm³", flush=True)
print("Ziel | Dreiecke | Zeit | Abw. alt→neu | Abw. neu→alt | Geschlecht | Loch | Abtrag")
for target in (100_000, 50_000, 20_000, 5_000, 2_000):
    t = time.perf_counter()
    coarse = run("decimate_mesh", sphere, triangles=target, method="fast").outputs[0].mesh
    dt = time.perf_counter() - t
    drilled = drill(coarse)
    print(f"{target} | {coarse.triangle_count} | {dt:.2f} s | {mesh_ops.deviation(sphere, coarse):.4f} | "
          f"{mesh_ops.deviation(coarse, sphere):.4f} | {1 - drilled.raw.euler_number // 2} | {hole(drilled)} | "
          f"{coarse.volume - drilled.volume:.1f}", flush=True)
