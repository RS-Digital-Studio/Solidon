"""Die größten frei hängenden Überhangstücke außerhalb der Kanäle: Ort, Höhe, Fläche, Auflage.

Aufruf: python sonde_offene_stuecke.py <wurzel> <netz.stl> [<anzahl>]
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from shapely.geometry import Polygon as ShapelyPolygon  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.slice.analysis import piece_area, slice_body  # noqa: E402

raw = trimesh.load(sys.argv[2], force="mesh", process=False)
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
count = int(sys.argv[3]) if len(sys.argv) > 3 else 12
result = slice_body(MeshData.of(raw), 0.2)
need = advise.support_need(result)
model = need.model
print(f"Körper {raw.bounds.round(1).tolist()}, Stützen nötig {need.needed}, Feld {need.patch:.1f}")
pieces = []
for index, layer in enumerate(result.layers):
    for number, piece in enumerate(layer.overhangs):
        name = (index, number)
        if name in model.channels:
            continue
        shape = ShapelyPolygon(piece.outline, piece.holes)
        where = "Modell" if name in model.open_pieces else "Bett/Insel"
        pieces.append((piece_area(piece), layer.z, shape.bounds, where))
for area, z, bounds, where in sorted(pieces, reverse=True)[:count]:
    print(
        f"{area:7.1f} mm²  z {z:6.2f}  x {bounds[0]:6.1f}…{bounds[2]:6.1f}  y {bounds[1]:6.1f}…{bounds[3]:6.1f}  {where}"
    )
