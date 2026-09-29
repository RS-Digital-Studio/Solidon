"""RM-279, Gegenprobe zu muendung.py: dieselbe Messung an einer geraden Kante.

Quader 40 x 30 x 20 ohne Bohrung, Verrunden der vier senkrechten Kanten, Netz
gegen exakt nahe der Kante bei x = 20, y = 15. Zeigt, was der Messweg selbst
an Abweichung liefert, und ob das Netz an geraden Kanten stimmt.
"""

import os
import sys

sys.path.insert(0, os.getcwd())
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

from app.core.brep import edit  # noqa: E402
from app.core.geom.edges import round_edges  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402

box = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
box.apply_translation((0.0, 0.0, 10.0))
mesh = MeshData(box)
solid = edit.box(40.0, 30.0, 20.0)
for radius in (0.5, 1.0, 2.0, 5.0):
    mesh_tri = round_edges(mesh, radius, "vertical").mesh.raw
    exact = edit.fillet(solid, radius, "vertical")
    exact_tri = exact.to_mesh(deflection=0.005).raw

    def near(points, grow=0.0):
        return (points[:, 0] > 20.0 - radius - 0.5 - grow) & (points[:, 1] > 15.0 - radius - 0.5 - grow)

    def near_part(tri, grow):
        part = tri.submesh([np.flatnonzero(near(tri.triangles_center, grow))], append=True)
        return trimesh.util.concatenate(part) if isinstance(part, list) else part

    def cloud(tri):
        return trimesh.sample.sample_surface(near_part(tri, 1.0), 1500000, seed=2)[0]

    a = trimesh.sample.sample_surface(near_part(mesh_tri, 0.0), 40000, seed=1)[0]
    a = a[near(a)]
    b = trimesh.sample.sample_surface(near_part(exact_tri, 0.0), 40000, seed=1)[0]
    b = b[near(b)]
    d = np.r_[cKDTree(cloud(exact_tri)).query(a)[0], cKDTree(cloud(mesh_tri)).query(b)[0]]
    print(f"R {radius}: Volumen Netz {mesh_tri.volume:.3f} exakt {exact.volume:.3f} | "
          f"Netz↔exakt nahe Kante max {d.max():.3f} mm, 99 % {np.percentile(d, 99):.3f} mm")
