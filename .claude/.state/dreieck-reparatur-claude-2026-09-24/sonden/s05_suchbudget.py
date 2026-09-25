"""Sonde 5: Kandidatenbudget der Durchdringungssuche an echten Modellen.

Je Körper: Plan, Zahl der Sweep-Paare insgesamt (das Budget zählt diese),
Zeit mit Budget (2 Mio.) und ohne Budget, gefundene Dreiecke.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

from common import KUNDE, R

from app.core.geom import intersections as X
from app.core.geom.mesh import read_mesh
from app.core.ingest import threemf
from app.core.ingest.loader import normalise

TARGETS = [
    ("3D Drucker/13_Besteckkorb_Abtropfkorb/Modular/Besteckkorb_Modular.3mf", "Modul B · Mitte links"),
    ("3D Drucker/13_Besteckkorb_Abtropfkorb/Besteckkorb_PETG-PRO-Grau.3mf", "Besteckkorb"),
    ("3D Drucker/04_Community-Modelle/Screen-Cover_Elegoo-CC2_STL/Screen-Cover_RS.3mf", "Cover (schwarz)"),
    ("3D Drucker/04_Community-Modelle/rasenrotor_alle_1.3mf", "main"),
    ("drill-holder.3mf", "Körper 1"),
    ("3D Drucker/15_CC2-Werkzeugbox/CC2-Werkzeugbox_Druckbereit.3mf", "Kofferschale B"),
]


def body_of(rel: str, part: str):
    path = KUNDE / rel
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        for obj in threemf.read_objects(payload):
            if str(obj.name) == part:
                return obj.mesh
        raise LookupError(part)
    return read_mesh(payload, path.suffix.lower())


def main(targets) -> None:
    for rel, part in targets:
        mesh = normalise(body_of(rel, part), "mm", weld_is_reading=rel.lower().endswith(".stl")).mesh
        surface = X._surface(mesh.raw.vertices, mesh.raw.faces)
        t0 = time.perf_counter()
        plan = X._plan(surface.low, surface.high)
        t_plan = time.perf_counter() - t0
        entries = X._entries(surface.low, surface.high, plan) or X._entries(
            surface.low, surface.high, X._Plan(plan.axis)
        )
        total_pairs = int(entries.counts.sum())
        simple = [int(X._entries(surface.low, surface.high, X._Plan(a)).counts.sum()) for a in range(3)]
        t0 = time.perf_counter()
        limited, complete = X.crossing_faces(mesh.raw.vertices, mesh.raw.faces, max_pairs=R.MAX_INTERSECTION_PAIRS)
        t_lim = time.perf_counter() - t0
        t0 = time.perf_counter()
        full, _ = X.crossing_faces(mesh.raw.vertices, mesh.raw.faces)
        t_full = time.perf_counter() - t0
        extents = mesh.raw.extents
        edges = np.linalg.norm(np.roll(mesh.raw.triangles, -1, axis=1) - mesh.raw.triangles, axis=2).max(axis=1)
        print(
            f"{rel} | {part}: tri={mesh.triangle_count} extents={np.round(extents,1).tolist()} "
            f"längste Kante median={np.median(edges):.2f} p90={np.percentile(edges,90):.2f}\n"
            f"   Plan={plan} ({t_plan:.2f}s) Sweep-Paare={total_pairs:,} (einfach je Achse {simple})\n"
            f"   mit Budget: {len(limited)} Dreiecke, vollständig={complete}, {t_lim:.2f}s | "
            f"ohne Budget: {len(full)} Dreiecke, {t_full:.2f}s"
        )
        sys.stdout.flush()


if __name__ == "__main__":
    main(TARGETS)
