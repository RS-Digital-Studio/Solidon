"""Sonde 15: Volumenvorzeichen weit vom Ursprung — enclosed_volume (am Ursprung, einsum) gegen
boolean._signed_volume (körpernah). Was machen unify_normals und _has_volume daraus?"""
import numpy as np
import trimesh
from common import R, MeshData
from app.core.geom.mesh import enclosed_volume
from app.core.geom.boolean import _signed_volume

for size in (1.0, 10.0):
    for offset in (1e5, 1e6, 1e7, 3e7, 1e8):
        box = trimesh.creation.box(extents=(size, size, size)).subdivide().subdivide()
        box.apply_translation((offset, offset * 0.7, offset * 0.3))
        mesh = MeshData.of(box)
        fixed, flipped = R.unify_normals(mesh)
        print(f"Würfel {size:>4} mm bei {offset:.0e}: enclosed={enclosed_volume(box):+.4f} lokal={_signed_volume(box):+.6f} "
              f"_has_volume={R._has_volume(mesh)} unify_normals kehrt um={flipped} danach lokal={_signed_volume(fixed.raw):+.6f}")
