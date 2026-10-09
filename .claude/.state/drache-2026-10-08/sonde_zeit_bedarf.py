"""Wie lange fragt ``support_need`` an einem Netz — gesamt und in grober Suchauflösung?

Aufruf: python sonde_zeit_bedarf.py <code-wurzel> <netz.stl>

Schnitt mit 0,2 mm (Druckdialog) und mit 1,0 mm (Orientierungssuche, grob),
je dreimal gefragt; gemessen wird ohne den Schnitt.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.slice.analysis import slice_body  # noqa: E402

raw = trimesh.load(sys.argv[2], process=False)
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
mesh = MeshData.of(raw)
for step in (0.2, 1.0):
    result = slice_body(mesh, step, overhang_angle=60.0, detail="support", support_volume=False)
    times = []
    for _ in range(3):
        started = time.perf_counter()
        need = advise.support_need(result)
        times.append(time.perf_counter() - started)
    print(
        f"{Path(sys.argv[2]).name} Schicht {step}: nötig {need.needed}, Feld {need.patch:.1f}, "
        f"Zeit {min(times):.2f} s (erste {times[0]:.2f} s)"
    )
