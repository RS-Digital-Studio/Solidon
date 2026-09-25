"""Review-Sonde: Laufzeit des Ringfüllers bei vielen Löchern (nur lesend).

G1  Icosphäre (Unterteilung 6) ohne 1 500 einzelne, nicht benachbarte Dreiecke (1 500 Dreiecksringe)
G2  dieselbe Kugel ohne 400 Eckfächer (Ringe zu 5–6 Ecken, nicht eben)
G3  Lochblech 12 x 12 Bohrungen, alle Bohrungswände fehlen (288 ebene Ringe zu je 48 Ecken)
G4  Icosphäre (Unterteilung 7) ohne 300 Flecken mit ~24–30 Randecken (Liepa-Größe)

Gemessen: `_fill_jobs` allein, `_fill_loops` (neu) gegen `fill_boundary_loops` aus HEAD.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import R, facts, head_repair  # noqa: E402

import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.units import EPS_GEOM, weld_tolerance  # noqa: E402

HEAD = head_repair()


def timed(label, function):
    start = time.perf_counter()
    value = function()
    print(f"  {label}: {time.perf_counter() - start:.2f} s")
    return value


def run(title: str, mesh: MeshData) -> None:
    print(title, "Dreiecke", len(mesh.raw.faces), "offen", R.open_edge_count(mesh))
    split, loops = R._hole_rings(mesh)
    print("  Ringe:", len(loops), "Längen:", sorted({len(loop) for loop in loops})[:12])
    points = np.asarray(split.raw.vertices, dtype=float)
    single = R._edge_table(split).rows(1)
    directed = np.asarray(split.raw.edges, dtype=np.int64)[single]
    owner = {
        (min(int(a), int(b)), max(int(a), int(b))): int(single[row]) // 3
        for row, (a, b) in enumerate(directed.tolist())
    }
    tri = np.asarray(split.raw.triangles, dtype=np.float64)
    centroids = tri.mean(axis=1)
    tolerance = max(10.0 * EPS_GEOM, weld_tolerance(float(split.bounds.diagonal)))
    jobs = timed("_fill_jobs", lambda: R._fill_jobs(points, loops, tolerance, owner, centroids))
    print("  Aufträge:", len(jobs), "Bänder:", sum(job.band is not None for job in jobs))
    filled = timed("_fill_loops (neu)", lambda: R._fill_loops(mesh))
    print("  neu:", filled.closed, "geschlossen", facts(filled.mesh))
    old = timed("fill_boundary_loops (HEAD)", lambda: HEAD.fill_boundary_loops(mesh))
    print("  HEAD:", old[1], "geschlossen", facts(old[0]))
    print()


# G1
sphere = trimesh.creation.icosphere(subdivisions=6, radius=50.0)
rng = np.random.default_rng(7)
chosen: list[int] = []
blocked = np.zeros(len(sphere.vertices), dtype=bool)
for face in rng.permutation(len(sphere.faces)).tolist():
    corners = sphere.faces[face]
    if blocked[corners].any():
        continue
    chosen.append(face)
    blocked[corners] = True
    if len(chosen) == 1500:
        break
keep = np.ones(len(sphere.faces), dtype=bool)
keep[chosen] = False
g1 = sphere.copy()
g1.update_faces(keep)
run("G1 1 500 Dreieckslöcher", MeshData.of(g1))

# G2
fans = []
used = np.zeros(len(sphere.vertices), dtype=bool)
neighbours = sphere.vertex_neighbors
for vertex in rng.permutation(len(sphere.vertices)).tolist():
    ring = [vertex, *neighbours[vertex]]
    if used[ring].any():
        continue
    second = {n for other in neighbours[vertex] for n in neighbours[other]}
    if used[list(second)].any():
        continue
    fans.append(vertex)
    used[list(second)] = True
    if len(fans) == 400:
        break
drop = np.isin(sphere.faces, fans).any(axis=1)
g2 = sphere.copy()
g2.update_faces(~drop)
run("G2 400 Eckfächer", MeshData.of(g2))

# G3 — Lochblech
import manifold3d  # noqa: E402

plate = manifold3d.Manifold.cube([130.0, 130.0, 8.0])
holes = []
centres = []
for i in range(12):
    for j in range(12):
        x, y = 10.0 + 10.0 * i, 10.0 + 10.0 * j
        centres.append((x, y))
        holes.append(
            manifold3d.Manifold.cylinder(12.0, 2.6, 2.6, 48).translate([x, y, -2.0])
        )
drilled = plate - manifold3d.Manifold.batch_boolean(holes, manifold3d.OpType.Add)
out = drilled.to_mesh()
body = trimesh.Trimesh(np.asarray(out.vert_properties)[:, :3], np.asarray(out.tri_verts), process=True)
centre_xy = body.triangles_center[:, :2]
distance = np.min(
    np.hypot(centre_xy[:, None, 0] - np.asarray(centres)[None, :, 0],
             centre_xy[:, None, 1] - np.asarray(centres)[None, :, 1]),
    axis=1,
)
wall = (np.abs(body.face_normals[:, 2]) < 0.5) & (distance < 3.0)
g3 = body.copy()
g3.update_faces(~wall)
g3.remove_unreferenced_vertices()
run("G3 Lochblech 12 x 12 ohne Bohrungswände", MeshData.of(g3))

# G4
big = trimesh.creation.icosphere(subdivisions=7, radius=80.0)
adjacency = big.face_neighborhood if hasattr(big, "face_neighborhood") else None
faces_of = [[] for _ in range(len(big.vertices))]
for index, face in enumerate(big.faces.tolist()):
    for corner in face:
        faces_of[corner].append(index)
patches = []
taken = np.zeros(len(big.vertices), dtype=bool)
for vertex in rng.permutation(len(big.vertices)).tolist():
    first = set(big.vertex_neighbors[vertex]) | {vertex}
    second = set(first)
    for other in first:
        second |= set(big.vertex_neighbors[other])
    third = set(second)
    for other in second:
        third |= set(big.vertex_neighbors[other])
    if taken[list(third)].any():
        continue
    taken[list(third)] = True
    patches.append(second)
    if len(patches) == 300:
        break
remove = np.zeros(len(big.faces), dtype=bool)
for patch in patches:
    inner = [corner for corner in patch]
    for corner in list(patch)[:7]:
        pass
    # alle Dreiecke, deren drei Ecken im Fleck liegen
remove = np.all(np.isin(big.faces, np.fromiter({c for p in patches for c in p}, dtype=np.int64)), axis=1)
g4 = big.copy()
g4.update_faces(~remove)
run("G4 300 Flecken", MeshData.of(g4))
