"""Kanalfrage und Sperrraum eines Netzes bei gegebenem Stützwinkel, ohne Slicer.

Aufruf: python sonde_kanalraum.py <code-wurzel> <netz.stl> <winkel> [<bahnbreite>]

Schnitt wie die Übergabe (0,2 mm, ``detail="support"``), dann ``model_support``
und ``channel_space``: Kanalstücke, gesperrte Säulen, Sperrvolumen, Rat.
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
from app.core.slice.analysis import channel_space, model_support, slice_body  # noqa: E402

raw = trimesh.load(sys.argv[2], process=False)
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
angle = float(sys.argv[3])
line = float(sys.argv[4]) if len(sys.argv) > 4 else 0.42
started = time.perf_counter()
result = slice_body(
    MeshData.of(raw),
    0.2,
    first_layer_height=0.2,
    overhang_angle=angle,
    bridge_from=0.84,
    detail="support",
    support_volume=False,
)
need = advise.support_need(result)
model = need.model
slabs = channel_space(result, model, line)
volume = sum((top - bottom) * region.area for bottom, top, region in slabs)
print(
    f"{Path(sys.argv[2]).name} Winkel {angle}: Kanalstücke {len(model.channels)} "
    f"({model.channel_area:.1f} mm²), gesperrte Säulen {len(model.channel_columns)}, "
    f"Sperrraum {volume:.0f} mm³, Stützen nötig {need.needed}, "
    f"{time.perf_counter() - started:.0f} s"
)
