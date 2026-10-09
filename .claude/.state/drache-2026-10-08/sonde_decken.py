"""Welche Kanaldecken hat ein Modell, und wie sehen sie aus?

Aufruf: python sonde_decken.py <code-wurzel> <modell> [anzahl]

Je Kanaldecke (``_Ceilings.of``): Stücke, Fläche, größtes Stück, größte
Schichtsumme, Höhenbereich, Grundriss und Lage; dazu, ob sie sich selbst
schließt (``_Ceilings.closes``, fehlt in Ständen vor dem 08.10.2026).
Am CC2 mit PLA wie die Übergabe.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import trimesh  # noqa: E402
from shapely.ops import unary_union  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.export import writer  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.ingest.loader import read_local_payload, read_model  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.slice import analysis  # noqa: E402
from app.core.types import SceneObject  # noqa: E402

path = Path(sys.argv[2])
shown = int(sys.argv[3]) if len(sys.argv) > 3 else 12
if path.suffix.lower() == ".stl" and path.name.startswith("obj"):
    raw = trimesh.load(path, process=False)
else:
    raw = read_model(read_local_payload(path), path.suffix).raw
raw.apply_translation((0.0, 0.0, -raw.bounds[0][2]))
mesh = MeshData.of(raw)
entry = SceneObject(id="obj_1", name=path.stem, mesh=mesh)
profile = profiles.make_profile("centauri-carbon-2", "pla")
settings = print_settings.resolve(profile)
result = writer._body_analysis(entry, mesh, settings, profile, None, detail="full")
model = analysis.model_support(result)
layers = result.layers
ceilings = analysis._Ceilings(layers, lambda index: analysis._material(layers[index]))
closes = getattr(ceilings, "closes", None)
seen: set = set()
rows = []
for name in sorted(model.channels):
    if name in seen:
        continue
    group = ceilings.of(name)
    seen |= group
    shapes = [ceilings.shape(member) for member in group]
    low_x, low_y, high_x, high_y = unary_union(shapes).bounds
    per_layer: dict[int, float] = {}
    for member, shape in zip(group, shapes, strict=True):
        per_layer[member[0]] = per_layer.get(member[0], 0.0) + shape.area
    zs = [layers[member[0]].z for member in group]
    rows.append(
        {
            "pieces": len(group),
            "area": round(sum(shape.area for shape in shapes), 2),
            "biggest": round(max(shape.area for shape in shapes), 2),
            "layer_max": round(max(per_layer.values()), 1),
            "closes": None if closes is None else closes(frozenset(group)),
            "z": (round(min(zs), 1), round(max(zs), 1)),
            "size": (round(high_x - low_x, 1), round(high_y - low_y, 1)),
            "at": (round((low_x + high_x) / 2, 1), round((low_y + high_y) / 2, 1)),
        }
    )
rows.sort(key=lambda row: -row["area"])
print(f"{len(rows)} Kanaldecken, {sum(r['pieces'] for r in rows)} Stücke")
print("Größe der Decken (Stücke):", Counter(min(r["pieces"], 20) for r in rows).most_common(8))
for row in rows[:shown]:
    print(row)
print("Fläche gesamt", round(sum(r["area"] for r in rows), 1))
