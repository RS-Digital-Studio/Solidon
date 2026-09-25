"""Eine lange Randkante mit mehreren aufsitzenden Punkten: wird sie ganz vernäht?"""

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.geom.repair import open_edge_count, repair, stitch_t_junctions

# Zwei Quader-Hälften: Die Oberseite eines 10x10x10-Würfels ist links grob
# (ein Dreieckspaar), das Nachbarband ist an der Stoßkante fein geteilt.
box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
# Die Oberseite (z=5) ersetzen: linke Hälfte als zwei Dreiecke, rechte Hälfte
# mit n Punkten auf der Stoßkante x=0.
verts = [list(v) for v in box.vertices]
faces = [list(f) for f in box.faces if not np.allclose(box.vertices[f][:, 2], 5.0)]
top = {tuple(np.round(v, 6)): i for i, v in enumerate(box.vertices) if abs(v[2] - 5.0) < 1e-9}
a = top[(-5.0, -5.0, 5.0)]
b = top[(5.0, -5.0, 5.0)]
c = top[(5.0, 5.0, 5.0)]
d = top[(-5.0, 5.0, 5.0)]
def add(p):
    verts.append(list(p))
    return len(verts) - 1
m0 = add((0.0, -5.0, 5.0))
m1 = add((0.0, 5.0, 5.0))
# links grob: a, m0, m1, d
faces += [[a, m0, m1], [a, m1, d]]
# rechts fein: Punkte auf x=0 bei y=-2.5, 0, 2.5
inner = [add((0.0, y, 5.0)) for y in (-2.5, 0.0, 2.5)]
chain = [m0, *inner, m1]
for s, e in zip(chain, chain[1:]):
    faces.append([s, b, e] if False else [s, b, e])
faces.append([m1, b, c])
mesh = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(faces), process=False)
trimesh.repair.fix_winding(mesh)
data = MeshData.of(mesh)
print("offen vorher:", open_edge_count(data), "dicht:", data.is_watertight)
stitched, count = stitch_t_junctions(data)
print("vernäht (ein Durchgang):", count, "offen danach:", open_edge_count(stitched), "dicht:", stitched.is_watertight)
result = repair(data)
print("repair(): dicht:", result.mesh.is_watertight, "offen:", open_edge_count(result.mesh), "Volumen:", round(result.mesh.volume, 4))
for finding in result.findings:
    print("  ", finding.code, finding.severity, str(finding.message))
areas = result.mesh.raw.area_faces
print("Dreiecke:", len(areas), "Fläche ~0:", int((areas < 1e-9).sum()))
