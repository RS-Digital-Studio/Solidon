"""RM-239 am Befund selbst: der Ring aus ``Siebhalter+X1C.3mf`` mit einem Riss.

Aufruf: python siebhalter.py ["F:/3D Dateien/Siebhalter+X1C.3mf"]
Sucht den Körper mit 7 996 Dreiecken, reißt ein Dreieck weit weg von den
zwölf Eckpaaren ab und verschweißt einmal wie bisher (trimesh) und einmal mit
``repair.weld`` — danach offene und verzweigte Kanten und die Zahl der
Dreiecke, die das Entfernen flacher Dreiecke übrig lässt.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.geom.repair import (  # noqa: E402
    branching_edge_count,
    open_edge_count,
    remove_degenerate_faces,
    weld,
)
from app.core.units import weld_digits, weld_tolerance  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else "F:/3D Dateien/Siebhalter+X1C.3mf"
scene = trimesh.load(path, process=False)
geometries = list(scene.geometry.values()) if isinstance(scene, trimesh.Scene) else [scene]
ring = next(g for g in geometries if len(g.faces) == 7996)
vertices = np.asarray(ring.vertices, dtype=float)
faces = np.asarray(ring.faces, dtype=np.int64)
digits = weld_digits(weld_tolerance(float(np.linalg.norm(ring.extents))))

keys = np.round(vertices * 10**digits).astype(np.int64)
_unique, group = np.unique(keys, axis=0, return_inverse=True)
group = np.asarray(group).reshape(-1)
paired = np.flatnonzero(np.bincount(group)[group] > 1)
print(f"{len(paired)} Ecken in Gruppen mit mehr als einer Ecke")

# Ein Dreieck weit weg von den Paaren abreißen.
centres = vertices[faces].mean(axis=1)
distance = np.min(
    np.linalg.norm(centres[:, None, :] - vertices[paired][None, :, :], axis=2), axis=1
)
row = int(np.argmax(distance))
torn = faces.copy()
torn[row] = len(vertices) + np.arange(3)
torn_vertices = np.vstack([vertices, vertices[faces[row]]])


def report(name: str, body: trimesh.Trimesh) -> None:
    mesh = MeshData.of(body)
    cleaned, dropped = remove_degenerate_faces(mesh)
    print(
        f"{name:8s} Ecken {len(body.vertices):5d}  offen {open_edge_count(mesh):3d}"
        f"  verzweigt {branching_edge_count(mesh):3d}  flache Dreiecke {dropped:3d}"
        f"  danach {cleaned.triangle_count} Dreiecke, dicht {cleaned.is_watertight}"
    )


for label, (v, f) in {"heil": (vertices, faces), "gerissen": (torn_vertices, torn)}.items():
    print(label)
    report("roh", trimesh.Trimesh(vertices=v, faces=f, process=False))
    old = trimesh.Trimesh(vertices=v, faces=f, process=False)
    old.merge_vertices(digits_vertex=digits)
    report("trimesh", old)
    new = trimesh.Trimesh(vertices=v, faces=f, process=False)
    merged = weld(new, digits)
    report(f"weld {merged}", new)


# Die Merkmale: bis RM-239 wurden aus 16 Flächen des Rings 28.
from collections import Counter  # noqa: E402

from app.core.geom.repair import repair  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402


def kinds(mesh: MeshData) -> Counter[str]:
    return Counter(feature.kind for feature in detect(mesh).values())


print("Merkmale heil        ", dict(kinds(MeshData.of(ring))))
repaired = repair(MeshData.of(trimesh.Trimesh(vertices=torn_vertices, faces=torn, process=False)))
print("Merkmale repariert   ", dict(kinds(repaired.mesh)), repaired.mesh.triangle_count, repaired.mesh.is_watertight)
print("  Befunde", [finding.code for finding in repaired.findings])
