"""Sonde 13: Gegenprobe der zwei neuen Mechanismen am Stand 18:14.

a) STITCH_ROUNDS: mehrere Punkte auf einer langen Kante (T-Stöße) — vernäht
   alles, keine Nullflächen?
b) _folds: Löcher, die nicht in einer Ebene liegen, aber harmlos zu füllen sind
   (über eine Körperkante, über eine Ecke, auf einer Kugel, auf einem Zylinder
   halb herum) — bleiben sie offen?
"""

from __future__ import annotations

import numpy as np
import trimesh

from common import R, MeshData, codes, facts

EPS = 1e-9


def remove(body: trimesh.Trimesh, mask: np.ndarray) -> MeshData:
    return MeshData.of(trimesh.Trimesh(vertices=body.vertices.copy(), faces=body.faces[~mask].copy(), process=False))


def zero_area(mesh: MeshData) -> int:
    return int(np.count_nonzero(mesh.raw.area_faces <= EPS))


# a) T-Stöße: ein Quader, dessen Oberseite rechts fein und links grob trianguliert ist
fine = trimesh.creation.box(extents=(20, 20, 20)).subdivide().subdivide()
centres = fine.triangles_center
left_top = (centres[:, 2] > 9.99) & (centres[:, 0] < 0)
coarse_vertices = np.array([[-10, -10, 10], [0, -10, 10], [0, 10, 10], [-10, 10, 10]], dtype=float)
body = trimesh.Trimesh(vertices=fine.vertices.copy(), faces=fine.faces[~left_top].copy(), process=False)
start = len(body.vertices)
vertices = np.vstack([body.vertices, coarse_vertices])
faces = np.vstack([body.faces, [[start, start + 1, start + 2], [start, start + 2, start + 3]]])
tee = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))
welded, _ = R.merge_vertices(tee)
print("a) T-Stöße vorher:", facts(welded))
stitched, seams = R.stitch_t_junctions(welded)
print("   vernäht:", seams, facts(stitched), "Nullflächen:", zero_area(stitched))
rep = R.repair(welded)
print("   repair:", codes(rep.findings), facts(rep.mesh), "Nullflächen:", zero_area(rep.mesh))

# b1) Loch über eine Körperkante (zwei Nachbarflächen, rechtwinklig)
box = trimesh.creation.box(extents=(20, 20, 20)).subdivide().subdivide()
c = box.triangles_center
edge_hole = (c[:, 0] > 5) & (c[:, 2] > 5) & (np.abs(c[:, 1]) < 5)
for label, mask, source in (
    ("b1 über eine Kante", edge_hole, box),
    ("b2 über eine Ecke", (c[:, 0] > 5) & (c[:, 1] > 5) & (c[:, 2] > 5), box),
):
    mesh = remove(source, mask)
    rep = R.repair(mesh, inspect_intersections=True)
    print(label, "vorher:", facts(mesh), "\n   repair:", codes(rep.findings), facts(rep.mesh))

sphere = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
cs = sphere.triangles_center
for label, limit in (("b3 Kugelkappe 60°", 5.0), ("b4 Kugel über den Äquator", -2.0)):
    mesh = remove(sphere, cs[:, 2] > limit)
    rep = R.repair(mesh, inspect_intersections=True)
    print(label, "vorher:", facts(mesh), "\n   repair:", codes(rep.findings), facts(rep.mesh))

cyl = trimesh.creation.cylinder(radius=10.0, height=30.0, sections=64).subdivide().subdivide()
cc = cyl.triangles_center
side = np.abs(np.hypot(cc[:, 0], cc[:, 1]) - 10.0) < 1.0
window = side & (cc[:, 0] > -5.0) & (np.abs(cc[:, 2]) < 8.0)   # Fenster über gut 240° des Umfangs
mesh = remove(cyl, window)
rep = R.repair(mesh, inspect_intersections=True)
print("b5 Zylinderfenster ~240°", "vorher:", facts(mesh), "\n   repair:", codes(rep.findings), facts(rep.mesh))
