"""Sonde B4-Rest: Viertel und Hälfte einer Bohrungswand fehlen — Grenze der glatten Füllung."""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path.cwd()))
warnings.simplefilter("ignore")
import app.core.geom.repair as R  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.perceive.features import detect, forget_cache  # noqa: E402

plate = R.merge_vertices(
    MeshData.of(trimesh.load("tests/data/meshes/plate_holes.stl", force="mesh"))
)[0]
forget_cache()
bores = sorted(
    (f for f in detect(plate).values() if f.kind == "hole"), key=lambda f: tuple(f.params["centre"])
)
wall = np.asarray(bores[0].face_indices)
centre = np.asarray(bores[0].params["centre"])
angles = np.arctan2(*(np.asarray(plate.raw.triangles_center)[wall][:, [1, 0]] - centre[[1, 0]]).T)
for share in (0.25, 0.5):
    gone = wall[(angles > -np.pi) & (angles < -np.pi + share * 2 * np.pi)]
    keep = np.setdiff1d(np.arange(plate.triangle_count), gone)
    broken = MeshData.of(plate.raw.submesh([keep], append=True, repair=False))
    for limit in (32,):
        R.SMOOTH_FILL_CORNERS = limit
        start = time.perf_counter()
        result = R.repair(broken)
        spent = time.perf_counter() - start
        forget_cache()
        kinds: dict[str, int] = {}
        for feature in detect(result.mesh).values():
            kinds[feature.kind] = kinds.get(feature.kind, 0) + 1
        print(
            f"Anteil {share} ({len(gone)} Dreiecke), Grenze {limit}: {spent:.2f} s, dicht "
            f"{result.mesh.is_watertight}, Volumen {plate.volume:.3f} -> {result.mesh.volume:.3f}, "
            f"Schnitte {len(R.self_intersecting_faces(result.mesh))}, {kinds}"
        )
