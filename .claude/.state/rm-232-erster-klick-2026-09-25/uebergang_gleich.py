"""RM-232: _blended_cavity_faces ab der Wand gegen die alte Rechnung über das ganze Netz."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
import numpy as np
import trimesh
from app.core.bootstrap import load_operations
from app.core.geom.mesh import read_mesh
from app.core.perceive import features as F
from app.core.perceive import relations as R
from app.core.units import EPS_GEOM

load_operations()


def old(body, candidates, indices):
    bore = next((f for f in candidates.values() if f.kind == "hole"), None)
    if bore is None or (axis := F.axis_of(bore)) is None or (centre := F.centre_of(bore)) is None:
        return indices
    allowed = np.ones(len(body.faces), dtype=bool)
    allowed[list(F._large_facet_faces(body))] = False
    allowed[list(indices)] = True
    pairs = np.asarray(body.face_adjacency, dtype=np.int64)
    if not len(pairs):
        return indices
    smooth = np.degrees(np.asarray(body.face_adjacency_angles)) < F.CURVATURE_LIMIT
    pairs = pairs[smooth & allowed[pairs[:, 0]] & allowed[pairs[:, 1]]]
    if not len(pairs):
        return indices
    labels = trimesh.graph.connected_component_labels(pairs, node_count=len(body.faces))
    expanded = np.flatnonzero(np.isin(labels, labels[list(indices)]))
    extra = np.asarray([i for i in expanded if i not in indices], dtype=np.int64)
    if not len(extra):
        return indices
    towards = np.asarray(centre) - np.asarray(body.triangles_center)[extra]
    direction = np.asarray(axis)
    towards -= np.outer(towards @ direction, direction)
    inward = np.einsum("ij,ij->i", towards, np.asarray(body.face_normals)[extra])
    if bool(np.any(inward < -EPS_GEOM)):
        return indices
    rings = R._face_boundary_rings(body, expanded)
    if rings is None or len(rings) != 2:
        return indices
    return {int(i) for i in expanded}


total = same = 0
t_old = t_new = 0.0
for name in sys.argv[1:]:
    if name.endswith(".3mf"):
        from app.core.geom.mesh import MeshData
        mesh = MeshData.of(trimesh.load(name, force="mesh"))
    else:
        mesh = read_mesh(Path(name).read_bytes(), Path(name).suffix)
    found = F.detect(mesh)
    body = F._one_body(mesh).raw
    for fid, feature in found.items():
        if feature.kind not in ("hole", "cone"):
            continue
        chain = R.cavity_chain_at(feature, found, mesh) or (feature,)
        candidates = {part.id: part for part in chain}
        indices = {i for part in chain for i in part.face_indices}
        if not indices:
            continue
        t = time.perf_counter(); a = old(body, candidates, set(indices)); t_old += time.perf_counter() - t
        t = time.perf_counter(); b = R._blended_cavity_faces(body, candidates, set(indices)); t_new += time.perf_counter() - t
        total += 1
        same += a == b
        if a != b:
            print("ABWEICHUNG", Path(name).name, fid, len(a), len(b))
print(f"{same} von {total} gleich; alt {t_old*1000:.0f} ms, neu {t_new*1000:.0f} ms")
