"""Sonde 22: *Reparieren* mit den heutigen Vorgaben der Operation an großen Modellen — Gesamtzeit und Schritte."""

from __future__ import annotations

import hashlib
import json
import time
from collections import defaultdict
from pathlib import Path

from common import KUNDE, R, codes, facts

from app.core.geom.mesh import read_mesh
from app.core.geom.ops import RepairParams
from app.core.ingest import threemf
from app.core.ingest.loader import normalise

print("repair.py", hashlib.sha1(Path(R.__file__).read_bytes()).hexdigest()[:8], flush=True)
defaults = RepairParams()
spent: dict[str, float] = defaultdict(float)
for name in ("merge_vertices", "remove_doubled_faces", "remove_degenerate_faces", "resolve_branching_edges",
             "stitch_t_junctions", "_filled_rounds", "unify_normals", "self_intersection_check",
             "resolve_self_intersections"):
    original = getattr(R, name)

    def timed(*args, _original=original, _name=name, **kwargs):
        t0 = time.perf_counter()
        try:
            return _original(*args, **kwargs)
        finally:
            spent[_name] += time.perf_counter() - t0

    setattr(R, name, timed)

TARGETS = [
    ("broomholdervcd_d35mm.stl", None),
    ("3D Drucker/04_Community-Modelle/Gaehnende-Katze_Figur_material.3mf", "kitek ziewa"),
    ("spiderman+voronoi+bambu+10cm_stls/obj_1_spiderman.stl", None),
    ("pirate+ship+with+sails_stls/obj_15_Assembly.stl", None),
    ("Mausoleum Dragon.3mf", "Körper 1"),
]
out = Path(__file__).with_name("s22.jsonl").open("w", encoding="utf-8")
for rel, part in TARGETS:
    path = KUNDE / rel
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        mesh = next(o.mesh for o in threemf.read_objects(payload) if part is None or str(o.name) == part)
    else:
        mesh = read_mesh(payload, path.suffix.lower())
    t0 = time.perf_counter()
    mesh = normalise(mesh, "mm", weld_is_reading=path.suffix.lower() == ".stl").mesh
    t_import = time.perf_counter() - t0
    spent.clear()
    t0 = time.perf_counter()
    result = R.repair(
        mesh,
        weld=defaults.weld, degenerate=defaults.degenerate, normals=defaults.normals,
        holes=defaults.fill_holes, small_components=defaults.small_components,
        self_intersections=defaults.self_intersections, inspect_intersections=True,
    )
    total = time.perf_counter() - t0
    row = {"file": rel, "tri": mesh.triangle_count, "import_s": round(t_import, 1), "repair_s": round(total, 1),
           "steps": {k: round(v, 1) for k, v in spent.items() if v >= 0.05}, "codes": codes(result.findings),
           "changed": result.changed, "after": facts(result.mesh)}
    out.write(json.dumps(row, ensure_ascii=False) + "\n"); out.flush()
    print(row, flush=True)
