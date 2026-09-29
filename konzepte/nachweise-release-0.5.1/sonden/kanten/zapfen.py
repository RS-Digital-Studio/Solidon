"""RM-279 (i) Gegenprobe: Rand eines Zapfens (Werkzeug liegt innen, zur Achse hin).

Zylinder r 10, h 20 (64 Seiten), obere Kante verrundet/gefast; Pappus mit dem
Schwerpunkt innen (r − 0,2234·R bzw. r − d/3) gegen Netz und exakt. Dazu ein
Quader mit gerundeten senkrechten Ecken (R 5), dessen Deckkante verrundet
wird: ein geschlossener Zug aus Strecken und Bögen.
"""

import math
import os
import sys

sys.path.insert(0, os.getcwd())
import trimesh  # noqa: E402

from app.core.brep import edit  # noqa: E402
from app.core.geom.edges import bevel_edges, round_edges  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402

R_BOSS = 10.0
C = (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi)
mesh = MeshData(trimesh.creation.cylinder(radius=R_BOSS, height=20.0, sections=64))
solid = edit.cylinder(2 * R_BOSS, 20.0)
for size, rounded in ((1.0, True), (2.0, True), (5.0, True), (2.0, False)):
    if rounded:
        formula = 2 * math.pi * (R_BOSS - C * size) * size * size * (1 - math.pi / 4)
    else:
        formula = 2 * math.pi * (R_BOSS - size / 3) * size * size / 2
    work = round_edges if rounded else bevel_edges
    out = work(mesh, size, "top").mesh
    exact = (edit.fillet if rounded else edit.chamfer)(solid, size, "top")
    print(
        f"Zapfen {'R' if rounded else 'Fase'} {size}: Netz {mesh.volume - out.volume:8.3f} "
        f"exakt {solid.volume - exact.volume:8.3f} Formel {formula:8.3f} dicht {out.is_watertight}"
        f" Teile {out.component_count}"
    )

box = edit.fillet(edit.box(40.0, 30.0, 20.0), 5.0, "vertical")
box_mesh = box.to_mesh()
for size in (1.0, 2.0, 4.0):
    out = round_edges(box_mesh, size, "top").mesh
    exact = edit.fillet(box, size, "top")
    print(
        f"Rundquader oben R {size}: Netz {box_mesh.volume - out.volume:8.3f} "
        f"exakt {box.volume - exact.volume:8.3f} dicht {out.is_watertight} Teile {out.component_count}"
    )
