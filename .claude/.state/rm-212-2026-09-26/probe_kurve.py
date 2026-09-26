"""Sonde RM-212: Wie fällt die Dreieckszahl des Kerns mit der Toleranz?

Je Netz simplify bei 0,05 · 4^k mm für k = 0..5 — der heutige Suchweg von
``_display_manifold_decimation`` — mit Dreieckszahl und Zeit, dazu das
Raster (``_clustered_for_display``) auf das Ziel 50 000 zum Vergleich.
Nur lesend; gerechnet wird am rohen Netz wie im Anzeigeweg.

Aufruf: python probe_kurve.py <datei> [<datei> ...]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import manifold3d
import numpy as np
import trimesh

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from app.core.geom import mesh_ops  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402

TARGET = 50_000

for name in sys.argv[1:]:
    raw = trimesh.load(name, force="mesh")
    mesh = MeshData.of(raw)
    print(f"{Path(name).name}: {mesh.triangle_count} Dreiecke, dicht {mesh.is_watertight}", flush=True)
    started = time.perf_counter()
    solid = manifold3d.Manifold(
        manifold3d.Mesh64(
            np.asarray(raw.vertices, dtype=np.float64), np.asarray(raw.faces, dtype=np.uint64)
        )
    )
    print(f"  Kern nimmt es: {not solid.is_empty()} ({time.perf_counter() - started:.2f} s)", flush=True)
    if not solid.is_empty():
        tolerance = 0.05
        for step in range(6):
            started = time.perf_counter()
            count = solid.simplify(tolerance).num_tri()
            print(f"  simplify({tolerance:7.3f}) → {count:>8} in {time.perf_counter() - started:.2f} s", flush=True)
            tolerance *= 4.0
    started = time.perf_counter()
    rastered = mesh_ops._clustered_for_display(mesh, TARGET, None)
    print(f"  Raster → {rastered.triangle_count} in {time.perf_counter() - started:.2f} s, dicht {rastered.is_watertight}", flush=True)
