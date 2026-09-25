"""Sonde B12: eigene Paritätsausbreitung gegen trimesh.repair.fix_winding — gleiche Dreiecke, Zeit."""

from __future__ import annotations

import sys
import time
import warnings
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path.cwd()))
warnings.simplefilter("ignore")
from app.core.geom.repair import merge_vertices, wind_consistently  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402


def compare(label: str, body: trimesh.Trimesh) -> None:
    ours = body.copy()
    theirs = body.copy()
    start = time.perf_counter()
    wind_consistently(ours)
    mine = time.perf_counter() - start
    start = time.perf_counter()
    trimesh.repair.fix_winding(theirs)
    other = time.perf_counter() - start
    same = np.array_equal(np.asarray(ours.faces), np.asarray(theirs.faces))
    print(
        f"{label}: {len(body.faces)} Dreiecke, gleich={same}, einheitlich "
        f"{ours.is_winding_consistent}/{theirs.is_winding_consistent}, "
        f"{mine:.3f} s gegen {other:.3f} s"
    )


rng = np.random.default_rng(20260924)


def shuffled(body: trimesh.Trimesh, share: float) -> trimesh.Trimesh:
    faces = np.asarray(body.faces).copy()
    pick = rng.random(len(faces)) < share
    faces[pick] = faces[pick][:, ::-1]
    return trimesh.Trimesh(vertices=np.asarray(body.vertices), faces=faces, process=False)


sphere = trimesh.creation.icosphere(subdivisions=5, radius=10.0)
compare("Kugel 30 % gedreht", shuffled(sphere, 0.3))
compare("Kugel 1 Dreieck", shuffled(sphere, 1.0 / len(sphere.faces)))
opened = sphere.copy()
opened.update_faces(np.asarray(opened.triangles_center)[:, 2] < 8.0)
opened.remove_unreferenced_vertices()
compare("Kugel offen 30 %", shuffled(opened, 0.3))
parts = trimesh.util.concatenate(
    [trimesh.creation.box(extents=(5, 5, 5)).subdivide().subdivide(), sphere]
)
compare("Zwei Teile 50 %", shuffled(parts, 0.5))
plate = merge_vertices(
    MeshData.of(trimesh.load("tests/data/meshes/plate_holes.stl", force="mesh"))
)[0].raw
compare("Lochplatte 20 %", shuffled(plate, 0.2))


path = Path("F:/3D Dateien/3D Drucker/04_Community-Modelle/Gaehnende-Katze_Figur_material.3mf")
if path.exists():

    raw = trimesh.load(path, force="mesh")
    cat = merge_vertices(MeshData.of(raw))[0].raw
    compare("Katze", cat)
