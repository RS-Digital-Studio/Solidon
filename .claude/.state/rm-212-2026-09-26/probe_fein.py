"""Sonde RM-212: Die Kurve zwischen dem Ein- und dem Sechzehnfachen des Sehnenfehlers, feiner.

Aufruf: python probe_fein.py <datei> [<datei> ...]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import manifold3d
import numpy as np
import trimesh

for name in sys.argv[1:]:
    raw = trimesh.load(name, force="mesh")
    solid = manifold3d.Manifold(
        manifold3d.Mesh64(np.asarray(raw.vertices, dtype=np.float64), np.asarray(raw.faces, dtype=np.uint64))
    )
    print(f"{Path(name).name}: {len(raw.faces)} Dreiecke", flush=True)
    for tolerance in (0.05, 0.1, 0.15, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8):
        started = time.perf_counter()
        count = solid.simplify(tolerance).num_tri()
        print(f"  simplify({tolerance:5.2f}) → {count:>8} in {time.perf_counter() - started:.2f} s", flush=True)
