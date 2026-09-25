"""Sonde RM-223: Was liefert konformes Verfeinern gegen das bisherige, und wie gut schätzen wir?

Je Datei und Kantenlänge: der bisherige Weg ``mesh_ops.remesh`` (trimesh nach
Bedarf, sonst gleichmäßig), der konforme ``mesh_ops.refined`` (exakter
Netzkern, ``refine_to_length``) — Dreiecke, dicht, Volumen, Teile, Zeit — und
drei Schätzungen: nach Fläche (heute), je Dreieck ``Σ ceil(l/e)²`` und je
Dreieck ``Σ 4^k``. Nur lesend; gerechnet wird am eingelesenen Netz, ohne
Merkmalserkennung.

Aufruf: python probe_konform.py <baum> <kante> <datei> [<datei> ...]
"""

from __future__ import annotations

import math
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

import numpy as np  # noqa: E402

from app.core.geom import mesh_ops  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.ingest import loader, threemf  # noqa: E402

EDGE = float(sys.argv[2])


def loaded(path: Path) -> MeshData:
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        parts = threemf.read_objects(payload)
        import trimesh

        body = trimesh.util.concatenate([part.mesh.raw for part in parts])
        mesh = MeshData.of(body)
    else:
        mesh = read_mesh(payload, path.suffix.lower())
    return loader.normalise(mesh, unit="mm", weld_is_reading=path.suffix.lower() == ".stl").mesh


def estimates(mesh: MeshData, edge: float) -> tuple[int, int, int]:
    corners = np.asarray(mesh.raw.triangles, dtype=np.float64)
    sides = np.stack(
        [
            np.linalg.norm(corners[:, 1] - corners[:, 0], axis=1),
            np.linalg.norm(corners[:, 2] - corners[:, 1], axis=1),
            np.linalg.norm(corners[:, 0] - corners[:, 2], axis=1),
        ],
        axis=1,
    )
    longest = sides.max(axis=1)
    by_area = mesh_ops.estimated_triangles(mesh, edge)
    squares = int(np.sum(np.ceil(np.maximum(longest / edge, 1.0)) ** 2))
    halvings = np.ceil(np.log2(np.maximum(longest / edge, 1.0)))
    quarters = int(np.sum(4.0**halvings))
    return by_area, squares, quarters


def described(mesh: MeshData, spent: float) -> str:
    return (
        f"{mesh.triangle_count:>9} Dreiecke, dicht {mesh.is_watertight}, "
        f"Volumen {mesh.volume:.3f}, Teile {mesh.component_count}, {spent:.1f} s"
    )


for name in sys.argv[3:]:
    path = Path(name)
    mesh = loaded(path)
    by_area, squares, quarters = estimates(mesh, EDGE)
    print(
        f"{path.name} bei {EDGE} mm: {mesh.triangle_count} Dreiecke, Volumen "
        f"{mesh.volume:.3f}, Teile {mesh.component_count}, dicht {mesh.is_watertight}",
        flush=True,
    )
    print(f"  Schätzung Fläche {by_area}, Σ ceil(l/e)² {squares}, Σ 4^k {quarters}")
    started = time.perf_counter()
    conform = mesh_ops.refined(mesh, EDGE)
    print(f"  konform   {described(conform, time.perf_counter() - started)}", flush=True)
    worst = float(np.asarray(conform.raw.edges_unique_length).max())
    print(f"            längste Kante danach {worst:.4f} mm, Volumen Δ {conform.volume - mesh.volume:+.6f}")
    started = time.perf_counter()
    old = mesh_ops.remesh(mesh, EDGE)
    print(f"  bisher    {described(old, time.perf_counter() - started)}", flush=True)
    print(f"            Faktor bisher/konform {old.triangle_count / max(conform.triangle_count, 1):.1f}")
    del old, conform
    print(f"  (math.isfinite: {math.isfinite(mesh.volume)})")
