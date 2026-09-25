"""Sonde 13c: Warum bleibt der Kugelrand (b4) offen? Ohren/Fächer, Faltprobe, Kantenbelegung."""
import numpy as np
import trimesh
from common import R, MeshData, facts
from app.core import units

sphere = trimesh.creation.icosphere(subdivisions=4, radius=10.0)
cs = sphere.triangles_center
mesh = MeshData.of(trimesh.Trimesh(vertices=sphere.vertices.copy(), faces=sphere.faces[~(cs[:, 2] > -2.0)].copy(), process=False))
mesh, _ = R.merge_vertices(mesh)
split, rings = R._hole_rings(mesh)
points = np.asarray(split.raw.vertices, dtype=float)
table = R._edge_table(split)
existing = {tuple(e): int(c) for e, c in zip(table.unique.tolist(), table.counts.tolist())}
for ring in rings:
    corners = points[ring]
    centre = np.asarray(units.exact_centre(corners.tolist()), dtype=np.float64)
    normal = R._ring_normal(corners, centre)
    reach = np.vstack([points, centre[None, :]])
    ears = R._loop_triangles(points, ring)
    fan = R._loop_fan(ring, len(points))
    for label, attempt in (("Ohren", ears), ("Fächer", fan)):
        if not len(attempt):
            print(label, "leer"); continue
        uses_middle = int(attempt.max()) >= len(points)
        area = np.cross(reach[attempt][:, 1] - reach[attempt][:, 0], reach[attempt][:, 2] - reach[attempt][:, 0])
        facing = area @ normal
        clash = sum(1 for p in attempt.tolist() for i in range(3)
                    if existing.get((min(p[i], p[(i+1)%3]), max(p[i], p[(i+1)%3])), 0) >= 2)
        print(f"Ring {len(ring)} Ecken, z von {corners[:,2].min():.2f} bis {corners[:,2].max():.2f}; {label}: {len(attempt)} Dreiecke,"
              f" Mitte={uses_middle}, rückwärts (facing<=0): {int((facing <= 1e-12).sum())}, min facing {facing.min():.4f},"
              f" Kanten schon zweifach belegt: {clash}, faltet={R._folds(reach[attempt], normal)}")
