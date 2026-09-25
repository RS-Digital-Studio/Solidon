"""B1 nachgestellt: plate_holes.stl ohne zwei Deckdreiecke mit gemeinsamer Ecke."""

import numpy as np

import app.core.bootstrap  # noqa: F401
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.repair import merge_vertices, repair, self_intersection_check
from app.core.perceive.features import detect

raw = read_mesh(open("tests/data/meshes/plate_holes.stl", "rb").read(), ".stl")
body, _ = merge_vertices(raw)
faces = np.asarray(body.raw.faces)
keep = np.ones(len(faces), dtype=bool)
keep[[52, 55]] = False
print("Dreiecke 52/55:", faces[52].tolist(), faces[55].tolist())
broken = MeshData.of(body.raw.submesh([np.flatnonzero(keep)], append=True, repair=False))
result = repair(broken)
found, complete = self_intersection_check(result.mesh)
print("dicht:", result.mesh.is_watertight, "Dreiecke:", result.mesh.triangle_count, "Durchdringungen:", len(found), complete)
print("Befunde:", [f.code for f in result.findings])
kinds = {}
for feature in detect(result.mesh).values() if hasattr(detect(result.mesh), "values") else detect(result.mesh):
    kinds[feature.kind] = kinds.get(feature.kind, 0) + 1
print("Merkmale:", kinds)
tops = [f for f in (detect(result.mesh).values() if hasattr(detect(result.mesh), "values") else detect(result.mesh)) if f.kind == "face" and f.params.get("centre", (0, 0, 0))[2] > 3.9]
print("Oberseite:", [(round(f.params.get("area", 0), 2)) for f in tops])
