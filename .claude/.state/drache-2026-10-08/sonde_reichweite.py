"""Wie weit ragt jede offene Decke über das Material, an dem sie ansetzt?

Aufruf: python sonde_reichweite.py <wurzel> <netz.stl> [<anzahl>]

Je Decke (``_Ceilings.of``, ohne Kanalstücke): Feld (Streifen vereinigt), Wurzel =
Material der Schicht unter ihrem untersten Stück, Reichweite = größter Abstand eines
Feldpunkts von der Wurzel (an den Eckpunkten des Felds gemessen). Dazu die Fläche,
die weiter als 1, 2 und 3 mm von der Wurzel liegt.
"""

from __future__ import annotations

import sys
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
for index, layer in enumerate(layers):
    for number in range(len(layer.overhangs)):
        name = (index, number)
        if name in seen or name in channels or ceilings.floats(name):
            continue
        group = ceilings.of(name)
        seen |= group
        members = sorted(group - channels)
        field = unary_union([ceilings.shape(member) for member in members])
        low = min(member[0] for member in members)
        root = material(max(low - 1, 0))
        points = shapely.points(shapely.get_coordinates(field.boundary))
        reach = float(shapely.distance(points, root).max()) if len(points) else 0.0
        far = [field.difference(root.buffer(limit)).area for limit in (1.0, 2.0, 3.0)]
        rows.append((field.area, reach, far, layers[low].z, len(members)))
print(f"Stützen nötig {need.needed}, Feld {need.patch:.1f}, Summe {need.overhang:.1f}")
for area, reach, far, z, pieces in sorted(rows, reverse=True)[:count]:
    print(
        f"  Feld {area:7.1f} mm²  Reichweite {reach:5.2f} mm  jenseits 1/2/3 mm "
        f"{far[0]:6.1f}/{far[1]:6.1f}/{far[2]:6.1f}  ab z {z:6.2f}  Stücke {pieces}"
    )
