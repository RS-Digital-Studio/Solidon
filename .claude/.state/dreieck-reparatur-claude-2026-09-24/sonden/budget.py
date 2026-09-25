"""Wie oft reißt das Paarbudget der Durchdringungssuche an echten Modellen?"""

import sys
import time
from pathlib import Path

import trimesh

from app.core.geom.intersections import crossing_faces
from app.core.geom.repair import MAX_INTERSECTION_PAIRS

ROOT = Path(r"F:\3D Dateien")
files = sorted(p for p in ROOT.rglob("*") if p.suffix.lower() in {".stl", ".3mf"})[: int(sys.argv[1]) if len(sys.argv) > 1 else 60]
for path in files:
    try:
        loaded = trimesh.load(path, force="mesh", process=False)
    except Exception as problem:  # noqa: BLE001
        print(f"{path.name}: nicht lesbar {problem}")
        continue
    faces = len(loaded.faces)
    if faces > 3_000_000:
        print(f"{path.name}: {faces} Dreiecke übersprungen")
        continue
    start = time.perf_counter()
    found, complete = crossing_faces(loaded.vertices, loaded.faces, None, max_pairs=MAX_INTERSECTION_PAIRS)
    budget = time.perf_counter() - start
    line = f"{path.name[:50]:50s} {faces:>9d} Dreiecke  Budget: {'vollständig' if complete else 'ABGEBROCHEN'} {len(found):>6d} Funde {budget:6.2f}s"
    if not complete:
        start = time.perf_counter()
        full, _ = crossing_faces(loaded.vertices, loaded.faces, None, max_pairs=None)
        line += f"  | ohne Budget {len(full):>6d} Funde {time.perf_counter() - start:6.2f}s"
    print(line, flush=True)
