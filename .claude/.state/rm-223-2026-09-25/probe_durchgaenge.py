"""Sonde RM-223: Wie viele Durchgänge braucht konformes Verfeinern bis zur Zusage?

``refine_to_length`` teilt jede Kante in ``ceil(l/e)`` Stücke, füllt das
Innere eines Dreiecks aber mit eigenen Kanten, die länger sein können — nach
einem Durchgang lagen die längsten bei 2,2 bis 3,9 mm für verlangte 1,0 mm.
Hier wird wiederholt, bis keine Kante mehr über ``e`` liegt, und je Durchgang
Dreiecke, längste Kante und Zeit gedruckt; dazu die Schätzung
``Fläche/(√3/4·e²) + 2·Σ_Kanten ceil(l/e) − 2F`` gegen das erste und letzte
Ergebnis. Nur lesend.

Aufruf: python probe_durchgaenge.py <baum> <kante> <datei> [<datei> ...]
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
print(f"gemessen wird {where}", flush=True)

import manifold3d  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom import mesh_ops  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.ingest import loader, threemf  # noqa: E402

EDGE = float(sys.argv[2])


def loaded(path: Path) -> MeshData:
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        parts = threemf.read_objects(payload)
        body = trimesh.util.concatenate([part.mesh.raw for part in parts])
        mesh = MeshData.of(body)
    else:
        mesh = read_mesh(payload, path.suffix.lower())
    return loader.normalise(mesh, unit="mm", weld_is_reading=path.suffix.lower() == ".stl").mesh


def estimate(mesh: MeshData, edge: float) -> int:
    lengths = np.asarray(mesh.raw.edges_unique_length, dtype=float)
    pieces = np.ceil(np.maximum(lengths / edge, 1.0))
    by_area = float(mesh.raw.area) / (np.sqrt(3.0) / 4.0 * edge * edge)
    return int(by_area + 2.0 * float(pieces.sum()) - 2.0 * mesh.triangle_count)


def longest(vertices: np.ndarray, faces: np.ndarray) -> float:
    corners = vertices[faces]
    sides = np.linalg.norm(corners - np.roll(corners, -1, axis=1), axis=2)
    return float(sides.max())


for name in sys.argv[3:]:
    path = Path(name)
    try:
        mesh = loaded(path)
    except Exception as error:
        print(f"{path.name}: nicht lesbar: {type(error).__name__}: {error}", flush=True)
        continue
    print(
        f"{path.name} bei {EDGE} mm: {mesh.triangle_count} Dreiecke, Fläche "
        f"{mesh.raw.area:.0f} mm², dicht {mesh.is_watertight}, Teile {mesh.component_count}",
        flush=True,
    )
    print(f"  Schätzung {estimate(mesh, EDGE)} (Fläche allein {mesh_ops.estimated_triangles(mesh, EDGE)})")
    if not mesh.is_watertight:
        print("  offen — der konforme Weg nimmt es nicht", flush=True)
        continue
    solid = manifold3d.Manifold(
        manifold3d.Mesh64(
            np.asarray(mesh.raw.vertices, dtype=np.float64),
            np.asarray(mesh.raw.faces, dtype=np.uint64),
        )
    )
    if solid.is_empty():
        print(f"  Kern lehnt ab: {solid.status()}", flush=True)
        continue
    started = time.perf_counter()
    for step in range(1, 9):
        solid = solid.refine_to_length(EDGE)
        built = solid.to_mesh64()
        vertices = np.asarray(built.vert_properties[:, :3], dtype=float)
        faces = np.asarray(built.tri_verts, dtype=np.int64)
        worst = longest(vertices, faces)
        print(
            f"  Durchgang {step}: {len(faces):>9} Dreiecke, längste {worst:.4f} mm, "
            f"{time.perf_counter() - started:.2f} s",
            flush=True,
        )
        if worst <= EDGE * (1.0 + 1e-9):
            break
        if len(faces) > mesh_ops.MAX_REMESH_TRIANGLES:
            print("  über der Decke", flush=True)
            break
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    print(
        f"  Ergebnis dicht {body.is_watertight}, Volumen Δ {body.volume - mesh.volume:+.6f}, "
        f"Teile {len(body.split(only_watertight=False))}",
        flush=True,
    )
