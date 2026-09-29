"""RM-279 (ii): Gruppe „senkrecht“ bzw. „alle“ — Absage oder Auslassen mit Befund?

Aufruf aus der Wurzel eines Arbeitsbaums: python gruppe.py. Beide Kerne; je
Fall: abgelehnt (mit Grenze) oder gelungen, wie viele Kanten bearbeitet, wie
viele ausgelassen, Volumen, dicht, Befunde.
"""

import math
import time
import os
import sys
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
from app.core.geom.edges import choose, edges_of  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene.cancel import NeverCancelled  # noqa: E402
from app.core.types import OpContext, Scene, SceneObject  # noqa: E402

load_operations()
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")
FILES = Path(r"F:\3D Dateien")


def run(entry, op, **params):
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


def bodies():
    box = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    box.apply_translation((0.0, 0.0, 10.0))
    bore = trimesh.creation.cylinder(radius=3.0, height=90.0, sections=48)
    bore.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1, 0, 0)))
    bore.apply_translation((0.0, 0.0, 10.0))
    yield "Quader mit Querbohrung", "Netz", boolean("difference", [MeshData(box), MeshData(bore)]).mesh, "vertical"
    yield "Quader mit Querbohrung", "exakt", edit.bore(
        edit.box(40.0, 30.0, 20.0), position=(0.0, -15.0, 10.0), axis="y", diameter=6.0
    ), "vertical"
    outer = edit.box(40.0, 30.0, 20.0)
    inner = edit.moved(edit.box(34.0, 24.0, 20.0), (3.0, 3.0, 3.0))
    hollow = edit.boolean("difference", [outer, inner])
    yield "Hohlkasten 3 mm Wand", "exakt", hollow, "all"
    yield "Hohlkasten 3 mm Wand", "Netz", hollow.to_mesh(), "all"
    for name in ("pegboard-goot-ceramic-screwdrivers-v3", "pegboard-pb3041-v4", "pegboard-gs-100-v2"):
        solid = step.read((FILES / f"{name}.step").read_bytes())
        yield name, "exakt", solid, "vertical"
        yield name, "Netz", solid.to_mesh(), "vertical"


CASES = [("fillet_edges", "radius", r) for r in (0.5, 1.0, 2.0, 5.0)] + [
    ("chamfer_edges", "distance", 1.0)
]
for name, kernel, body, group in bodies():
    kind = "brep" if kernel == "exakt" else "mesh"
    entries = edit.edges_of(body) if kind == "brep" else edges_of(body)
    print(f"\n== {name} ({kernel}), „{group}“: {len(choose(entries, group))} Kanten, Volumen {body.volume:.3f}")
    entry = SceneObject(id="obj_1", name=name, mesh=body, kind=kind)
    for op, field, size in CASES:
        label = f"{'Verrunden R' if op == 'fillet_edges' else 'Fase '}{size}"
        started = time.perf_counter()
        try:
            result = run(entry, op, edges=group, **{field: size})
        except AppError as error:
            largest = getattr(error, "values", {}).get("largest_mm")
            print(f"  {label:14s} ABGELEHNT, Grenze {largest}")
            continue
        out = result.outputs[0].mesh
        found = {f.code: f for f in result.findings}
        parts = []
        for code in ("edges.too_narrow", "edges.not_built", "edges.skipped"):
            item = found.get(code)
            if item is not None:
                parts.append(
                    f"{code.split('.')[1]}: bearbeitet {item.values.get('worked')}, ausgelassen "
                    f"{item.values.get('skipped')}"
                    + (f", passt unter {item.values['largest_mm']}" if "largest_mm" in item.values else "")
                    + f", Stelle {item.location is not None}"
                )
        detail = "; ".join(parts) if parts else "alle bearbeitet"
        print(
            f"  {label:14s} gelungen ({time.perf_counter() - started:.1f} s): {detail}; Volumen {out.volume:.3f}, "
            f"dicht {out.is_watertight}, Befunde {sorted(found)}"
        )
