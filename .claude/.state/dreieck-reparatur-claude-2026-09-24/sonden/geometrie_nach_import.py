"""Sonde: Was liegt nach dem Import tatsächlich vor (Volumen, geschlossen, Durchdringungen)?"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.geom.repair import self_intersection_check  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402

for name in sys.argv[1:]:
    path = Path(name)
    raw = read_mesh(path.read_bytes(), path.suffix)
    mesh = raw if isinstance(raw, MeshData) else MeshData.of(raw)
    result = normalise(mesh, "mm", weld_is_reading=True)
    body = result.mesh.raw
    faces, complete = self_intersection_check(result.mesh, None)
    print(
        f"{path.name}: Dreiecke {len(body.faces)} geschlossen={body.is_watertight} "
        f"Volumen={float(body.volume):.2f} Teile={result.info.components} "
        f"Durchdringende Dreiecke={len(faces)} vollständig={complete}"
    )
    if len(faces):
        centres = np.asarray(body.triangles_center)[np.asarray(sorted(faces))[:6]]
        print("   Mitten:", np.round(centres, 2).tolist())
