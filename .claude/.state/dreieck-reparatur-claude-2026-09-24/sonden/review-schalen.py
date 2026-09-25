"""Review-Sonde: Schalen, Teil im Teil, Splitter und „Dicke geben" (nur lesend).

A  Hohlkörper richtig gewickelt + getrenntes, großes umgestülptes Teil
B  Kugel mit Hohlraum und darin gefangener Kugel (Rassel, „Schiff in der Flasche")
C  Würfel + 20 lose Einzeldreiecke (Splitter): kommt `repair.no_thickness`?
C2 wie C, dazu ein Fenster in einem Zylinder, das offen bleibt: wird `still_open` verdeckt?
D  Würfel + flaches Blatt: `repair.no_thickness` mit „Dicke geben" — was macht thicken mit dem Würfel?
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import R, facts  # noqa: E402

import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData, face_components  # noqa: E402
from app.core.geom.mesh_ops import _thickened  # noqa: E402


def shell_volumes(mesh: MeshData) -> list[float]:
    body = mesh.raw
    out = []
    for faces in face_components(body):
        tri = np.asarray(body.triangles, dtype=np.float64)[faces]
        local = tri - tri[0, 0]
        crossed = np.cross(local[:, 1], local[:, 2])
        products = (local[:, 0] * crossed).sum(axis=1)
        out.append(round(math.fsum(products.tolist()) / 6.0, 3))
    return sorted(out)


def inverted(body: trimesh.Trimesh) -> trimesh.Trimesh:
    return trimesh.Trimesh(body.vertices, body.faces[:, ::-1], process=False)


def joined(*bodies: trimesh.Trimesh) -> MeshData:
    return MeshData.of(trimesh.util.concatenate(list(bodies)))


def report(title: str, result) -> None:
    print(title)
    print("  codes:", [f.code for f in result.findings])
    for entry in result.findings:
        print("   ", entry.code, entry.severity, str(entry.message), entry.values,
              [a.id for a in entry.suggestions] if entry.suggestions else [])
    print("  shells:", shell_volumes(result.mesh), "facts:", facts(result.mesh))


# A — Hohlkörper (außen +8000, Hohlraum -1000) + getrennter umgestülpter Würfel 22³
outer = trimesh.creation.box((20.0, 20.0, 20.0))
cavity = inverted(trimesh.creation.box((10.0, 10.0, 10.0)))
big = inverted(trimesh.creation.box((22.0, 22.0, 22.0)))
big.apply_translation((60.0, 0.0, 0.0))
case_a = joined(outer, cavity, big)
print("A vorher shells:", shell_volumes(case_a))
report("A repair()", R.repair(case_a))
print()

# B — Kugel r=20 mit Hohlraum r=15 und gefangener Kugel r=5 in der Mitte
shell = trimesh.creation.icosphere(subdivisions=3, radius=20.0)
hollow = inverted(trimesh.creation.icosphere(subdivisions=3, radius=15.0))
ball = trimesh.creation.icosphere(subdivisions=3, radius=5.0)
case_b = joined(shell, hollow, ball)
print("B vorher shells:", shell_volumes(case_b))
report("B repair()", R.repair(case_b))
print("B parts_inside_parts:", R.parts_inside_parts(case_b.raw.copy()))
print()


def splinters(count: int, size: float) -> list[trimesh.Trimesh]:
    out = []
    for index in range(count):
        x = 40.0 + 5.0 * index
        vertices = np.array([[x, 0.0, 0.0], [x + size, 0.0, 0.0], [x, size, 0.0]])
        out.append(trimesh.Trimesh(vertices, [[0, 1, 2]], process=False))
    return out


# C — Würfel 20 (Fläche 2400) + 20 Einzeldreiecke zu je 1,125 mm² (< 0,1 % von 2400)
cube = trimesh.creation.box((20.0, 20.0, 20.0))
case_c = joined(cube, *splinters(20, 1.5))
report("C repair()", R.repair(case_c))
print()

# C2 — wie C, dazu ein Zylinder mit einem Fenster über 240°, das offen bleiben soll
cylinder = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=64)
cylinder.apply_translation((0.0, 60.0, 0.0))
centres = cylinder.triangles_center - np.array([0.0, 60.0, 0.0])
angle = np.degrees(np.arctan2(centres[:, 1], centres[:, 0])) % 360.0
radial = np.hypot(centres[:, 0], centres[:, 1])
window = (angle < 240.0) & (np.abs(centres[:, 2]) < 5.0) & (radial > 9.0)
cylinder.update_faces(~window)
cylinder.remove_unreferenced_vertices()
alone = R.repair(MeshData.of(cylinder.copy()))
print("C2 Zylinderfenster allein:", [f.code for f in alone.findings], facts(alone.mesh))
case_c2 = joined(cube, cylinder, *splinters(20, 1.5))
report("C2 repair()", R.repair(case_c2))
print()

# D — Würfel 20 + flaches Blatt 12 x 12 (zwei Dreiecke) daneben
sheet = trimesh.Trimesh(
    np.array([[40.0, 0.0, 0.0], [52.0, 0.0, 0.0], [52.0, 12.0, 0.0], [40.0, 12.0, 0.0]]),
    [[0, 1, 2], [0, 2, 3]],
    process=False,
)
case_d = joined(cube, sheet)
result_d = R.repair(case_d)
report("D repair()", result_d)
thick = _thickened(result_d.mesh, 0.8)
print("D nach thicken(0,8): shells", shell_volumes(thick), "facts", facts(thick))
