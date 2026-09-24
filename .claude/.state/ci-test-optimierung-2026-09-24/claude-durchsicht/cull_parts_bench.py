"""Wandmessung an allen Bausteinen: Vollvergleich gegen Vorauswahl je Einstellung."""

from __future__ import annotations

import sys
import time

sys.path.insert(0, r"F:\3D Druck")

import numpy as np
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom import mesh as m
from app.core.knowledge.parts.registry import PARTS
from app.core.units import EPS_GEOM

load_operations()
settings = [tuple(float(p) for p in value.split(":")) for value in sys.argv[1:]] or [(2.0, 2.0)]


def rays(body):
    return (
        np.asarray(body.triangles, dtype=float),
        np.asarray(body.triangles_center, dtype=float),
        -np.asarray(body.face_normals, dtype=float),
    )


cases = []
for spec in [s for s in PARTS.all() if s.name in {'printed_nut', 'printed_screw', 'printed_thread', 'fit_ladder', 'seal_gasket'}]:
    body = spec.fn(spec.params()).mesh.raw
    cases.append((spec.name, body))
for subdivisions in (4, 5):
    cases.append((f"kugel{subdivisions}", trimesh.creation.icosphere(subdivisions, radius=10.0)))
from tests.test_seal_geometry import path  # noqa: E402
from app.core.geom.seal import seal_geometry  # noqa: E402

for height in (1.2, 12.0):
    cases.append(
        (
            f"dichtschnur{height}",
            seal_geometry(path(), groove_width=height, groove_depth=height, protrusion=0,
                          gasket_width=height, section="round", offset=5).gasket.raw,
        )
    )

totals = {"voll": 0.0, **{f"{g:g}:{c:g}": 0.0 for g, c in settings}}
for name, body in cases:
    triangles, origins, directions = rays(body)
    pairs = len(triangles) * len(origins)
    row = [f"{name:22s} {len(triangles):6d}"]
    reference = None
    if len(triangles) <= 21000:
        started = time.perf_counter()
        reference = m._nearest_ray_hits(triangles, origins, directions, EPS_GEOM,
                                        EPS_GEOM * 100.0, None)
        seconds = time.perf_counter() - started
        totals["voll"] += seconds
        row.append(f"voll {seconds:6.2f}")
    for growth, shift in settings:
        m.RAY_CULL_GROWTH = growth
        m.RAY_CULL_CELL_SHIFT = int(shift)
        value = f"{growth:g}:{shift:g}"
        started = time.perf_counter()
        result = m.ray_hits_batch(triangles, origins, directions, edge_margin=EPS_GEOM,
                                  minimum_travel=EPS_GEOM * 100.0)
        seconds = time.perf_counter() - started
        totals[value] += seconds
        same = "" if reference is None else (
            "=" if np.array_equal(result[0], reference[0])
            and np.array_equal(result[1], reference[1]) else "UNGLEICH"
        )
        row.append(f"{value} {seconds:6.2f}{same}")
    print("  ".join(row), f"({pairs / 1e6:.0f} Mio. Paare)", flush=True)
print("Summen:", {key: round(value, 1) for key, value in totals.items()})
