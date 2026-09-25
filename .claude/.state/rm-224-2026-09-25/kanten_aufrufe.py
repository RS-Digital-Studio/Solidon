"""Sonde RM-224: Welche Kantenzählungen in ``normalise`` wirklich rechnen, und für wen.

Umhüllt ``mesh.edge_table`` an jeder Stelle, an der es beim Namen liegt, und
schreibt je Aufruf Dauer, Dreieckszahl, ob der Cache traf, und die Kette der
aufrufenden Funktionen. Nur lesend.

Aufruf: python kanten_aufrufe.py <baum> <datei>
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))

import app  # noqa: E402
import app.core.bootstrap  # noqa: E402
from app.core.geom import mesh as mesh_module  # noqa: E402
from app.core.geom import repair as repair_module  # noqa: E402
from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.ingest import loader  # noqa: E402

print(f"gemessen wird {Path(app.__file__).resolve()}")
original = mesh_module.edge_table
calls: list[tuple[float, int, bool, str]] = []


def counted(body):  # noqa: ANN001, ANN202
    cache = getattr(body, "_cache", None)
    hit = cache is not None and "solidon_edge_table" in cache
    started = time.perf_counter()
    table = original(body)
    frame = sys._getframe(1)
    chain = []
    while frame is not None and len(chain) < 4:
        chain.append(frame.f_code.co_name)
        frame = frame.f_back
    calls.append((time.perf_counter() - started, len(body.faces), hit, " < ".join(chain)))
    return table


for holder in (mesh_module, repair_module):
    if getattr(holder, "edge_table", None) is original:
        holder.edge_table = counted

path = Path(sys.argv[2])
payload = path.read_bytes()
suffix = path.suffix.lower()
loader.normalise(read_mesh(payload, suffix), unit="mm", weld_is_reading=suffix == ".stl")
calls.clear()
loader.normalise(read_mesh(payload, suffix), unit="mm", weld_is_reading=suffix == ".stl")
for spent, faces, hit, chain in calls:
    print(f"{spent * 1000:7.1f} ms  {faces:8d}  {'Cache' if hit else 'neu  '}  {chain}")
print(f"zusammen {sum(call[0] for call in calls):.3f} s, neu gerechnet {sum(1 for call in calls if not call[2])}")
