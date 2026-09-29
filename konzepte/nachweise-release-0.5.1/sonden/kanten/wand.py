"""(ii) Kandidaten für die Tests: Wand 40 x 3 x 20 und Hohlkasten, Gruppe „alle“, beide Kerne."""
import os
import sys

sys.path.insert(0, os.getcwd())
import trimesh  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.brep import edit  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene.cancel import NeverCancelled  # noqa: E402
from app.core.types import OpContext, Scene, SceneObject  # noqa: E402

load_operations()
profile = profiles.make_profile("centauri-carbon-2", "petg")


def run(entry, op, **params):
    spec = REGISTRY.get(op)
    return spec.fn(OpContext(scene=Scene(objects={entry.id: entry}), inputs=[entry], params=spec.params(**params),
        profile=profile, quality="fine", seed=None, progress=lambda f, t: None, ask=lambda q, c: c[0],
        cancelled=NeverCancelled()))


outer = edit.box(40.0, 30.0, 20.0)
inner = edit.moved(edit.box(34.0, 24.0, 20.0), (3.0, 3.0, 3.0))
hollow = edit.boolean("difference", [outer, inner])
bodies = [
    ("Wand exakt", edit.box(40.0, 3.0, 20.0), "brep"),
    ("Wand Netz", MeshData.of(trimesh.creation.box(extents=(40.0, 3.0, 20.0))), "mesh"),
    ("Hohlkasten exakt", hollow, "brep"),
    ("Hohlkasten Netz", hollow.to_mesh(), "mesh"),
]
for name, body, kind in bodies:
    entry = SceneObject(id="obj_1", name=name, mesh=body, kind=kind)
    for op, field, size, group in (("fillet_edges", "radius", 2.0, "all"), ("chamfer_edges", "distance", 2.9, "all"),
                                    ("fillet_edges", "radius", 2.0, "top"), ("fillet_edges", "radius", 1.4, "all")):
        try:
            result = run(entry, op, edges=group, **{field: size})
            codes = {f.code: dict(f.values) for f in result.findings}
            out = result.outputs[0].mesh
            print(f"{name} {op} {size} {group}: gelungen, Höhe {out.bounds.size[2]:.4f}, Volumen {out.volume:.3f}, {codes}")
        except AppError as error:
            print(f"{name} {op} {size} {group}: abgelehnt {getattr(error, 'values', {})}")
