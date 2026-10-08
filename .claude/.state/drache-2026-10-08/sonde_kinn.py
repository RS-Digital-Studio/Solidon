"""Stützbedarf an einer schrägen Unterseite (Kinn): Streifen je Schicht und Decke.

Aufruf: python sonde_kinn.py <code-wurzel> [<unterseite an der wand> …]

Bau wie ``jaw_in_a_pocket`` aus ``tests/test_slice_findings.py``: Unterseite
steigt von der Wand bis 50 mm an der Spitze. Je Fall: Stücke, größtes Stück,
Summe, Decken mit Fläche und mittlerer Streifenbreite, Stützbedarf.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from shapely.geometry import Polygon as ShapelyPolygon  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.geom.transform import place_on_bed  # noqa: E402
from app.core.slice import advise, analysis  # noqa: E402
from app.core.slice.analysis import piece_area, slice_body  # noqa: E402


def brick(x, y, z, at):
    body = trimesh.creation.box(extents=(x, y, z))
    body.apply_translation(at)
    return body


def jaw(low: float) -> MeshData:
    head = trimesh.convex.convex_hull(
        [
            (x, y, z)
            for x in (-8.0, 8.0)
            for y, z in ((15.0, low), (-3.0, 50.0), (15.0, 56.0), (-3.0, 56.0))
        ]
    )
    parts = [
        brick(80.0, 60.0, 4.0, (0.0, 0.0, 2.0)),
        brick(40.0, 10.0, 60.0, (0.0, 20.0, 34.0)),
        brick(8.0, 30.0, 52.0, (-16.0, 0.0, 30.0)),
        brick(8.0, 30.0, 52.0, (16.0, 0.0, 30.0)),
        head,
    ]
    return place_on_bed(MeshData.of(trimesh.boolean.union(parts)))


for low in [float(value) for value in (sys.argv[2:] or ["44", "47"])]:
    result = slice_body(jaw(low), 0.2)
    need = advise.support_need(result)
    names = [
        (index, number)
        for index, layer in enumerate(result.layers)
        if low - 0.5 < layer.z < 51.0
        for number, piece in enumerate(layer.overhangs)
        if piece_area(piece) > 0.05
    ]
    layers = result.layers
    ceilings = analysis._Ceilings(layers, lambda index: analysis._material(layers[index]))
    groups = {ceilings.of(name) for name in names}
    print(
        f"Unterseite {low}: Stücke {len(names)}, größtes {need.patch:.1f} mm², "
        f"Summe {need.overhang:.1f} mm², nötig {need.needed}"
    )
    for group in sorted(groups, key=len, reverse=True)[:4]:
        shapes = [
            ShapelyPolygon(*(lambda c: (c.outline, c.holes))(layers[i].overhangs[n]))
            for i, n in group
        ]
        area = sum(shape.area for shape in shapes)
        length = sum(shape.length / 2.0 for shape in shapes)
        print(
            f"   Decke: {len(group)} Stücke, {area:.1f} mm², mittlere Streifenbreite {area / max(length, 1e-9):.3f} mm"
        )
