"""S4: Radiusreihe — misst die Bohrungserkennung systematisch zu klein?"""

import math
import _iso  # noqa: F401

import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive import features as pf

detect_holes = getattr(pf, "detect_holes", None)
forget = getattr(pf, "forget_cache", None)
print("detect_holes:", detect_holes is not None, "forget_cache:", forget is not None)

rows = [(5.2, 16), (5.2, 24), (5.2, 48), (15.0, 16), (30.0, 16), (30.0, 24), (50.0, 32), (5.2, 8), (5.2, 12)]
for d, n in rows:
    box = trimesh.creation.box(extents=(90.0, 90.0, 8.0))
    cyl = trimesh.creation.cylinder(radius=d / 2, height=20.0, sections=n)
    body = trimesh.boolean.difference([box, cyl], engine="manifold")
    if forget:
        try:
            forget()
        except Exception:  # noqa: BLE001
            pass
    holes = detect_holes(MeshData.of(body)) if detect_holes else []
    holes = list(holes.values()) if isinstance(holes, dict) else list(holes)
    if not holes:
        print(f"Soll Ø{d} n={n}: KEINE Bohrung erkannt")
        continue
    h = holes[0]
    dia = getattr(h, "diameter", None)
    if dia is None:
        p = getattr(h, "params", {}) or {}
        dia = p.get("diameter") or (2 * p["radius"] if "radius" in p else None)
    formula = d * math.sqrt(5 + 4 * math.cos(2 * math.pi / n)) / 3
    print(f"Soll Ø{d} n={n}: gemessen {dia:.4f}  Abweichung {dia - d:+.4f}  Formel {formula:.4f}  Inkreis {d*math.cos(math.pi/n):.4f}")
