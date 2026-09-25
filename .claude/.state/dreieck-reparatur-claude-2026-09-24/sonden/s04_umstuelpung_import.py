"""Sonde 4: Wie leicht kommt ein offener Körper beim Import umgestülpt heraus?

Fall: ein sonst richtig orientierter Körper mit einem Loch und EINEM falsch
herum gewickelten Dreieck. trimesh.repair.fix_winding richtet am offenen Netz
alles nach einem Bezugsdreieck aus; ist das Bezugsdreieck das falsche, dreht es
den ganzen Rest um. Beim Import läuft fix_inversion nur, wenn das Netz vorher
dicht war, und die anschließende Lochfüllung läuft mit normals=False.
"""

from __future__ import annotations

import numpy as np
import trimesh

from common import R, MeshData, codes, facts

from app.core.ingest.loader import normalise


def case(flip_index: int, hole: int, subdivisions: int = 2) -> None:
    body = trimesh.creation.box(extents=(20, 20, 20))
    for _ in range(subdivisions):
        body = body.subdivide()
    faces = body.faces.copy()
    faces[flip_index] = faces[flip_index, ::-1]
    keep = np.ones(len(faces), bool)
    keep[hole] = False
    opened = trimesh.Trimesh(vertices=body.vertices.copy(), faces=faces[keep], process=False)
    mesh = MeshData.of(opened)
    imported = normalise(mesh, "mm")
    rep = R.repair(mesh)
    print(f"falsch gewickelt: Dreieck {flip_index}, Loch: Dreieck {hole}")
    print("   Import  :", codes(imported.findings), facts(imported.mesh))
    print("   Repar.  :", codes(rep.findings), facts(rep.mesh))


# Das falsche Dreieck ist das erste im Netz (Bezugsdreieck von fix_winding).
case(flip_index=0, hole=50)
# Das falsche Dreieck liegt irgendwo; das erste ist richtig.
case(flip_index=77, hole=50)
# Ohne Loch (dicht): hier greift fix_inversion beim Import.
body = trimesh.creation.box(extents=(20, 20, 20)).subdivide().subdivide()
faces = body.faces.copy()
faces[0] = faces[0, ::-1]
closed = MeshData.of(trimesh.Trimesh(vertices=body.vertices.copy(), faces=faces, process=False))
imp = normalise(closed, "mm")
print("dicht, Dreieck 0 falsch: Import", codes(imp.findings), facts(imp.mesh))

# Ein STL-Import (Dreieckssuppe, wie aus der Datei): verschweißen gehört zum Lesen.
body = trimesh.creation.box(extents=(20, 20, 20)).subdivide().subdivide()
faces = body.faces.copy()
faces[0] = faces[0, ::-1]
keep = np.ones(len(faces), bool)
keep[50] = False
soup = trimesh.Trimesh(vertices=body.vertices[faces[keep]].reshape(-1, 3),
                       faces=np.arange(3 * int(keep.sum())).reshape(-1, 3), process=False)
imp = normalise(MeshData.of(soup), "mm", weld_is_reading=True)
print("STL-Suppe, Dreieck 0 falsch + Loch: Import", codes(imp.findings), facts(imp.mesh))
