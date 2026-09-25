"""Paarbudget an einzelnen Körpern (STL auf oberster Ebene), wie die Reparatur sie sieht."""

import time
from pathlib import Path

import trimesh

from app.core.geom.intersections import crossing_faces
from app.core.geom.repair import MAX_INTERSECTION_PAIRS

ROOT = Path(r"F:\3D Dateien")
paths = sorted(ROOT.glob("*.stl")) + sorted((ROOT / "pirate+ship+with+sails_stls").glob("*.stl"))[:3] + sorted((ROOT / "spiderman+voronoi+bambu+10cm_stls").glob("*.stl"))[:2]
for path in paths:
    loaded = trimesh.load(path, force="mesh")  # verschweißt wie der Import
    faces = len(loaded.faces)
    start = time.perf_counter()
    found, complete = crossing_faces(loaded.vertices, loaded.faces, None, max_pairs=MAX_INTERSECTION_PAIRS)
    first = time.perf_counter() - start
    line = f"{path.name[:48]:48s} {faces:>8d}  {'voll' if complete else 'ABBRUCH'} {len(found):>6d} Funde {first:6.2f}s"
    if not complete:
        start = time.perf_counter()
        full, _ = crossing_faces(loaded.vertices, loaded.faces, None, max_pairs=None)
        line += f" | ganz: {len(full):>6d} Funde {time.perf_counter() - start:6.2f}s"
    print(line, flush=True)
