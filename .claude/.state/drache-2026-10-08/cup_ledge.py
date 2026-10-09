"""Sonde zum Nachtrag „im umschlossenen Raum nichts aussparen“: ein offener
Becher mit Kanal und Sims darin.

Aufruf: python cup_ledge.py <code-wurzel> [winkel]

Becher Ø 80 mm, innen Ø 68 mm, Boden 4 mm, 60 mm hoch, oben offen. Innen an der
Wand ein Block mit einem Tunnel von 8 mm Weite (Decke 8 x 16 mm auf 20 mm Höhe:
Kanal, stützwürdig, gesperrt). An der Seite des Blocks ein Sims 14 x 14 mm auf
15 mm Höhe, 6 mm vom Tunnel — stützwürdig, über dem Becherboden. Der Becher ist
oben offen, eine Stütze unter dem Sims ist erreichbar; in jedem waagerechten
Schnitt ist sein Inneres aber ein Loch der Fläche.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from shapely.geometry import box  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import advise, analysis  # noqa: E402
from app.core.slice.analysis import model_support, slice_body  # noqa: E402


def brick(extents, centre):
    body = trimesh.creation.box(extents=extents)
    body.apply_translation(centre)
    return body


def cup() -> MeshData:
    outer = trimesh.creation.cylinder(radius=40.0, height=60.0, sections=96)
    outer.apply_translation((0.0, 0.0, 30.0))
    inner = trimesh.creation.cylinder(radius=34.0, height=60.0, sections=96)
    inner.apply_translation((0.0, 0.0, 34.0))
    shell = trimesh.boolean.difference([outer, inner])
    block = brick((22.0, 16.0, 30.0), (25.0, 0.0, 19.0))
    tunnel = brick((8.0, 30.0, 16.0), (24.0, 0.0, 12.0))
    ledge = brick((14.0, 14.0, 3.0), (7.0, 0.0, 16.5))
    body = trimesh.boolean.union([shell, trimesh.boolean.difference([block, tunnel]), ledge])
    return MeshData.of(body)


angle = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
result = slice_body(cup(), 0.2, overhang_angle=angle)
model = model_support(result)
try:
    slabs = analysis.channel_space(result, model, 0.42)
except TypeError:  # alter Stand
    slabs = analysis.channel_space(result, model)
ledge = box(0.0, -7.0, 14.0, 7.0)
covered = []
for z in (5.0, 10.0, 14.5):
    regions = [region for low, high, region in slabs if low <= z <= high]
    part = unary_union(regions).intersection(ledge).area / ledge.area if regions else 0.0
    covered.append(f"z {z:4.1f}: {part:.0%}")
need = advise.support_need(result)
print(
    f"{ROOT.name} Winkel {angle:.0f}: Kanalstücke {len(model.channels)}, "
    f"gesperrt {len(model.channel_columns)}, ausgespart {len(model.open_columns)} + "
    f"{len(getattr(model, 'bed_columns', ()))}, Stütze nötig {need.needed}; "
    f"Grundriss des Simses im Sperrraum: {', '.join(covered)}",
    flush=True,
)
