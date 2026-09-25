"""Sonde: erzeugt künstlich beschädigte STL-Dateien für die Befundsonde."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent / "netze"
HERE.mkdir(exist_ok=True)


def save(name: str, mesh: trimesh.Trimesh) -> None:
    mesh.export(HERE / f"{name}.stl")


def cube() -> trimesh.Trimesh:
    return trimesh.creation.box((20.0, 20.0, 20.0))


# 1 — gedrehte Außenseiten: zwei Dreiecke umgedreht
flipped = cube()
faces = np.array(flipped.faces)
faces[[0, 5]] = faces[[0, 5]][:, ::-1]
save("gedrehte_flaechen", trimesh.Trimesh(flipped.vertices, faces, process=False))

# 2 — ganz umgestülpt
inside_out = cube()
save("umgestuelpt", trimesh.Trimesh(inside_out.vertices, inside_out.faces[:, ::-1], process=False))

# 3 — Flosse: ein drittes Dreieck an einer Kante (Verzweigung und offene Ränder)
fin = cube()
edge = fin.edges_unique[0]
a, b = fin.vertices[edge[0]], fin.vertices[edge[1]]
tip = (a + b) / 2 + np.array([15.0, 15.0, 0.0])
verts = np.vstack([fin.vertices, tip])
fin_faces = np.vstack([fin.faces, [edge[0], edge[1], len(fin.vertices)]])
save("flosse", trimesh.Trimesh(verts, fin_faces, process=False))

# 4 — offene Fläche: ein Quadrat aus zwei Dreiecken
sheet = trimesh.Trimesh(
    [[0, 0, 0], [30, 0, 0], [30, 30, 0], [0, 30, 0]], [[0, 1, 2], [0, 2, 3]], process=False
)
save("offene_flaeche", sheet)

# 5 — Rohr ohne Deckel
tube = trimesh.creation.cylinder(radius=10.0, height=30.0, sections=48)
keep = np.abs(tube.face_normals[:, 2]) < 0.5
save("rohr_ohne_deckel", trimesh.Trimesh(tube.vertices, tube.faces[keep], process=True))

# 6 — Kugel mit großer Kappe entfernt (große Öffnung, nicht eben)
sphere = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
keep = sphere.triangles_center[:, 2] < 12.0
save("kugel_ohne_kappe", trimesh.Trimesh(sphere.vertices, sphere.faces[keep], process=True))

# 7 — zwei ineinandergeschobene Würfel (Durchdringung)
first = cube()
second = cube()
second.apply_translation((8.0, 8.0, 8.0))
save("durchdringung", trimesh.util.concatenate([first, second]))

# 8 — Würfel mit kleinem Loch und zusätzlichem Krümel
holed = trimesh.creation.box((20.0, 20.0, 20.0))
holed = holed.subdivide().subdivide()
keep = np.ones(len(holed.faces), dtype=bool)
keep[:2] = False
crumb = trimesh.creation.box((0.2, 0.2, 0.2))
crumb.apply_translation((30.0, 0.0, 0.0))
save(
    "loch_und_kruemel",
    trimesh.util.concatenate([trimesh.Trimesh(holed.vertices, holed.faces[keep]), crumb]),
)

# 9 — T-Stoß: eine Seite geteilt, die Nachbarseite nicht
box = trimesh.creation.box((20.0, 20.0, 20.0))
tri = box.faces[0]
p0, p1, p2 = box.vertices[tri]
mid = (p0 + p1) / 2
verts = np.vstack([box.vertices, mid])
m = len(box.vertices)
t_faces = np.vstack([box.faces[1:], [tri[0], m, tri[2]], [m, tri[1], tri[2]]])
save("t_stoss", trimesh.Trimesh(verts, t_faces, process=False))

print("\n".join(sorted(path.name for path in HERE.glob("*.stl"))))
