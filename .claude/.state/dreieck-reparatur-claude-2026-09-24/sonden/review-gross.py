"""Review-Sonde: Import und *Reparieren* (heutige Vorgaben) an großen Modellen — Stand jetzt.

Nachmessung von s22 am aktuellen Stand, mit den heutigen Funktionsnamen. Nur lesend.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import KUNDE, R, codes, facts  # noqa: E402

from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.geom.ops import RepairParams  # noqa: E402
from app.core.ingest import threemf  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402

print("repair.py", hashlib.sha1(Path(R.__file__).read_bytes()).hexdigest()[:8], flush=True)
defaults = RepairParams()
spent: dict[str, float] = defaultdict(float)
for name in (
    "merge_vertices", "remove_doubled_faces", "remove_degenerate_faces", "resolve_branching_edges",
    "stitch_t_junctions", "_filled_rounds", "unify_normals", "crossings_of",
    "_intersections_resolvable", "resolve_self_intersections", "parts_inside_parts",
    "remove_open_splinters",
):
    original = getattr(R, name)

    def timed(*args, _original=original, _name=name, **kwargs):
        start = time.perf_counter()
        try:
            return _original(*args, **kwargs)
        finally:
            spent[_name] += time.perf_counter() - start

    setattr(R, name, timed)

TARGETS = [
    ("broomholdervcd_d35mm.stl", None),
    ("3D Drucker/04_Community-Modelle/Gaehnende-Katze_Figur_material.3mf", "kitek ziewa"),
    ("spiderman+voronoi+bambu+10cm_stls/obj_1_spiderman.stl", None),
    ("pirate+ship+with+sails_stls/obj_15_Assembly.stl", None),
    ("Mausoleum Dragon.3mf", "Körper 1"),
]
out = Path(__file__).with_name("review-gross.jsonl").open("w", encoding="utf-8")
for rel, part in TARGETS:
    path = KUNDE / rel
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        mesh = next(o.mesh for o in threemf.read_objects(payload) if part is None or str(o.name) == part)
    else:
        mesh = read_mesh(payload, path.suffix.lower())
    spent.clear()
    start = time.perf_counter()
    imported = normalise(mesh, "mm", weld_is_reading=path.suffix.lower() == ".stl")
    t_import = time.perf_counter() - start
    import_steps = {key: round(value, 1) for key, value in spent.items() if value >= 0.05}
    mesh = imported.mesh
    spent.clear()
    start = time.perf_counter()
    result = R.repair(
        mesh,
        weld=defaults.weld,
        degenerate=defaults.degenerate,
        normals=defaults.normals,
        holes=defaults.fill_holes,
        small_components=defaults.small_components,
        self_intersections=defaults.self_intersections,
        inspect_intersections=True,
    )
    total = time.perf_counter() - start
    row = {
        "file": rel,
        "tri": mesh.triangle_count,
        "import_s": round(t_import, 1),
        "import_steps": import_steps,
        "import_codes": codes(imported.findings),
        "repair_s": round(total, 1),
        "steps": {key: round(value, 1) for key, value in spent.items() if value >= 0.05},
        "codes": codes(result.findings),
        "changed": result.changed,
        "after": facts(result.mesh),
    }
    out.write(json.dumps(row, ensure_ascii=False) + "\n")
    out.flush()
    print(row, flush=True)
