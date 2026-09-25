"""Sonde RM-224: Zeit von ``loader.normalise`` an einer Datei, ohne Profiler.

Liest die Datei wie der Import, fährt ``normalise`` einmal zum Aufwärmen und
dann ``--runs`` Mal, druckt je Lauf die Zeit und am Ende Median, Befunde und
Kennzahlen des Ergebnisses — die müssen zwischen zwei Ständen gleich sein.

Aufruf: python zeit_normalise.py <baum> <datei> [--runs N]
"""

from __future__ import annotations

import statistics
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
runs = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 3
suffix = path.suffix.lower()
payload = path.read_bytes()
loader.normalise(read_mesh(payload, suffix), unit="mm", weld_is_reading=suffix == ".stl")
times = []
result = None
for _ in range(runs):
    mesh = read_mesh(payload, suffix)
    started = time.perf_counter()
    result = loader.normalise(mesh, unit="mm", weld_is_reading=suffix == ".stl")
    times.append(time.perf_counter() - started)
    print(f"  Lauf: {times[-1]:.3f} s")
assert result is not None
body = result.mesh
print(f"{path.name}: Median {statistics.median(times):.3f} s über {runs} Läufe")
print(f"  Befunde: {sorted(finding.code for finding in result.findings)}")
print(
    f"  Dreiecke {body.triangle_count}, dicht {body.is_watertight}, "
    f"Wicklung {bool(body.raw.is_winding_consistent)}, Teile {body.component_count}, "
    f"Volumen {body.volume:.6f}"
)
