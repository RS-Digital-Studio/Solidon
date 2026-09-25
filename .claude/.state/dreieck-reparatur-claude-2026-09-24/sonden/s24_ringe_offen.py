"""Sonde 24: Warum bleiben Ringe am aktuellen Stand offen? (Katze, Flaschenhalter) — je Ring: Ohren/Fächer/Faltung/Kanten."""
import hashlib
from pathlib import Path
import numpy as np
from common import KUNDE, R, MeshData, facts
from app.core import units
from app.core.ingest import threemf
from app.core.ingest.loader import normalise

print("repair.py", hashlib.sha1(Path(R.__file__).read_bytes()).hexdigest()[:8])
for rel, part in (("3D Drucker/04_Community-Modelle/Flaschenhalter_4er_material.3mf", "Bottle-holder-v3 v5"),
                  ("3D Drucker/04_Community-Modelle/Gaehnende-Katze_Figur_material.3mf", "kitek ziewa")):
    obj = next(o for o in threemf.read_objects((KUNDE / rel).read_bytes()) if str(o.name) == part)
    mesh = normalise(obj.mesh, "mm").mesh
    split, rings = R._hole_rings(mesh)
    points = np.asarray(split.raw.vertices, dtype=float)
    table = R._edge_table(split)
    existing = {tuple(e): int(c) for e, c in zip(table.unique.tolist(), table.counts.tolist())}
    print(f"{part}: {facts(mesh)} Ringe={len(rings)} Längen={[len(r) for r in rings]}")
    for ring in rings:
        corners = points[ring]
        centre = np.asarray(units.exact_centre(corners.tolist()), dtype=np.float64)
        normal = R._ring_normal(corners, centre)
        span = float(np.ptp(corners @ (normal if normal is not None else np.array([0, 0, 1.0]))))
        size = float(np.linalg.norm(np.ptp(corners, axis=0)))
        reach = np.vstack([points, centre[None, :]])
        out = []
        for label, attempt in (("Ohren", R._loop_triangles(points, ring)), ("Fächer", R._loop_fan(ring, len(points)))):
            if not len(attempt) or normal is None:
                out.append(f"{label}: leer/ohne Normale"); continue
            clash = sum(1 for p in attempt.tolist() for i in range(3)
                        if existing.get((min(p[i], p[(i+1)%3]), max(p[i], p[(i+1)%3])), 0) >= 2)
            out.append(f"{label}: {len(attempt)} Dr., belegt={clash}, faltet={R._folds(reach[attempt], normal)}")
        print(f"   Ring {len(ring)}: Ausdehnung {size:.2f} mm, Unebenheit {span:.3f} mm; " + " | ".join(out))
