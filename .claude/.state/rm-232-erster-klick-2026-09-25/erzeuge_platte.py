"""Die dichte Platte der Sonden: ``plate_holes.stl`` viermal unterteilt (203 776 Dreiecke)."""

from pathlib import Path

import trimesh

here = Path(__file__).parent
mesh = trimesh.load_mesh(here.parents[2] / "tests" / "data" / "meshes" / "plate_holes.stl")
for _round in range(4):
    mesh = mesh.subdivide()
mesh.export(here / "plate_dense.stl")
print(len(mesh.faces), "Dreiecke")
