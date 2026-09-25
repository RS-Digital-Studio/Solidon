"""Review-Sonde: Viele überlappende Schalen (Bausatzfigur) — Zeit und Ergebnis der Auflösung (nur lesend)."""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import R, facts  # noqa: E402

import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402

spent: dict[str, float] = defaultdict(float)
for name in ("crossings_of", "_intersections_resolvable", "resolve_self_intersections",
             "_still_crosses", "unify_normals", "parts_inside_parts", "_filled_rounds"):
    original = getattr(R, name)

    def timed(*args, _original=original, _name=name, **kwargs):
        start = time.perf_counter()
        try:
            return _original(*args, **kwargs)
        finally:
            spent[_name] += time.perf_counter() - start

    setattr(R, name, timed)

rng = np.random.default_rng(5)
for count in (100, 400):
    spheres = []
    for _index in range(count):
        ball = trimesh.creation.icosphere(subdivisions=2, radius=float(2.0 + 2.0 * rng.random()))
        ball.apply_translation(rng.random(3) * 40.0)
        spheres.append(ball)
    mesh = MeshData.of(trimesh.util.concatenate(spheres))
    spent.clear()
    start = time.perf_counter()
    result = R.repair(mesh, self_intersections=True, inspect_intersections=True)
    total = time.perf_counter() - start
    print(f"{count} Kugeln ({len(mesh.raw.faces)} Dreiecke): repair {total:.1f} s",
          {key: round(value, 2) for key, value in spent.items()})
    print("  Befunde:", [f.code for f in result.findings], facts(result.mesh))
