"""Sonde 1: resolve_self_intersections neu gegen HEAD an gebauten Fällen."""

from __future__ import annotations

import math
import time

import numpy as np
import trimesh

from common import MESHES, R, MeshData, codes, facts, head_repair, welded

H = head_repair()


def tube_along(points: np.ndarray, radius: float = 1.5, sides: int = 12) -> trimesh.Trimesh:
    """Geschlossene Röhre entlang eines geschlossenen Pfads — eine Schale."""
    n = len(points)
    rings = []
    for i in range(n):
        tangent = points[(i + 1) % n] - points[i - 1]
        tangent /= np.linalg.norm(tangent)
        up = np.array([0.0, 0.0, 1.0])
        side = np.cross(tangent, up)
        side /= np.linalg.norm(side)
        up2 = np.cross(side, tangent)
        ring = [points[i] + radius * (math.cos(a) * up2 + math.sin(a) * side)
                for a in np.linspace(0, 2 * math.pi, sides, endpoint=False)]
        rings.append(ring)
    vertices = np.asarray(rings).reshape(-1, 3)
    faces = []
    for i in range(n):
        j = (i + 1) % n
        for k in range(sides):
            l = (k + 1) % sides
            a, b, c, d = i * sides + k, i * sides + l, j * sides + l, j * sides + k
            faces += [[a, b, c], [a, c, d]]
    body = trimesh.Trimesh(vertices=vertices, faces=np.asarray(faces), process=False)
    if body.volume < 0:
        body.invert()
    return body


def figure_eight(samples: int = 96, size: float = 20.0) -> np.ndarray:
    t = np.linspace(0, 2 * math.pi, samples, endpoint=False)
    # Lemniskate von Gerono, flach in z: kreuzt sich in der Mitte selbst.
    return np.column_stack([size * np.sin(t), size * np.sin(t) * np.cos(t), np.zeros_like(t)])


def report(name: str, mesh: MeshData) -> None:
    print(f"\n=== {name}")
    before = facts(mesh, intersections=True)
    print("vorher:", before)
    for label, module in (("NEU ", R), ("HEAD", H)):
        t0 = time.perf_counter()
        try:
            got, changed = module.resolve_self_intersections(mesh)
        except Exception as problem:  # noqa: BLE001
            print(label, "Ausnahme:", type(problem).__name__, problem)
            continue
        spent = time.perf_counter() - t0
        after = facts(got, intersections=True)
        print(f"{label} changed={changed} {spent:.2f}s ->", after)
    t0 = time.perf_counter()
    result = R.repair(mesh, self_intersections=True, inspect_intersections=True)
    print(f"repair(neu, SI an) {time.perf_counter()-t0:.2f}s:", codes(result.findings), facts(result.mesh))
    t0 = time.perf_counter()
    result = H.repair(mesh, self_intersections=True)
    print(f"repair(HEAD, SI an) {time.perf_counter()-t0:.2f}s:", codes(result.findings), facts(result.mesh))


# A: zwei überlappende Würfel als getrennte Schalen
report("A broken_selfint (zwei Schalen)", welded(MESHES / "broken_selfint.stl"))

# B: eine einzige Schale, die sich selbst kreuzt (Achterröhre)
tube = MeshData.of(tube_along(figure_eight()))
report("B Achterröhre (eine Schale)", tube)

# C: generated_figure.stl (der frühere Testfall für 'der Schritt wirkt')
report("C generated_figure.stl", welded(MESHES / "generated_figure.stl"))

# D: Hohlkörper mit Innenschale + überlappende Außenschale
outer = welded(MESHES / "broken_selfint.stl").raw
cube = welded(MESHES / "cube_clean.stl").raw.copy()
cube.apply_scale(0.1)
cube.apply_translation((-5.0, -5.0, -5.0))
cube.invert()
report("D Innenschale + überlappende Außenschalen", MeshData.of(trimesh.util.concatenate([outer, cube])))

# E: Achterröhre mit Hohlraum (Innenschale in der Röhre)
inner = tube_along(figure_eight(), radius=0.5)
inner.invert()
report("E Achterröhre mit innerer Röhre (Hohlkörper)", MeshData.of(trimesh.util.concatenate([tube.raw, inner])))

# F: zwei überlappende Würfel, einer umgestülpt
a = welded(MESHES / "cube_clean.stl").raw.copy()
b = a.copy()
b.apply_translation((8.0, 8.0, 8.0))
b.invert()
report("F zwei überlappende Würfel, einer umgestülpt", MeshData.of(trimesh.util.concatenate([a, b])))

# G: Kugel teilweise in Würfel (zwei Schalen, eine ganz innen)
s = trimesh.creation.icosphere(subdivisions=3, radius=4.0)
cube2 = welded(MESHES / "cube_clean.stl").raw.copy()
report("G Kugel ganz im Würfel (zwei positive Schalen)", MeshData.of(trimesh.util.concatenate([cube2, s])))

print("\nfertig")
