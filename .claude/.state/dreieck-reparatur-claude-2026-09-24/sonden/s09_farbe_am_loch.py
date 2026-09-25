"""Sonde 9: Welche Füllflächen bekommen am zweifarbigen Loch den falschen Slot, und warum?

Je Fülldreieck: Mitte, gewählter Slot, Slots der Ausgangsflächen an seinen
eigenen Randkanten. „Falsch" heißt hier: Das Dreieck hat mindestens eine
eigene Kante am alten Rand, und keiner dieser Randnachbarn trägt den
gewählten Slot.
"""

from __future__ import annotations

import numpy as np
import trimesh

from common import R, MeshData


def two_colour_hole(subdivisions: int = 3, half: float = 4.0):
    body = trimesh.creation.box(extents=(20, 20, 20))
    for _ in range(subdivisions):
        body = body.subdivide()
    centres = body.triangles_center
    hole = (centres[:, 2] > 9.99) & (np.abs(centres[:, 0]) < half) & (np.abs(centres[:, 1]) < half)
    body = trimesh.Trimesh(vertices=body.vertices.copy(), faces=body.faces[~hole].copy(), process=False)
    slots = np.where(body.triangles_center[:, 0] < 0.0, 1, 2)
    return MeshData.of(body, slots=tuple(int(s) for s in slots))


source = two_colour_hole()
n = source.triangle_count
edges = {}
for index, face in enumerate(np.asarray(source.raw.faces)):
    for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
        edges.setdefault((min(a, b), max(a, b)), []).append(index)
boundary = {edge: owners[0] for edge, owners in edges.items() if len(owners) == 1}
print("Randkanten:", len(boundary), "Ringe:", len(R.boundary_loops(source)))
mesh, rings = R._hole_rings(source)
print("nach _hole_rings:", len(rings), "Ringe, Längen", [len(r) for r in rings],
      "Ecken vorher/nachher", source.vertex_count, mesh.vertex_count)

closed, filled, wide = R.fill_boundary_loops(source)
faces = np.asarray(closed.raw.faces)
points = np.asarray(closed.raw.vertices)
src_points = np.asarray(source.raw.vertices)
# Randkanten des Ausgangs nach Ort (die Füllung kann Ecken neu nummeriert haben)
by_place = {}
for (a, b), owner in boundary.items():
    key = tuple(sorted((tuple(np.round(src_points[a], 6)), tuple(np.round(src_points[b], 6)))))
    by_place[key] = source.slots[owner]
wrong = 0
for index in range(n, len(faces)):
    face = faces[index]
    rim = []
    for a, b in ((face[0], face[1]), (face[1], face[2]), (face[2], face[0])):
        key = tuple(sorted((tuple(np.round(points[a], 6)), tuple(np.round(points[b], 6)))))
        if key in by_place:
            rim.append(by_place[key])
    chosen = closed.slots[index]
    bad = bool(rim) and chosen not in rim
    wrong += bad
    centre = points[face].mean(axis=0)
    print(f"  Fülldreieck {index}: Mitte x={centre[0]:+6.2f} y={centre[1]:+6.2f} Slot={chosen} "
          f"Randnachbarn={rim} {'FALSCH' if bad else ''}")
print(f"falsch (gewählter Slot nicht unter den eigenen Randnachbarn): {wrong} von {len(faces) - n}")
