"""RM-279: Volumen nach Verrunden R 1 an jeder Gruppe, Quader 40 x 30 x 20 mit Querbohrung Ø 6.

Aufruf aus der Wurzel eines Arbeitsbaums: python verrunden.py. Beide Kerne.
"""

import math
import os
import sys
from pathlib import Path

TREE = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
sys.path.insert(0, TREE)
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve()), app.__file__
import trimesh  # noqa: E402

from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom.edges import round_edges  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402

box = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
box.apply_translation((0.0, 0.0, 10.0))
bore = trimesh.creation.cylinder(radius=3.0, height=60.0, sections=48)
bore.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1, 0, 0)))
bore.apply_translation((0.0, 0.0, 10.0))
outcome = boolean("difference", [MeshData(box), MeshData(bore)])
body = outcome.mesh if hasattr(outcome, "mesh") else outcome
body = body if isinstance(body, MeshData) else MeshData(body)
print(f"Netz ohne: {body.volume:.4f}")
for choice in ("vertical", "horizontal", "top", "bottom"):
    rounded = round_edges(body, 1.0, choice)
    print(f"Netz {choice:10s} {rounded.mesh.volume:.4f}")

from app.core.brep import edit, kernel  # noqa: E402

if kernel.available():
    solid = edit.bore(edit.box(40.0, 30.0, 20.0), position=(0.0, -15.0, 10.0), axis="y", diameter=6.0)
    print(f"exakt ohne: {solid.volume:.4f}")
    for choice in ("vertical", "horizontal", "top", "bottom"):
        print(f"exakt {choice:10s} {edit.fillet(solid, 1.0, choice).volume:.4f}")
