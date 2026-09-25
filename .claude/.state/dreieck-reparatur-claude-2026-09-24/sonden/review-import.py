"""Review-Sonde: Import-Schritte 4/4b/6 (nur lesend).

E  Baugruppe: Ort der großen Öffnung nach dem gemeinsamen Aufsetzen (`_group_on_bed`)
F  `unify_normals=False` am Ladeschritt — dreht Schritt 4b trotzdem?
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import facts  # noqa: E402

import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.ingest.ops import _group_on_bed  # noqa: E402
from app.core.types import SceneObject  # noqa: E402

# E — zwei Körper; der erste ist ein Würfel ohne Oberseite (große Öffnung), weit weg vom Ursprung
open_box = trimesh.creation.box((20.0, 20.0, 20.0))
top = open_box.triangles_center[:, 2] > 9.9
open_box.update_faces(~top)
open_box.remove_unreferenced_vertices()
open_box.apply_translation((100.0, 100.0, 50.0))
other = trimesh.creation.box((10.0, 10.0, 10.0))
other.apply_translation((140.0, 100.0, 45.0))

outputs = []
findings = []
for name, body in (("offen", open_box), ("zu", other)):
    result = normalise(MeshData.of(body.copy()), "mm", place_on_bed=False, centre=False)
    outputs.append(SceneObject(id="", name=name, mesh=result.mesh, material_slots=[]))
    findings.extend(result.findings)
wide = [entry for entry in findings if entry.code == "repair.wide_hole_filled"]
print("E Befund vor dem Aufsetzen:", [(entry.code, entry.location) for entry in wide])
moved = _group_on_bed(list(outputs), findings, place_on_bed=True, centre=True)
box = moved[0].mesh.bounds
print("E Körper 'offen' danach: min", box.minimum, "max", box.maximum)
wide = [entry for entry in findings if entry.code == "repair.wide_hole_filled"]
print("E Befund nach dem Aufsetzen:", [(entry.code, entry.location) for entry in wide])
print()

# F — offenes Netz, einheitlich verkehrt gewickelt, unify_normals=False
cube = trimesh.creation.box((20.0, 20.0, 20.0))
cube = trimesh.Trimesh(cube.vertices, cube.faces[:, ::-1], process=False)
cube.update_faces(np.arange(len(cube.faces)) != 0)
cube.remove_unreferenced_vertices()
before = np.array(cube.faces, copy=True)
result = normalise(MeshData.of(cube.copy()), "mm", unify_normals=False)
print("F Befunde:", [entry.code for entry in result.findings])
print("F Fakten:", facts(result.mesh))
