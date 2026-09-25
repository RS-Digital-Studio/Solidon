"""Sonde RM-221: Was eine Boolesche Operation an ineinandersteckenden Teilen tut.

Liest Kundendateien wie der Import (``loader.normalise``), fragt
``repair.parts_that_cross`` und fährt dann *Fläche versetzen* (+1 mm) an der
größten ebenen Fläche und eine Bohrung. Je Fall: Teilezahl und Volumen davor
und danach, die Rechenstufe und die Befundcodes. Nur lesend.

Aufruf: python sonde_verschmelzen.py <baum> [datei …]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))

import app  # noqa: E402

where = str(Path(app.__file__).resolve())
if not where.startswith(str(TREE.resolve())):
    raise SystemExit(f"falscher Baum geladen: {where}")
print(f"gemessen wird {where}")

import app.core.bootstrap  # noqa: E402,F401
from app.core.deferred import trimesh  # noqa: E402
from app.core.geom import faces  # noqa: E402
from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom import repair as R  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.ingest import loader  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402

FILES = [Path(item) for item in sys.argv[2:]] or [
    Path(r"F:\3D Dateien\pirate+ship+with+sails_stls\obj_11_Cylinder_B.stl"),
]


def describe(label: str, mesh: MeshData) -> None:
    print(
        f"  {label}: Teile {mesh.component_count}, Volumen {mesh.volume:.3f} mm³, "
        f"dicht {mesh.is_watertight}, Dreiecke {mesh.triangle_count}"
    )


for path in FILES:
    print(f"== {path.name}")
    raw = read_mesh(path.read_bytes(), path.suffix.lower())
    normalised = loader.normalise(raw, unit="mm")
    body = normalised.mesh
    describe("eingelesen", body)
    started = time.perf_counter()
    crossing = R.parts_that_cross(body.raw)
    print(f"  steckt ineinander: {crossing} ({time.perf_counter() - started:.3f} s)")
    print(f"  Befunde Import: {[f.code for f in normalised.findings]}")
    found = detect(body)
    planes = [feature for feature in found.values() if feature.kind == "face"]
    if planes:
        face = max(planes, key=lambda feature: float(feature.params.get("area", 0.0)))
        outcome = faces.push_face(body, face, 1.0)
        print(
            f"  Fläche versetzen +1 an {face.id} ({float(face.params.get('area', 0.0)):.2f} mm²): "
            f"Stufe {outcome.solver.strategy}, Befunde {[f.code for f in outcome.findings]}"
        )
        describe("danach", outcome.mesh)
    low, high = body.bounds.minimum, body.bounds.maximum
    middle = [(low[index] + high[index]) / 2.0 for index in range(3)]
    tool = trimesh.creation.cylinder(radius=1.0, height=(high[2] - low[2]) + 4.0, sections=48)
    tool.apply_translation(middle)
    drilled = boolean("difference", [body, MeshData(tool)])
    print(
        f"  Bohrung Ø 2 senkrecht durch die Mitte: Stufe {drilled.solver.strategy}, "
        f"Befunde {[f.code for f in drilled.findings]}"
    )
    describe("gebohrt", drilled.mesh)
