"""Sonde 13d: Ohrenschneiden, das belegte Kanten beim Wählen der Ohren meidet (nur Sonde, kein App-Code)."""
import math
import numpy as np
import trimesh
from common import R, MeshData, facts
from app.core import units
from app.core.geom.transform import along
from app.core.units import EPS_GEOM

def ears_avoiding(points, loop, forbidden):
    ring = points[loop]
    centre = np.asarray(units.exact_centre(ring.tolist()), dtype=np.float64)
    normal = R._ring_normal(ring, centre)
    local = ring - centre
    bu = np.cross(normal, (1.0, 0.0, 0.0) if abs(normal[0]) < 0.9 else (0.0, 1.0, 0.0)); bu /= math.hypot(*bu)
    bv = np.cross(normal, bu)
    flat = np.column_stack((along(local, bu), along(local, bv)))
    ahead = np.roll(flat, -1, axis=0)
    signed = float((flat[:, 0] * ahead[:, 1] - flat[:, 1] * ahead[:, 0]).sum()) / 2.0
    rest = list(range(len(loop))) if signed >= 0 else list(reversed(range(len(loop))))
    ears, stuck = [], 0
    def inside(a, b, c):
        corners = flat[[a, b, c]]; edges = np.roll(corners, -1, axis=0) - corners
        others = [i for i in rest if i not in (a, b, c)]
        if not others: return False
        off = flat[others][:, None, :] - corners[None, :, :]
        side = edges[None, :, 0] * off[:, :, 1] - edges[None, :, 1] * off[:, :, 0]
        return bool(np.any(np.all(side >= -EPS_GEOM, axis=1)))
    while len(rest) > 3 and stuck <= len(rest):
        a, b, c = rest[0], rest[1], rest[2]
        e1 = flat[b] - flat[a]; e2 = flat[c] - flat[b]
        turn = float(e1[0] * e2[1] - e1[1] * e2[0])
        diag = (min(loop[a], loop[c]), max(loop[a], loop[c]))
        if turn > EPS_GEOM and diag not in forbidden and not inside(a, b, c):
            ears.append([loop[a], loop[b], loop[c]]); rest.pop(1); stuck = 0
        else:
            rest.append(rest.pop(0)); stuck += 1
    if len(rest) == 3:
        ears.append([loop[rest[0]], loop[rest[1]], loop[rest[2]]]); return np.asarray(ears)
    return None

sphere = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
cs = sphere.triangles_center
mesh = MeshData.of(trimesh.Trimesh(vertices=sphere.vertices.copy(), faces=sphere.faces[~(cs[:, 2] > -2.0)].copy(), process=False))
mesh, _ = R.merge_vertices(mesh)
split, rings = R._hole_rings(mesh)
points = np.asarray(split.raw.vertices, dtype=float)
table = R._edge_table(split)
forbidden = {tuple(e) for e, c in zip(table.unique.tolist(), table.counts.tolist()) if c >= 2}
ears = ears_avoiding(points, rings[0], forbidden)
print("Ohren mit Sperre:", None if ears is None else len(ears))
if ears is not None:
    faces = np.vstack([split.raw.faces, ears])
    closed = MeshData.of(trimesh.Trimesh(vertices=points, faces=faces, process=False))
    fixed, _ = R.unify_normals(closed)
    print("Ergebnis:", facts(fixed, intersections=True))
