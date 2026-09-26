"""RM-240: Teile einer Bohrungswand und eines Senkungskegels fehlen — was kommt zurück?

Aufruf aus dem Projektordner: python .claude/.state/rm-240-bohrungswand-2026-09-26/sonde.py
Je Fall: Löcher und Kegel nach der Reparatur, Volumen gegen die heile Platte.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import numpy as np  # noqa: E402

from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.geom.repair import merge_vertices, repair  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402

MESHES = Path("tests/data/meshes")


def raw(name: str) -> MeshData:
    return read_mesh((MESHES / name).read_bytes(), ".stl")


def without(mesh: MeshData, faces: np.ndarray) -> MeshData:
    keep = np.setdiff1d(np.arange(mesh.triangle_count), faces)
    return MeshData.of(mesh.raw.submesh([keep], append=True, repair=False))


def share(mesh: MeshData, feature, part: str) -> np.ndarray:
    wall = np.asarray(feature.face_indices)
    offset = np.asarray(mesh.raw.triangles_center)[wall] - np.asarray(feature.params["centre"])
    if part == "viertel":
        return wall[(offset[:, 0] < 0.0) & (offset[:, 1] < 0.0)]
    if part == "halb":
        return wall[offset[:, 0] < 0.0]
    if part == "dreiviertel":
        return wall[~((offset[:, 0] >= 0.0) & (offset[:, 1] >= 0.0))]
    raise ValueError(part)


def report(label: str, whole: MeshData, broken: MeshData) -> None:
    result = repair(broken)
    kinds = [f.kind for f in detect(result.mesh).values() if f.kind in ("hole", "cone")]
    print(
        f"{label:28s} dicht {result.mesh.is_watertight!s:5s}"
        f"  Bohrungen {kinds.count('hole')}  Kegel {kinds.count('cone')}"
        f"  Volumen {float(result.mesh.volume) - float(whole.volume):+.3f} mm³"
        f"  {[f.code for f in result.findings if f.code.startswith('repair.')]}"
    )


plate, _ = merge_vertices(raw("plate_holes.stl"))
bores = sorted(
    (f for f in detect(plate).values() if f.kind == "hole"), key=lambda f: tuple(f.params["centre"])
)
print("heil: Bohrungen", len(bores), "Volumen", round(float(plate.volume), 3))
for part in ("viertel", "halb", "dreiviertel"):
    report(f"plate_holes {part}", plate, without(plate, share(plate, bores[0], part)))

sunk = normalise(raw("plate_countersunk.stl"), "mm").mesh
cone = next(f for f in detect(sunk).values() if f.kind == "cone")
kinds = [f.kind for f in detect(sunk).values() if f.kind in ("hole", "cone")]
print("heil: Bohrungen", kinds.count("hole"), "Kegel", kinds.count("cone"), "Volumen", round(float(sunk.volume), 3))
for part in ("viertel", "halb", "dreiviertel"):
    report(f"plate_countersunk {part}", sunk, without(sunk, share(sunk, cone, part)))
