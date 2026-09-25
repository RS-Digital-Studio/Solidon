"""Sonde RM-224: Wo ``loader.normalise`` an großen Netzen seine Zeit lässt.

Liest eine Datei wie der Import (STL mit ``weld_is_reading``), fährt
``normalise`` einmal warm (Bibliotheken geladen) unter ``cProfile`` und
druckt die teuersten Aufrufe nach Eigen- und Gesamtzeit. Nur lesend.

Aufruf: python profil_normalise.py <baum> <datei> [<ausgabe.txt>]
"""

from __future__ import annotations

import cProfile
import io
import pstats
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
from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.ingest import loader  # noqa: E402

path = Path(sys.argv[2])
suffix = path.suffix.lower()
payload = path.read_bytes()

# Einmal kalt, damit Importe und Caches der Bibliotheken nicht mitzählen.
loader.normalise(read_mesh(payload, suffix), unit="mm", weld_is_reading=suffix == ".stl")

mesh = read_mesh(payload, suffix)
profiler = cProfile.Profile()
started = time.perf_counter()
profiler.enable()
result = loader.normalise(mesh, unit="mm", weld_is_reading=suffix == ".stl")
profiler.disable()
spent = time.perf_counter() - started
print(f"{path.name}: {mesh.triangle_count} Dreiecke, normalise {spent:.3f} s")
print(f"Befunde: {[finding.code for finding in result.findings]}")
print(f"Ergebnis: dicht {result.mesh.is_watertight}, Teile {result.mesh.component_count}")
stream = io.StringIO()
stats = pstats.Stats(profiler, stream=stream)
stats.sort_stats("cumulative").print_stats(45)
stats.sort_stats("tottime").print_stats(25)
text = stream.getvalue()
if len(sys.argv) > 3:
    Path(sys.argv[3]).write_text(text, encoding="utf-8")
else:
    print(text)
