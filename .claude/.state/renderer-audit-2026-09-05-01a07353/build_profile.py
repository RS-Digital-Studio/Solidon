"""Profiliert den Szenenaufbau des GFX-Renderers ohne Fenster: was `add_surface` kostet.

Aufruf: python build_profile.py [--stage 0|1|2] [--source <stl>]
Stufe 0 ist der Baum mit 197 120 Dreiecken, 1 und 2 teilen jedes Dreieck
vollständig in vier (788 480 beziehungsweise 3 153 920), wie `budget_probe.py`.
Gemessen wird `GfxRenderer.add_surface` samt erstem Bild, mit cProfile, in
einem Puffer ohne Fenster; die Zahlen enthalten den Profiler-Aufschlag.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
import time
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")


def subdivide(vertices, faces, stages: int):
    import numpy as np

    for _ in range(stages):
        a, b, c = faces[:, 0], faces[:, 1], faces[:, 2]
        n = len(vertices)
        mid_ab = (vertices[a] + vertices[b]) / 2.0
        mid_bc = (vertices[b] + vertices[c]) / 2.0
        mid_ca = (vertices[c] + vertices[a]) / 2.0
        vertices = np.vstack([vertices, mid_ab, mid_bc, mid_ca])
        i_ab = n + np.arange(len(faces))
        i_bc = i_ab + len(faces)
        i_ca = i_bc + len(faces)
        faces = np.vstack(
            [
                np.column_stack([a, i_ab, i_ca]),
                np.column_stack([i_ab, b, i_bc]),
                np.column_stack([i_ca, i_bc, c]),
                np.column_stack([i_ab, i_bc, i_ca]),
            ]
        )
    return vertices, faces


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, default=2)
    parser.add_argument("--source", type=Path, default=Path(r"C:\Users\rober\Downloads\tree_with_tray_stl.stl"))
    args = parser.parse_args()
    import numpy as np
    import trimesh

    mesh = trimesh.load(str(args.source), force="mesh", process=False)
    vertices = np.asarray(mesh.vertices, dtype=float)
    faces = np.asarray(mesh.faces, dtype=np.int64)
    vertices, faces = subdivide(vertices, faces, args.stage)
    print(f"Dreiecke: {len(faces)}", flush=True)

    from app.ui.render.api import CameraPose, SurfaceStyle
    from app.ui.render.gfx_renderer import GfxRenderer

    view = GfxRenderer(offscreen=True, size=(1600, 900))
    view.set_background("#202020")
    profile = cProfile.Profile()
    started = time.perf_counter()
    profile.enable()
    item = view.add_surface(vertices, faces, name="baum", style=SurfaceStyle(smooth=True))
    built = time.perf_counter()
    view.set_camera_pose(CameraPose((300.0, -300.0, 300.0), (0.0, 0.0, 50.0), (0.0, 0.0, 1.0)))
    view.reset_camera(item.bounds())
    view.render()
    first = time.perf_counter()
    view.render()
    second = time.perf_counter()
    profile.disable()
    print(
        f"add_surface {1000 * (built - started):.0f} ms | erstes Bild {1000 * (first - built):.0f} ms"
        f" | zweites Bild {1000 * (second - first):.1f} ms",
        flush=True,
    )
    stream = io.StringIO()
    pstats.Stats(profile, stream=stream).sort_stats("cumulative").print_stats(r"gfx_renderer|pygfx|numpy|wgpu", 30)
    print(stream.getvalue())
    view.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
