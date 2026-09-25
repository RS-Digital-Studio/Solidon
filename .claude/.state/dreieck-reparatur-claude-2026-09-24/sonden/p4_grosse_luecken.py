"""Sonde 4: Große Lücken — fehlende Mantelstücke, fehlende Wände, fehlende Deckel.

Fragt, was die Füllung aus einer fehlenden Fläche macht, die kein Loch in
einer Ebene ist: Wird die Bohrung zugestopft, entsteht ein Scheinmerkmal,
sagt der Bericht etwas? Gemessen am Import- wie am Reparaturweg (beide rufen
``repair``), hier direkt an ``repair`` und an ``normalise``.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.geom.repair import open_edge_count, repair, self_intersection_check  # noqa: E402
from app.core.ingest.loader import normalise, read_model  # noqa: E402
from app.core.perceive.features import detect, forget_cache  # noqa: E402

REPO = Path(r"F:\3D Druck")
OUT = Path(__file__).with_suffix(".txt")


def load(name: str) -> MeshData:
    payload = (REPO / "tests/data/meshes" / name).read_bytes()
    return normalise(read_model(payload, ".stl"), "mm").mesh


def without(mesh: MeshData, gone) -> MeshData:
    keep = np.ones(mesh.triangle_count, dtype=bool)
    keep[list(gone)] = False
    return MeshData.of(trimesh.Trimesh(np.asarray(mesh.raw.vertices),
                                       np.asarray(mesh.raw.faces)[keep], process=False))


def summary(found) -> str:
    kinds = dict(Counter(f.kind for f in found.values()))
    rounds = sorted(
        (f.kind, round(float(f.params.get("diameter", 0.0)), 3))
        for f in found.values() if f.kind in {"hole", "pin", "cone", "slot", "fillet", "torus"}
    )
    return f"{kinds} {rounds}"


def case(out, title: str, pristine: MeshData, gone) -> None:
    damaged = without(pristine, gone)
    fixed = repair(damaged)
    imported = normalise(read_model(damaged.raw.export(file_type="stl"), ".stl"), "mm")
    forget_cache()
    before = detect(pristine)
    forget_cache()
    after = detect(fixed.mesh)
    forget_cache()
    after_import = detect(imported.mesh)
    crossings, complete = self_intersection_check(fixed.mesh)
    out.write(f"\n## {title} ({len(gone)} Dreiecke entfernt)\n")
    out.write(f"  vorher   : {summary(before)}\n")
    out.write(f"  Reparatur: open={open_edge_count(fixed.mesh)} wt={fixed.mesh.is_watertight} "
              f"parts={fixed.mesh.component_count} vol={fixed.mesh.volume:.2f} "
              f"(vorher {pristine.volume:.2f}) Durchdringungen={len(crossings)}/{complete} "
              f"Befunde={[f.code for f in fixed.findings]}\n")
    out.write(f"  danach   : {summary(after)}\n")
    out.write(f"  Import   : Befunde={[f.code for f in imported.findings]} "
              f"vol={imported.mesh.volume:.2f} -> {summary(after_import)}\n")
    out.flush()


def main() -> None:
    with OUT.open("w", encoding="utf-8") as out:
        plate = load("plate_holes.stl")
        centres = np.asarray(plate.raw.triangles_center)
        radial = np.linalg.norm(centres[:, :2] - (25.0, 15.0), axis=1)
        wall = np.flatnonzero(np.abs(radial - 2.6) < 0.05)
        angle = np.degrees(np.arctan2(centres[:, 1] - 15.0, centres[:, 0] - 25.0))
        case(out, "Lochplatte: ganze Bohrungswand fehlt", plate, wall.tolist())
        quarter = wall[(angle[wall] > 0) & (angle[wall] < 90)]
        case(out, "Lochplatte: Viertel der Bohrungswand fehlt", plate, quarter.tolist())
        half = wall[(angle[wall] > -90) & (angle[wall] < 90)]
        case(out, "Lochplatte: halbe Bohrungswand fehlt", plate, half.tolist())
        upper = wall[centres[wall, 2] > 0.0]
        case(out, "Lochplatte: obere Hälfte der Bohrungswand fehlt", plate, upper.tolist())

        post = load("post_with_fillet.stl")
        centres = np.asarray(post.raw.triangles_center)
        normals = np.asarray(post.raw.face_normals)
        top = np.flatnonzero((centres[:, 2] > 29.99) & (normals[:, 2] > 0.99))
        case(out, "Pfosten: Deckel fehlt", post, top.tolist())
        radial = np.linalg.norm(centres[:, :2], axis=1)
        mantle = np.flatnonzero((np.abs(radial - 6.0) < 0.05) & (centres[:, 2] > 6.5))
        case(out, "Pfosten: ganzer Mantel fehlt", post, mantle.tolist())
        band = mantle[(centres[mantle, 2] > 12) & (centres[mantle, 2] < 18)]
        case(out, "Pfosten: Mantelband z 12..18 fehlt", post, band.tolist())

        sunk = load("plate_countersunk.stl")
        centres = np.asarray(sunk.raw.triangles_center)
        normals = np.asarray(sunk.raw.face_normals)
        cone = np.flatnonzero((np.abs(normals[:, 2]) > 0.3) & (np.abs(normals[:, 2]) < 0.9))
        case(out, "Senkung: ganzer Kegel fehlt", sunk, cone.tolist())


if __name__ == "__main__":
    main()
