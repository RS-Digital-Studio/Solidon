"""Welche STEP-Modelle in F:\\3D Dateien haben stehende Ringe (seitliche Bohrungen)?"""

import os
import sys
from pathlib import Path

TREE = os.getcwd()
sys.path.insert(0, TREE)
import math  # noqa: E402

from app.core.brep import edit, step  # noqa: E402
from app.core.geom.edges import edge_lie_of  # noqa: E402

for path in sorted(Path(r"F:\3D Dateien").glob("*.st*p")):
    try:
        solid = step.read(path.read_bytes())
        edges = edit.edges_of(solid)
    except Exception as error:  # noqa: BLE001 - Sonde
        print(path.name, "nicht lesbar:", type(error).__name__)
        continue
    rings = [e for e in edges if math.dist(e.direction, (0, 0, 0)) < 1e-6]
    lies = [edge_lie_of(e) for e in rings]
    print(f"{path.name}: Kanten {len(edges)}, Ringe {len(rings)}, stehend {lies.count('upright')}, "
          f"Volumen {solid.volume:.1f}")
