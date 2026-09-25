import sys, time; sys.path.insert(0, r"F:\3D Druck")
from pathlib import Path
from collections import Counter
import numpy as np
from app.core.ingest import threemf
from app.core.ingest.loader import normalise
from app.core.geom.repair import repair, open_edge_count, branching_edge_count, self_intersection_check
from app.core.perceive.features import detect, forget_cache
parts = threemf.read_objects(Path(r"F:\3D Dateien\Blessed+Family+–+Heart+Script+Decor.3mf").read_bytes(), [])
raw = parts[0].mesh
plain = normalise(raw, "mm", mend=False)
mended = normalise(raw, "mm")
fixed = repair(plain.mesh)
for label, mesh, finds in (("ohne Flicken", plain.mesh, plain.findings), ("Import", mended.mesh, mended.findings), ("Reparatur", fixed.mesh, fixed.findings)):
    forget_cache(); t = time.perf_counter(); f = detect(mesh); took = time.perf_counter() - t
    s, c = self_intersection_check(mesh)
    print(f"{label}: tri={mesh.triangle_count} open={open_edge_count(mesh)} branch={branching_edge_count(mesh)} wt={mesh.is_watertight} parts={mesh.component_count} vol={mesh.volume:.2f} Durchdringungen={len(s)}/{c} ({took:.2f}s)")
    print("   Befunde", [x.code for x in finds])
    print("   Arten", dict(Counter(v.kind for v in f.values())))
