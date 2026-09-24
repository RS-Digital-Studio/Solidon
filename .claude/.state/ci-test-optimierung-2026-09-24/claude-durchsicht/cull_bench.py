"""Vorauswahl gegen Vollvergleich an Vollkörpern und an der Dichtschnur."""

from __future__ import annotations

import sys
import time

sys.path.insert(0, r"F:\3D Druck")

import numpy as np
import trimesh

from app.core.geom import mesh as m
from app.core.units import EPS_GEOM


def bodies():
    for subdivisions in (4, 5):
        sphere = trimesh.creation.icosphere(subdivisions=subdivisions, radius=10.0)
        yield f"Kugel {len(sphere.faces)}", sphere
    from tests.test_seal_geometry import path
    from app.core.geom.seal import seal_geometry

    gasket = seal_geometry(
        path(), groove_width=12.0, groove_depth=12.0, protrusion=0, gasket_width=12.0,
        section="round", offset=5,
    ).gasket.raw
    yield f"Dichtschnur {len(gasket.faces)}", gasket


for name, body in bodies():
    triangles = np.asarray(body.triangles, dtype=float)
    origins = np.asarray(body.triangles_center, dtype=float)
    directions = -np.asarray(body.face_normals, dtype=float)
    started = time.perf_counter()
    culled = m.ray_hits_batch(triangles, origins, directions, edge_margin=EPS_GEOM,
                              minimum_travel=EPS_GEOM * 100.0)
    culled_seconds = time.perf_counter() - started
    if len(triangles) > 30000:
        print(f"{name}: Auswahl {culled_seconds:.1f} s", flush=True)
        continue
    started = time.perf_counter()
    full = m._nearest_ray_hits(triangles, origins, directions, EPS_GEOM, EPS_GEOM * 100.0, None)
    full_seconds = time.perf_counter() - started
    same = np.array_equal(culled[0], full[0]) and np.array_equal(culled[1], full[1])
    print(f"{name}: Auswahl {culled_seconds:.1f} s, voll {full_seconds:.1f} s, gleich {same}",
          flush=True)
