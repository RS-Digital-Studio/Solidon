"""Warum schließt (oder nicht) die Decke über einem Punkt? Haltefrage einzeln.

Aufruf: python sonde_gewoelbe.py <wurzel> <netz.stl> <winkel> <x> <y> <z>
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from shapely.geometry import Point  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import analysis  # noqa: E402

raw = trimesh.load(sys.argv[2], process=False)
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
result = analysis.slice_body(
    MeshData.of(raw), 0.2, first_layer_height=0.2, overhang_angle=float(sys.argv[3]),
    bridge_from=0.84, detail="support", support_volume=False,
)
x, y, z = (float(value) for value in sys.argv[4:7])
layers = result.layers
index = min(range(len(layers)), key=lambda number: abs(layers[number].z - z))
ceilings = analysis._Ceilings(layers, lambda number: analysis._material(layers[number]))
target = Point(x, y)
name = min(
    ((index, number) for number in range(len(layers[index].overhangs))),
    key=lambda candidate: ceilings.shape(candidate).distance(target),
)
group = ceilings.of(name)
shapes = [ceilings.shape(member) for member in group]
print(f"Stück {name} z {layers[index].z:.2f}, Decke {len(group)} Stücke, {sum(s.area for s in shapes):.1f} mm²")
print("schließt:", ceilings.closes(group))
footprint = unary_union(shapes)
print("Grundriss", footprint.bounds, "Teile", len(getattr(footprint, "geoms", [footprint])))
