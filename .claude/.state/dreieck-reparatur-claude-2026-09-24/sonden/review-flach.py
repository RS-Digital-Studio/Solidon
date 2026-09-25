"""Review-Sonde: Überschneidungen an einem umgestülpten Körper mit „Außenseiten angleichen: aus"."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import R  # noqa: E402

import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402

first = trimesh.creation.box((20.0, 20.0, 20.0))
second = trimesh.creation.box((20.0, 20.0, 20.0))
second.apply_translation((8.0, 5.0, 3.0))
both = trimesh.util.concatenate([first, second])
inverted = trimesh.Trimesh(both.vertices, both.faces[:, ::-1], process=False)
mesh = MeshData.of(inverted)
print("Schnitte:", len(R.crossings_of(mesh).faces))
for resolve in (True, False):
    result = R.repair(mesh, normals=False, self_intersections=resolve, inspect_intersections=True)
    print("self_intersections", resolve, "->", [(f.code, str(f.message)) for f in result.findings])
