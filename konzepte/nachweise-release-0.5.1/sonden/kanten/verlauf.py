"""RM-279 (i), Rest: Radiusverlauf an einem Bohrungsrand — Netz gegen exakt.

Quader 40 x 30 x 20 mit Querbohrung Ø 6, eine Mündung, Verlauf 2 → 4 → 2
(Stelle 50 %). Aufruf aus der Wurzel eines Arbeitsbaums.
"""

import math
import os
import sys

sys.path.insert(0, os.getcwd())
import trimesh  # noqa: E402

from app.core.brep import edit  # noqa: E402
from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom.edges import RadiusLaw, edge_key, edges_of, round_edges  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402

box = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
box.apply_translation((0.0, 0.0, 10.0))
bore = trimesh.creation.cylinder(radius=3.0, height=90.0, sections=48)
bore.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1, 0, 0)))
bore.apply_translation((0.0, 0.0, 10.0))
mesh = boolean("difference", [MeshData(box), MeshData(bore)]).mesh
solid = edit.bore(edit.box(40.0, 30.0, 20.0), position=(0.0, -15.0, 10.0), axis="y", diameter=6.0)
for radii in ((2.0, 2.0), (2.0, 4.0, 2.0), (3.0, 5.0, 3.0)):
    positions = (0.0, 0.5, 1.0) if len(radii) == 3 else (0.0, 1.0)
    law = RadiusLaw(positions, radii)
    ring = [e for e in edges_of(mesh) if math.dist(e.direction, (0, 0, 0)) < 1e-6 and e.middle[1] < 0]
    exact_ring = [
        e for e in edit.edges_of(solid) if math.dist(e.direction, (0, 0, 0)) < 1e-6 and e.middle[1] < 0
    ]
    netz = mesh.volume - round_edges(mesh, max(radii), "named", [edge_key(ring[0])], law=law).mesh.volume
    exakt = solid.volume - edit.fillet(solid, max(radii), "named", [edit.edge_key(exact_ring[0])], law=law).volume
    print(f"Verlauf {radii}: Netz {netz:8.3f}  exakt {exakt:8.3f}  Netz/exakt {netz / exakt:6.3f}")
