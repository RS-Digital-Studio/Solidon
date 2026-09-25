"""Review-Sonde: Was `unify_normals` an einem einzelnen, richtigen Körper kostet (nur lesend)."""

from __future__ import annotations

import sys
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import R  # noqa: E402

import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData, signed_volume  # noqa: E402

big = trimesh.creation.icosphere(subdivisions=8, radius=50.0)
mesh = MeshData.of(big)
_ = big.is_watertight, big.is_winding_consistent

start = time.perf_counter()
body = mesh.raw.copy()
print(f"copy {time.perf_counter() - start:.2f} s")

start = time.perf_counter()
R.wind_consistently(body)
print(f"wind_consistently (früher Ausstieg) {time.perf_counter() - start:.2f} s")

tracemalloc.start()
start = time.perf_counter()
R.turn_shells_outward(body)
spent = time.perf_counter() - start
_current, peak = tracemalloc.get_traced_memory()
tracemalloc.stop()
print(f"turn_shells_outward {spent:.2f} s, Spitze {peak / 1e6:.0f} MB bei {len(big.faces)} Dreiecken")

start = time.perf_counter()
volume = signed_volume(body)
print(f"signed_volume allein {time.perf_counter() - start:.2f} s ({volume:.1f})")
