"""Frei hängende Stücke außerhalb der Kanäle nach mittlerer Breite (Fläche durch halben Umfang).

Aufruf: python sonde_kanten.py <wurzel> <netz.stl> [<grenze mm> …]

Zeigt je Breitenklasse Zahl und Fläche, die größten Stücke mit Breite, und was der
Stützbedarf sagte, wenn Stücke unter einer Breitengrenze nicht zählten.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from shapely.geometry import Polygon as ShapelyPolygon  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.slice.analysis import piece_area, slice_body, worth_support  # noqa: E402

raw = trimesh.load(sys.argv[2], force="mesh", process=False)
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
limits = [float(value) for value in sys.argv[3:]] or [1.0, 1.5, 2.0, 3.0]
result = slice_body(MeshData.of(raw), 0.2)
need = advise.support_need(result)
channels = need.model.channels
pieces = []
for index, layer in enumerate(result.layers):
    for number, piece in enumerate(layer.overhangs):
        if (index, number) in channels:
            continue
        shape = ShapelyPolygon(piece.outline, piece.holes)
        area = piece_area(piece)
        width = area / max(shape.length / 2.0, 1e-9)
        pieces.append((area, width, layer.z))
print(f"Stützen nötig {need.needed}, Summe ohne Kanäle {need.overhang:.1f}, Feld {need.patch:.1f}")
for area, width, z in sorted(pieces, reverse=True)[:10]:
    print(f"  {area:7.1f} mm²  Breite {width:5.2f} mm  z {z:6.2f}")
for limit in limits:
    kept = [(area, width) for area, width, _z in pieces if width >= limit]
    total = math.fsum(area for area, _width in kept)
    largest = max((area for area, _width in kept), default=0.0)
    print(
        f"ab Breite {limit:3.1f} mm: {len(kept)} Stücke, Summe {total:7.1f}, größtes {largest:6.1f}, "
        f"worth_support {worth_support(largest, total)}"
    )
