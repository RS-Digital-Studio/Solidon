"""RM-279 (i): Wie sieht eine verrundete Mündung aus — Netz gegen exakt gegen Formel?

Aufruf aus der Wurzel eines Arbeitsbaums: python muendung.py. Quader 40 x 30 x 20
mit Bohrung Ø 6, einmal quer (Y) und einmal stehend (Z), durchgehend: zwei
Mündungen. Verrundet bzw. gefast werden genau die zwei Ringe (einzeln gewählt,
Schlüssel). Je Maß: was an den Mündungen weggeht, an beiden Kernen und nach
Pappus (Verrunden: Zwickel R²(1 − π/4), Schwerpunkt 0,2234·R vom Eck; Fase:
Dreieck d²/2, Schwerpunkt d/3 vom Eck; Umlauf um die Bohrachse), und die
größte Abweichung der Netzfläche von der exakten nahe der Mündung (dichte
Punktwolke, Abstand rund 0,02 mm).
"""

import math
import os
import sys
from pathlib import Path

TREE = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
sys.path.insert(0, TREE)
import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve()), app.__file__
import numpy as np  # noqa: E402
import trimesh  # noqa: E402
from scipy.spatial import cKDTree  # noqa: E402

from app.core.brep import edit  # noqa: E402
from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom.edges import bevel_edges, edge_key, edges_of, round_edges  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402

R_BORE = 3.0
SPANDREL_CENTROID = (10.0 - 3.0 * math.pi) / (12.0 - 3.0 * math.pi)


def pappus(size: float, rounded: bool) -> float:
    if rounded:
        area = size * size * (1.0 - math.pi / 4.0)
        centroid = SPANDREL_CENTROID * size
    else:
        area = size * size / 2.0
        centroid = size / 3.0
    return 2 * 2.0 * math.pi * (R_BORE + centroid) * area


def mesh_body(axis: str) -> MeshData:
    box = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    box.apply_translation((0.0, 0.0, 10.0))
    bore = trimesh.creation.cylinder(radius=R_BORE, height=90.0, sections=48)
    if axis == "y":
        bore.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1, 0, 0)))
    bore.apply_translation((0.0, 0.0, 10.0))
    return boolean("difference", [MeshData(box), MeshData(bore)]).mesh


def solid_body(axis: str):
    box = edit.box(40.0, 30.0, 20.0)
    if axis == "y":
        return edit.bore(box, position=(0.0, -15.0, 10.0), axis="y", diameter=2 * R_BORE)
    return edit.bore(box, position=(0.0, 0.0, 20.0), axis="z", diameter=2 * R_BORE)


def near_mouth(points: np.ndarray, axis: str, size: float) -> np.ndarray:
    if axis == "y":
        off_axis = np.hypot(points[:, 0], points[:, 2] - 10.0)
        return (np.abs(points[:, 1]) > 15.0 - size - 0.5) & (off_axis < R_BORE + size + 0.5)
    off_axis = np.hypot(points[:, 0], points[:, 1])
    return ((points[:, 2] > 20.0 - size - 0.5) | (points[:, 2] < size + 0.5)) & (
        off_axis < R_BORE + size + 0.5
    )


def near_part(tri, axis, size):
    touching = near_mouth(tri.vertices, axis, size)[tri.faces].any(axis=1)
    touching |= near_mouth(tri.triangles_center, axis, size)
    part = tri.submesh([np.flatnonzero(touching)], append=True)
    return trimesh.util.concatenate(part) if isinstance(part, list) else part


def torus_deviation(tri, axis: str, size: float) -> float:
    """Größter Abstand der Netzrundung von der analytischen (Torus um die Bohrachse).

    Punkte der Rundungszone: Abstand zur Achse zwischen r und r + R, Tiefe
    unter der Wand zwischen 0 und R, ohne die Wand selbst und die Bohrung.
    Die exakte Rundung ist dieser Torus; der exakte Kern trifft Pappus.
    """
    points = np.vstack([tri.vertices, trimesh.sample.sample_surface(tri, 400000, seed=3)[0]])
    if axis == "y":
        rho = np.hypot(points[:, 0], points[:, 2] - 10.0)
        depth = 15.0 - np.abs(points[:, 1])
    else:
        rho = np.hypot(points[:, 0], points[:, 1])
        depth = np.minimum(20.0 - points[:, 2], points[:, 2])
    zone = (rho > R_BORE + 1e-3) & (rho < R_BORE + size) & (depth > 1e-3) & (depth < size)
    deviation = np.abs(np.hypot(rho[zone] - (R_BORE + size), depth[zone] - size) - size)
    return float(deviation.max())


def ring_keys(entries, key):
    return [key(e) for e in entries if math.dist(e.direction, (0.0, 0.0, 0.0)) < 1e-6]


for axis, label in (("y", "Querbohrung"), ("z", "stehende Bohrung")):
    mesh = mesh_body(axis)
    solid = solid_body(axis)
    mesh_keys = ring_keys(edges_of(mesh), edge_key)
    solid_keys = ring_keys(edit.edges_of(solid), edit.edge_key)
    assert len(mesh_keys) == 2 and len(solid_keys) == 2
    print(f"\n== {label}")
    for size, rounded in ((0.5, True), (1.0, True), (2.0, True), (5.0, True), (1.0, False), (2.0, False)):
        work = round_edges if rounded else bevel_edges
        mesh_out = work(mesh, size, "named", mesh_keys).mesh
        exact_out = (edit.fillet if rounded else edit.chamfer)(solid, size, "named", solid_keys)
        mesh_mouths = mesh.volume - mesh_out.volume
        exact_mouths = solid.volume - exact_out.volume
        exact_tri = exact_out.to_mesh(deflection=0.005).raw
        mesh_tri = mesh_out.raw
        grow = size + 1.0
        samples = trimesh.sample.sample_surface(near_part(mesh_tri, axis, size), 40000, seed=1)[0]
        samples = samples[near_mouth(samples, axis, size)]
        forward = cKDTree(
            trimesh.sample.sample_surface(near_part(exact_tri, axis, grow), 1500000, seed=2)[0]
        ).query(samples)[0]
        back = trimesh.sample.sample_surface(near_part(exact_tri, axis, size), 40000, seed=1)[0]
        back = back[near_mouth(back, axis, size)]
        backward = cKDTree(
            trimesh.sample.sample_surface(near_part(mesh_tri, axis, grow), 1500000, seed=2)[0]
        ).query(back)[0]
        both = np.r_[forward, backward]
        torus = torus_deviation(mesh_tri, axis, size) if rounded else float("nan")
        name = f"{'R' if rounded else 'Fase'} {size:3.1f}"
        print(
            f"  {name:8s}: weg Netz {mesh_mouths:8.3f} ({(mesh_mouths / pappus(size, rounded) - 1) * 100:+5.1f} %)"
            f"  exakt {exact_mouths:8.3f}  Formel {pappus(size, rounded):8.3f} mm³ | Netz↔exakt max "
            f"{both.max():.3f} mm, 99 % {np.percentile(both, 99):.3f} mm | Netz↔Torus max {torus:.4f} mm"
            f" | Netz dicht {mesh_out.is_watertight}"
        )
