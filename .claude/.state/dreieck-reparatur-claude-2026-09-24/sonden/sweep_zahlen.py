"""Wie viele Sweep-Paare zählt die Suche, und wie viele Hüllen überdecken sich wirklich?"""

import sys
import time
from pathlib import Path

import numpy as np
import trimesh

from app.core.geom import intersections as its

for name in sys.argv[1:]:
    loaded = trimesh.load(Path(name), force="mesh")
    surface = its._surface(np.asarray(loaded.vertices, dtype=float), np.asarray(loaded.faces))
    plan = its._plan(surface.low, surface.high)
    entries = its._entries(surface.low, surface.high, plan)
    sweep = int(entries.counts.sum())
    search = its._Search(max_pairs=None)
    start = time.perf_counter()
    real = sum(len(first) for first, _second in its._candidates(surface, None, search, plan))
    took = time.perf_counter() - start
    extent = surface.high - surface.low
    print(
        f"{Path(name).name[:40]:40s} {len(loaded.faces):>8d} Dreiecke  Plan {plan}  "
        f"Sweep {sweep:>11,d}  Hüllenpaare {real:>10,d}  ({took:.1f}s)  "
        f"Hüllmaß Median {np.median(extent, axis=0).round(3)} Max {extent.max(axis=0).round(1)}",
        flush=True,
    )
