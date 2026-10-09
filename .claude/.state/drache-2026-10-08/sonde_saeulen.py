"""Wo liegen die gesperrten Kanalsäulen? Je Säule Fläche, Höhe, Landung, Lage.

Aufruf: python sonde_saeulen.py <code-wurzel> <netz.stl> <winkel>
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from shapely.geometry import Polygon as ShapelyPolygon  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice.analysis import model_support, piece_area, slice_body  # noqa: E402

raw = trimesh.load(sys.argv[2], process=False)
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
result = slice_body(
    MeshData.of(raw),
    0.2,
    first_layer_height=0.2,
    overhang_angle=float(sys.argv[3]),
    bridge_from=0.84,
    detail="support",
    support_volume=False,
)
model = model_support(result)
for outline, low, high in sorted(model.channel_columns, key=lambda column: column[2]):
    shape = ShapelyPolygon(outline.outline, outline.holes)
    x0, y0, x1, y1 = shape.bounds
    print(
        f"z {high:6.1f} Landung {low:6.1f} Fläche {piece_area(outline):6.2f} "
        f"x {x0:7.1f}..{x1:7.1f} y {y0:7.1f}..{y1:7.1f}"
    )
