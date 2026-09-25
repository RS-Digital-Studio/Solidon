"""Sonde: Verrundung im Korpus, zwei Nachbardreiecke fehlen — alte gegen neue Füllung."""

from __future__ import annotations

import sys
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path.cwd()))
warnings.simplefilter("ignore")
import app.core.geom.repair as R  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.perceive.features import detect, forget_cache  # noqa: E402

MESHES = Path("tests/data/meshes")


def without(mesh: MeshData, faces: list[int]) -> MeshData:
    keep = np.setdiff1d(np.arange(mesh.triangle_count), faces)
    return MeshData.of(mesh.raw.submesh([keep], append=True, repair=False))


whole = normalise(read_mesh((MESHES / "block_with_rounded_edge.stl").read_bytes(), ".stl"), "mm").mesh
forget_cache()
fillet = next(f for f in detect(whole).values() if f.kind == "fillet")
print("Verrundung", fillet.id, fillet.params["radius"], len(fillet.face_indices))
faces = np.asarray(whole.raw.faces)
for pair in [(88, 64), (96, 72), (97, 74)]:
    broken = without(whole, list(pair))
    removed = sorted(tuple(sorted(faces[f].tolist())) for f in pair)
    for corners in (16, 0):
        R.SMOOTH_FILL_CORNERS = corners
        result = R.repair(broken)
        added = np.asarray(result.mesh.raw.faces)[broken.triangle_count :]
        forget_cache()
        radii = [
            f.params["radius"] for f in detect(result.mesh).values() if f.kind == "fillet"
        ]
        # Vergleich über Punktlagen, weil die Nummern nach dem Ausschneiden anders sind.
        points = np.asarray(result.mesh.raw.vertices)
        added_pts = sorted(
            tuple(sorted(tuple(np.round(points[v], 6).tolist()) for v in row)) for row in added
        )
        orig_pts = sorted(
            tuple(sorted(tuple(np.round(np.asarray(whole.raw.vertices)[v], 6).tolist()) for v in faces[f]))
            for f in pair
        )
        print(
            pair,
            corners,
            "dicht",
            result.mesh.is_watertight,
            "neu",
            len(added),
            "gleich wie vorher",
            added_pts == orig_pts,
            "R",
            [round(r, 6) for r in radii],
        )
