"""RM-279: Welche Kanten wählt jede Gruppe am Quader 40 x 30 x 20 mit Querbohrung Ø 6?

Aufruf: python auswahl.py <baum>. Beide Kerne; je Gruppe Anzahl, davon Ringe,
und die Lage der Ringe nach der Beschriftung (edge_lie_of).
"""

import math
import sys
from pathlib import Path

TREE = sys.argv[1] if len(sys.argv) > 1 else __import__("os").getcwd()
sys.path.insert(0, TREE)
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve()), app.__file__
import trimesh  # noqa: E402

from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom.edges import choose, edge_lie_of, edges_of  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402


def ring(entry):
    return math.dist(entry.direction, (0.0, 0.0, 0.0)) < 1e-6


def report(name, edges):
    rings = [e for e in edges if ring(e)]
    print(f"{name}: Kanten {len(edges)}, Ringe {len(rings)}, Lage der Ringe {[edge_lie_of(e) for e in rings]}")
    for choice in ("vertical", "horizontal", "top", "bottom"):
        chosen = choose(edges, choice)
        print(f"  {choice:10s} {len(chosen):3d}  davon Ringe {sum(1 for e in chosen if ring(e))}")


box = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
box.apply_translation((0.0, 0.0, 10.0))
bore = trimesh.creation.cylinder(radius=3.0, height=60.0, sections=48)
bore.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1, 0, 0)))
bore.apply_translation((0.0, 0.0, 10.0))
outcome = boolean("difference", [MeshData(box), MeshData(bore)])
body = outcome.mesh if hasattr(outcome, "mesh") else outcome
report("Netz", edges_of(body if isinstance(body, MeshData) else MeshData(body)))

from app.core.brep import edit, kernel  # noqa: E402

if kernel.available():
    solid = edit.bore(edit.box(40.0, 30.0, 20.0), position=(0.0, -15.0, 10.0), axis="y", diameter=6.0)
    report("exakt", edit.edges_of(solid))
else:
    print("exakt: OpenCASCADE fehlt")
