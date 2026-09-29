"""S5: Referenzauswahl an einer nicht erkannten Ø0,5-mm-Bohrung."""

import dataclasses
import _iso  # noqa: F401

import numpy as np
import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.scene.placement import at_point, prepare_surface


def describe(obj, depth=0):
    if dataclasses.is_dataclass(obj):
        return {f.name: describe(getattr(obj, f.name), depth + 1) for f in dataclasses.fields(obj)} if depth < 2 else type(obj).__name__
    if isinstance(obj, (list, tuple)):
        return f"{type(obj).__name__}[{len(obj)}]" + (f" erste: {describe(obj[0], depth + 1)}" if obj and depth < 2 else "")
    if isinstance(obj, np.ndarray):
        return f"ndarray{obj.shape}"
    return repr(obj)[:80]


for hole_d, label in ((0.5, "Ø0,5 unerkannt"), (5.2, "Ø5,2 erkannt")):
    box = trimesh.creation.box(extents=(20.0, 20.0, 4.0))
    cyl = trimesh.creation.cylinder(radius=hole_d / 2, height=10.0, sections=48)
    body = trimesh.boolean.difference([box, cyl], engine="manifold")
    mesh = MeshData.of(body)
    feats = detect(mesh)
    kinds = {}
    for f in feats.values():
        kinds[f.kind] = kinds.get(f.kind, 0) + 1
    print(f"--- {label}: detect -> {kinds}")
    normals = np.asarray(body.face_normals)
    centres = np.asarray(body.triangles_center)
    top = [i for i in range(len(normals)) if normals[i][2] > 0.99 and centres[i][2] > 1.9]
    print("Dreiecke der Oberseite:", len(top))
    prepared = prepare_surface(mesh, top[0], feats)
    print("PreparedSurface:", describe(prepared))
    for attr in ("edges", "candidates", "boundary", "segments", "lines", "references"):
        v = getattr(prepared, attr, None)
        if v is not None:
            print(f"  {attr}: {len(v) if hasattr(v, '__len__') else v}")
    placement = at_point(prepared, (0.3, 0.3, 2.0))
    print("SurfacePlacement:", describe(placement))
    for attr in ("references", "edges", "distances", "reference_lengths", "anchors"):
        v = getattr(placement, attr, None)
        if v is not None:
            print(f"  {attr}: {describe(v)}")
            if isinstance(v, (list, tuple)):
                for item in v[:2]:
                    print("     ", describe(item, 1))
