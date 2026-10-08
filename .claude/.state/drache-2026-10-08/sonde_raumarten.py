"""Welche Art Raum sperrt die Kanalsperre je Scheibe? Frei, eng, Loch (umschlossen).

Aufruf: python sonde_raumarten.py <wurzel> <netz.stl> <winkel>
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from shapely.geometry import Polygon as ShapelyPolygon  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import analysis  # noqa: E402

raw = trimesh.load(sys.argv[2], process=False)
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
result = analysis.slice_body(
    MeshData.of(raw),
    0.2,
    first_layer_height=0.2,
    overhang_angle=float(sys.argv[3]),
    bridge_from=0.84,
    detail="support",
    support_volume=False,
)
model = analysis.model_support(result)
layers = result.layers
columns = model.channel_columns
footprints = [ShapelyPolygon(item.outline, item.holes) for item, _l, _h in columns]
lows = [low for _o, low, _h in columns]
highs = [high for _o, _l, high in columns]
for z in range(int(min(lows)) + 1, int(max(highs)) + 1, 4):
    active = [
        shape for shape, low, high in zip(footprints, lows, highs, strict=True) if low <= z <= high
    ]
    if not active:
        continue
    index = min(range(len(layers)), key=lambda number: abs(layers[number].z - z))
    material = analysis._material(layers[index])
    reach = unary_union([shape.buffer(analysis.CHANNEL_WIDTH / 2.0) for shape in active])
    free = reach.intersection(material.convex_hull).difference(material)
    narrow = analysis._narrow(material, reach.bounds)
    holes = unary_union(
        [ShapelyPolygon(ring) for part in analysis._areas_of(material) for ring in part.interiors]
    ).difference(material)
    print(
        f"z {z:3d}: frei {free.area:7.0f}  eng {free.intersection(narrow).area:7.0f}  "
        f"Loch {free.intersection(holes).area:7.0f}"
    )
