"""RM-279 am echten Modell: Schraubendreherhalter mit Querbohrungen Ø 4,5 längs Y.

Aufruf aus der Wurzel eines Arbeitsbaums: python echt.py. Exakt aus der STEP,
als Netz aus der Tessellierung derselben Datei (dasselbe Teil, beide Kerne).
Je Gruppe: Anzahl, davon Ringe, und ob jede gewählte Kante so heißt wie die
Gruppe (Beschriftung ``edge_lie_of``).
"""

import math
import os
import sys
from pathlib import Path

TREE = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
sys.path.insert(0, TREE)
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve()), app.__file__

from app.core.brep import edit, step  # noqa: E402
from app.core.geom.edges import choose, edge_lie_of, edges_of  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402

MODEL = Path(r"F:\3D Dateien\pegboard-goot-ceramic-screwdrivers-v3.step")
WORD = {"vertical": "upright", "horizontal": "flat"}


def ring(entry):
    return math.dist(entry.direction, (0.0, 0.0, 0.0)) < 1e-6


def report(name, edges):
    rings = [e for e in edges if ring(e)]
    lies = [edge_lie_of(e) for e in rings]
    print(f"{name}: Kanten {len(edges)}, Ringe {len(rings)}, "
          f"davon stehend {lies.count('upright')}, liegend {lies.count('flat')}")
    for choice in ("vertical", "horizontal", "top", "bottom"):
        chosen = choose(edges, choice)
        wrong = [e for e in chosen if choice in WORD and edge_lie_of(e) != WORD[choice]]
        print(f"  {choice:10s} {len(chosen):4d}  davon Ringe {sum(1 for e in chosen if ring(e)):3d}"
              f"  anders beschriftet {len(wrong)}")


solid = step.read(MODEL.read_bytes())
report("exakt", edit.edges_of(solid))
mesh = solid.to_mesh() if hasattr(solid, "to_mesh") else None
if mesh is None:
    from app.core.brep.kernel import tessellate

    mesh = tessellate(solid)
report("Netz", edges_of(mesh if isinstance(mesh, MeshData) else MeshData(mesh)))

from app.ui.labels import edge_label  # noqa: E402

exact_rings = [e for e in edit.edges_of(solid) if ring(e)]
print("Beschriftung einer Mündung (exakt):", edge_label(exact_rings[0]))
