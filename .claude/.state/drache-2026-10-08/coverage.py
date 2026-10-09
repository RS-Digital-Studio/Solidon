"""Welche stützbedürftigen Flächen des Drachen liegen in der Stützsperre?

Stützbedürftig wie Orca mit ``support_threshold_angle`` = 30: Fläche, deren
Neigung zur Waagerechten unter 30° liegt und nach unten zeigt. Nur Flächen
über 1 mm Höhe (darunter stützt niemand).
"""

import sys

import numpy as np
import trimesh

dragon = trimesh.load(sys.argv[1], process=False)
blocker = trimesh.load(sys.argv[2], process=False)
threshold = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0

normals = dragon.face_normals
areas = dragon.area_faces
centres = dragon.triangles_center
limit = -np.cos(np.radians(threshold))
down = (normals[:, 2] < limit) & (centres[:, 2] > 1.0)
print(f"stützbedürftig: {down.sum()} Dreiecke, {areas[down].sum():.0f} mm²")

probe = centres[down] - np.array([0.0, 0.0, 0.3])
import shapely

levels = np.round(probe[:, 2] / 0.2) * 0.2
inside = np.zeros(len(probe), dtype=bool)
unique = np.unique(levels)
origin = np.zeros(3)
sections = blocker.section_multiplane(origin, [0, 0, 1], list(unique))
for z, section in zip(unique, sections, strict=True):
    if section is None:
        continue
    pick = levels == z
    count = np.zeros(pick.sum(), dtype=int)
    for loop in section.discrete:
        if len(loop) < 4:
            continue
        ring = shapely.Polygon(loop[:, :2]).buffer(0)
        count += shapely.contains_xy(ring, probe[pick, 0], probe[pick, 1])
    inside[pick] = count % 2 == 1
blocked_area = areas[down][inside].sum()
print(
    f"davon in der Sperre: {inside.sum()} Dreiecke, {blocked_area:.0f} mm² = {blocked_area / areas[down].sum():.1%}"
)

# Nach Höhenband, damit man sieht, wo
zs = centres[down][:, 2]
for low in range(0, 140, 10):
    band = (zs >= low) & (zs < low + 10)
    if not band.any():
        continue
    total = areas[down][band].sum()
    blocked = areas[down][band & inside].sum()
    print(
        f"  z {low:3d}-{low + 10:3d}: {total:7.0f} mm², gesperrt {blocked:7.0f} mm² ({blocked / total:.0%})"
    )

np.save("down_mask.npy", down)
np.save("down_inside.npy", inside)
