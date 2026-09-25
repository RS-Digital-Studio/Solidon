"""Gegenprobe RM-224: Dichtheit und Umlaufsinn aus der Kantenzählung gegen trimesh.

Je Körper aus ``F:\\3D Dateien`` zwei Lesarten — roh (wie gelesen) und
verschweißt (wie der Import) — und je Lesart zwei Antworten: trimeshs
``graph.is_watertight`` und die aus ``repair._edge_table``. Jede Abweichung
wird gedruckt; am Ende die Zahl der Vergleiche. Nur lesend.

Aufruf: python gegenprobe_dichtheit.py <baum>
"""

from __future__ import annotations

import sys
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))

import app  # noqa: E402

where = str(Path(app.__file__).resolve())
if not where.startswith(str(TREE.resolve())):
    raise SystemExit(f"falscher Baum geladen: {where}")
print(f"gemessen wird {where}")

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

import app.core.bootstrap  # noqa: E402,F401
from app.core.geom import repair as R  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.ingest import threemf  # noqa: E402
from app.core.units import weld_digits, weld_tolerance  # noqa: E402

KUNDE = Path(r"F:\3D Dateien")
SUFFIXES = {".stl", ".3mf", ".obj", ".ply", ".glb"}


def bodies(path: Path):
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        objects = threemf.read_objects(payload)
        if objects:
            return [(str(part.name), part.mesh.raw) for part in objects]
    return [(path.name, read_mesh(payload, path.suffix.lower()).raw)]


def compare(label: str, body: trimesh.Trimesh) -> bool:
    if not len(body.faces):
        return True
    expected = trimesh.graph.is_watertight(edges=body.edges, edges_sorted=body.edges_sorted)
    fresh = body.copy()
    R._edge_table(MeshData.of(fresh))
    cache = fresh._cache
    got = (bool(cache["is_watertight"]), bool(cache["is_winding_consistent"]))
    if (bool(expected[0]), bool(expected[1])) != got:
        print(f"ABWEICHUNG {label}: trimesh {expected}, Kantenzählung {got}")
        return False
    return True


checked = 0
wrong = 0
files = sorted(
    path
    for path in KUNDE.rglob("*")
    if path.is_file() and path.suffix.lower() in SUFFIXES and path.stat().st_size < 150_000_000
)
for path in files:
    try:
        found = bodies(path)
    except Exception as problem:  # Fremde Dateien, fremde Fehler — nur gezählt
        print(f"übersprungen {path.name}: {problem}")
        continue
    for name, raw in found:
        welded = raw.copy()
        diagonal = float(np.linalg.norm(welded.bounds[1] - welded.bounds[0])) if len(welded.faces) else 0.0
        welded.merge_vertices(digits_vertex=weld_digits(weld_tolerance(diagonal)))
        for label, body in ((f"{path.name}/{name} roh", raw), (f"{path.name}/{name} verschweißt", welded)):
            checked += 1
            if not compare(label, body):
                wrong += 1
print(f"{checked} Vergleiche, {wrong} Abweichungen")
