"""Sonde RM-224: Wer in ``loader.normalise`` die teuren Kantenfragen stellt.

Wie ``profil_normalise.py``, druckt aber zu ausgewählten Funktionen die
Aufrufer mit ihrer Zeit — die Frage ist nicht mehr *was* kostet, sondern
*wer* es auslöst. Nur lesend.

Aufruf: python profil_aufrufer.py <baum> <datei> [<ausgabe.txt>]
"""

from __future__ import annotations

import cProfile
import io
import pstats
import sys
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))

import app  # noqa: E402

where = str(Path(app.__file__).resolve())
if not where.startswith(str(TREE.resolve())):
    raise SystemExit(f"falscher Baum geladen: {where}")
print(f"gemessen wird {where}")

import app.core.bootstrap  # noqa: E402,F401
from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.ingest import loader  # noqa: E402

path = Path(sys.argv[2])
suffix = path.suffix.lower()
payload = path.read_bytes()
loader.normalise(read_mesh(payload, suffix), unit="mm", weld_is_reading=suffix == ".stl")

mesh = read_mesh(payload, suffix)
profiler = cProfile.Profile()
profiler.enable()
loader.normalise(mesh, unit="mm", weld_is_reading=suffix == ".stl")
profiler.disable()

WATCHED = (
    "edge_table",
    "face_components",
    "_adjacency_by_place",
    "fully_stitched",
    "face_adjacency",
    "merge_vertices",
    "unify_normals",
    "_flat_fills",
    "_resolve_branching_once",
    "edges_sorted",
)
stream = io.StringIO()
stats = pstats.Stats(profiler, stream=stream)
for name in WATCHED:
    stats.print_callers(rf"\({name}\)")
# Und die Gegenrichtung für die Abläufe: welcher Schritt wie viel kostet.
for name in ("normalise", "repair", "_filled_rounds", "_fill_loops"):
    stats.print_callees(rf"\({name}\)")
text = stream.getvalue()
if len(sys.argv) > 3:
    Path(sys.argv[3]).write_text(text, encoding="utf-8")
else:
    print(text)
