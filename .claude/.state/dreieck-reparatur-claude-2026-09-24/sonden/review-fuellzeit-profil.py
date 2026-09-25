"""Review-Sonde: Wo `_fill_jobs` bei vielen Dreieckslöchern die Zeit lässt (nur lesend)."""

from __future__ import annotations

import cProfile
import pstats
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import R  # noqa: E402

import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.units import EPS_GEOM, weld_tolerance  # noqa: E402

sphere = trimesh.creation.icosphere(subdivisions=6, radius=50.0)
rng = np.random.default_rng(7)


def holed(count: int) -> MeshData:
    chosen: list[int] = []
    blocked = np.zeros(len(sphere.vertices), dtype=bool)
    for face in rng.permutation(len(sphere.faces)).tolist():
        corners = sphere.faces[face]
        if blocked[corners].any():
            continue
        chosen.append(face)
        blocked[corners] = True
        if len(chosen) == count:
            break
    keep = np.ones(len(sphere.faces), dtype=bool)
    keep[chosen] = False
    body = sphere.copy()
    body.update_faces(keep)
    return MeshData.of(body)


def inputs(mesh: MeshData):
    split, loops = R._hole_rings(mesh)
    points = np.asarray(split.raw.vertices, dtype=float)
    single = R._edge_table(split).rows(1)
    directed = np.asarray(split.raw.edges, dtype=np.int64)[single]
    owner = {
        (min(int(a), int(b)), max(int(a), int(b))): int(single[row]) // 3
        for row, (a, b) in enumerate(directed.tolist())
    }
    centroids = np.asarray(split.raw.triangles, dtype=np.float64).mean(axis=1)
    tolerance = max(10.0 * EPS_GEOM, weld_tolerance(float(split.bounds.diagonal)))
    return points, loops, tolerance, owner, centroids


for count in (100, 200, 400):
    args = inputs(holed(count))
    start = time.perf_counter()
    R._fill_jobs(*args)
    print(f"{count} Dreieckslöcher: _fill_jobs {time.perf_counter() - start:.2f} s")
    start = time.perf_counter()
    R._fill_jobs(args[0], args[1], args[2])  # ohne Bandpaarung
    print(f"{count} Dreieckslöcher: _fill_jobs ohne Bänder {time.perf_counter() - start:.2f} s")

args = inputs(holed(400))
profile = cProfile.Profile()
profile.enable()
R._fill_jobs(*args)
profile.disable()
pstats.Stats(profile).sort_stats("cumulative").print_stats(12)
