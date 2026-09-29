"""RM-279, Messung für die Vorgabe „senkrecht“: Was geschieht an den Mündungen seitlicher Bohrungen?

Aufruf aus der Wurzel eines Arbeitsbaums: python vorgabe.py. Je Körper (beide
Kerne) und Fall (Verrunden R 0,5/1/2/5, Fase 1) die Operation mit
``edges="vertical"`` einmal neu (Ringe nach ihrer Ebene) und einmal wie bisher.
Ausgabe: gelungen?, Volumen, dicht/gültig, Befunde, und der Unterschied neu
gegen bisher — das ist, was an den Mündungen geschieht.
"""

import math
import os
import sys
import time
from pathlib import Path

TREE = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
sys.path.insert(0, TREE)
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve()), app.__file__
import trimesh  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.brep import edit, step  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom.edges import choose, edge_lie_of, edges_of  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene.cancel import NeverCancelled  # noqa: E402
from app.core.types import OpContext, Scene, SceneObject  # noqa: E402

load_operations()
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")
FILES = Path(r"F:\3D Dateien")


def cross_bored_mesh() -> MeshData:
    box = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    box.apply_translation((0.0, 0.0, 10.0))
    bore = trimesh.creation.cylinder(radius=3.0, height=90.0, sections=48)
    bore.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1, 0, 0)))
    bore.apply_translation((0.0, 0.0, 10.0))
    return boolean("difference", [MeshData(box), MeshData(bore)]).mesh


def bodies():
    yield "Quader Netz", "mesh", cross_bored_mesh()
    yield "Quader exakt", "brep", edit.bore(
        edit.box(40.0, 30.0, 20.0), position=(0.0, -15.0, 10.0), axis="y", diameter=6.0
    )
    for name in ("pegboard-goot-ceramic-screwdrivers-v3", "pegboard-pb3041-v4", "pegboard-gs-100-v2"):
        solid = step.read((FILES / f"{name}.step").read_bytes())
        yield f"{name} exakt", "brep", solid
        yield f"{name} Netz (Tessellierung)", "mesh", solid.to_mesh()
    three = FILES / "pegboard-goot-ceramic-screwdrivers-v3.3mf"
    if three.exists():
        yield "pegboard-goot-ceramic-screwdrivers-v3 Netz (3MF)", "mesh", read_mesh(three)


def run(entry: SceneObject, op: str, **params):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=PROFILE,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def closed(body, kind) -> str:
    return ("dicht" if body.is_watertight else "OFFEN") + f"/{body.component_count}T"


CASES = [("fillet_edges", {"radius": r}) for r in (0.5, 1.0, 2.0, 5.0)] + [
    ("chamfer_edges", {"distance": 1.0})
]

for name, kind, body in bodies():
    entries = edit.edges_of(body) if kind == "brep" else edges_of(body)
    rings = [e for e in entries if math.dist(e.direction, (0, 0, 0)) < 1e-6]
    standing = [e for e in rings if edge_lie_of(e) == "upright"]
    new = choose(entries, "vertical")
    old = choose(entries, "vertical", rings_by_plane=False)
    print(f"\n== {name}: Kanten {len(entries)}, Ringe {len(rings)}, stehend {len(standing)}; "
          f"senkrecht neu {len(new)}, bisher {len(old)}; Volumen {body.volume:.3f}")
    entry = SceneObject(id="obj_1", name=name, mesh=body, kind=kind)
    for op, params in CASES:
        label = f"{'Verrunden R' if op == 'fillet_edges' else 'Fase '}{next(iter(params.values()))}"
        volumes = {}
        for rings_by_plane in (True, False):
            started = time.perf_counter()
            try:
                result = run(entry, op, edges="vertical", rings_by_plane=rings_by_plane, **params)
            except AppError as error:
                print(f"  {label:14s} {'neu' if rings_by_plane else 'bisher':6s} ABGELEHNT "
                      f"{type(error).__name__}: {str(getattr(error, 'detail', error))[:150]}")
                continue
            out = result.outputs[0].mesh
            volumes[rings_by_plane] = out.volume
            codes = sorted({f.code for f in result.findings})
            print(f"  {label:14s} {'neu' if rings_by_plane else 'bisher':6s} {out.volume:12.3f} "
                  f"{closed(out, kind):8s} {time.perf_counter() - started:5.1f}s  Befunde {codes}")
        if len(volumes) == 2:
            print(f"  {label:14s} an den Mündungen: {volumes[False] - volumes[True]:.3f} mm³ weg")
