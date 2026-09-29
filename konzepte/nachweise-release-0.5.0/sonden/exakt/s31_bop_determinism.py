"""Liefert die parallele Boolesche jedes Mal dieselbe Topologie in derselben Reihenfolge?

Gemessen wird je Fall eine Signatur des Ergebnisses — je Fläche in der
Reihenfolge von ``Solid.faces`` Trägerart, Inhalt und Schwerpunkt, gerundet
auf 10⁻⁹ —, zwölfmal parallel und einmal seriell. Gleiche Reihenfolge heißt
gleiche Merkmalsnummern (``face_1`` …) und gleiche Vernetzung (Cache, §15.1).
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

TREE = r"F:\3D Druck.review-050\wt-exakt"
sys.path.insert(0, TREE)
import app  # noqa: E402

print(app.__file__)
from OCP.BRepAdaptor import BRepAdaptor_Surface  # noqa: E402

import app.core.brep.kernel as kernel  # noqa: E402
from app.core.brep import edit, profiles, step  # noqa: E402
from app.core.brep.properties import properties  # noqa: E402
from app.core.knowledge.parts.build import threaded  # noqa: E402
from app.core.knowledge.parts.shapes import building  # noqa: E402

original = kernel.boolean_builder
PARALLEL = {"on": False}


def builder(kind, first, second, *, tolerance=None):
    operation = original(kind, first, second, tolerance=tolerance)
    operation.SetRunParallel(PARALLEL["on"])
    return operation


kernel.boolean_builder = builder
edit.boolean_builder = builder  # type: ignore[attr-defined]
profiles.boolean_builder = builder  # type: ignore[attr-defined]


def signature(solid) -> str:
    rows = []
    for face in solid.faces():
        measured = properties(face, "surface")
        rows.append(
            (
                int(BRepAdaptor_Surface(face).GetType()),
                round(measured.mass, 9),
                tuple(round(value, 9) for value in measured.centre),
            )
        )
    mesh = solid.mesh.raw
    triangles = hashlib.sha1(mesh.faces.tobytes() + mesh.vertices.round(9).tobytes()).hexdigest()
    return hashlib.sha1(repr(rows).encode()).hexdigest()[:12] + "/" + triangles[:12]


cat = step.read((Path(r"F:\3D Dateien") / "Cat_3.stp").read_bytes())
tray = step.read((Path(r"F:\3D Dateien") / "build_tray_v3.step").read_bytes())
with building("brep"):
    rod = threaded(40.08, 3.0, 8.0, bottom=float(cat.bounds.maximum[2]))
neck = edit.moved(rod, (-15.0, -37.0, 0.0))
bore = edit.moved(edit.cylinder(20.0, 80.0), (60.0, 100.0, -5.0))

cases = {
    "cat+neck": lambda: edit.boolean("union", [cat, neck]),
    "tray-bore": lambda: edit.boolean("difference", [tray, bore]),
    "thread": lambda: profiles.threaded_rod(3.0, 0.5, 60.0),
}
for name, case in cases.items():
    PARALLEL["on"] = False
    serial = signature(case())
    PARALLEL["on"] = True
    parallel = {signature(case()) for _round in range(12)}
    print(f"{name}: serial {serial} parallel {sorted(parallel)} same={parallel == {serial}}")
