"""Sonde 12: Was kostet die vollständige Durchdringungsprüfung je Modellgröße?

Je Körper: rohe Sweep-Paare (zählt das heutige Budget), gefilterte
Kandidatenpaare (nach den zwei anderen Achsen, das ist die echte Arbeit),
Zeit mit Budget 2 Mio., Zeit ohne Budget, Zahl der Schnittdreiecke. Schreibt
eine Zeile JSON je Körper nach s12.jsonl.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from common import KUNDE

from app.core.geom import intersections as X
from app.core.geom import repair as R
from app.core.geom.mesh import read_mesh
from app.core.ingest import threemf
from app.core.ingest.loader import normalise

OUT = Path(__file__).with_name("s12.jsonl")
TARGETS = [
    ("3D Drucker/13_Besteckkorb_Abtropfkorb/Modular/Besteckkorb_Modular.3mf", "Modul B · Mitte links"),
    ("broomholdervcd_d35mm.stl", None),
    ("tree_no_tray_stl.stl", None),
    ("pirate+ship+with+sails_stls/obj_5_ship sails 3d model.stl_8.stl", None),
    ("spiderman+voronoi+bambu+10cm_stls/obj_1_spiderman.stl", None),
    ("pirate+ship+with+sails_stls/obj_15_Assembly.stl", None),
    ("Mausoleum Dragon.3mf", "Körper 1"),
]


def body_of(rel: str, part: str | None):
    path = KUNDE / rel
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        for obj in threemf.read_objects(payload):
            if part is None or str(obj.name) == part:
                return obj.mesh
        raise LookupError(part)
    return read_mesh(payload, path.suffix.lower())


with OUT.open("w", encoding="utf-8") as sink:
    for rel, part in TARGETS:
        mesh = normalise(body_of(rel, part), "mm", weld_is_reading=rel.lower().endswith(".stl")).mesh
        n = mesh.triangle_count
        surface = X._surface(mesh.raw.vertices, mesh.raw.faces)
        t0 = time.perf_counter()
        plan = X._plan(surface.low, surface.high)
        t_plan = time.perf_counter() - t0
        entries = X._entries(surface.low, surface.high, plan) or X._entries(
            surface.low, surface.high, X._Plan(plan.axis)
        )
        sweep = int(entries.counts.sum())
        t0 = time.perf_counter()
        filtered = sum(len(first) for first, _second in X._candidates(surface, None, X._Search(), plan))
        t_cand = time.perf_counter() - t0
        t0 = time.perf_counter()
        _lim, complete = X.crossing_faces(mesh.raw.vertices, mesh.raw.faces, max_pairs=R.MAX_INTERSECTION_PAIRS)
        t_lim = time.perf_counter() - t0
        t0 = time.perf_counter()
        full, _ = X.crossing_faces(mesh.raw.vertices, mesh.raw.faces)
        t_full = time.perf_counter() - t0
        row = {
            "file": rel, "tri": n, "plan": repr(plan), "plan_s": round(t_plan, 2),
            "sweep_pairs": sweep, "filtered_pairs": filtered, "candidates_s": round(t_cand, 2),
            "limited_complete": complete, "limited_found": len(_lim), "limited_s": round(t_lim, 2),
            "full_found": len(full), "full_s": round(t_full, 2),
            "sweep_per_tri": round(sweep / n, 1), "filtered_per_tri": round(filtered / n, 1),
            "us_per_filtered_pair": round(1e6 * t_full / max(filtered, 1), 3),
        }
        sink.write(json.dumps(row, ensure_ascii=False) + "\n")
        sink.flush()
        print(row, flush=True)
