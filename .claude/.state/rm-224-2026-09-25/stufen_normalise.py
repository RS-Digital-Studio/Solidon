"""Sonde RM-224: Wanduhrzeit je Schritt von ``loader.normalise``, ohne Profiler.

cProfile verteuert Python-lastige Schritte stärker als NumPy-lastige und
verschiebt damit die Rangfolge. Hier werden ausgewählte Funktionen nur mit
``perf_counter`` umhüllt — an jeder Stelle, an der sie beim Namen geholt
werden — und je Funktion Aufrufe, eigene Summe und die Dreieckszahl des
Netzes festgehalten. Verschachtelte Zeiten zählen beim Äußeren mit.

Aufruf: python stufen_normalise.py <baum> <datei> [--runs N]
"""

from __future__ import annotations

import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))

import app  # noqa: E402

where = str(Path(app.__file__).resolve())
if not where.startswith(str(TREE.resolve())):
    raise SystemExit(f"falscher Baum geladen: {where}")
print(f"gemessen wird {where}")

import app.core.bootstrap  # noqa: E402,F401
import trimesh  # noqa: E402

from app.core.geom import mesh as mesh_module  # noqa: E402
from app.core.geom import repair as repair_module  # noqa: E402
from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.ingest import loader  # noqa: E402

RUNS = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 3

spent: dict[str, list[float]] = defaultdict(list)


def wrapped(name: str, function):  # noqa: ANN001, ANN202
    def timed(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        started = time.perf_counter()
        try:
            return function(*args, **kwargs)
        finally:
            spent[name].append(time.perf_counter() - started)

    return timed


# Modulfunktionen: an jeder Stelle ersetzen, an der sie beim Namen liegen.
MODULE_FUNCTIONS = {
    mesh_module: ("edge_table", "face_components", "_adjacency_by_place"),
    repair_module: (
        "merge_vertices",
        "remove_doubled_faces",
        "remove_degenerate_faces",
        "resolve_branching_edges",
        "stitch_t_junctions",
        "_filled_rounds",
        "_fill_loops",
        "_flat_fills",
        "_hole_rings",
        "remove_open_splinters",
        "unify_normals",
        "wind_consistently",
        "turn_shells_outward",
        "_crossed_edge_count",
        "is_closed",
        "repair",
        "_tears_it_further",
    ),
    loader: ("normalise", "_count_components"),
}
for module, names in MODULE_FUNCTIONS.items():
    for name in names:
        original = getattr(module, name)
        timed = wrapped(f"{module.__name__.rsplit('.', 1)[-1]}.{name}", original)
        for holder in (mesh_module, repair_module, loader):
            if getattr(holder, name, None) is original:
                setattr(holder, name, timed)

# trimesh-Methoden, die unmittelbar Zeit kosten.
for name in ("merge_vertices", "nondegenerate_faces", "unique_faces"):
    setattr(trimesh.Trimesh, name, wrapped(f"trimesh.{name}", getattr(trimesh.Trimesh, name)))

path = Path(sys.argv[2])
suffix = path.suffix.lower()
payload = path.read_bytes()
loader.normalise(read_mesh(payload, suffix), unit="mm", weld_is_reading=suffix == ".stl")

totals: dict[str, list[float]] = defaultdict(list)
counts: dict[str, int] = {}
for _run in range(RUNS):
    spent.clear()
    mesh = read_mesh(payload, suffix)
    started = time.perf_counter()
    result = loader.normalise(mesh, unit="mm", weld_is_reading=suffix == ".stl")
    print(f"  Lauf: {time.perf_counter() - started:.3f} s")
    for name, values in spent.items():
        totals[name].append(sum(values))
        counts[name] = len(values)

print(f"{path.name}: {mesh.triangle_count} Dreiecke")
print(f"Befunde: {[finding.code for finding in result.findings]}")
print(
    f"Ergebnis: dicht {result.mesh.is_watertight}, Teile {result.mesh.component_count}, "
    f"Dreiecke {result.mesh.triangle_count}, Volumen {result.mesh.volume:.6f}"
)
print("Median je Schritt über die Läufe (Aufrufe je Lauf):")
for name, values in sorted(totals.items(), key=lambda item: -statistics.median(item[1])):
    print(f"  {statistics.median(values):7.3f} s  {counts[name]:3d}x  {name}")
