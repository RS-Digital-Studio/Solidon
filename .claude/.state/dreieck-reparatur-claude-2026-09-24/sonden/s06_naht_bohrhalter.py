"""Sonde 6: Naht-zusammengesetzt.stl (normals_flipped ohne Wirkung, Volumen −6 %)
und drill-holder.3mf Körper 1 (69 Teile, Durchdringung unresolved)."""

from __future__ import annotations

import numpy as np
import trimesh

from common import KUNDE, R, MeshData, codes, facts, signed_volume_local

from app.core.geom import boolean as B
from app.core.geom.mesh import face_components, read_mesh
from app.core.ingest import threemf
from app.core.ingest.loader import normalise


def pieces_of(mesh: MeshData):
    out = []
    for p in face_components(mesh.raw):
        sub = mesh.raw.submesh([p], append=True, repair=False)
        out.append((len(p), bool(sub.is_watertight), bool(sub.is_winding_consistent),
                    round(signed_volume_local(sub), 3)))
    return out


print("=== Naht-zusammengesetzt.stl")
path = KUNDE / "3D Drucker" / "16_CC2-Auffangrinne" / "Naht-zusammengesetzt.stl"
mesh = read_mesh(path.read_bytes(), ".stl")
imp = normalise(mesh, "mm", weld_is_reading=True)
print("Import:", codes(imp.findings), facts(imp.mesh, intersections=True))
print("Teile:", pieces_of(imp.mesh))
flipped, did = R.unify_normals(imp.mesh)
print("unify_normals: flipped=", did, facts(flipped))
print("Teile danach:", pieces_of(flipped))
# Welche Kanten sind nach fix_winding noch gleichläufig?
body = flipped.raw
edges = body.edges_sorted
_, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
directed = body.edges
same = {}
for row, e in enumerate(inverse.reshape(-1)):
    same.setdefault(int(e), []).append(tuple(directed[row]))
bad = [k for k, v in same.items() if len(v) == 2 and v[0] == v[1]]
print("gleichläufige Kanten nach unify_normals:", len(bad))
rep = R.repair(imp.mesh, inspect_intersections=True)
print("repair:", codes(rep.findings), facts(rep.mesh))
for f in rep.findings:
    print("   ", f.code, "|", str(f.message))

print("\n=== drill-holder.3mf Körper 1")
payload = (KUNDE / "drill-holder.3mf").read_bytes()
obj = next(o for o in threemf.read_objects(payload) if str(o.name) == "Körper 1")
imp = normalise(obj.mesh, "mm")
m = imp.mesh
print("Import:", codes(imp.findings), facts(m))
parts = pieces_of(m)
print("Teile:", len(parts), "davon ohne Volumen/offen:",
      [p for p in parts if not (p[1] and p[2] and p[3] > 0)][:10])
vols = sorted(p[3] for p in parts)
print("Teilvolumina (kleinste 10):", vols[:10], "größte:", vols[-3:])
found, complete = R.self_intersection_check(m)
comp = np.zeros(m.triangle_count, dtype=int)
for index, p in enumerate(face_components(m.raw)):
    comp[p] = index
print("Durchdringungsdreiecke:", len(found), "in Teilen:", len(set(comp[list(found)].tolist())))
pieces = [MeshData.of(m.raw.submesh([p], append=True, repair=False)) for p in face_components(m.raw)]
try:
    out = B.boolean("union", pieces, stages=("direct",))
    print("Vereinigung direkt:", facts(out.mesh, intersections=True))
except Exception as problem:  # noqa: BLE001
    print("Vereinigung direkt scheitert:", type(problem).__name__, problem)
