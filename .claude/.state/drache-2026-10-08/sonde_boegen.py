"""Offene Decken: schließen sie sich (Bogen, Brücke) oder kragen sie aus, wie weit ragen sie,
und welche Brückenweite steckt in ihren Schichten?

Aufruf: python sonde_boegen.py <wurzel> <netz.stl> [<anzahl>]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import shapely  # noqa: E402
import trimesh  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import advise, analysis  # noqa: E402

raw = trimesh.load(sys.argv[2], force="mesh", process=False)
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
count = int(sys.argv[3]) if len(sys.argv) > 3 else 12
result = analysis.slice_body(MeshData.of(raw), 0.2)
need = advise.support_need(result)
channels = need.model.channels
layers = result.layers
materials: dict[int, object] = {}


def material(index: int):  # type: ignore[no-untyped-def]
    if index not in materials:
        materials[index] = analysis._material(layers[index])
    return materials[index]


ceilings = analysis._Ceilings(layers, material)
seen: set[tuple[int, int]] = set()
rows = []
started = time.perf_counter()
for index, layer in enumerate(layers):
    for number in range(len(layer.overhangs)):
        name = (index, number)
        if name in seen or name in channels or ceilings.floats(name):
            continue
        group = ceilings.of(name)
        seen |= group
        members = frozenset(group - channels)
        field = unary_union([ceilings.shape(member) for member in members])
        if field.area < 5.0:
            continue
        low = min(member[0] for member in members)
        root = material(max(low - 1, 0))
        points = shapely.points(shapely.get_coordinates(field.boundary))
        reach = float(shapely.distance(points, root).max()) if len(points) else 0.0
        closes = ceilings.closes(members)
        bridge = max(layers[member[0]].bridge_width for member in members)
        rows.append((field.area, reach, closes, bridge, layers[low].z, len(members)))
print(
    f"Stützen nötig {need.needed}, Feld {need.patch:.1f}, Summe {need.overhang:.1f}, "
    f"{time.perf_counter() - started:.1f} s"
)
for area, reach, closes, bridge, z, pieces in sorted(rows, reverse=True)[:count]:
    print(
        f"  Feld {area:7.1f} mm²  Reichweite {reach:5.2f}  schließt {closes!s:5}  "
        f"Brücke {bridge:5.1f} mm  ab z {z:6.2f}  Stücke {pieces}"
    )
