import sys, time; sys.path.insert(0, r"F:\3D Druck")
from pathlib import Path
from app.core.ingest import threemf
from app.core.ingest.loader import normalise, read_model
from app.core.geom.repair import repair
for label, mesh in (
    ("Drache", normalise(threemf.read_objects(Path(r"F:\3D Dateien\Mausoleum Dragon.3mf").read_bytes(), [])[0].mesh, "mm").mesh),
    ("Gartenschlauchhalter", normalise(threemf.read_objects(Path(r"F:\3D Dateien\garden-hose-holder.3mf").read_bytes(), [])[0].mesh, "mm").mesh),
):
    for inspect in (False, True):
        t = time.perf_counter()
        r = repair(mesh, inspect_intersections=inspect)
        print(f"{label} ({mesh.triangle_count} △) Prüfung={inspect}: {time.perf_counter()-t:.1f}s changed={r.changed} {[f.code for f in r.findings]}")
