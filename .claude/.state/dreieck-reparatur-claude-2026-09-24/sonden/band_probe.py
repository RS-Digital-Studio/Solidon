"""Sonde: fehlende Wände an Korpusdateien — Band oder Deckel, und was die Erkennung danach sieht."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np
import trimesh

sys.path.insert(0, str(Path.cwd()))
warnings.simplefilter("ignore")
import app.core.geom.repair as R  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402

MESHES = Path("tests/data/meshes")


def welded(name: str) -> MeshData:
    return R.merge_vertices(read_mesh((MESHES / name).read_bytes(), ".stl"))[0]


def without(mesh: MeshData, faces: np.ndarray) -> MeshData:
    keep = np.setdiff1d(np.arange(mesh.triangle_count), faces)
    return MeshData.of(mesh.raw.submesh([keep], append=True, repair=False))


def report(label: str, whole: MeshData, broken: MeshData) -> None:
    result = R.repair(broken)
    mesh = result.mesh
    kinds = {}
    for feature in detect(mesh).values():
        kinds[feature.kind] = kinds.get(feature.kind, 0) + 1
    before = {}
    for feature in detect(whole).values():
        before[feature.kind] = before.get(feature.kind, 0) + 1
    print(
        f"{label}: dicht={mesh.is_watertight} Vol {whole.volume:.2f} -> {mesh.volume:.2f} "
        f"Schnitte={len(R.self_intersecting_faces(mesh))} {sorted({f.code for f in result.findings})}"
    )
    print(f"   Merkmale vorher {before}\n   nachher         {kinds}")


plate = welded("plate_holes.stl")
features = detect(plate)
bores = [f for f in features.values() if f.kind == "hole"]
wall = np.asarray(sorted(bores, key=lambda f: f.params["centre"])[0].face_indices)
report("Bohrungswand fehlt", plate, without(plate, wall))

sunk = welded("plate_countersunk.stl")
cones = [f for f in detect(sunk).values() if f.kind == "cone"]
if cones:
    report("Senkungskegel fehlt", sunk, without(sunk, np.asarray(cones[0].face_indices)))

tube = trimesh.creation.cylinder(radius=10.0, height=30.0, sections=48)
caps = np.flatnonzero(np.abs(tube.face_normals[:, 2]) > 0.5)
open_tube = MeshData.of(tube)
report("Rohr ohne Deckel", MeshData.of(tube), without(open_tube, caps))

sphere = trimesh.creation.icosphere(subdivisions=3, radius=10.0)
poles = np.flatnonzero(np.abs(sphere.triangles_center[:, 2]) > 9.0)
report("Kugel ohne Pole", MeshData.of(sphere), without(MeshData.of(sphere), poles))
